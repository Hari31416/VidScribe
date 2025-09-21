from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.runtime import Runtime

from .utils import (
    save_intermediate_text,
    handle_llm_markdown_response,
    cache_intermediate_text,
)
from .states import FormatterState, FormatterStateFinal
from app.services import create_llm_instance
from app.prompts import FORMATTER_SYSTEM_PROMPT
from app.utils import create_simple_logger

logger = create_simple_logger(__name__)


async def formatter_agent(
    state: FormatterState, runtime: Runtime
) -> FormatterStateFinal:
    """Formats the given text using an LLM based on the provided runtime configuration."""
    formatted_text = cache_intermediate_text(
        video_id=runtime.context["video_id"],
        note_type="formatted",
        chunk_idx=state["chunk_idx"],
        total_chunks=runtime.context["num_chunks"],
        refresh_notes=runtime.context.get("refresh_notes", False),
    )
    if formatted_text:
        return {"formatted_notes": [formatted_text]}

    llm = create_llm_instance(
        provider=runtime.context["provider"], model=runtime.context["model"]
    )

    original_text = state["image_integrated_note"]
    current_chunk = state["chunk_idx"]
    system_message = SystemMessage(content=FORMATTER_SYSTEM_PROMPT)
    human_message = HumanMessage(content=original_text)

    response = await llm.ainvoke([system_message, human_message])
    formatted_text = handle_llm_markdown_response(response)
    save_intermediate_text(
        video_id=runtime.context["video_id"],
        chunk_idx=current_chunk,
        text=formatted_text,
        note_type="formatted",
    )
    return {"formatted_notes": [formatted_text]}
