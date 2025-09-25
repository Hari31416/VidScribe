from pathlib import Path
from langgraph.runtime import Runtime

from .states import ExporterState
from app.utils import create_simple_logger
from app.services.markdown_to_pdf import convert_markdown_to_pdf
from app.graph.nodes.notes import save_final_notes_path
from app.graph.nodes.summarizer import save_summary_path

logger = create_simple_logger(__name__)


async def exporter_agent(state: ExporterState, runtime: Runtime) -> ExporterState:
    """Exports the collected notes and summary to PDF format."""
    video_id = runtime.context["video_id"]

    collected_notes_path = save_final_notes_path(video_id)
    summary_path = save_summary_path(video_id)

    collected_notes_path = Path(collected_notes_path)
    summary_path = Path(summary_path)

    # convert collected notes to PDF
    collected_notes_pdf_path = convert_markdown_to_pdf(
        md_path=collected_notes_path, remove_embedded_md=True
    )
    logger.info(f"Collected notes PDF saved at: {collected_notes_pdf_path}")

    # convert summary to PDF
    summary_pdf_path = convert_markdown_to_pdf(
        md_path=summary_path, remove_embedded_md=True
    )
    logger.info(f"Summary PDF saved at: {summary_pdf_path}")

    return {
        "collected_notes_pdf_path": str(collected_notes_pdf_path),
        "summary_pdf_path": str(summary_pdf_path),
    }
