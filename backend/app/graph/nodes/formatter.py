import os
from typing_extensions import TypedDict
from typing import Literal
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langgraph.runtime import Runtime

from .notes import create_path_to_save_notes
from app.services import create_llm_instance
from app.prompts import FORMATTER_SYSTEM_PROMPT
from app.utils import create_simple_logger

logger = create_simple_logger(__name__)


class FormatterStateOne(TypedDict):
    original_text: str
    formatted_text: str
    chunk_number: int = 1


class FormatterStateAll(TypedDict):
    chunk_notes: list[str]
    formatted_notes: list[str]


def save_intermediate_text(
    video_id: str,
    chunk_number: int | str,
    text: str,
    note_type: Literal["raw", "formatted"] = "formatted",
) -> None:
    path = create_path_to_save_notes(video_id)
    path = os.path.join(path, "partial")
    os.makedirs(path, exist_ok=True)
    file_path = os.path.join(path, f"{note_type}_chunk_{chunk_number}.md")
    with open(file_path, "w") as file:
        file.write(text)
    logger.info(f"Intermediate {note_type} text saved at: {file_path}")


async def format_one_doc(
    llm, original_text, current_chunk, runtime: Runtime
) -> FormatterStateOne:
    """Formats the given text using an LLM based on the provided runtime configuration."""
    save_intermediate_text(
        video_id=runtime.context["video_id"],
        chunk_number=current_chunk,
        text=original_text,
        note_type="raw",
    )
    llm = create_llm_instance(
        provider=runtime.context["provider"], model=runtime.context["model"]
    )
    system_message = SystemMessage(content=FORMATTER_SYSTEM_PROMPT)
    human_message = HumanMessage(content=original_text)
    response = await llm.ainvoke([system_message, human_message])
    if isinstance(response, AIMessage):
        save_intermediate_text(
            video_id=runtime.context["video_id"],
            chunk_number=current_chunk,
            text=response.content,
            note_type="formatted",
        )
        formatted_text = response.content
    else:
        logger.error("Unexpected response type from LLM")
        formatted_text = original_text

    out = FormatterStateOne(
        original_text=original_text,
        formatted_text=formatted_text,
        chunk_number=current_chunk,
    )
    return out


async def format_all_docs(
    state: FormatterStateAll, runtime: Runtime
) -> FormatterStateAll:
    """Formats all given texts using an LLM based on the provided runtime configuration."""
    llm = create_llm_instance(
        provider=runtime.context["provider"], model=runtime.context["model"]
    )
    state["formatted_notes"] = []
    for i, original_text in enumerate(state["chunk_notes"]):
        logger.info(f"Working on formatting chunk {i+1}/{len(state['chunk_notes'])}")
        state_chunk = await format_one_doc(
            llm, original_text, current_chunk=i + 1, runtime=runtime
        )
        state["formatted_notes"].append(state_chunk["formatted_text"])
    return state
