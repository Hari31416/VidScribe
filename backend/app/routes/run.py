import asyncio
import json
from typing import Any, AsyncGenerator, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from app.graph import stream_run_graph
from app.utils import create_simple_logger

router = APIRouter(prefix="/run", tags=["run"])

logger = create_simple_logger(__name__)


class StreamConfigModel(BaseModel):
    include_data: bool = True
    include_fields: Optional[List[str]] = Field(
        default=None,
        description=(
            "Subset of data fields to include. Valid keys: "
            "['chunks','chunk_notes','image_integrated_notes','formatted_notes','collected_notes','summary',"
            " 'collected_notes_pdf_path','summary_pdf_path','timestamps_output','image_insertions_output','extracted_images_output','integrates']"
        ),
    )
    max_items_per_field: Optional[int] = None
    max_chars_per_field: Optional[int] = None


class RunRequest(BaseModel):
    video_id: str
    video_path: str
    num_chunks: int = 2
    provider: str = "google"
    model: str = "gemini-2.0-flash"
    show_graph: bool = False
    refresh_notes: bool = False
    stream_config: Optional[StreamConfigModel] = None


def _to_sse(event: Dict[str, Any]) -> str:
    """Format a dict as Server-Sent Event message."""
    payload = jsonable_encoder(event)
    return f"event: progress\n" f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _ensure_pdf_fields(sc: Dict[str, Any]) -> Dict[str, Any]:
    include_fields = sc.get("include_fields")
    if isinstance(include_fields, list):
        for pdf_field in ("collected_notes_pdf_path", "summary_pdf_path"):
            if pdf_field not in include_fields:
                include_fields.append(pdf_field)
    return sc


@router.post("/stream")
async def run_stream(req: RunRequest):
    """Stream live progress as Server-Sent Events (SSE)."""

    async def gen() -> AsyncGenerator[str, None]:
        cancel_event = asyncio.Event()
        try:
            # Build a plain dict stream_config and drop None values to avoid None lists
            sc = (
                _ensure_pdf_fields(req.stream_config.model_dump())
                if req.stream_config
                else {}
            )
            async for event in stream_run_graph(
                video_id=req.video_id,
                video_path=req.video_path,
                num_chunks=int(req.num_chunks),
                provider=req.provider,
                model=req.model,
                show_graph=req.show_graph,
                stream_config=sc,
                cancel_event=cancel_event,
                refresh_notes=req.refresh_notes,
            ):
                yield _to_sse(event)
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("Streaming failed: %s", exc, exc_info=True)
            yield _to_sse(
                {
                    "phase": "error",
                    "progress": 0,
                    "message": f"Error: {exc}",
                    "data": {},
                }
            )

    return StreamingResponse(gen(), media_type="text/event-stream")


@router.post("/final")
async def run_final(req: RunRequest):
    """Run the pipeline and return only the final result as JSON."""
    last_event: Optional[Dict[str, Any]] = None
    try:
        sc = (
            _ensure_pdf_fields(req.stream_config.model_dump())
            if req.stream_config
            else {}
        )
        async for event in stream_run_graph(
            video_id=req.video_id,
            video_path=req.video_path,
            num_chunks=int(req.num_chunks),
            provider=req.provider,
            model=req.model,
            show_graph=req.show_graph,
            stream_config=sc,
            refresh_notes=req.refresh_notes,
        ):
            last_event = event
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("Run failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if not last_event:
        raise HTTPException(status_code=500, detail="No output produced")

    phase = last_event.get("phase")
    if phase in {"error", "cancelled"}:
        return JSONResponse(
            status_code=400 if phase == "cancelled" else 500,
            content={
                "phase": phase,
                "progress": last_event.get("progress", 0),
                "message": last_event.get("message", ""),
                "data": last_event.get("data", {}),
                "counters": last_event.get("counters", {}),
            },
        )

    return {
        "phase": last_event.get("phase"),
        "progress": last_event.get("progress"),
        "message": last_event.get("message"),
        "data": last_event.get("data", {}),
        "counters": last_event.get("counters", {}),
    }
