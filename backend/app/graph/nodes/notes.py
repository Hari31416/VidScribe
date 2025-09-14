import os

from typing_extensions import TypedDict
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langgraph.runtime import Runtime

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


def save_final_notes(video_id: str, text: str) -> None:
    path = create_path_to_save_notes(video_id)
    file_path = os.path.join(path, "final_notes.md")
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
    state["chunk_notes"] = []
    for i, chunk in enumerate(state["chunks"]):
        logger.info(f"Working on chunk {i+1}/{len(state['chunks'])}")
        human_message = HumanMessage(content=chunk)
        response = await llm.ainvoke([system_message, human_message])
        if isinstance(response, AIMessage):
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


async def notes_collector_agent_node(
    state: NotesCollectorAgentState, runtime: Runtime
) -> NotesCollectorAgentState:
    """Collects and merges notes from multiple chunks using an LLM based on the provided runtime configuration."""
    llm = create_llm_instance(
        provider=runtime.context["provider"], model=runtime.context["model"]
    )
    system_message = SystemMessage(content=NOTES_COLLECTOR_SYSTEM_PROMPT)
    notes_xml = convert_list_of_notes_to_xml(state["formatted_notes"])
    human_message = HumanMessage(content=notes_xml)
    response = await llm.ainvoke([system_message, human_message])
    if isinstance(response, AIMessage):
        save_final_notes(video_id=runtime.context["video_id"], text=response.content)
        state["collected_notes"] = response.content
    else:
        logger.error("Unexpected response type from LLM")
        state["collected_notes"] = ""
    return state
