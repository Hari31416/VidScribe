import os

from typing_extensions import TypedDict
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langgraph.runtime import Runtime
from typing import Literal

from app.services import create_llm_instance
from app.prompts import CHUNK_NOTES_SYSTEM_PROMPT, NOTES_COLLECTOR_SYSTEM_PROMPT
from app.utils import create_simple_logger

logger = create_simple_logger(__name__)
cur_file_dir = os.path.dirname(os.path.abspath(__file__))
# move three levels up to reach the 'backend' directory
backend_dir = os.path.abspath(os.path.join(cur_file_dir, "../../../"))
outputs_dir = os.path.join(backend_dir, "outputs")
os.makedirs(outputs_dir, exist_ok=True)
logger.debug(f"Outputs directory set at: {outputs_dir}")


class ChunkNotesAgentState(TypedDict):
    chunks: list[str]
    chunk_notes: list[str]


class NotesCollectorAgentState(TypedDict):
    formatted_notes: list[str]
    collected_notes: str


def create_path_to_save_notes(video_id: str) -> str:
    notes_dir = os.path.join(outputs_dir, "notes", video_id)
    os.makedirs(notes_dir, exist_ok=True)
    return notes_dir


def save_intermediate_text_path(
    video_id: str,
    chunk_number: int | str,
    note_type: Literal["raw", "integrated", "formatted"] = "formatted",
) -> str:
    path = create_path_to_save_notes(video_id)
    path = os.path.join(path, "partial")
    os.makedirs(path, exist_ok=True)
    file_path = os.path.join(path, f"{note_type}_chunk_{chunk_number}.md")
    return file_path


def save_intermediate_text(
    video_id: str,
    chunk_number: int | str,
    text: str,
    note_type: Literal["raw", "integrated", "formatted"] = "formatted",
) -> None:
    file_path = save_intermediate_text_path(
        video_id=video_id, chunk_number=chunk_number, note_type=note_type
    )
    with open(file_path, "w") as file:
        file.write(text)
    logger.info(f"Intermediate {note_type} text saved at: {file_path}")


def save_final_notes_path(video_id: str) -> str:
    path = create_path_to_save_notes(video_id)
    file_path = os.path.join(path, "final_notes.md")
    return file_path


def save_final_notes(video_id: str, text: str) -> None:
    file_path = save_final_notes_path(video_id=video_id)
    with open(file_path, "w") as file:
        file.write(text)
    logger.info(f"Final notes saved at: {file_path}")


async def chunk_notes_agent_node(
    state: ChunkNotesAgentState, runtime: Runtime
) -> ChunkNotesAgentState:
    """Generates notes for each chunk of text using an LLM based on the provided runtime configuration."""
    llm = create_llm_instance(
        provider=runtime.context["provider"], model=runtime.context["model"]
    )

    system_message = SystemMessage(content=CHUNK_NOTES_SYSTEM_PROMPT)
    refresh_notes = runtime.context.get("refresh_notes", False)
    state["chunk_notes"] = []
    for i, chunk in enumerate(state["chunks"]):
        file_path = save_intermediate_text_path(
            video_id=runtime.context["video_id"], chunk_number=i + 1, note_type="raw"
        )
        if os.path.exists(file_path) and not refresh_notes:
            logger.info(
                f"Skipping chunk {i+1}/{len(state['chunks'])} as raw text already saved at: {file_path}"
            )
            with open(file_path, "r") as file:
                saved_text = file.read()
            state["chunk_notes"].append(saved_text)
            continue
        logger.info(f"Working on chunk {i+1}/{len(state['chunks'])}")
        human_message = HumanMessage(content=chunk)
        response = await llm.ainvoke([system_message, human_message])
        if isinstance(response, AIMessage):
            save_intermediate_text(
                video_id=runtime.context["video_id"],
                chunk_number=i + 1,
                text=response.content,
                note_type="raw",
            )
            state["chunk_notes"].append(response.content)
        else:
            logger.error("Unexpected response type from LLM")
            state["chunk_notes"].append("")
    return state


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


async def notes_collector_agent_node(
    state: NotesCollectorAgentState, runtime: Runtime
) -> NotesCollectorAgentState:
    """Collects and merges notes from multiple chunks using an LLM based on the provided runtime configuration."""
    file_path = save_final_notes_path(video_id=runtime.context["video_id"])
    if os.path.exists(file_path) and not runtime.context.get("refresh_notes", False):
        logger.info(
            f"Skipping notes collection as final notes already saved at: {file_path}"
        )
        with open(file_path, "r") as file:
            saved_text = file.read()
        state["collected_notes"] = saved_text
        return state

    llm = create_llm_instance(
        provider=runtime.context["provider"], model=runtime.context["model"]
    )
    system_message = SystemMessage(content=NOTES_COLLECTOR_SYSTEM_PROMPT)
    notes_xml = convert_list_of_notes_to_xml(state["formatted_notes"])
    human_message = HumanMessage(content=notes_xml)
    response = await llm.ainvoke([system_message, human_message])
    if isinstance(response, AIMessage):
        updated_notes = _update_image_links_in_final_notes(response.content)
        save_final_notes(video_id=runtime.context["video_id"], text=updated_notes)
        state["collected_notes"] = updated_notes
    else:
        logger.error("Unexpected response type from LLM")
        state["collected_notes"] = ""
    return state
