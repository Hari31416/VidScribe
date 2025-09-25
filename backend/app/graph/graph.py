from typing import List, Dict
from langgraph.runtime import Runtime
from langgraph.graph.state import CompiledStateGraph
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send

from app.graph.nodes.states import (
    RuntimeState,
    ImageIntegratorOverallState,
    OverAllState,
)
from app.graph.nodes.transcript import (
    get_raw_transcript,
    extract_text_from_transcript_chunk,
)
from app.graph.nodes.chunker import chunk_transcript
from app.graph.nodes.notes import chunk_notes_agent, notes_collector_agent
from app.graph.nodes.image_integrator import (
    timestamp_generator_agent,
    image_insertion_generation_agent,
    extract_frames,
    image_integrator_agent,
)
from app.graph.nodes.formatter import formatter_agent
from app.graph.nodes.summarizer import summarizer_agent
from app.graph.nodes.exporter import exporter_agent
from app.utils import create_simple_logger

logger = create_simple_logger(__name__)


def display_graph(graph: CompiledStateGraph, use_ascii: bool = True, **kwargs) -> None:
    if use_ascii:
        graph.get_graph(**kwargs).print_ascii()
        return

    from IPython.display import display, Image

    img = Image(graph.get_graph(**kwargs).draw_mermaid_png())
    display(img)


def create_transcript_chunks(
    state: OverAllState, runtime: Runtime
) -> Dict[str, List[str]]:
    raw_transcript = get_raw_transcript(runtime.context["video_id"])
    chunks = chunk_transcript(
        raw_transcript, num_chunks=runtime.context["num_chunks"], show_avg_tokens=True
    )
    chunks = [extract_text_from_transcript_chunk(chunk) for chunk in chunks]
    return {"chunks": chunks}


def build_notes_and_image_integration_subgraph(show_graph: bool = True, **kwargs):
    builder = StateGraph(
        ImageIntegratorOverallState,
        context_schema=RuntimeState,
        output_schema=OverAllState,
    )
    builder.add_node("chunk_notes_agent", chunk_notes_agent)
    builder.add_node("timestamp_generator_agent", timestamp_generator_agent)
    builder.add_node(
        "image_insertion_generation_agent", image_insertion_generation_agent
    )
    builder.add_node("extract_frames", extract_frames)
    builder.add_node("image_integrator_agent", image_integrator_agent)
    builder.add_node("formatter_agent", formatter_agent)

    builder.add_edge(START, "chunk_notes_agent")
    builder.add_edge("chunk_notes_agent", "timestamp_generator_agent")
    builder.add_edge("timestamp_generator_agent", "image_insertion_generation_agent")
    builder.add_edge("image_insertion_generation_agent", "extract_frames")
    builder.add_edge("extract_frames", "image_integrator_agent")
    builder.add_edge("image_integrator_agent", "formatter_agent")
    builder.add_edge("formatter_agent", END)

    subgraph = builder.compile(**kwargs)
    if not show_graph:
        return subgraph

    try:
        display_graph(subgraph, xray=True)
    except Exception as e:
        logger.warning(f"Could not display graph: {e}")
        logger.info("Printing ASCII representation of the graph instead:")
        subgraph.get_graph(xray=True).print_ascii()

    return subgraph


async def send_to_notes(
    state: OverAllState, runtime: Runtime
) -> ImageIntegratorOverallState:
    to_return = []
    for i, chunk in enumerate(state["chunks"]):
        res = Send(
            "notes_and_image_integration_subgraph",
            {"chunk": chunk, "chunk_idx": i + 1},
        )
        to_return.append(res)
    return to_return


def create_graph(show_graph: bool = True, **kwargs) -> CompiledStateGraph:
    notes_and_image_integration_subgraph = build_notes_and_image_integration_subgraph(
        show_graph=False, **kwargs
    )

    builder = StateGraph(OverAllState, context_schema=RuntimeState)
    builder.add_node("create_transcript_chunks", create_transcript_chunks)
    builder.add_node(
        "notes_and_image_integration_subgraph", notes_and_image_integration_subgraph
    )
    builder.add_node("formatter_agent", formatter_agent)
    builder.add_node("notes_collector_agent", notes_collector_agent)
    builder.add_node("summarizer_agent", summarizer_agent)
    builder.add_node("exporter_agent", exporter_agent)

    builder.add_edge(START, "create_transcript_chunks")
    builder.add_conditional_edges(
        "create_transcript_chunks",
        send_to_notes,
        ["notes_and_image_integration_subgraph"],
    )

    builder.add_edge("notes_and_image_integration_subgraph", "notes_collector_agent")
    builder.add_edge("notes_collector_agent", "summarizer_agent")
    builder.add_edge("summarizer_agent", "exporter_agent")
    builder.add_edge("exporter_agent", END)

    graph = builder.compile(**kwargs)
    if not show_graph:
        return graph

    try:
        display_graph(graph, xray=True, use_ascii=True)
    except Exception as e:
        logger.warning(f"Could not display graph: {e}")
        logger.info("Printing ASCII representation of the graph instead:")
        graph.get_graph(xray=True).print_ascii()

    return graph
