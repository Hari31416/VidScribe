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
    username: str = None,
    run_id: str = None,
) -> None:
    """Save intermediate chunk text to MinIO (and local as fallback)."""
    # Upload to MinIO if username provided
    if username:
        try:
            from app.services.storage_service import get_storage_service

            storage = get_storage_service()
            filename = f"partial/{note_type}_chunk_{chunk_idx}.md"
            storage.upload_notes(
                username=username,
                project_id=video_id,
                filename=filename,
                data=text,
                run_id=run_id,
            )
            logger.info(
                f"Intermediate {note_type} text uploaded to MinIO for chunk {chunk_idx}"
            )
            return
        except Exception as e:
            logger.warning(f"MinIO upload failed, falling back to local: {e}")

    # Fallback to local file
    file_path = save_intermediate_text_path(
        video_id=video_id, chunk_idx=chunk_idx, note_type=note_type
    )
    with open(file_path, "w") as file:
        file.write(text)
    logger.info(f"Intermediate {note_type} text saved locally at: {file_path}")


def save_final_notes_path(video_id: str) -> str:
    file_path = os.path.join(notes_dir, video_id, "final_notes.md")
    return file_path


def cache_intermediate_text(
    video_id: str,
    note_type: Literal["raw", "integrated", "formatted", "final", "summary"],
    chunk_idx: int | str = None,
    total_chunks: int = None,
    refresh_notes: bool = False,
    username: str = None,
    run_id: str = None,
):
    """Check MinIO first for cached notes, then local filesystem."""
    if refresh_notes:
        return None

    # Determine filename based on note type
    if note_type in ["final", "summary"]:
        filename = "final_notes.md" if note_type == "final" else "summary.md"
    else:
        filename = f"partial/{note_type}_chunk_{chunk_idx}.md"

    # Try MinIO first if username provided
    if username:
        try:
            from app.services.storage_service import get_storage_service, ARTIFACT_NOTES

            storage = get_storage_service()

            # Build the full path with run_id
            full_filename = f"{run_id}/{filename}" if run_id else filename

            if storage.file_exists(username, video_id, ARTIFACT_NOTES, full_filename):
                content = storage.download_file(
                    username, video_id, ARTIFACT_NOTES, filename, run_id=run_id
                )
                if content:
                    log_msg = f"Found cached {note_type.title()} text in MinIO"
                    if chunk_idx is not None and total_chunks is not None:
                        log_msg += f" for chunk {chunk_idx}/{total_chunks}"
                    logger.info(log_msg)
                    return (
                        content.decode("utf-8")
                        if isinstance(content, bytes)
                        else content
                    )
        except Exception as e:
            logger.warning(f"MinIO cache check failed: {e}")

    # Fallback to local filesystem
    if note_type in ["final", "summary"]:
        file_path = save_final_notes_path(video_id=video_id)
        if note_type == "summary":
            file_path = file_path.replace("final_notes.md", "summary.md")
    else:
        file_path = save_intermediate_text_path(
            video_id=video_id, chunk_idx=chunk_idx, note_type=note_type
        )

    if os.path.exists(file_path):
        log_msg = f"Found cached {note_type.title()} text locally at {file_path}"
        if chunk_idx is not None and total_chunks is not None:
            log_msg += f" for chunk {chunk_idx}/{total_chunks}"
        logger.info(log_msg)

        with open(file_path, "r") as file:
            cached_text = file.read()
        return cached_text

    return None


def cache_from_minio(
    username: str,
    project_id: str,
    run_id: str,
    filename: str,
    refresh: bool = False,
) -> str | None:
    """
    Check MinIO storage for cached notes content.

    Args:
        username: User's username (required)
        project_id: Project/video ID
        run_id: Run ID for versioned notes
        filename: Filename to check (e.g., 'final_notes.md')
        refresh: If True, skip cache

    Returns:
        Cached content as string, or None if not found
    """
    if refresh:
        return None

    if not username:
        logger.warning("No username provided for MinIO cache check")
        return None

    try:
        from app.services.storage_service import get_storage_service, ARTIFACT_NOTES

        storage = get_storage_service()

        # Check if file exists
        if storage.file_exists(
            username,
            project_id,
            ARTIFACT_NOTES,
            f"{run_id}/{filename}" if run_id else filename,
        ):
            content = storage.download_file(
                username, project_id, ARTIFACT_NOTES, filename, run_id=run_id
            )
            if content:
                logger.info(
                    f"Found cached '{filename}' in MinIO for user '{username}', run '{run_id}'"
                )
                return (
                    content.decode("utf-8") if isinstance(content, bytes) else content
                )
    except Exception as e:
        logger.warning(f"MinIO cache check failed: {e}")

    return None


def save_to_minio(
    username: str,
    project_id: str,
    run_id: str,
    filename: str,
    content: str | bytes,
    content_type: str = None,
) -> bool:
    """
    Save content to MinIO storage.

    Args:
        username: User's username (required)
        project_id: Project/video ID
        run_id: Run ID for versioned notes
        filename: Filename to save
        content: Content to save
        content_type: MIME type

    Returns:
        True if successful, False otherwise
    """
    if not username:
        logger.error("Cannot save to MinIO: username is required")
        return False

    try:
        from app.services.storage_service import get_storage_service

        storage = get_storage_service()
        storage.upload_notes(
            username=username,
            project_id=project_id,
            filename=filename,
            data=content,
            run_id=run_id,
            content_type=content_type,
        )
        logger.info(
            f"Saved '{filename}' to MinIO for user '{username}', run '{run_id}'"
        )
        return True
    except Exception as e:
        logger.error(f"Failed to save to MinIO: {e}")
        return False


def save_generated_json_objects_path(
    video_id: str,
    chunk_idx: int | str,
    json_type: Literal["timestamps", "image_insertions"] = "timestamps",
) -> None:
    path = create_path_to_save_notes(video_id)
    path = os.path.join(path, "partial")
    os.makedirs(path, exist_ok=True)
    file_path = os.path.join(path, f"{json_type}_chunk_{chunk_idx}.json")
    return file_path


def save_generated_json_objects(
    video_id: str,
    chunk_idx: int | str,
    data: dict,
    json_type: Literal["timestamps", "image_insertions"] = "timestamps",
    username: str = None,
    run_id: str = None,
) -> None:
    """Save generated JSON to MinIO (and local as fallback)."""
    json_string = json.dumps(data, indent=4)

    # Upload to MinIO if username provided
    if username:
        try:
            from app.services.storage_service import get_storage_service

            storage = get_storage_service()
            filename = f"partial/{json_type}_chunk_{chunk_idx}.json"
            storage.upload_notes(
                username=username,
                project_id=video_id,
                filename=filename,
                data=json_string,
                run_id=run_id,
                content_type="application/json",
            )
            logger.info(
                f"Generated {json_type} JSON uploaded to MinIO for chunk {chunk_idx}"
            )
            return
        except Exception as e:
            logger.warning(f"MinIO upload failed, falling back to local: {e}")

    # Fallback to local file
    file_path = save_generated_json_objects_path(video_id, chunk_idx, json_type)
    with open(file_path, "w") as file:
        file.write(json_string)
    logger.info(f"Generated {json_type} JSON saved locally at: {file_path}")


def read_generated_json_objects(
    video_id: str,
    chunk_idx: int | str,
    note_type: Literal["timestamps", "image_insertions"] = "timestamps",
) -> dict | None:
    path = create_path_to_save_notes(video_id)
    path = os.path.join(path, "partial")
    file_path = os.path.join(path, f"{note_type}_chunk_{chunk_idx}.json")
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
    username: str = None,
    run_id: str = None,
):
    """Check MinIO first for cached JSON, then local filesystem."""
    if refresh_json:
        return None

    filename = f"partial/{json_type}_chunk_{chunk_idx}.json"

    # Try MinIO first if username provided
    if username:
        try:
            from app.services.storage_service import get_storage_service, ARTIFACT_NOTES

            storage = get_storage_service()

            full_filename = f"{run_id}/{filename}" if run_id else filename

            if storage.file_exists(username, video_id, ARTIFACT_NOTES, full_filename):
                content = storage.download_file(
                    username, video_id, ARTIFACT_NOTES, filename, run_id=run_id
                )
                if content:
                    log_msg = f"Found cached {json_type.replace('_', ' ').title()} JSON in MinIO"
                    if chunk_idx is not None and total_chunks is not None:
                        log_msg += f" for chunk {chunk_idx}/{total_chunks}"
                    logger.info(log_msg)
                    return json.loads(
                        content.decode("utf-8")
                        if isinstance(content, bytes)
                        else content
                    )
        except Exception as e:
            logger.warning(f"MinIO cache check failed: {e}")

    # Fallback to local filesystem
    file_path = save_generated_json_objects_path(
        video_id=video_id, chunk_idx=chunk_idx, json_type=json_type
    )
    if os.path.exists(file_path):
        log_msg = f"Found cached {json_type.replace('_', ' ').title()} JSON locally at {file_path}"
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
