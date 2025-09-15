import os
from typing_extensions import TypedDict
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langgraph.runtime import Runtime

from .notes import create_path_to_save_notes
from .formatter import format_one_doc
from app.services import create_llm_instance
from app.prompts import SUMMARIZER_SYSTEM_PROMPT
from app.utils import create_simple_logger

logger = create_simple_logger(__name__)


class SummarizerState(TypedDict):
    collected_notes: str
    summary: str


def save_summary_path(video_id: str) -> str:
    path = create_path_to_save_notes(video_id)
    file_path = os.path.join(path, "summary.md")
    return file_path


def save_summary(video_id: str, text: str) -> None:
    file_path = save_summary_path(video_id=video_id)
    with open(file_path, "w") as file:
        file.write(text)
    logger.info(f"Summary saved at: {file_path}")


async def summarizer_node(state: SummarizerState, runtime: Runtime) -> SummarizerState:
    """Generates a summary of the given text using an LLM based on the provided runtime configuration."""
    file_path = save_summary_path(video_id=runtime.context["video_id"])
    if os.path.exists(file_path) and not runtime.context.get("refresh_notes", False):
        logger.info(f"Skipping summarization as summary already saved at: {file_path}")
        with open(file_path, "r") as file:
            saved_text = file.read()
        state["summary"] = saved_text
        return state

    llm = create_llm_instance(
        provider=runtime.context["provider"], model=runtime.context["model"]
    )
    system_message = SystemMessage(content=SUMMARIZER_SYSTEM_PROMPT)
    human_message = HumanMessage(content=state["collected_notes"])
    response = await llm.ainvoke([system_message, human_message])
    if isinstance(response, AIMessage):
        raw_summary = response.content
        logger.info("Raw summary generated, proceeding to format it.")
        formatted_summary = await format_one_doc(
            llm, raw_summary, current_chunk="summary", runtime=runtime
        )
        formatted_summary = formatted_summary["formatted_text"]
        save_summary(video_id=runtime.context["video_id"], text=formatted_summary)
        state["summary"] = formatted_summary
    else:
        logger.error("Unexpected response type from LLM")
        state["summary"] = state["collected_notes"]
    return state
