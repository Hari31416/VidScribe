"""
Download Routes for VidScribe Backend.
Provides endpoints for downloading files and triggering video downloads.
All file downloads are proxied through the backend from MinIO.
"""

import asyncio
import json
import io
from functools import partial
from typing import Any, AsyncGenerator, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.services.auth import get_current_user
from app.services.download_ytdlp import download_media
from app.services.storage_service import (
    get_storage_service,
    ARTIFACT_VIDEOS,
    ARTIFACT_FRAMES,
    ARTIFACT_TRANSCRIPTS,
    ARTIFACT_NOTES,
    VALID_ARTIFACT_TYPES,
)
from app.services.database.project_database import get_project, update_project
from app.utils import create_simple_logger

videos_router = APIRouter(prefix="/videos", tags=["videos"])
files_router = APIRouter(prefix="/files", tags=["files"])

logger = create_simple_logger(__name__)


# =============================================================================
# Request/Response Models
# =============================================================================


class DownloadVideoRequest(BaseModel):
    video_id: str
    resolution: Optional[int] = Field(
        default=None,
        ge=144,
        le=4320,
        description="Maximum video height in pixels",
    )
    audio_only: bool = Field(default=False)
    video_only: bool = Field(default=False)
    audio_format: str = Field(default="mp3")
    overwrite: bool = Field(default=False)


# =============================================================================
# File Download Endpoints (Proxied from MinIO)
# =============================================================================


@files_router.get("/download")
async def download_file(
    project_id: str = Query(..., description="Project ID"),
    artifact_type: str = Query(
        ..., description="Artifact type (videos, frames, transcripts, notes)"
    ),
    filename: str = Query(..., description="Filename to download"),
    current_user: dict = Depends(get_current_user),
):
    """
    Download a file from a project's storage.
    Files are streamed from MinIO through the backend.
    """
    username = current_user["username"]
    storage = get_storage_service()

    # Validate artifact type
    if artifact_type not in VALID_ARTIFACT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid artifact_type. Must be one of: {VALID_ARTIFACT_TYPES}",
        )

    # Verify project belongs to user
    project = get_project(username, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Check if file exists
    if not storage.file_exists(username, project_id, artifact_type, filename):
        raise HTTPException(status_code=404, detail="File not found")

    try:
        # Download file from MinIO
        file_bytes = storage.download_file(
            username, project_id, artifact_type, filename
        )

        # Determine content type
        content_type = "application/octet-stream"
        if filename.endswith(".pdf"):
            content_type = "application/pdf"
        elif filename.endswith(".md"):
            content_type = "text/markdown"
        elif filename.endswith(".json"):
            content_type = "application/json"
        elif filename.endswith(".mp4"):
            content_type = "video/mp4"
        elif filename.endswith(".mp3"):
            content_type = "audio/mpeg"
        elif filename.endswith((".jpg", ".jpeg")):
            content_type = "image/jpeg"
        elif filename.endswith(".png"):
            content_type = "image/png"

        # Stream the file
        return StreamingResponse(
            io.BytesIO(file_bytes),
            media_type=content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Length": str(len(file_bytes)),
            },
        )

    except Exception as e:
        logger.error(f"Download failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Download failed")


@files_router.get("/list")
async def list_project_files(
    project_id: str = Query(..., description="Project ID"),
    artifact_type: Optional[str] = Query(None, description="Filter by artifact type"),
    current_user: dict = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    List files in a project's storage.
    """
    username = current_user["username"]
    storage = get_storage_service()

    # Verify project belongs to user
    project = get_project(username, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if artifact_type:
        if artifact_type not in VALID_ARTIFACT_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid artifact_type. Must be one of: {VALID_ARTIFACT_TYPES}",
            )
        files = storage.list_files(username, project_id, artifact_type)
        return {
            "project_id": project_id,
            "artifact_type": artifact_type,
            "files": files,
        }

    # List all artifact types
    result = {"project_id": project_id, "files": {}}
    for at in VALID_ARTIFACT_TYPES:
        result["files"][at] = storage.list_files(username, project_id, at)

    return result


# =============================================================================
# YouTube Video Download Endpoints
# =============================================================================


@videos_router.post("/download")
async def download_video(
    req: DownloadVideoRequest,
    current_user: dict = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Download a video from YouTube and store it in the user's project.
    """
    username = current_user["username"]
    storage = get_storage_service()

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
    except Exception as exc:
        logger.error("Video download failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Video download failed") from exc

    status = result.get("status")
    if status == "error":
        raise HTTPException(
            status_code=400, detail=result.get("error", "Download failed")
        )

    # Upload downloaded files to MinIO
    downloaded_files = result.get("downloaded_files", [])
    uploaded_keys = []

    for file_path in downloaded_files:
        try:
            from pathlib import Path

            p = Path(file_path)
            key = storage.upload_file_from_path(
                username,
                req.video_id,
                ARTIFACT_VIDEOS,
                str(p),
                p.name,
            )
            uploaded_keys.append(key)
        except Exception as e:
            logger.warning(f"Failed to upload {file_path} to MinIO: {e}")

    # Create or update project
    from app.services.database.project_database import project_exists, create_project

    if not project_exists(username, req.video_id):
        create_project(
            user_id=username,
            project_id=req.video_id,
            name=req.video_id,
            has_video=True,
            has_transcript=False,
        )
    else:
        update_project(username, req.video_id, {"has_video": True})

    return {
        "status": status,
        "project_id": req.video_id,
        "count": len(uploaded_keys),
        "files": uploaded_keys,
    }


@videos_router.post("/download/stream")
async def download_video_stream(
    req: DownloadVideoRequest,
    current_user: dict = Depends(get_current_user),
) -> StreamingResponse:
    """
    Download video with streaming progress updates (SSE).
    """
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
        except Exception as exc:
            logger.error("Video download failed: %s", exc, exc_info=True)
            await queue.put({"status": "error", "error": str(exc)})
        finally:
            await queue.put(None)

    asyncio.create_task(run_download())

    async def event_generator() -> AsyncGenerator[str, None]:
        while True:
            payload = await queue.get()
            if payload is None:
                break
            yield f"event: progress\ndata: {json.dumps(payload)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
