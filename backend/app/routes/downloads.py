import asyncio
import json
import mimetypes
from functools import partial
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from app.services.download_ytdlp import download_media
from app.utils import create_simple_logger

videos_router = APIRouter(prefix="/videos", tags=["videos"])
files_router = APIRouter(prefix="/files", tags=["files"])

logger = create_simple_logger(__name__)

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
OUTPUTS_DIR = (BACKEND_ROOT / "outputs").resolve()
mimetypes.add_type("text/markdown", ".md")


class DownloadVideoRequest(BaseModel):
    video_id: str
    resolution: Optional[int] = Field(
        default=None,
        ge=144,
        le=4320,
        description="Maximum height of the downloaded video in pixels. Defaults to provider's best.",
    )
    audio_only: bool = Field(
        default=False,
        description="If true, download only audio and convert to audio_format.",
    )
    video_only: bool = Field(
        default=False,
        description="If true, download only the video stream without audio.",
    )
    audio_format: str = Field(
        default="mp3",
        description="Audio format to use when audio_only is true.",
    )
    overwrite: bool = Field(
        default=False,
        description="If false and the file already exists, skip downloading again.",
    )


@videos_router.post("/download")
async def download_video(req: DownloadVideoRequest) -> Dict[str, Any]:
    if req.audio_only and req.video_only:
        raise HTTPException(
            status_code=400,
            detail="audio_only and video_only cannot both be true.",
        )

    loop = asyncio.get_running_loop()
    runner = partial(
        download_media,
        req.video_id,
        resolution=req.resolution,
        audio_only=req.audio_only,
        video_only=req.video_only,
        audio_format=req.audio_format,
        overwrite=req.overwrite,
    )

    try:
        result = await loop.run_in_executor(None, runner)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("Video download failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Video download failed") from exc

    status = result.get("status")
    if status == "error":
        raise HTTPException(
            status_code=400, detail=result.get("error", "Download failed")
        )
    if status not in {"success", "skipped"}:
        raise HTTPException(status_code=500, detail="Unexpected download status")

    files: List[str] = result.get("downloaded_files") or []
    files_payload = []
    for fp in files:
        abs_path = str(Path(fp).resolve())
        rel_path = _relative_to_outputs(abs_path)
        files_payload.append(
            {
                "absolute_path": abs_path,
                "relative_path": rel_path,
                "download_url": _build_download_url(rel_path),
            }
        )

    output_dir = result.get("output_dir")
    output_dir_abs = str(Path(output_dir).resolve()) if output_dir else None
    output_dir_rel = _relative_to_outputs(output_dir_abs) if output_dir_abs else None

    return {
        "status": status,
        "video_id": req.video_id,
        "count": result.get("count", len(files_payload)),
        "audio_only": req.audio_only,
        "video_only": req.video_only,
        "resolution": req.resolution,
        "output_dir": {
            "absolute": output_dir_abs,
            "relative": output_dir_rel,
        },
        "files": files_payload,
    }


@videos_router.post("/download/stream")
async def download_video_stream(req: DownloadVideoRequest) -> StreamingResponse:
    if req.audio_only and req.video_only:
        raise HTTPException(
            status_code=400,
            detail="audio_only and video_only cannot both be true.",
        )

    queue: asyncio.Queue[Optional[Dict[str, Any]]] = asyncio.Queue()
    loop = asyncio.get_running_loop()

    async def run_download() -> None:
        def callback(progress: Dict[str, Any]) -> None:
            asyncio.run_coroutine_threadsafe(queue.put(progress), loop)

        await queue.put({"status": "started", "video_id": req.video_id})
        try:
            result = await loop.run_in_executor(
                None,
                partial(
                    download_media,
                    req.video_id,
                    resolution=req.resolution,
                    audio_only=req.audio_only,
                    video_only=req.video_only,
                    audio_format=req.audio_format,
                    overwrite=req.overwrite,
                    progress_callback=callback,
                ),
            )
            await queue.put(
                {
                    "status": result.get("status", "completed"),
                    "video_id": req.video_id,
                    "result": result,
                }
            )
        except Exception as exc:  # pylint: disable=broad-except
            logger.error(
                "Video download failed during streaming: %s", exc, exc_info=True
            )
            await queue.put({"status": "error", "error": str(exc)})
        finally:
            await queue.put(None)

    asyncio.create_task(run_download())

    async def event_generator() -> AsyncGenerator[str, None]:
        while True:
            payload = await queue.get()
            if payload is None:
                break
            yield _to_sse(payload)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@files_router.get("/download")
async def download_file(
    path: str = Query(
        ..., description="Path to file relative to the backend outputs directory."
    )
):
    resolved_path = _resolve_requested_path(path)
    media_type, _ = mimetypes.guess_type(str(resolved_path))
    return FileResponse(
        resolved_path,
        media_type=media_type or "application/octet-stream",
        filename=resolved_path.name,
    )


def _relative_to_outputs(path: str) -> Optional[str]:
    try:
        resolved = Path(path).resolve()
        return str(resolved.relative_to(OUTPUTS_DIR))
    except (ValueError, RuntimeError):
        return None


def _build_download_url(relative_path: Optional[str]) -> Optional[str]:
    if not relative_path:
        return None
    return f"/files/download?path={quote(relative_path)}"


def _resolve_requested_path(path: str) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute():
        parts = candidate.parts
        if parts and parts[0] == OUTPUTS_DIR.name:
            candidate = Path(*parts[1:]) if len(parts) > 1 else Path(".")
        candidate = OUTPUTS_DIR / candidate
    try:
        resolved = candidate.resolve(strict=True)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="File not found") from exc

    try:
        resolved.relative_to(OUTPUTS_DIR)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="Requested path is outside of the allowed outputs directory.",
        ) from exc

    if not resolved.is_file():
        raise HTTPException(status_code=400, detail="Requested path is not a file")

    return resolved


def _to_sse(event: Dict[str, Any]) -> str:
    return f"event: progress\n" f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
