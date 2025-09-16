from typing_extensions import TypedDict
from typing import List, Dict
from langgraph.graph import StateGraph, START, END
from langgraph.runtime import Runtime

from app.graph.nodes import *
from app.utils import create_simple_logger

logger = create_simple_logger(__name__)


class OverAllState(TypedDict):
    chunks: List[str]
    chunk_notes: List[str]
    formatted_notes: List[str]
    collected_notes: str
    summary: str


class RuntimeState(TypedDict):
    provider: str = "google"
    model: str = "gemini-2.0-flash"
    video_id: str
    num_chunks: int = 2
    refresh_notes: bool = False


def create_transcript_chunks(
    state: OverAllState, runtime: Runtime
) -> Dict[str, List[str]]:
    raw_transcript = get_raw_transcript(runtime.context["video_id"])
    chunks = chunk_transcript(
        raw_transcript, num_chunks=runtime.context["num_chunks"], show_avg_tokens=True
    )
    chunks = [extract_text_from_transcript_chunk(chunk) for chunk in chunks]
    return {"chunks": chunks}


def create_graph(show_graph: bool = True, **kwargs) -> StateGraph:
    builder = StateGraph(OverAllState, context_schema=RuntimeState)

    # start by chunking
    builder.add_node("create_transcript_chunks", create_transcript_chunks)
    builder.add_edge(START, "create_transcript_chunks")

    ## then do notes for each chunk
    builder.add_node("chunk_notes", chunk_notes_agent_node)
    builder.add_edge("create_transcript_chunks", "chunk_notes")

    ## Format each chunk note
    builder.add_node("format_docs", format_all_docs)
    builder.add_edge("chunk_notes", "format_docs")

    ## Create final notes
    builder.add_node("collect_notes", notes_collector_agent_node)
    builder.add_edge("format_docs", "collect_notes")

    ## Create summary
    builder.add_node("summarizer", summarizer_node)
    builder.add_edge("collect_notes", "summarizer")
    builder.add_edge("summarizer", END)

    graph = builder.compile(**kwargs)
    logger.info("Graph successfully created.")
    if show_graph:
        from IPython.display import display

        display(graph)

    return graph
