import os
from typing_extensions import TypedDict
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langgraph.runtime import Runtime

from .notes import save_intermediate_text, save_intermediate_text_path
from app.services import create_llm_instance
from app.prompts import FORMATTER_SYSTEM_PROMPT
from app.utils import create_simple_logger

logger = create_simple_logger(__name__)


class FormatterStateOne(TypedDict):
    original_text: str
    formatted_text: str
    chunk_number: int = 1


class FormatterStateAll(TypedDict):
    image_integrated_notes: list[str]
    formatted_notes: list[str]


async def format_one_doc(
    llm, original_text, current_chunk, runtime: Runtime
) -> FormatterStateOne:
    """Formats the given text using an LLM based on the provided runtime configuration."""
    file_path = save_intermediate_text_path(
        video_id=runtime.context["video_id"],
        chunk_number=current_chunk,
        note_type="formatted",
    )
    if os.path.exists(file_path):
        logger.info(
            f"Skipping formatting for chunk {current_chunk} as formatted text already saved at: {file_path}"
        )
        with open(file_path, "r") as file:
            saved_text = file.read()
        out = FormatterStateOne(
            original_text=original_text,
            formatted_text=saved_text,
            chunk_number=current_chunk,
        )
        return out

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
    for i, original_text in enumerate(state["image_integrated_notes"]):
        logger.info(
            f"Working on formatting chunk {i+1}/{len(state['image_integrated_notes'])}"
        )
        state_chunk = await format_one_doc(
            llm, original_text, current_chunk=i + 1, runtime=runtime
        )
        state["formatted_notes"].append(state_chunk["formatted_text"])
    return state
