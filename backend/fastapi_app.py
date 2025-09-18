import asyncio
import json
from typing import AsyncGenerator, Optional, List, Dict, Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.graph import stream_run_graph
from app.utils import create_simple_logger


logger = create_simple_logger(__name__)


app = FastAPI(title="VidScribe API", version="0.1.0")

# Allow access from typical local dev origins. Adjust as needed.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For dev; narrow this for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class StreamConfigModel(BaseModel):
    include_data: bool = True
    include_fields: Optional[List[str]] = Field(
        default=None,
        description="Subset of ['chunks','chunk_notes','image_integrated_notes','formatted_notes','collected_notes','summary']",
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


@app.get("/")
async def root() -> Dict[str, str]:
    return {"status": "ok", "service": "VidScribe API"}


def _to_sse(event: Dict[str, Any]) -> str:
    """Format a dict as SSE message with type 'progress'."""
    return f"event: progress\n" f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


@app.post("/run/stream")
async def run_stream(req: RunRequest):
    """Stream live progress as Server-Sent Events (SSE).

    Content-Type: text/event-stream
    Each event has shape: { phase, progress, message, data } where data may contain
    keys: chunks, chunk_notes, image_integrated_notes, formatted_notes, collected_notes, summary
    """

    async def gen() -> AsyncGenerator[str, None]:
        cancel_event = asyncio.Event()
        try:
            # Build a plain dict stream_config and drop None values to avoid None lists
            sc = req.stream_config.model_dump() if req.stream_config else {}
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
        except Exception as e:
            logger.error(f"Streaming failed: {e}", exc_info=True)
            # Emit an error event before closing
            yield _to_sse(
                {
                    "phase": "error",
                    "progress": 0,
                    "message": f"Error: {e}",
                    "data": {},
                }
            )

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.post("/run/final")
async def run_final(req: RunRequest):
    """Run the pipeline and return only the final result as JSON."""
    last_event: Optional[Dict[str, Any]] = None
    try:
        sc = req.stream_config.model_dump() if req.stream_config else {}
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
    except Exception as e:
        logger.error(f"Run failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

    if not last_event:
        raise HTTPException(status_code=500, detail="No output produced")

    # If an error or cancellation occurred, surface that status
    phase = last_event.get("phase")
    if phase in {"error", "cancelled"}:
        return JSONResponse(
            status_code=400 if phase == "cancelled" else 500,
            content={
                "phase": phase,
                "progress": last_event.get("progress", 0),
                "message": last_event.get("message", ""),
                "data": last_event.get("data", {}),
            },
        )

    return {
        "phase": last_event.get("phase"),
        "progress": last_event.get("progress"),
        "message": last_event.get("message"),
        "data": last_event.get("data", {}),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("fastapi_app:app", host="0.0.0.0", port=8000, reload=True)
