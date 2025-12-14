import os
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.runtime import Runtime

from .utils import (
    create_path_to_save_notes,
    cache_intermediate_text,
    handle_llm_markdown_response,
)
from .states import SummarizerState
from app.services import create_llm_instance
from app.services.storage_service import get_storage_service
from app.prompts import SUMMARIZER_SYSTEM_PROMPT
from app.utils import create_simple_logger

logger = create_simple_logger(__name__)


def save_summary_path(video_id: str) -> str:
    """Returns local file path for temporary operations (e.g., PDF conversion)."""
    path = create_path_to_save_notes(video_id)
    file_path = os.path.join(path, "summary.md")
    return file_path


def save_summary(
    video_id: str, text: str, username: str = None, run_id: str = None
) -> None:
    """Save summary to local filesystem and optionally to MinIO storage."""
    # Always save locally for PDF conversion
    file_path = save_summary_path(video_id=video_id)
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "w") as file:
        file.write(text)
    logger.info(f"Summary saved locally at: {file_path}")

    # Also save to MinIO if username is provided
    if username:
        try:
            storage = get_storage_service()
            storage.upload_notes(
                username=username,
                project_id=video_id,
                filename="summary.md",
                data=text,
                run_id=run_id,
            )
            logger.info(
                f"Summary uploaded to MinIO for user '{username}', run '{run_id}'"
            )
        except Exception as e:
            logger.error(f"Failed to upload summary to MinIO: {e}")


async def summarizer_agent(state: SummarizerState, runtime: Runtime) -> SummarizerState:
    """Generates a summary of the given text using an LLM based on the provided runtime configuration."""
    saved_summary = cache_intermediate_text(
        video_id=runtime.context["video_id"],
        note_type="summary",
        refresh_notes=runtime.context.get("refresh_notes", False),
        username=runtime.context.get("username"),
        run_id=runtime.context.get("run_id"),
    )
    if saved_summary:
        return {"summary": saved_summary}

    llm = create_llm_instance(
        provider=runtime.context["provider"], model=runtime.context["model"]
    )

    # Build system message with optional user feedback
    system_content = SUMMARIZER_SYSTEM_PROMPT
    user_feedback = runtime.context.get("user_feedback")
    if user_feedback:
        system_content += f"\n\n<user_instructions>\nThe user has provided the following additional instructions. Please incorporate these preferences when creating the summary:\n{user_feedback}\n</user_instructions>"

    system_message = SystemMessage(content=system_content)
    human_message = HumanMessage(content=state["collected_notes"])
    response = await llm.ainvoke([system_message, human_message])

    summary = handle_llm_markdown_response(response)
    save_summary(
        video_id=runtime.context["video_id"],
        text=summary,
        username=runtime.context.get("username"),
        run_id=runtime.context.get("run_id"),
    )
    return {"summary": summary}
