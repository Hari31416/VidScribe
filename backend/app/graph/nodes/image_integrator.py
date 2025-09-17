from typing_extensions import TypedDict, Annotated
from typing import List
from textwrap import dedent
from pydantic import BaseModel
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.runtime import Runtime
from typing import Literal
import os
import json

from app.services import create_llm_instance, extract_frame
from .notes import (
    save_intermediate_text,
    create_path_to_save_notes,
    save_intermediate_text_path,
)
from app.prompts import (
    TIMESTAMP_GENERATOR_SYSTEM_PROMPT,
    IMAGE_INTEGRATOR_SYSTEM_PROMPT,
)
from app.utils import create_simple_logger

logger = create_simple_logger(__name__)


class TimestampGeneratorInput(TypedDict):
    chunk_text: str
    chunk_notes: str
    chunk_id: int = 1


class Timestamp(BaseModel):
    timestamp: Annotated[str, "Timestamp in HH:MM:SS format"]
    reason: Annotated[str, "Short explanation why this timestamp is important"]


class TimestampGeneratorOutput(BaseModel):
    timestamps: List[Timestamp]


class ImageIntegratorInput(TypedDict):
    timestamps: List[Timestamp]
    chunk_notes: str


class ImageInsertion(BaseModel):
    timestamp: Annotated[str, "Timestamp in HH:MM:SS format"]
    line_number: Annotated[int, "Line number in the notes to insert the image"]
    caption: Annotated[str, "a short text caption for the image"]


class ImageIntegratorOutput(BaseModel):
    image_insertions: List[ImageInsertion]


class ImageExtraction(TypedDict):
    timestamp: str
    frame_path: str


# Created using `ImageInsertion` and `ImageExtraction` to map where to insert which extracted frame
class ImageInsertionInput(TypedDict):
    timestamp: str
    line_number: int
    caption: str
    frame_path: str


class ImageIntegratorOverallState(TypedDict):
    chunk_text: str
    chunk_notes: str
    chunk_id: int = 1
    image_insertions: List[ImageInsertion]
    image_integrated_notes: str
    timestamps: List[Timestamp]
    inserted_images: List[ImageInsertionInput]


def _save_generated_json_objects(
    video_id: str,
    chunk_number: int | str,
    data: dict,
    note_type: Literal["timestamps", "image_insertions"] = "timestamps",
) -> None:
    path = create_path_to_save_notes(video_id)
    path = os.path.join(path, "partial")
    os.makedirs(path, exist_ok=True)
    file_path = os.path.join(path, f"{note_type}_chunk_{chunk_number}.json")

    with open(file_path, "w") as file:
        json.dump(data, file, indent=4)
    logger.info(f"Generated {note_type} JSON saved at: {file_path}")


def _read_generated_json_objects(
    video_id: str,
    chunk_number: int | str,
    note_type: Literal["timestamps", "image_insertions"] = "timestamps",
) -> dict | None:
    path = create_path_to_save_notes(video_id)
    path = os.path.join(path, "partial")
    file_path = os.path.join(path, f"{note_type}_chunk_{chunk_number}.json")
    if not os.path.exists(file_path):
        return None

    with open(file_path, "r") as file:
        data = json.load(file)
    logger.info(f"Read existing {note_type} JSON from: {file_path}")
    return data


def _convert_image_path_to_relative(image_path: str, video_id: str) -> str:
    """Convert an absolute image path to a relative path based on the notes file location."""
    if os.path.isabs(image_path):
        path = create_path_to_save_notes(video_id)
        path = os.path.join(path, "partial")
        image_path = os.path.relpath(image_path, start=path)
    return image_path


def _format_chunk_text_for_timestamp_generator(
    chunk_text: str, chunk_notes: str
) -> str:
    """Formats the chunk text and notes for the timestamp generator prompt. Format is:

    <transcript>
    {{transcript_text}}
    </transcript>
    <notes>
    {{notes_text}}
    </notes>
    """
    formatted_text = dedent(
        f"""
        <transcript>
        {chunk_text}
        </transcript>
        <notes>
        {chunk_notes}
        </notes>
        """
    ).strip()
    return formatted_text


async def timestamp_generator_agent(
    state: ImageIntegratorOverallState,
    runtime: Runtime,
) -> ImageIntegratorOverallState:
    """Generates timestamps for important moments in the chunk text based on the chunk notes."""
    file_path = save_intermediate_text_path(
        video_id=runtime.context["video_id"],
        chunk_number=state["chunk_id"],
        note_type="timestamps",
    )
    if os.path.exists(file_path):
        logger.info(
            f"Skipping timestamp generation for chunk {state['chunk_id']} as timestamps already exist at: {file_path}"
        )
        existing_data = _read_generated_json_objects(
            video_id=runtime.context["video_id"],
            chunk_number=state["chunk_id"],
            note_type="timestamps",
        )
        if existing_data:
            state["timestamps"] = [
                Timestamp(**ts) for ts in existing_data.get("timestamps", [])
            ]
        return state

    llm = create_llm_instance(
        provider=runtime.context["provider"],
        model=runtime.context["model"],
        response_format=TimestampGeneratorOutput,
    )
    system_message = SystemMessage(content=TIMESTAMP_GENERATOR_SYSTEM_PROMPT)
    human_message = HumanMessage(
        content=_format_chunk_text_for_timestamp_generator(
            state["chunk_text"], state["chunk_notes"]
        )
    )
    response = await llm.ainvoke([system_message, human_message])
    assert isinstance(response, TimestampGeneratorOutput)
    _save_generated_json_objects(
        video_id=runtime.context["video_id"],
        chunk_number=state["chunk_id"],
        data=response.model_dump(),
        note_type="timestamps",
    )
    state["timestamps"] = response.timestamps
    return response


def _format_chunk_text_for_image_integrator(
    timestamps: List[Timestamp], chunk_notes: str
) -> str:
    """Formats the timestamps and chunk notes for the image integrator prompt. Format is:

    <timestamps>
    <timestamp>
    <timestamp>{{time in HH:MM:SS}}</timestamp>
    <reason>{{short_explanation}}</reason>
    </timestamp>
    ...
    </timestamps>
    <notes>
    {{notes_text}}
    </notes>
    """
    timestamps_str = "\n".join(
        [
            dedent(
                f"""
            <timestamp>
            <timestamp>{ts.timestamp}</timestamp>
            <reason>{ts.reason}</reason>
            </timestamp>
            """
            ).strip()
            for ts in timestamps
        ]
    )
    formatted_text = dedent(
        f"""
        <timestamps>
        {timestamps_str}
        </timestamps>
        <notes>
        {chunk_notes}
        </notes>
        """
    ).strip()
    return formatted_text


async def image_integrator_chunk_agent(
    state: ImageIntegratorOverallState,
    runtime: Runtime,
) -> ImageIntegratorOverallState:
    """Uses LLM to decide where to insert images in the chunk notes based on the timestamps and captions."""
    file_path = save_intermediate_text_path(
        video_id=runtime.context["video_id"],
        chunk_number=state["chunk_id"],
        note_type="image_insertions",
    )
    if os.path.exists(file_path):
        logger.info(
            f"Skipping image insertion generation for chunk {state['chunk_id']} as image insertions already exist at: {file_path}"
        )
        existing_data = _read_generated_json_objects(
            video_id=runtime.context["video_id"],
            chunk_number=state["chunk_id"],
            note_type="image_insertions",
        )
        if existing_data:
            state["image_insertions"] = [
                ImageInsertion(**ii) for ii in existing_data.get("image_insertions", [])
            ]
        return state

    llm = create_llm_instance(
        provider=runtime.context["provider"],
        model=runtime.context["model"],
        response_format=ImageIntegratorOutput,
    )
    system_message = SystemMessage(content=IMAGE_INTEGRATOR_SYSTEM_PROMPT)
    human_message = HumanMessage(
        content=_format_chunk_text_for_image_integrator(
            state["timestamps"], state["chunk_notes"]
        )
    )
    response = await llm.ainvoke([system_message, human_message])
    assert isinstance(response, ImageIntegratorOutput)
    _save_generated_json_objects(
        video_id=runtime.context["video_id"],
        chunk_number=state["chunk_id"],
        data=response.model_dump(),
        note_type="image_insertions",
    )
    state["image_insertions"] = response.image_insertions
    return state


async def extract_frames(
    state: ImageIntegratorOverallState,
    runtime: Runtime,
) -> ImageIntegratorOverallState:
    """Extracts frames from the video at the specified timestamps and saves them to disk."""
    video_id = runtime.context["video_id"]
    video_path = runtime.context["video_path"]
    image_extractions = []
    for ts in state["timestamps"]:
        try:
            frame_path, _ = extract_frame(
                video_id=video_id,
                video_path=video_path,
                timestamp=ts.timestamp,
            )
            logger.info(f"Extracted frame at {ts.timestamp} to {frame_path}")
            image_extractions.append(
                ImageExtraction(timestamp=ts.timestamp, frame_path=frame_path)
            )
        except Exception as e:
            logger.error(f"Failed to extract frame at {ts.timestamp}: {e}")
    state["inserted_images"] = image_extractions
    return state


def _integrate_images_into_notes(
    notes: str,
    image_insertions: List[ImageInsertionInput],
) -> str:
    """Integrates the image insertion into the notes at the specified line number.
    The format is:
    ![caption](frame_path)
    """
    if not isinstance(image_insertions, list):
        image_insertions = [image_insertions]

    if len(image_insertions) == 0:
        return notes

    notes_lines = notes.split("\n")
    # sort image insertions by line number descending to avoid messing up line numbers
    image_insertions = sorted(
        image_insertions, key=lambda x: x["line_number"], reverse=True
    )
    for insertion in image_insertions:
        line_number = insertion["line_number"]
        caption = insertion["caption"]
        frame_path = insertion["frame_path"]
        # convert to relative path if absolute
        if os.path.isabs(frame_path):
            frame_path = os.path.relpath(
                frame_path, start=os.path.dirname(os.path.abspath(notes))
            )
        markdown_image = f"![{caption}]({frame_path})"
        if 0 <= line_number - 1 < len(notes_lines):
            notes_lines.insert(line_number - 1, markdown_image)
            logger.info(
                f"Inserted image at line number {line_number} with caption '{caption}'"
            )
        else:
            logger.warning(
                f"Line number {line_number} out of range for notes with {len(notes_lines)} lines. Appending image at the end."
            )
            notes_lines.append(markdown_image)

    image_integrated_notes = "\n".join(notes_lines)
    return image_integrated_notes


async def image_integrator_chunk(
    state: ImageIntegratorOverallState,
    runtime: Runtime,
) -> ImageIntegratorOverallState:
    "Uses helper methods to extract frames and integrate them into the chunk notes."
    # Step 0: If integrated notes already exist, skip processing
    file_path = save_intermediate_text_path(
        video_id=runtime.context["video_id"],
        chunk_number=state["chunk_id"],
        note_type="integrated",
    )
    if os.path.exists(file_path):
        logger.info(
            f"Skipping image integration for chunk {state['chunk_id']} as integrated notes already exist at: {file_path}"
        )
        with open(file_path, "r") as file:
            saved_text = file.read()
        state["image_integrated_notes"] = saved_text
        state["inserted_images"] = []
        return state

    # # Step 1: Extract frames at the specified timestamps
    # image_extractions = await extract_frames(runtime, state["timestamps"])
    # logger.info(f"Extracted {len(image_extractions)} frames from video.")

    # Step 2: Map extracted frames to image insertions
    inserted_image = []
    image_extractions = state.get("inserted_images", [])
    for insertion in state["image_insertions"]:
        matching_extraction = next(
            (ie for ie in image_extractions if ie["timestamp"] == insertion.timestamp),
            None,
        )
        if matching_extraction:
            inserted_image.append(
                ImageInsertionInput(
                    timestamp=insertion.timestamp,
                    line_number=insertion.line_number,
                    caption=insertion.caption,
                    frame_path=matching_extraction["frame_path"],
                )
            )
        else:
            logger.warning(
                f"No extracted frame found for timestamp {insertion.timestamp}"
            )

    # Step 3: Integrate images into chunk notes
    for img in inserted_image:
        img["frame_path"] = _convert_image_path_to_relative(
            img["frame_path"], runtime.context["video_id"]
        )
    image_integrated_notes = _integrate_images_into_notes(
        state["chunk_notes"], inserted_image
    )
    save_intermediate_text(
        video_id=runtime.context["video_id"],
        chunk_number=state["chunk_id"],
        text=image_integrated_notes,
        note_type="integrated",
    )
    logger.info("Integrated images into chunk notes.")
    state["image_integrated_notes"] = image_integrated_notes
    state["inserted_images"] = inserted_image

    return state
