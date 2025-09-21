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
from app.prompts import SUMMARIZER_SYSTEM_PROMPT
from app.utils import create_simple_logger

logger = create_simple_logger(__name__)


def save_summary_path(video_id: str) -> str:
    path = create_path_to_save_notes(video_id)
    file_path = os.path.join(path, "summary.md")
    return file_path


def save_summary(video_id: str, text: str) -> None:
    file_path = save_summary_path(video_id=video_id)
    with open(file_path, "w") as file:
        file.write(text)
    logger.info(f"Summary saved at: {file_path}")


async def summarizer_agent(state: SummarizerState, runtime: Runtime) -> SummarizerState:
    """Generates a summary of the given text using an LLM based on the provided runtime configuration."""
    saved_summary = cache_intermediate_text(
        video_id=runtime.context["video_id"],
        note_type="summary",
        refresh_notes=runtime.context.get("refresh_notes", False),
    )
    if saved_summary:
        return {"summary": saved_summary}

    llm = create_llm_instance(
        provider=runtime.context["provider"], model=runtime.context["model"]
    )
    system_message = SystemMessage(content=SUMMARIZER_SYSTEM_PROMPT)
    human_message = HumanMessage(content=state["collected_notes"])
    response = await llm.ainvoke([system_message, human_message])

    summary = handle_llm_markdown_response(response)
    save_summary(video_id=runtime.context["video_id"], text=summary)
    return {"summary": summary}
