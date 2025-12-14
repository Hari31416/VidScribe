import os

from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.runtime import Runtime

from .utils import (
    notes_dir,
    save_intermediate_text,
    cache_intermediate_text,
    handle_llm_markdown_response,
)
from .states import ChunkNotesAgentState, NotesCollectorAgentState
from app.services import create_llm_instance
from app.prompts import CHUNK_NOTES_SYSTEM_PROMPT, NOTES_COLLECTOR_SYSTEM_PROMPT
from app.utils import create_simple_logger

logger = create_simple_logger(__name__)


def save_final_notes_path(video_id: str) -> str:
    file_path = os.path.join(notes_dir, video_id, "final_notes.md")
    return file_path


def save_final_notes(video_id: str, text: str) -> None:
    file_path = save_final_notes_path(video_id=video_id)
    with open(file_path, "w") as file:
        file.write(text)
    logger.info(f"Final notes saved at: {file_path}")


async def chunk_notes_agent(
    state: ChunkNotesAgentState, runtime: Runtime
) -> dict[str, str]:
    """Generates notes for each chunk of text using an LLM based on the provided runtime configuration."""
    system_message = SystemMessage(content=CHUNK_NOTES_SYSTEM_PROMPT)
    refresh_notes = runtime.context.get("refresh_notes", False)
    chunk_idx = state.get("chunk_idx", 0)

    saved_note = cache_intermediate_text(
        video_id=runtime.context["video_id"],
        note_type="raw",
        chunk_idx=chunk_idx,
        total_chunks=runtime.context["num_chunks"],
        refresh_notes=refresh_notes,
    )
    if saved_note:
        return {"chunk_note": saved_note, "chunk_notes": [saved_note]}

    llm = create_llm_instance(
        provider=runtime.context["provider"], model=runtime.context["model"]
    )

    chunk = state.get("chunk", "")
    human_message = HumanMessage(content=chunk)
    response = await llm.ainvoke([system_message, human_message])
    chunk_note = handle_llm_markdown_response(response)
    save_intermediate_text(
        video_id=runtime.context["video_id"],
        chunk_idx=chunk_idx,
        text=chunk_note,
        note_type="raw",
    )
    return {"chunk_note": chunk_note, "chunk_notes": [chunk_note]}


def convert_list_of_notes_to_xml(notes: list[str]) -> str:
    """Converts a list of notes into an XML format."""
    xml_notes = "<notes>\n"
    for note in notes:
        xml_notes += f"  <note>{note}</note>\n"
    xml_notes += "</notes>"
    return xml_notes


def _update_image_links_in_final_notes(final_notes: str) -> str:
    # move from ../../../frames/ to ../../frames/ in the final notes
    updated_notes = final_notes.replace("../../../frames/", "../../frames/")
    return updated_notes


async def notes_collector_agent(
    state: NotesCollectorAgentState, runtime: Runtime
) -> dict[str, str]:
    """Collects and merges notes from multiple chunks using an LLM based on the provided runtime configuration."""
    collected_notes = cache_intermediate_text(
        video_id=runtime.context["video_id"],
        note_type="final",
        refresh_notes=runtime.context.get("refresh_notes", False),
    )
    if collected_notes:
        return {"collected_notes": collected_notes}

    llm = create_llm_instance(
        provider=runtime.context["provider"], model=runtime.context["model"]
    )

    # Build system message with optional user feedback
    system_content = NOTES_COLLECTOR_SYSTEM_PROMPT
    user_feedback = runtime.context.get("user_feedback")
    if user_feedback:
        system_content += f"\n\n<user_instructions>\nThe user has provided the following additional instructions. Please incorporate these preferences when creating the final notes:\n{user_feedback}\n</user_instructions>"

    system_message = SystemMessage(content=system_content)
    notes_xml = convert_list_of_notes_to_xml(state["formatted_notes"])
    human_message = HumanMessage(content=notes_xml)

    response = await llm.ainvoke([system_message, human_message])

    collected_notes = handle_llm_markdown_response(response)
    updated_notes = _update_image_links_in_final_notes(collected_notes)
    save_final_notes(video_id=runtime.context["video_id"], text=updated_notes)
    return {"collected_notes": updated_notes}
