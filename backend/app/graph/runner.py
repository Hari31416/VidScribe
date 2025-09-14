from __future__ import annotations

from typing import AsyncGenerator, Dict, Any, List, TypedDict, Tuple

from app.graph.graph import create_graph, OverAllState, RuntimeState
from app.utils import create_simple_logger

logger = create_simple_logger(__name__)


class ProgressEvent(TypedDict, total=False):
    phase: str
    progress: int  # 0-100
    message: str
    data: Dict[str, Any]


def _empty_overall_state() -> OverAllState:
    return OverAllState(
        chunks=[],
        chunk_notes=[],
        formatted_notes=[],
        collected_notes="",
        summary="",
    )


def _compute_progress(state: OverAllState, expected_chunks: int) -> Tuple[int, str]:
    """Heuristic progress percentage and phase name based on available state.

    We map phases as:
    - chunks: 20%
    - chunk_notes: 20% -> 50% (scaled by completed notes out of expected)
    - format_docs: 50% -> 80% (scaled by formatted out of expected)
    - collect_notes: 90%
    - summary: 100%
    """

    # Done
    if state.get("summary"):
        return 100, "summary"

    # Collected notes
    if state.get("collected_notes"):
        return 90, "collect_notes"

    # Formatting progress
    formatted: List[str] = state.get("formatted_notes") or []
    if formatted:
        # Start at 50, end at 80
        done = min(len(formatted), max(expected_chunks, 1))
        pct = 50 + int(30 * (done / max(expected_chunks, 1)))
        return min(pct, 80), "format_docs"

    # Chunk notes progress
    notes: List[str] = state.get("chunk_notes") or []
    if notes:
        # Start at 20, end at 50
        done = min(len(notes), max(expected_chunks, 1))
        pct = 20 + int(30 * (done / max(expected_chunks, 1)))
        return min(pct, 50), "chunk_notes"

    # Chunks created
    chunks: List[str] = state.get("chunks") or []
    if chunks:
        return 20, "chunks"

    # Starting
    return 0, "starting"


STATE_KEYS = {"chunks", "chunk_notes", "formatted_notes", "collected_notes", "summary"}


def _update_state_from_obj(
    obj: Any, state: OverAllState, depth: int = 0, max_depth: int = 3
) -> None:
    """Recursively scan an arbitrary object for known state keys and merge them into state.

    This makes the runner resilient to different astream yield shapes.
    """
    if depth > max_depth or obj is None:
        return

    if isinstance(obj, dict):
        # If top-level keys overlap, merge them directly
        for k in STATE_KEYS.intersection(obj.keys()):
            state[k] = obj[k]  # type: ignore[index]
        # Recurse into child values
        for v in obj.values():
            _update_state_from_obj(v, state, depth + 1, max_depth)
    elif isinstance(obj, (list, tuple)):
        for item in obj:
            _update_state_from_obj(item, state, depth + 1, max_depth)
    else:
        # Unsupported type; ignore
        return


async def stream_run_graph(
    *,
    video_id: str,
    num_chunks: int = 2,
    provider: str = "google",
    model: str = "gemini-2.0-flash",
    show_graph: bool = False,
) -> AsyncGenerator[ProgressEvent, None]:
    """Run the VidScribe graph and stream progress events with partial outputs.

    Yields ProgressEvent dictionaries suitable for UI consumption.
    """

    graph = create_graph(show_graph=show_graph)

    state = _empty_overall_state()
    runtime = RuntimeState(
        provider=provider,
        model=model,
        video_id=video_id,
        num_chunks=int(num_chunks),
    )

    # Initial event
    progress, phase = _compute_progress(state, int(num_chunks))
    yield {
        "phase": phase,
        "progress": progress,
        "message": "Starting graph execution…",
        "data": {
            "chunks": [],
            "chunk_notes": [],
            "formatted_notes": [],
            "collected_notes": "",
            "summary": "",
        },
    }

    try:
        async for new_state in graph.astream(input=state, context=runtime):
            # Merge: be resilient to different shapes by scanning for known keys
            _update_state_from_obj(new_state, state)

            progress, phase = _compute_progress(state, int(num_chunks))

            message_map = {
                "starting": "Preparing…",
                "chunks": "Chunks created",
                "chunk_notes": "Chunk notes generated",
                "format_docs": "Notes formatted",
                "collect_notes": "Notes collected",
                "summary": "Summary generated",
            }

            yield {
                "phase": phase,
                "progress": progress,
                "message": message_map.get(phase, "Working…"),
                "data": {
                    "chunks": state.get("chunks", []),
                    "chunk_notes": state.get("chunk_notes", []),
                    "formatted_notes": state.get("formatted_notes", []),
                    "collected_notes": state.get("collected_notes", ""),
                    "summary": state.get("summary", ""),
                },
            }

        # Done
        yield {
            "phase": "done",
            "progress": 100,
            "message": "Graph execution completed",
            "data": {
                "chunks": state.get("chunks", []),
                "chunk_notes": state.get("chunk_notes", []),
                "formatted_notes": state.get("formatted_notes", []),
                "collected_notes": state.get("collected_notes", ""),
                "summary": state.get("summary", ""),
            },
        }
    except Exception as e:
        logger.error(f"Graph execution failed: {e}", exc_info=True)
        yield {
            "phase": "error",
            "progress": 0,
            "message": f"Error: {e}",
            "data": {},
        }


__all__ = ["stream_run_graph"]
