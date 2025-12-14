from typing import List
import json
import re
from textwrap import dedent
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.runtime import Runtime
import os

from app.services import create_llm_instance, extract_frame
from .utils import (
    save_intermediate_text,
    create_path_to_save_notes,
    cache_generated_json,
    save_generated_json_objects,
    cache_intermediate_text,
)
from .states import (
    Timestamp,
    TimestampGeneratorOutput,
    ImageInsertion,
    ImageIntegratorOutput,
    ImageExtraction,
    ImageIntegratorOverallState,
    ImageInsertionInput,
    TimestampGeneratorInput,
    ImageIntegratorInput,
    ImageExtractionInput,
    OverAllState,
)
from app.prompts import (
    TIMESTAMP_GENERATOR_SYSTEM_PROMPT,
    IMAGE_INTEGRATOR_SYSTEM_PROMPT,
)
from app.utils import create_simple_logger

logger = create_simple_logger(__name__)


def _convert_image_path_to_relative(image_path: str, video_id: str) -> str:
    """Convert an absolute image path to a relative path based on the notes file location."""
    if os.path.isabs(image_path):
        path = create_path_to_save_notes(video_id)
        path = os.path.join(path, "partial")
        image_path = os.path.relpath(image_path, start=path)
    return image_path


def _format_chunk_for_timestamp_generator(chunk: str, chunk_note: str) -> str:
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
        {chunk}
        </transcript>
        <notes>
        {chunk_note}
        </notes>
        """
    ).strip()
    return formatted_text


def _extract_json_from_text(text: str) -> dict | None:
    """Try to extract a JSON object from an LLM text response.

    - Prefer fenced code blocks ```json ... ```
    - Fallback to first {...} block in the text
    """
    if not text:
        return None
    # Code fence
    fence = re.search(r"```json\s*(.*?)\s*```", text, flags=re.DOTALL | re.IGNORECASE)
    if fence:
        try:
            return json.loads(fence.group(1))
        except Exception:
            pass
    # Any JSON object
    brace = re.search(r"\{[\s\S]*\}$", text.strip())
    if brace:
        try:
            return json.loads(brace.group(0))
        except Exception:
            pass
    # Try to find the first and last brace
    try:
        start = text.index("{")
        end = text.rindex("}") + 1
        return json.loads(text[start:end])
    except Exception:
        return None


async def timestamp_generator_agent(
    state: TimestampGeneratorInput,
    runtime: Runtime,
) -> ImageIntegratorOverallState:
    """Generates timestamps for important moments in the chunk text based on the chunk notes."""
    timestamps = cache_generated_json(
        video_id=runtime.context["video_id"],
        json_type="timestamps",
        chunk_idx=state["chunk_idx"],
        total_chunks=runtime.context.get("total_chunks"),
        refresh_json=runtime.context.get("refresh_notes", False),
        username=runtime.context.get("username"),
        run_id=runtime.context.get("run_id"),
    )
    if timestamps:
        timestamps = [Timestamp(**ts) for ts in timestamps.get("timestamps", [])]
        return {"timestamps": timestamps, "timestamps_output": [timestamps]}

    system_message = SystemMessage(content=TIMESTAMP_GENERATOR_SYSTEM_PROMPT)
    human_message = HumanMessage(
        content=_format_chunk_for_timestamp_generator(
            state["chunk"], state["chunk_note"]
        )
    )

    # Try structured output first
    try:
        llm = create_llm_instance(
            provider=runtime.context["provider"],
            model=runtime.context["model"],
            response_format=TimestampGeneratorOutput,
        )
        response = await llm.ainvoke([system_message, human_message])
        assert isinstance(
            response, TimestampGeneratorOutput
        ), "LLM response is not of type TimestampGeneratorOutput"
        save_generated_json_objects(
            video_id=runtime.context["video_id"],
            chunk_idx=state["chunk_idx"],
            data=response.model_dump(),
            json_type="timestamps",
            username=runtime.context.get("username"),
            run_id=runtime.context.get("run_id"),
        )
        return {
            "timestamps": response.timestamps,
            "timestamps_output": [response.timestamps],
        }
    except Exception as e:
        logger.warning(
            f"Structured output failed for timestamp_generator_agent, falling back to JSON parsing: {e}"
        )
        # Unstructured fallback
        llm = create_llm_instance(
            provider=runtime.context["provider"], model=runtime.context["model"]
        )
        # Nudge model to return clean JSON
        fallback_system = SystemMessage(
            content=TIMESTAMP_GENERATOR_SYSTEM_PROMPT
            + '\nReturn ONLY valid JSON with the shape {"timestamps":[{"timestamp":"HH:MM:SS","reason":"..."}]}'
        )
        res = await llm.ainvoke([fallback_system, human_message])
        text = getattr(res, "content", str(res))
        data = _extract_json_from_text(text) or {}
        try:
            parsed = TimestampGeneratorOutput(**data)
        except Exception:
            logger.error("Failed to parse timestamps JSON; returning empty list")
            parsed = TimestampGeneratorOutput(timestamps=[])
        save_generated_json_objects(
            video_id=runtime.context["video_id"],
            chunk_idx=state["chunk_idx"],
            data=parsed.model_dump(),
            json_type="timestamps",
            username=runtime.context.get("username"),
            run_id=runtime.context.get("run_id"),
        )
        return {
            "timestamps": parsed.timestamps,
            "timestamps_output": [parsed.timestamps],
        }


def _format_chunk_for_image_integrator(
    timestamps: List[Timestamp], chunk_note: str
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
        {chunk_note}
        </notes>
        """
    ).strip()
    return formatted_text


async def image_insertion_generation_agent(
    state: ImageIntegratorInput,
    runtime: Runtime,
) -> ImageIntegratorOverallState:
    """Uses LLM to decide where to insert images in the chunk notes based on the timestamps and captions."""
    image_insertions = cache_generated_json(
        video_id=runtime.context["video_id"],
        json_type="image_insertions",
        chunk_idx=state["chunk_idx"],
        total_chunks=runtime.context.get("total_chunks"),
        refresh_json=runtime.context.get("refresh_notes", False),
        username=runtime.context.get("username"),
        run_id=runtime.context.get("run_id"),
    )
    if image_insertions:
        image_insertions = [
            ImageInsertion(**ii) for ii in image_insertions.get("image_insertions", [])
        ]
        return {
            "image_insertions": image_insertions,
            "image_insertions_output": [image_insertions],
        }

    system_message = SystemMessage(content=IMAGE_INTEGRATOR_SYSTEM_PROMPT)
    human_message = HumanMessage(
        content=_format_chunk_for_image_integrator(
            state["timestamps"], state["chunk_note"]
        )
    )

    # Try structured output first
    try:
        llm = create_llm_instance(
            provider=runtime.context["provider"],
            model=runtime.context["model"],
            response_format=ImageIntegratorOutput,
        )
        response = await llm.ainvoke([system_message, human_message])
        assert isinstance(
            response, ImageIntegratorOutput
        ), "LLM response is not of type ImageIntegratorOutput"
        save_generated_json_objects(
            video_id=runtime.context["video_id"],
            chunk_idx=state["chunk_idx"],
            data=response.model_dump(),
            json_type="image_insertions",
            username=runtime.context.get("username"),
            run_id=runtime.context.get("run_id"),
        )
        return {
            "image_insertions": response.image_insertions,
            "image_insertions_output": [response.image_insertions],
        }
    except Exception as e:
        logger.warning(
            f"Structured output failed for image_insertion_generation_agent, falling back to JSON parsing: {e}"
        )
        # Unstructured fallback
        llm = create_llm_instance(
            provider=runtime.context["provider"], model=runtime.context["model"]
        )
        fallback_system = SystemMessage(
            content=IMAGE_INTEGRATOR_SYSTEM_PROMPT
            + '\nReturn ONLY valid JSON with the shape {"image_insertions":[{"timestamp":"HH:MM:SS","line_number":0,"caption":"..."}]}'
        )
        res = await llm.ainvoke([fallback_system, human_message])
        text = getattr(res, "content", str(res))
        data = _extract_json_from_text(text) or {}
        try:
            parsed = ImageIntegratorOutput(**data)
        except Exception:
            logger.error("Failed to parse image insertions JSON; returning empty list")
            parsed = ImageIntegratorOutput(image_insertions=[])
        save_generated_json_objects(
            video_id=runtime.context["video_id"],
            chunk_idx=state["chunk_idx"],
            data=parsed.model_dump(),
            json_type="image_insertions",
            username=runtime.context.get("username"),
            run_id=runtime.context.get("run_id"),
        )
        return {
            "image_insertions": parsed.image_insertions,
            "image_insertions_output": [parsed.image_insertions],
        }


async def extract_frames(
    state: ImageExtractionInput,
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
    return {
        "extracted_images": image_extractions,
        "extracted_images_output": [image_extractions],
    }


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


async def image_integrator_agent(
    state: ImageIntegratorOverallState,
    runtime: Runtime,
) -> OverAllState:
    "Uses helper methods to extract frames and integrate them into the chunk notes."
    # Step 0: If integrated notes already exist, skip processing
    image_integrated_notes = cache_intermediate_text(
        video_id=runtime.context["video_id"],
        chunk_idx=state["chunk_idx"],
        note_type="integrated",
        refresh_notes=runtime.context.get("refresh_notes", False),
        username=runtime.context.get("username"),
        run_id=runtime.context.get("run_id"),
    )

    if image_integrated_notes:
        return {
            "chunk_notes": [state["chunk_note"]],
            "image_integrated_notes": [image_integrated_notes],
            "integrates": [state],
            "image_integrated_note": image_integrated_notes,
        }

    inserted_image = []
    image_extractions = state.get("extracted_images", [])
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

    for img in inserted_image:
        img["frame_path"] = _convert_image_path_to_relative(
            img["frame_path"], runtime.context["video_id"]
        )
    image_integrated_notes = _integrate_images_into_notes(
        state["chunk_note"], inserted_image
    )
    save_intermediate_text(
        video_id=runtime.context["video_id"],
        chunk_idx=state["chunk_idx"],
        text=image_integrated_notes,
        note_type="integrated",
        username=runtime.context.get("username"),
        run_id=runtime.context.get("run_id"),
    )
    logger.info("Integrated images into chunk notes.")
    return {
        "chunk_notes": [state["chunk_note"]],
        "image_integrated_notes": [image_integrated_notes],
        "integrates": [state],
        "image_integrated_note": image_integrated_notes,
    }
