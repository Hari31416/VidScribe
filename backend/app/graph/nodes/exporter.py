from pathlib import Path
from langgraph.runtime import Runtime

from .states import ExporterState
from app.utils import create_simple_logger
from app.services.markdown_to_pdf import convert_markdown_to_pdf
from app.services.storage_service import get_storage_service
from app.graph.nodes.notes import save_final_notes_path
from app.graph.nodes.summarizer import save_summary_path
from app.services.markdown_embedder import (
    DEFAULT_PREAMBLE,
    DEFAULT_PREAMBLE_WITHOUT_TOC,
)

logger = create_simple_logger(__name__)


def upload_pdf_to_minio(
    pdf_path: Path,
    username: str,
    project_id: str,
    run_id: str,
    filename: str,
) -> None:
    """Upload a PDF file to MinIO storage."""
    if not username:
        logger.warning(f"No username provided, skipping MinIO upload for {filename}")
        return

    try:
        storage = get_storage_service()
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()
        storage.upload_notes(
            username=username,
            project_id=project_id,
            filename=filename,
            data=pdf_bytes,
            run_id=run_id,
            content_type="application/pdf",
        )
        logger.info(
            f"PDF '{filename}' uploaded to MinIO for user '{username}', run '{run_id}'"
        )
    except Exception as e:
        logger.error(f"Failed to upload PDF to MinIO: {e}")


async def exporter_agent(state: ExporterState, runtime: Runtime) -> ExporterState:
    """Exports the collected notes and summary to PDF format and uploads to MinIO."""
    video_id = runtime.context["video_id"]
    username = runtime.context.get("username")
    run_id = runtime.context.get("run_id")

    collected_notes_path = save_final_notes_path(video_id)
    summary_path = save_summary_path(video_id)

    collected_notes_path = Path(collected_notes_path)
    summary_path = Path(summary_path)

    # convert collected notes to PDF
    collected_notes_pdf_path = convert_markdown_to_pdf(
        md_path=collected_notes_path,
        remove_embedded_md=True,
        preamble=DEFAULT_PREAMBLE,
    )
    logger.info(f"Collected notes PDF saved at: {collected_notes_pdf_path}")

    # Upload final_notes.pdf to MinIO
    upload_pdf_to_minio(
        collected_notes_pdf_path, username, video_id, run_id, "final_notes.pdf"
    )

    # convert summary to PDF
    summary_pdf_path = convert_markdown_to_pdf(
        md_path=summary_path,
        remove_embedded_md=True,
        preamble=DEFAULT_PREAMBLE_WITHOUT_TOC,
    )
    logger.info(f"Summary PDF saved at: {summary_pdf_path}")

    # Upload summary.pdf to MinIO
    upload_pdf_to_minio(summary_pdf_path, username, video_id, run_id, "summary.pdf")

    return {
        "collected_notes_pdf_path": str(collected_notes_pdf_path),
        "summary_pdf_path": str(summary_pdf_path),
    }
