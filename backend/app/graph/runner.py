from typing import AsyncGenerator, Dict, Any, List, TypedDict, Tuple, Optional
import asyncio

from app.graph.graph import create_graph, OverAllState, RuntimeState
from app.utils import create_simple_logger

logger = create_simple_logger(__name__)


class ProgressEvent(TypedDict, total=False):
    phase: str
    progress: int  # 0-100
    message: str
    data: Dict[str, Any]
    counters: Dict[str, Any]
    stream: Dict[str, Any]


class StreamConfig(TypedDict, total=False):
    # Whether to include any data at all
    include_data: bool
    # Only include these fields from state (subset of STATE_KEYS). If not provided, include all.
    include_fields: List[str]
    # For list fields: cap number of items
    max_items_per_field: int
    # For string fields and list items: cap characters
    max_chars_per_field: int


def _empty_overall_state() -> OverAllState:
    return OverAllState(
        chunks=[],
        chunk_notes=[],
        image_integrated_notes=[],
        formatted_notes=[],
        collected_notes="",
        integrates=[],
        summary="",
        timestamps_output=[],
        image_insertions_output=[],
        extracted_images_output=[],
    )


def _compute_progress(state: OverAllState, expected_chunks: int) -> Tuple[int, str]:
    """Heuristic progress percentage and phase name based on available state.

    We map phases as:
    - chunks: 20%
    - chunk_notes: 20% -> 40% (scaled by completed notes out of expected)
    - image_integrated_notes: 40% -> 50% (scaled by integrated notes out of expected)
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

    # Image integration progress
    image_int: List[str] = state.get("image_integrated_notes") or []
    if image_int:
        # Start at 40, end at 50
        done = min(len(image_int), max(expected_chunks, 1))
        pct = 40 + int(10 * (done / max(expected_chunks, 1)))
        return min(pct, 50), "image_integration"

    # Chunk notes progress
    notes: List[str] = state.get("chunk_notes") or []
    if notes:
        # Start at 20, end at 40
        done = min(len(notes), max(expected_chunks, 1))
        pct = 20 + int(20 * (done / max(expected_chunks, 1)))
        return min(pct, 40), "chunk_notes"

    # Chunks created
    chunks: List[str] = state.get("chunks") or []
    if chunks:
        return 20, "chunks"

    # Starting
    return 0, "starting"


STATE_KEYS = {
    "chunks",
    "chunk_notes",
    "image_integrated_notes",
    "formatted_notes",
    "collected_notes",
    "summary",
    "timestamps_output",
    "image_insertions_output",
    "extracted_images_output",
    "integrates",
}


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


def _shape_data_for_stream(
    state: Dict[str, Any], stream_config: Optional[StreamConfig]
) -> Dict[str, Any]:
    """Return a shaped copy of state limited by stream_config for efficient UI streaming."""
    if not stream_config:
        stream_config = {}

    include_data = stream_config.get("include_data", True)
    if not include_data:
        return {}

    raw_include_fields = stream_config.get("include_fields")
    if not raw_include_fields:
        include_fields = set(STATE_KEYS)
    else:
        include_fields = set(raw_include_fields)
    include_fields = include_fields.intersection(STATE_KEYS)
    max_items = stream_config.get("max_items_per_field")
    max_chars = stream_config.get("max_chars_per_field")

    out: Dict[str, Any] = {}
    for key in STATE_KEYS:
        if key not in include_fields:
            continue
        val = state.get(key)
        if val is None:
            continue

        # Lists (chunks, chunk_notes, formatted_notes)
        if isinstance(val, list):
            sliced = val
            if isinstance(max_items, int) and max_items >= 0:
                sliced = val[:max_items]
            if isinstance(max_chars, int) and max_chars >= 0:
                shaped_items: List[Any] = []
                for item in sliced:
                    if isinstance(item, str):
                        shaped_items.append(item[:max_chars])
                    elif isinstance(item, list):
                        # For nested lists (e.g., timestamps_output), shape inner strings if any
                        inner: List[Any] = []
                        for inner_item in item:
                            inner.append(
                                inner_item[:max_chars]
                                if isinstance(inner_item, str)
                                else inner_item
                            )
                        shaped_items.append(inner)
                    else:
                        shaped_items.append(item)
                out[key] = shaped_items
            else:
                out[key] = sliced
        # Strings (collected_notes, summary)
        elif isinstance(val, str):
            out[key] = (
                val[:max_chars]
                if isinstance(max_chars, int) and max_chars >= 0
                else val
            )
        else:
            out[key] = val

    return out


def _compute_counters(state: OverAllState, expected_chunks: int) -> Dict[str, Any]:
    """Compute progress counters for UI display.

    Returns a nested dict with current vs total for key artifacts.
    """

    def _safe_len(x: Any) -> int:
        try:
            return len(x)  # type: ignore[arg-type]
        except Exception:
            return 0

    # Notes
    chunk_notes = state.get("chunk_notes") or []
    image_integrated_notes = state.get("image_integrated_notes") or []
    formatted_notes = state.get("formatted_notes") or []
    collected_notes = state.get("collected_notes") or ""
    summary = state.get("summary") or ""

    # Multi-output debug fields are lists of lists
    timestamps_output = state.get("timestamps_output") or []
    image_insertions_output = state.get("image_insertions_output") or []
    extracted_images_output = state.get("extracted_images_output") or []

    # Totals across items (flatten)
    total_timestamps = sum(_safe_len(lst) for lst in timestamps_output)
    total_image_insertions = sum(_safe_len(lst) for lst in image_insertions_output)
    total_extracted_images = sum(_safe_len(lst) for lst in extracted_images_output)

    counters = {
        "expected_chunks": max(int(expected_chunks), 0),
        "notes_created": {
            "current": _safe_len(chunk_notes),
            "total": max(int(expected_chunks), 0),
        },
        "timestamps_created": {
            "current_items": total_timestamps,
            "chunks_completed": _safe_len(timestamps_output),
            "total_chunks": max(int(expected_chunks), 0),
        },
        "image_insertions_created": {
            "current_items": total_image_insertions,
            "chunks_completed": _safe_len(image_insertions_output),
            "total_chunks": max(int(expected_chunks), 0),
        },
        "extracted_images_created": {
            "current_items": total_extracted_images,
            "chunks_completed": _safe_len(extracted_images_output),
            "total_chunks": max(int(expected_chunks), 0),
        },
        "integrated_image_notes_created": {
            "current": _safe_len(image_integrated_notes),
            "total": max(int(expected_chunks), 0),
        },
        "formatted_notes_created": {
            "current": _safe_len(formatted_notes),
            "total": max(int(expected_chunks), 0),
        },
        "finalization": {
            "collected": bool(collected_notes),
            "summary": bool(summary),
        },
        "notes_by_type": {
            "raw": _safe_len(chunk_notes),
            "integrated": _safe_len(image_integrated_notes),
            "formatted": _safe_len(formatted_notes),
            "collected": 1 if collected_notes else 0,
            "summary": 1 if summary else 0,
        },
    }
    return counters


async def stream_run_graph(
    *,
    video_id: str,
    video_path: str,
    num_chunks: int = 2,
    provider: str = "google",
    model: str = "gemini-2.0-flash",
    refresh_notes: bool = False,
    show_graph: bool = False,
    stream_config: Optional[StreamConfig] = None,
    cancel_event: Optional[asyncio.Event] = None,
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
        video_path=video_path,
        num_chunks=int(num_chunks),
        refresh_notes=refresh_notes,
    )

    # Early cancellation
    if cancel_event and cancel_event.is_set():
        yield {
            "phase": "cancelled",
            "progress": 0,
            "message": "Execution cancelled",
            "data": {},
        }
        return

    # Initial event
    progress, phase = _compute_progress(state, int(num_chunks))
    yield {
        "phase": phase,
        "progress": progress,
        "message": "Starting graph execution…",
        "data": _shape_data_for_stream(
            {
                "chunks": [],
                "chunk_notes": [],
                "image_integrated_notes": [],
                "formatted_notes": [],
                "collected_notes": "",
                "summary": "",
                "timestamps_output": [],
                "image_insertions_output": [],
                "extracted_images_output": [],
                "integrates": [],
            },
            stream_config,
        ),
        "counters": _compute_counters(state, int(num_chunks)),
    }

    try:
        # Iterate over both values and updates in the stream
        async for item in graph.astream(
            input=state,
            context=runtime,
            subgraphs=True,
            stream_mode=["values", "updates"],
        ):
            # Check for cancellation between steps
            if cancel_event and cancel_event.is_set():
                yield {
                    "phase": "cancelled",
                    "progress": 0,
                    "message": "Execution cancelled",
                    "data": {},
                }
                return

            # Unpack stream item to determine mode and payload
            mode: Optional[str] = None
            payload: Any = item
            if isinstance(item, tuple) and len(item) >= 3:
                # Common astream tuple shape: (node, mode, payload)
                mode = item[1]
                payload = item[2]
            elif isinstance(item, dict):
                # Fallback: direct dict payload (older versions)
                mode = None
                payload = item

            # Merge: be resilient to different shapes by scanning for known keys
            _update_state_from_obj(payload, state)

            progress, phase = _compute_progress(state, int(num_chunks))

            message_map = {
                "starting": "Preparing…",
                "chunks": "Chunks created",
                "chunk_notes": "Chunk notes generated",
                "image_integration": "Images integrated into notes",
                "format_docs": "Notes formatted",
                "collect_notes": "Notes collected",
                "summary": "Summary generated",
            }

            yield {
                "phase": phase,
                "progress": progress,
                "message": message_map.get(phase, "Working…"),
                "data": _shape_data_for_stream(state, stream_config),
                "counters": _compute_counters(state, int(num_chunks)),
                "stream": {
                    "mode": mode or "values",
                    "update": payload if mode == "updates" else None,
                },
            }

        # Done
        yield {
            "phase": "done",
            "progress": 100,
            "message": "Graph execution completed",
            "data": _shape_data_for_stream(state, stream_config),
            "counters": _compute_counters(state, int(num_chunks)),
        }
    except asyncio.CancelledError:
        yield {
            "phase": "cancelled",
            "progress": 0,
            "message": "Execution cancelled",
            "data": {},
        }
        return
    except Exception as e:
        logger.error(f"Graph execution failed: {e}", exc_info=True)
        yield {
            "phase": "error",
            "progress": 0,
            "message": f"Error: {e}",
            "data": {},
        }


__all__ = ["stream_run_graph"]
