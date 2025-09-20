import os
import json

from app.utils import create_simple_logger
from typing import Literal
from langchain_core.messages import AIMessage

logger = create_simple_logger(__name__)
cur_file_dir = os.path.dirname(os.path.abspath(__file__))
# move three levels up to reach the 'backend' directory
backend_dir = os.path.abspath(os.path.join(cur_file_dir, "../../../"))
outputs_dir = os.path.join(backend_dir, "outputs")
notes_dir = os.path.join(outputs_dir, "notes")
frames_dir = os.path.join(outputs_dir, "frames")
video_dir = os.path.join(outputs_dir, "videos")
all_dirs = {
    "outputs": outputs_dir,
    "notes": notes_dir,
    "frames": frames_dir,
    "videos": video_dir,
}

for dir_name, dir_path in all_dirs.items():
    logger.debug(f"{dir_name.capitalize()} directory set at: {dir_path}")
    os.makedirs(dir_path, exist_ok=True)


def create_path_to_save_notes(video_id: str) -> str:
    notes_dir = os.path.join(outputs_dir, "notes", video_id)
    os.makedirs(notes_dir, exist_ok=True)
    return notes_dir


def save_intermediate_text_path(
    video_id: str,
    chunk_idx: int | str,
    note_type: Literal["raw", "integrated", "formatted"] = "formatted",
) -> str:
    path = create_path_to_save_notes(video_id)
    path = os.path.join(path, "partial")
    os.makedirs(path, exist_ok=True)
    file_path = os.path.join(path, f"{note_type}_chunk_{chunk_idx}.md")
    return file_path


def save_intermediate_text(
    video_id: str,
    chunk_idx: int | str,
    text: str,
    note_type: Literal["raw", "integrated", "formatted"] = "formatted",
) -> None:
    file_path = save_intermediate_text_path(
        video_id=video_id, chunk_idx=chunk_idx, note_type=note_type
    )
    with open(file_path, "w") as file:
        file.write(text)
    logger.info(f"Intermediate {note_type} text saved at: {file_path}")


def save_final_notes_path(video_id: str) -> str:
    file_path = os.path.join(notes_dir, video_id, "final_notes.md")
    return file_path


def cache_intermediate_text(
    video_id: str,
    note_type: Literal["raw", "integrated", "formatted", "final", "summary"],
    chunk_idx: int | str = None,
    total_chunks: int = None,
    refresh_notes: bool = False,
):
    if note_type in ["final", "summary"]:
        file_path = save_final_notes_path(video_id=video_id)
        if note_type == "summary":
            file_path = file_path.replace("final_notes.md", "summary.md")
    else:
        file_path = save_intermediate_text_path(
            video_id=video_id, chunk_idx=chunk_idx, note_type=note_type
        )
    if os.path.exists(file_path) and not refresh_notes:
        log_msg = f"Found cached {note_type.title()} text at {file_path}"
        if chunk_idx is not None and total_chunks is not None:
            log_msg += f" for chunk {chunk_idx}/{total_chunks}"
        logger.info(log_msg)

        with open(file_path, "r") as file:
            cached_text = file.read()
        return cached_text

    return None


def save_generated_json_objects_path(
    video_id: str,
    chunk_number: int | str,
    json_type: Literal["timestamps", "image_insertions"] = "timestamps",
) -> None:
    path = create_path_to_save_notes(video_id)
    path = os.path.join(path, "partial")
    os.makedirs(path, exist_ok=True)
    file_path = os.path.join(path, f"{json_type}_chunk_{chunk_number}.json")
    return file_path


def save_generated_json_objects(
    video_id: str,
    chunk_number: int | str,
    data: dict,
    json_type: Literal["timestamps", "image_insertions"] = "timestamps",
) -> None:
    file_path = save_generated_json_objects_path(video_id, chunk_number, json_type)

    with open(file_path, "w") as file:
        json.dump(data, file, indent=4)
    logger.info(f"Generated {json_type} JSON saved at: {file_path}")


def read_generated_json_objects(
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


def cache_generated_json(
    video_id: str,
    json_type: Literal["timestamps", "image_insertions"],
    chunk_idx: int | str,
    total_chunks: int = None,
    refresh_json: bool = False,
):
    file_path = save_generated_json_objects_path(
        video_id=video_id, chunk_number=chunk_idx, json_type=json_type
    )
    if os.path.exists(file_path) and not refresh_json:
        log_msg = (
            f"Found cached {json_type.replace('_', ' ').title()} JSON at {file_path}"
        )
        if chunk_idx is not None and total_chunks is not None:
            log_msg += f" for chunk {chunk_idx}/{total_chunks}"
        logger.info(log_msg)

        with open(file_path, "r") as file:
            cached_json = json.load(file)
        return cached_json

    return None


def handle_llm_markdown_response(response: AIMessage) -> str:
    if not isinstance(response, AIMessage):
        logger.error("Unexpected response type from LLM")
        return str(response)

    content = response.content
    if content.startswith("```") and content.endswith("```"):
        # Remove the triple backticks
        content = content[3:-3].strip()
        # If there's a language specifier, remove it
        if "\n" in content:
            first_line, rest_of_content = content.split("\n", 1)
            if first_line.isalpha():  # Simple check for language specifier
                content = rest_of_content.strip()
    return content
