import asyncio
import json
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
        expanded_fields = list(include_fields)
        for pdf_field in ("collected_notes_pdf_path", "summary_pdf_path"):
            if pdf_field not in expanded_fields:
                expanded_fields.append(pdf_field)
        cfg["include_fields"] = expanded_fields
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
    video_path,
    num_chunks,
    provider,
    model,
    compact_mode,
    include_fields,
    max_items,
    max_chars,
    refresh_notes,
):
    try:
        global _CANCEL_EVENT
        _CANCEL_EVENT = asyncio.Event()
        stream_config = _make_stream_config(
            compact_mode, include_fields, max_items, max_chars
        )

        def _format_counters_md(
            counters: dict | None, overall_progress: int | None = None
        ) -> str:
            if not counters:
                return ""
            try:
                exp_chunks = int(counters.get("expected_chunks", 0) or 0)
                notes = counters.get("notes_created", {}) or {}
                integ = counters.get("integrated_image_notes_created", {}) or {}
                fmt = counters.get("formatted_notes_created", {}) or {}
                tss = counters.get("timestamps_created", {}) or {}
                ins = counters.get("image_insertions_created", {}) or {}
                ext = counters.get("extracted_images_created", {}) or {}
                fin = counters.get("finalization", {}) or {}

                def _pct(cur: int, tot: int) -> int:
                    tot = max(int(tot or 0), 1)
                    cur = max(int(cur or 0), 0)
                    return max(0, min(100, int(round((cur / tot) * 100))))

                def _bar(cur: int, tot: int, width: int = 18) -> str:
                    p = _pct(cur, tot)
                    filled = int(round((p / 100) * width))
                    return f"[{('█' * filled) + ('░' * (width - filled))}] {p}%"

                # Chunk-based stages
                raw_c, raw_t = int(notes.get("current", 0) or 0), int(
                    notes.get("total", exp_chunks) or exp_chunks
                )
                int_c, int_t = int(integ.get("current", 0) or 0), int(
                    integ.get("total", exp_chunks) or exp_chunks
                )
                fmt_c, fmt_t = int(fmt.get("current", 0) or 0), int(
                    fmt.get("total", exp_chunks) or exp_chunks
                )

                # Item-based metrics
                tss_items = int(tss.get("current_items", 0) or 0)
                tss_chunks_c = int(tss.get("chunks_completed", 0) or 0)
                tss_chunks_t = int(tss.get("total_chunks", exp_chunks) or exp_chunks)

                ins_items = int(ins.get("current_items", 0) or 0)
                ins_chunks_c = int(ins.get("chunks_completed", 0) or 0)
                ins_chunks_t = int(ins.get("total_chunks", exp_chunks) or exp_chunks)

                ext_items = int(ext.get("current_items", 0) or 0)
                ext_chunks_c = int(ext.get("chunks_completed", 0) or 0)
                ext_chunks_t = int(ext.get("total_chunks", exp_chunks) or exp_chunks)

                collected = bool(fin.get("collected", False))
                summary = bool(fin.get("summary", False))
                collected_pdf = bool(fin.get("collected_notes_pdf", False))
                summary_pdf = bool(fin.get("summary_pdf", False))

                # Build Markdown
                md: list[str] = []
                # Overall progress (from event)
                if overall_progress is not None:
                    p = max(0, min(100, int(overall_progress)))
                    filled = int(round((p / 100) * 24))
                    md.append("### Overall")
                    md.append(f"[{('█' * filled) + ('░' * (24 - filled))}] {p}%")
                    md.append("")
                md.append("### Progress")
                md.append("")
                md.append("| Stage | Count | Progress |")
                md.append("| --- | ---: | :--- |")
                md.append(f"| Raw notes | {raw_c}/{raw_t} | {_bar(raw_c, raw_t)} |")
                md.append(
                    f"| Integrated notes | {int_c}/{int_t} | {_bar(int_c, int_t)} |"
                )
                md.append(
                    f"| Formatted notes | {fmt_c}/{fmt_t} | {_bar(fmt_c, fmt_t)} |"
                )

                md.append("")
                md.append("### Media and timestamps")
                md.append("")
                md.append("| Metric | Items | Chunks | Progress |")
                md.append("| --- | ---: | ---: | :--- |")
                md.append(
                    f"| Timestamps | {tss_items} | {tss_chunks_c}/{tss_chunks_t} | {_bar(tss_chunks_c, tss_chunks_t)} |"
                )
                md.append(
                    f"| Image insertions | {ins_items} | {ins_chunks_c}/{ins_chunks_t} | {_bar(ins_chunks_c, ins_chunks_t)} |"
                )
                md.append(
                    f"| Extracted images | {ext_items} | {ext_chunks_c}/{ext_chunks_t} | {_bar(ext_chunks_c, ext_chunks_t)} |"
                )

                md.append("")
                md.append("### Finalization")
                md.append("")
                md.append("| Artifact | Status |")
                md.append("| --- | :---: |")
                md.append(f"| Collected notes | {'✅' if collected else '❌'} |")
                md.append(f"| Summary | {'✅' if summary else '❌'} |")
                md.append(
                    f"| Collected notes PDF | {'✅' if collected_pdf else '❌'} |"
                )
                md.append(f"| Summary PDF | {'✅' if summary_pdf else '❌'} |")
                return "\n".join(md)
            except Exception:
                # Fallback to raw JSON if structure changes
                return json.dumps(counters, indent=2)

        def _format_stream_mode_md(stream_info: dict | None) -> str:
            mode = (stream_info or {}).get("mode")
            if mode == "updates":
                return "🟢 **Stream:** updates · per-node delta"
            if mode == "values":
                return "🔵 **Stream:** values · cumulative snapshot"
            return "⚪ **Stream:** —"

        async for event in stream_run_graph(
            video_id=video_id,
            video_path=video_path,
            num_chunks=int(num_chunks),
            provider=provider,
            model=model,
            show_graph=False,
            stream_config=stream_config,
            cancel_event=_CANCEL_EVENT,
            refresh_notes=refresh_notes,
        ):
            data = event.get("data", {})
            counters = event.get("counters", {})
            stream_info = event.get("stream", {})
            progress_text = event.get("message", "Working…")
            progress_num = int(event.get("progress", 0) or 0)
            collected_pdf_path = data.get("collected_notes_pdf_path")
            summary_pdf_path = data.get("summary_pdf_path")
            if event.get("phase") == "cancelled":
                yield (
                    "Cancelled by user",
                    "\n".join(data.get("chunks", []) or []),
                    "\n\n".join(data.get("chunk_notes", []) or []),
                    "\n\n".join(data.get("image_integrated_notes", []) or []),
                    "\n\n".join(data.get("formatted_notes", []) or []),
                    data.get("collected_notes", ""),
                    data.get("summary", ""),
                    _format_counters_md(counters, progress_num),
                    _format_stream_mode_md(stream_info),
                    collected_pdf_path or None,
                    summary_pdf_path or None,
                )
                _CANCEL_EVENT = None
                return
            yield (
                progress_text,
                "\n".join(data.get("chunks", []) or []),
                "\n\n".join(data.get("chunk_notes", []) or []),
                "\n\n".join(data.get("image_integrated_notes", []) or []),
                "\n\n".join(data.get("formatted_notes", []) or []),
                data.get("collected_notes", ""),
                data.get("summary", ""),
                _format_counters_md(counters, progress_num),
                _format_stream_mode_md(stream_info),
                collected_pdf_path or None,
                summary_pdf_path or None,
            )
        _CANCEL_EVENT = None
    except Exception as e:
        logger.error(f"Error running graph: {str(e)}", exc_info=True)
        error_msg = f"Error: {str(e)}"
        yield (error_msg, "", "", "", "", "", "", "", "", None, None)


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
        gr.update(visible=v("image_integrated_notes")),
        gr.update(visible=v("formatted_notes")),
        gr.update(visible=v("collected_notes")),
        gr.update(visible=v("summary")),
        gr.update(visible=v("collected_notes_pdf_path")),
        gr.update(visible=v("summary_pdf_path")),
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
                "image_integrated_notes",
                "formatted_notes",
                "collected_notes",
                "summary",
                "collected_notes_pdf_path",
                "summary_pdf_path",
            ],
            value=[
                "formatted_notes",
                "summary",
                "collected_notes_pdf_path",
                "summary_pdf_path",
            ],
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
        video_path = gr.Textbox(
            label="Video Path",
            value="/home/hari/Desktop/VidScribe/backend/outputs/videos/wjZofJX0v4M/Transformers_the_tech_behind_LLMs_Deep_Learning_Chapter_5.mp4",
        )
        num_chunks = gr.Number(label="Number of Chunks", value=2, minimum=1)
        refresh_notes = gr.Checkbox(label="Refresh Notes", value=True)
    with gr.Row():
        provider = gr.Dropdown(
            label="Provider",
            choices=["google", "openai", "openrouter"],
            value="google",
        )
        model = gr.Textbox(label="Model", value="gemini-2.0-flash")

    run_btn = gr.Button("Run Graph")
    cancel_btn = gr.Button("Cancel")

    progress_output = gr.Textbox(label="Progress", value="Ready to run")
    stats_output = gr.Markdown(value="", elem_id="stats")
    stream_mode_output = gr.Markdown(value="", elem_id="stream_mode")
    # Initial visibility matches default compact settings: formatted_notes + summary only
    chunks_output = gr.Textbox(label="Chunks", lines=5, visible=False)
    notes_output = gr.Textbox(label="Chunk Notes", lines=10, visible=False)
    image_notes_output = gr.Textbox(
        label="Image Integrated Notes", lines=10, visible=False
    )
    formatted_output = gr.Textbox(label="Formatted Notes", lines=10, visible=True)
    collected_output = gr.Textbox(label="Collected Notes", lines=10, visible=False)
    summary_output = gr.Textbox(label="Summary", lines=5, visible=True)
    collected_pdf_output = gr.File(
        label="Collected Notes PDF",
        visible=False,
    )
    summary_pdf_output = gr.File(
        label="Summary PDF",
        visible=False,
    )

    run_btn.click(
        run_graph,
        inputs=[
            video_id,
            video_path,
            num_chunks,
            provider,
            model,
            compact_mode,
            include_fields,
            max_items,
            max_chars,
            refresh_notes,
        ],
        outputs=[
            progress_output,
            chunks_output,
            notes_output,
            image_notes_output,
            formatted_output,
            collected_output,
            summary_output,
            stats_output,
            stream_mode_output,
            collected_pdf_output,
            summary_pdf_output,
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
            image_notes_output,
            formatted_output,
            collected_output,
            summary_output,
            collected_pdf_output,
            summary_pdf_output,
        ],
    )

    include_fields.change(
        _visibility_updates,
        inputs=[compact_mode, include_fields],
        outputs=[
            chunks_output,
            notes_output,
            image_notes_output,
            formatted_output,
            collected_output,
            summary_output,
            collected_pdf_output,
            summary_pdf_output,
        ],
    )

if __name__ == "__main__":
    demo.launch()
