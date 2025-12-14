"""
Pipeline Run Routes for VidScribe Backend.
Provides endpoints for running the notes generation pipeline.
All endpoints require authentication.
"""

import asyncio
import json
import uuid
from typing import Any, AsyncGenerator, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from app.graph import stream_run_graph
from app.services.auth import get_current_user
from app.services.database.project_database import (
    get_project,
    update_project_status,
    create_run,
    update_run_status,
    list_runs,
)
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
    project_id: str  # Changed from video_id to project_id
    num_chunks: int = 2
    provider: str = "google"
    model: str = "gemini-2.0-flash"
    show_graph: bool = False
    refresh_notes: bool = False
    add_images: bool = True  # Set to False for transcript-only mode
    user_feedback: Optional[str] = None  # Optional user instructions for LLM
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
async def run_stream(
    req: RunRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """Stream live progress as Server-Sent Events (SSE)."""
    username = current_user["username"]

    # Verify project belongs to user
    project = get_project(username, req.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if not project.get("has_transcript", False):
        raise HTTPException(status_code=400, detail="Project has no transcript")

    # Check if we should add images
    add_images = req.add_images and project.get("has_video", False)

    # Create a new run for this pipeline execution
    run_id = f"run_{uuid.uuid4().hex[:12]}"
    try:
        create_run(
            user_id=username,
            project_id=req.project_id,
            run_id=run_id,
            provider=req.provider,
            model=req.model,
            user_feedback=req.user_feedback,
        )
    except Exception as e:
        logger.error(f"Failed to create run: {e}")
        raise HTTPException(status_code=500, detail="Failed to start pipeline run")

    async def gen() -> AsyncGenerator[str, None]:
        cancel_event = asyncio.Event()
        queue: "asyncio.Queue[str | None]" = asyncio.Queue()

        # Build stream config once
        sc = (
            _ensure_pdf_fields(req.stream_config.model_dump())
            if req.stream_config
            else {}
        )

        async def _producer() -> None:
            """Produce SSE strings onto the queue from the graph stream."""
            try:
                logger.info(
                    f"SSE producer started for user '{username}', project '{req.project_id}', run '{run_id}'"
                )

                # Update run status
                update_run_status(username, req.project_id, run_id, "processing")

                async for event in stream_run_graph(
                    video_id=req.project_id,
                    username=username,  # Pass username for storage access
                    run_id=run_id,  # Pass run_id for notes versioning
                    video_path=None,  # Not needed with MinIO
                    num_chunks=int(req.num_chunks),
                    provider=req.provider,
                    model=req.model,
                    show_graph=req.show_graph,
                    add_images=add_images,
                    user_feedback=req.user_feedback,
                    stream_config=sc,
                    cancel_event=cancel_event,
                    refresh_notes=req.refresh_notes,
                ):
                    await queue.put(_to_sse(event))

                    # Check for completion
                    if event.get("phase") == "done":
                        update_run_status(username, req.project_id, run_id, "completed")
                    elif event.get("phase") == "error":
                        update_run_status(username, req.project_id, run_id, "failed")

            except asyncio.CancelledError:
                logger.info("SSE producer cancelled")
                update_run_status(username, req.project_id, run_id, "failed")
                return
            except Exception as exc:
                logger.error("Streaming failed: %s", exc, exc_info=True)
                update_run_status(username, req.project_id, run_id, "failed")
                await queue.put(
                    _to_sse(
                        {
                            "phase": "error",
                            "progress": 0,
                            "message": f"Error: {exc}",
                            "data": {},
                        }
                    )
                )
            finally:
                logger.info("SSE producer finishing")
                await queue.put(None)

        async def _watch_client_disconnect(task: asyncio.Task) -> None:
            """Monitor client connection; cancel producer immediately on disconnect."""
            try:
                while True:
                    if await request.is_disconnected():
                        logger.warning("Client disconnected; cancelling run")
                        cancel_event.set()
                        task.cancel()
                        break
                    await asyncio.sleep(0.2)
            except asyncio.CancelledError:
                pass

        producer_task: asyncio.Task = asyncio.create_task(_producer())
        watcher_task: asyncio.Task = asyncio.create_task(
            _watch_client_disconnect(producer_task)
        )

        try:
            yield ": connected\n\n"
            while True:
                item = await queue.get()
                if item is None:
                    break
                yield item
        finally:
            watcher_task.cancel()
            producer_task.cancel()

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/final")
async def run_final(
    req: RunRequest,
    current_user: dict = Depends(get_current_user),
):
    """Run the pipeline and return only the final result as JSON."""
    username = current_user["username"]

    # Verify project belongs to user
    project = get_project(username, req.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if not project.get("has_transcript", False):
        raise HTTPException(status_code=400, detail="Project has no transcript")

    # Check if we should add images
    add_images = req.add_images and project.get("has_video", False)

    # Create a new run for this pipeline execution
    run_id = f"run_{uuid.uuid4().hex[:12]}"
    try:
        create_run(
            user_id=username,
            project_id=req.project_id,
            run_id=run_id,
            provider=req.provider,
            model=req.model,
            user_feedback=req.user_feedback,
        )
    except Exception as e:
        logger.error(f"Failed to create run: {e}")
        raise HTTPException(status_code=500, detail="Failed to start pipeline run")

    last_event: Optional[Dict[str, Any]] = None
    try:
        sc = (
            _ensure_pdf_fields(req.stream_config.model_dump())
            if req.stream_config
            else {}
        )

        async for event in stream_run_graph(
            video_id=req.project_id,
            username=username,
            run_id=run_id,
            video_path=None,
            num_chunks=int(req.num_chunks),
            provider=req.provider,
            model=req.model,
            show_graph=req.show_graph,
            add_images=add_images,
            user_feedback=req.user_feedback,
            stream_config=sc,
            refresh_notes=req.refresh_notes,
        ):
            last_event = event

    except Exception as exc:
        logger.error("Run failed: %s", exc, exc_info=True)
        update_run_status(username, req.project_id, run_id, "failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if not last_event:
        update_run_status(username, req.project_id, run_id, "failed")
        raise HTTPException(status_code=500, detail="No output produced")

    phase = last_event.get("phase")
    if phase in {"error", "cancelled"}:
        update_run_status(username, req.project_id, run_id, "failed")
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

    data = last_event.get("data", {})
    notes_files = {
        "final_notes_md": bool(data.get("collected_notes")),
        "final_notes_pdf": bool(data.get("collected_notes_pdf_path")),
        "summary_md": bool(data.get("summary")),
        "summary_pdf": bool(data.get("summary_pdf_path")),
    }
    update_run_status(
        username, req.project_id, run_id, "completed", notes_files=notes_files
    )
    return {
        "project_id": req.project_id,
        "run_id": run_id,
        "phase": last_event.get("phase"),
        "progress": last_event.get("progress"),
        "message": last_event.get("message"),
        "data": last_event.get("data", {}),
        "counters": last_event.get("counters", {}),
    }


@router.get("/project/{project_id}/runs")
async def list_project_runs(
    project_id: str,
    current_user: dict = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """List all pipeline runs for a project."""
    username = current_user["username"]

    # Verify project belongs to user
    project = get_project(username, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    return list_runs(username, project_id)
