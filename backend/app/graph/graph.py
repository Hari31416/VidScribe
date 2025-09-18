from typing_extensions import TypedDict
from typing import List, Dict, Optional
from langgraph.graph import StateGraph, START, END
from langgraph.runtime import Runtime
from langgraph.graph.state import CompiledStateGraph

from app.graph.nodes import *
from app.graph import *
from app.utils import create_simple_logger

logger = create_simple_logger(__name__)


class RuntimeState(TypedDict):
    provider: str = "google"
    model: str = "gemini-2.0-flash"
    video_id: str
    video_path: str
    num_chunks: int = 2
    refresh_notes: bool = False
    add_images: bool = True


class ImageIntegratorLoopState(TypedDict):
    integrates = List[ImageIntegratorOverallState]


class OverAllState(TypedDict):
    chunks: List[str]
    chunk_notes: List[str]
    image_integrated_notes: Optional[List[str]]
    formatted_notes: List[str]
    collected_notes: str
    integrates: Optional[List[ImageIntegratorOverallState]]
    summary: str


class TranscriptAndChunkingSubgraphState(TypedDict):
    chunks: List[str]
    chunk_notes: List[str]


### Transcript, Chunking and Raw Chunk Notes Subgraph ###


def create_transcript_chunks(
    state: OverAllState, runtime: Runtime
) -> Dict[str, List[str]]:
    raw_transcript = get_raw_transcript(runtime.context["video_id"])
    chunks = chunk_transcript(
        raw_transcript, num_chunks=runtime.context["num_chunks"], show_avg_tokens=True
    )
    chunks = [extract_text_from_transcript_chunk(chunk) for chunk in chunks]
    state["chunks"] = chunks
    return state


def create_transcript_and_chunks_subgraph(
    show_graph: bool = True, **kwargs
) -> CompiledStateGraph:
    transcript_and_chunk_subgraph_builder = StateGraph(
        TranscriptAndChunkingSubgraphState, context_schema=RuntimeState
    )
    transcript_and_chunk_subgraph_builder.add_node(
        "create_transcript_chunks", create_transcript_chunks
    )
    transcript_and_chunk_subgraph_builder.add_edge(START, "create_transcript_chunks")

    transcript_and_chunk_subgraph_builder.add_node(
        "chunk_notes", chunk_notes_agent_node
    )
    transcript_and_chunk_subgraph_builder.add_edge(
        "create_transcript_chunks", "chunk_notes"
    )
    transcript_and_chunk_subgraph = transcript_and_chunk_subgraph_builder.compile(
        **kwargs
    )

    if show_graph:
        display_graph(transcript_and_chunk_subgraph, xray=True)

    return transcript_and_chunk_subgraph


def create_image_extractor_subgraph(
    show_graph: bool = True, **kwargs
) -> CompiledStateGraph:

    image_extractor_subgraph_builder = StateGraph(
        ImageIntegratorOverallState, context_schema=RuntimeState
    )

    image_extractor_subgraph_builder.add_node(
        "timestamp_generator_agent", timestamp_generator_agent
    )
    image_extractor_subgraph_builder.add_edge(START, "timestamp_generator_agent")

    image_extractor_subgraph_builder.add_node(
        "image_integrator_chunk_agent", image_integrator_chunk_agent
    )
    image_extractor_subgraph_builder.add_edge(
        "timestamp_generator_agent", "image_integrator_chunk_agent"
    )

    image_extractor_subgraph_builder.add_node("extract_frames", extract_frames)
    image_extractor_subgraph_builder.add_edge(
        "image_integrator_chunk_agent", "extract_frames"
    )

    image_extractor_subgraph_builder.add_node(
        "image_integrator_chunk", image_integrator_chunk
    )
    image_extractor_subgraph_builder.add_edge(
        "extract_frames", "image_integrator_chunk"
    )

    image_extractor_subgraph = image_extractor_subgraph_builder.compile(**kwargs)

    if show_graph:
        display_graph(image_extractor_subgraph, xray=True)

    return image_extractor_subgraph


def format_and_final_notes_subgraph(
    show_graph: bool = True, **kwargs
) -> CompiledStateGraph:

    format_and_summarize_subgraph_builder = StateGraph(
        OverAllState, context_schema=RuntimeState
    )
    format_and_summarize_subgraph_builder.add_node("format_all_docs", format_all_docs)
    format_and_summarize_subgraph_builder.add_edge(START, "format_all_docs")

    ## Create final notes
    format_and_summarize_subgraph_builder.add_node(
        "collect_notes", notes_collector_agent_node
    )
    format_and_summarize_subgraph_builder.add_edge("format_all_docs", "collect_notes")

    ## Create summary
    format_and_summarize_subgraph_builder.add_node("summarizer", summarizer_node)
    format_and_summarize_subgraph_builder.add_edge("collect_notes", "summarizer")

    format_and_summarize_subgraph = format_and_summarize_subgraph_builder.compile(
        **kwargs
    )
    if show_graph:
        display_graph(format_and_summarize_subgraph, xray=True)

    return format_and_summarize_subgraph


async def chunking_to_image_integrator(
    state: TranscriptAndChunkingSubgraphState,
    runtime: Runtime,
    image_extractor_subgraph: CompiledStateGraph,
) -> ImageIntegratorLoopState:
    total_chunks = len(state["chunks"])
    results = []
    for idx in range(total_chunks):
        logger.info(f"Processing chunk {idx+1}/{total_chunks}")
        res = await image_extractor_subgraph.ainvoke(
            input={
                "chunk_text": state["chunks"][idx],
                "chunk_notes": state["chunk_notes"][idx],
                "chunk_id": idx,
            },
            context=runtime.context,
        )
        results.append(res)
        logger.info(f"Completed chunk {idx+1}/{total_chunks}")
    return ImageIntegratorLoopState(integrates=results)


async def collect_images_integrated_notes(
    state: ImageIntegratorLoopState, runtime: Runtime
) -> OverAllState:
    integrates = state["integrates"]
    new_overall_state: OverAllState = {
        "chunks": [s["chunk_text"] for s in integrates],
        "chunk_notes": [s["chunk_notes"] for s in integrates],
        "image_integrated_notes": [s["image_integrated_notes"] for s in integrates],
    }
    return new_overall_state


def create_graph(show_graph: bool = True, **kwargs) -> CompiledStateGraph:
    transcript_and_chunk_subgraph = create_transcript_and_chunks_subgraph(
        show_graph=False, **kwargs
    )
    image_extractor_subgraph = create_image_extractor_subgraph(
        show_graph=False, **kwargs
    )
    format_and_summarize_subgraph = format_and_final_notes_subgraph(
        show_graph=False, **kwargs
    )

    async def chunking_to_image_integrator_node(state, runtime):
        return await chunking_to_image_integrator(
            state, runtime, image_extractor_subgraph
        )

    final_graph_builder = StateGraph(OverAllState, context_schema=RuntimeState)
    final_graph_builder.add_node(
        "transcript_and_chunk_subgraph", transcript_and_chunk_subgraph
    )
    final_graph_builder.add_edge(START, "transcript_and_chunk_subgraph")

    final_graph_builder.add_node(
        "chunking_to_image_integrator", chunking_to_image_integrator_node
    )
    final_graph_builder.add_edge(
        "transcript_and_chunk_subgraph", "chunking_to_image_integrator"
    )

    final_graph_builder.add_node(
        "collect_images_integrated_notes", collect_images_integrated_notes
    )
    final_graph_builder.add_edge(
        "chunking_to_image_integrator", "collect_images_integrated_notes"
    )

    final_graph_builder.add_node(
        "format_and_summarize_subgraph", format_and_summarize_subgraph
    )
    final_graph_builder.add_edge(
        "collect_images_integrated_notes", "format_and_summarize_subgraph"
    )
    final_graph_builder.add_edge("format_and_summarize_subgraph", END)
    final_graph = final_graph_builder.compile()

    if show_graph:
        display_graph(final_graph, xray=True)

    return final_graph


def display_graph(graph: CompiledStateGraph, **kwargs) -> None:
    from IPython.display import display, Image

    img = Image(graph.get_graph(**kwargs).draw_mermaid_png())
    display(img)
