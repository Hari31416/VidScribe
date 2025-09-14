import asyncio
import gradio as gr
from app.graph import stream_run_graph
from app.utils import create_simple_logger

logger = create_simple_logger(__name__)


_CANCEL_EVENT: asyncio.Event | None = None


def _make_stream_config(compact_mode: bool, include_fields, max_items, max_chars):
    if not compact_mode:
        return None
    cfg = {"include_data": True}
    # include_fields comes from a CheckboxGroup (list[str] or None)
    if include_fields:
        cfg["include_fields"] = include_fields
    if max_items is not None:
        try:
            mi = int(max_items)
        except Exception:
            mi = None
        if mi is not None:
            cfg["max_items_per_field"] = mi
    if max_chars is not None:
        try:
            mc = int(max_chars)
        except Exception:
            mc = None
        if mc is not None:
            cfg["max_chars_per_field"] = mc
    return cfg


async def run_graph(
    video_id,
    num_chunks,
    provider,
    model,
    compact_mode,
    include_fields,
    max_items,
    max_chars,
):
    try:
        global _CANCEL_EVENT
        _CANCEL_EVENT = asyncio.Event()
        stream_config = _make_stream_config(
            compact_mode, include_fields, max_items, max_chars
        )
        async for event in stream_run_graph(
            video_id=video_id,
            num_chunks=int(num_chunks),
            provider=provider,
            model=model,
            show_graph=False,
            stream_config=stream_config,
            cancel_event=_CANCEL_EVENT,
        ):
            data = event.get("data", {})
            progress_text = event.get("message", "Working…")
            if event.get("phase") == "cancelled":
                yield (
                    "Cancelled by user",
                    "\n".join(data.get("chunks", []) or []),
                    "\n\n".join(data.get("chunk_notes", []) or []),
                    "\n\n".join(data.get("formatted_notes", []) or []),
                    data.get("collected_notes", ""),
                    data.get("summary", ""),
                )
                _CANCEL_EVENT = None
                return
            yield (
                progress_text,
                "\n".join(data.get("chunks", []) or []),
                "\n\n".join(data.get("chunk_notes", []) or []),
                "\n\n".join(data.get("formatted_notes", []) or []),
                data.get("collected_notes", ""),
                data.get("summary", ""),
            )
        _CANCEL_EVENT = None
    except Exception as e:
        logger.error(f"Error running graph: {str(e)}", exc_info=True)
        error_msg = f"Error: {str(e)}"
        yield (error_msg, "", "", "", "", "")


def cancel_run():
    global _CANCEL_EVENT
    if _CANCEL_EVENT is not None:
        _CANCEL_EVENT.set()
    return "Cancelling…"


def _visibility_updates(compact_mode_val, include_fields_val):
    show_all = not compact_mode_val

    def v(field):
        return (
            True if show_all else (include_fields_val and field in include_fields_val)
        )

    return (
        gr.update(visible=v("chunks")),
        gr.update(visible=v("chunk_notes")),
        gr.update(visible=v("formatted_notes")),
        gr.update(visible=v("collected_notes")),
        gr.update(visible=v("summary")),
    )


with gr.Blocks() as demo:
    gr.Markdown("# VidScribe Graph Runner")
    gr.Markdown("Enter the video ID and parameters, and control streaming granularity.")

    # Put compact streaming picker on top
    with gr.Accordion("Streaming options", open=False):
        compact_mode = gr.Checkbox(
            label="Compact streaming (limit data size)", value=True
        )
        include_fields = gr.CheckboxGroup(
            label="Include fields",
            choices=[
                "chunks",
                "chunk_notes",
                "formatted_notes",
                "collected_notes",
                "summary",
            ],
            value=["formatted_notes", "summary"],
        )
        max_items = gr.Number(
            label="Max items per list field (-1 for unlimited)",
            value=3,
            precision=0,
        )
        max_chars = gr.Number(
            label="Max chars per field (-1 for unlimited)",
            value=2000,
            precision=0,
        )

    with gr.Row():
        video_id = gr.Textbox(
            label="Video ID", placeholder="e.g., FOONnnq975k", value="wjZofJX0v4M"
        )
        num_chunks = gr.Number(label="Number of Chunks", value=2, minimum=1)

    with gr.Row():
        provider = gr.Dropdown(
            label="Provider", choices=["google", "openai"], value="google"
        )
        model = gr.Textbox(label="Model", value="gemini-2.0-flash")

    run_btn = gr.Button("Run Graph")
    cancel_btn = gr.Button("Cancel")

    progress_output = gr.Textbox(label="Progress", value="Ready to run")
    # Initial visibility matches default compact settings: formatted_notes + summary only
    chunks_output = gr.Textbox(label="Chunks", lines=5, visible=False)
    notes_output = gr.Textbox(label="Chunk Notes", lines=10, visible=False)
    formatted_output = gr.Textbox(label="Formatted Notes", lines=10, visible=True)
    collected_output = gr.Textbox(label="Collected Notes", lines=10, visible=False)
    summary_output = gr.Textbox(label="Summary", lines=5, visible=True)

    run_btn.click(
        run_graph,
        inputs=[
            video_id,
            num_chunks,
            provider,
            model,
            compact_mode,
            include_fields,
            max_items,
            max_chars,
        ],
        outputs=[
            progress_output,
            chunks_output,
            notes_output,
            formatted_output,
            collected_output,
            summary_output,
        ],
    )

    cancel_btn.click(
        cancel_run,
        inputs=None,
        outputs=progress_output,
    )

    # Dynamic visibility updates when compact mode or include fields change
    compact_mode.change(
        _visibility_updates,
        inputs=[compact_mode, include_fields],
        outputs=[
            chunks_output,
            notes_output,
            formatted_output,
            collected_output,
            summary_output,
        ],
    )

    include_fields.change(
        _visibility_updates,
        inputs=[compact_mode, include_fields],
        outputs=[
            chunks_output,
            notes_output,
            formatted_output,
            collected_output,
            summary_output,
        ],
    )

if __name__ == "__main__":
    demo.launch()
