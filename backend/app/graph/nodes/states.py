from typing_extensions import TypedDict
from typing import List, Annotated, Optional
import operator
from pydantic import BaseModel

from app.utils import create_simple_logger

logger = create_simple_logger(__name__)


# Takes a chunk and its index, returns the raw note for that chunk
class ChunkNotesAgentState(TypedDict):
    chunk: str
    chunk_idx: int | str


# Formats a given chunk of text (used as inout for the formatter agent)
class FormatterState(TypedDict):
    image_integrated_note: str
    chunk_idx: int = 1


# final state after formatting all chunks (use as output for the formatter agent)
class FormatterStateFinal(TypedDict):
    image_integrated_notes: Annotated[List[str], operator.add]
    formatted_notes: Annotated[List[str], operator.add]


# Takes a chunk, its note and its index, returns the timestamp for that chunk
class TimestampGeneratorInput(TypedDict):
    chunk: str
    chunk_note: str
    chunk_idx: int = 1


# Base model for a timestamp with its reason (to be used in LLM)
class Timestamp(BaseModel):
    timestamp: Annotated[str, "Timestamp in HH:MM:SS format"]
    reason: Annotated[str, "Short explanation why this timestamp is important"]


# To be passed as response model to the LLM
class TimestampGeneratorOutput(BaseModel):
    timestamps: List[Timestamp]


# Takes timestamps and chunk note, returns image insertions after LLM processing
class ImageIntegratorInput(TypedDict):
    timestamps: List[Timestamp]
    chunk_note: str
    chunk_idx: int = 1


# Base model for an image insertion with timestamp, line number and caption (to be used in LLM)
class ImageInsertion(BaseModel):
    timestamp: Annotated[str, "Timestamp in HH:MM:SS format"]
    line_number: Annotated[int, "Line number in the notes to insert the image"]
    caption: Annotated[str, "a short text caption for the image"]


# To be passed as response model to the LLM
class ImageIntegratorOutput(BaseModel):
    image_insertions: List[ImageInsertion]


# Extract images after ImageInsertion is decided by LLM
class ImageExtractionInput(TypedDict):
    timestamps: List[Timestamp]


# Extract images after ImageInsertion is decided by LL
class ImageExtraction(TypedDict):
    timestamps: List[Timestamp]
    frame_path: str


# Created using `ImageInsertion` and `ImageExtraction` to map where to insert which extracted frame
# Used as input to the image integration agent
class ImageInsertionInput(TypedDict):
    timestamp: str
    line_number: int
    caption: str
    frame_path: str


# Overall state for image integration for a single chunk
class ImageIntegratorOverallState(TypedDict):
    chunk: str
    chunk_note: str
    chunk_idx: int = 1
    image_insertions: List[ImageInsertion]
    extracted_images: List[ImageExtraction]
    inserted_images: List[ImageInsertionInput]
    image_integrated_note: str
    timestamps: List[Timestamp]


# Takes formatted notes after image integration and generates final notes
class NotesCollectorAgentState(TypedDict):
    formatted_notes: List[str]
    collected_notes: str


class SummarizerState(TypedDict):
    collected_notes: str
    summary: str


class ExporterState(TypedDict):
    collected_notes_pdf_path: str
    summary_pdf_path: str


# Final overall state after processing all chunks
class OverAllState(TypedDict):
    chunks: List[str]
    chunk_notes: Annotated[List[str], operator.add]
    image_integrated_notes: Annotated[List[str], operator.add]
    formatted_notes: Annotated[List[str], operator.add]
    collected_notes: str
    integrates: Annotated[List[ImageIntegratorOverallState], operator.add]
    summary: str
    collected_notes_pdf_path: str
    summary_pdf_path: str
    timestamps_output: Annotated[List[List[Timestamp]], operator.add]
    image_insertions_output: Annotated[List[List[ImageInsertion]], operator.add]
    extracted_images_output: Annotated[List[List[ImageExtraction]], operator.add]
    # last three are for debugging and progress tracking


class TranscriptAndChunkingSubgraphState(TypedDict):
    chunks: List[str]
    chunk_notes: List[str]


class RuntimeState(TypedDict):
    provider: str = "google"
    model: str = "gemini-2.0-flash"
    video_id: str
    video_path: Optional[str] = None  # Optional for transcript-only uploads
    num_chunks: int = 2
    refresh_notes: bool = False
    add_images: bool = True  # Set to False for transcript-only mode
    user_feedback: Optional[str] = None  # Optional user instructions for LLM
