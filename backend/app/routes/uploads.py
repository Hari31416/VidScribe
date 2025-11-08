import json
import os
import shutil
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.utils import create_simple_logger
from app.services.transcript_conversion import (
    vtt_to_youtube_json,
    srt_to_youtube_json,
)

router = APIRouter(prefix="/uploads", tags=["uploads"])

logger = create_simple_logger(__name__)

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
OUTPUTS_DIR = (BACKEND_ROOT / "outputs").resolve()
VIDEOS_DIR = (OUTPUTS_DIR / "videos").resolve()
TRANSCRIPTS_DIR = (OUTPUTS_DIR / "transcripts").resolve()
FRAMES_DIR = (OUTPUTS_DIR / "frames").resolve()

# Ensure directories exist
VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
FRAMES_DIR.mkdir(parents=True, exist_ok=True)


class UploadResponse(BaseModel):
    status: str
    video_id: str
    message: str
    video_path: Optional[str] = None
    transcript_path: Optional[str] = None


class DeleteResponse(BaseModel):
    status: str
    video_id: str
    message: str
    deleted_items: dict[str, bool]
    space_freed_mb: Optional[float] = None


@router.post("/video-and-transcript", response_model=UploadResponse)
async def upload_video_and_transcript(
    video: UploadFile = File(..., description="Video file to upload"),
    transcript: UploadFile = File(
        ...,
        description="Transcript file in JSON format (YouTube transcript API format)",
    ),
    video_id: Optional[str] = Form(
        None,
        description="Optional custom video ID. If not provided, a random UUID will be generated.",
    ),
) -> UploadResponse:
    """
    Upload a video file and its corresponding transcript.

    This endpoint allows users to upload their own video files along with
    transcripts, creating a dummy video_id that can be used with the existing
    API endpoints. The system will cache these files for future use.

    Parameters
    ----------
    video : UploadFile
        The video file to upload (supports common video formats)
    transcript : UploadFile
        The transcript file in JSON format. Should follow YouTube transcript API format:
        [{"text": "...", "start": 0.0, "duration": 2.5}, ...]
    video_id : str, optional
        Custom video ID. If not provided, generates a random UUID prefixed with 'upload_'

    Returns
    -------
    UploadResponse
        Contains status, generated video_id, and paths to saved files
    """
    try:
        # Generate or validate video_id
        if video_id:
            # Sanitize the provided video_id
            video_id = "".join(
                c for c in video_id if c.isalnum() or c in ("_", "-")
            ).strip()
            if not video_id:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid video_id. Must contain alphanumeric characters, underscores, or hyphens.",
                )
        else:
            # Generate a unique video_id with 'upload_' prefix
            video_id = f"upload_{uuid.uuid4().hex[:12]}"

        logger.info(f"Processing upload for video_id: {video_id}")

        # Create video directory for this upload
        video_dir = VIDEOS_DIR / video_id
        video_dir.mkdir(parents=True, exist_ok=True)

        # Save video file
        video_filename = video.filename or "video.mp4"
        # Sanitize filename
        video_filename = "".join(
            c for c in video_filename if c.isalnum() or c in ("_", "-", ".")
        )
        video_path = video_dir / video_filename

        # Check if video already exists
        if video_path.exists():
            logger.warning(f"Video file already exists at {video_path}. Overwriting...")

        # Write video file in chunks to handle large files
        chunk_size = 1024 * 1024  # 1MB chunks
        with open(video_path, "wb") as f:
            while chunk := await video.read(chunk_size):
                f.write(chunk)

        logger.info(f"Saved video to: {video_path}")

        if transcript.content_type not in [
            "text/vtt",
            "application/x-subrip",
            "application/json",
        ]:
            raise HTTPException(
                status_code=400,
                detail="Unsupported file type. Only VTT and SRT are allowed.",
            )

        file_extension = (
            ".vtt"
            if transcript.content_type == "text/vtt"
            else (
                ".srt" if transcript.content_type == "application/x-subrip" else ".json"
            )
        )

        # Validate and save transcript
        transcript_content = await transcript.read()
        if file_extension == ".vtt":
            logger.info("Converting VTT transcript to YouTube JSON format")
            transcript_data = vtt_to_youtube_json(transcript_content.decode("utf-8"))
        elif file_extension == ".srt":
            logger.info("Converting SRT transcript to YouTube JSON format")
            transcript_data = srt_to_youtube_json(transcript_content.decode("utf-8"))
        else:  # JSON
            try:
                transcript_data = json.loads(transcript_content.decode("utf-8"))
            except json.JSONDecodeError as e:
                # Clean up the video file if transcript is invalid
                video_path.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid transcript JSON format: {str(e)}",
                ) from e

        # Validate transcript structure
        if not isinstance(transcript_data, list):
            video_path.unlink(missing_ok=True)
            raise HTTPException(
                status_code=400,
                detail="Transcript must be a JSON array of transcript entries.",
            )

        # Save transcript in the expected location
        transcript_path = TRANSCRIPTS_DIR / f"{video_id}.json"
        with open(transcript_path, "w", encoding="utf-8") as f:
            json.dump(transcript_data, f, ensure_ascii=False, indent=4)

        logger.info(f"Saved transcript to: {transcript_path}")

        return UploadResponse(
            status="success",
            video_id=video_id,
            message=f"Successfully uploaded video and transcript with ID: {video_id}",
            video_path=str(video_path.resolve()),
            transcript_path=str(transcript_path.resolve()),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to upload video and transcript: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to upload files: {str(e)}",
        ) from e


@router.get("/check/{video_id}")
async def check_upload(video_id: str):
    """
    Check if a video and transcript exist for the given video_id.

    Parameters
    ----------
    video_id : str
        The video ID to check

    Returns
    -------
    dict
        Status of the video and transcript files
    """
    video_dir = VIDEOS_DIR / video_id
    transcript_path = TRANSCRIPTS_DIR / f"{video_id}.json"

    video_exists = video_dir.exists() and video_dir.is_dir()
    transcript_exists = transcript_path.exists() and transcript_path.is_file()

    video_files = []
    if video_exists:
        video_files = [
            str(f.relative_to(OUTPUTS_DIR)) for f in video_dir.iterdir() if f.is_file()
        ]

    return {
        "video_id": video_id,
        "video_exists": video_exists,
        "transcript_exists": transcript_exists,
        "video_files": video_files,
        "transcript_path": (
            str(transcript_path.relative_to(OUTPUTS_DIR)) if transcript_exists else None
        ),
        "ready_for_processing": video_exists and transcript_exists,
    }


def _get_directory_size(path: Path) -> float:
    """
    Calculate the total size of a directory in MB.

    Parameters
    ----------
    path : Path
        Directory path to calculate size for

    Returns
    -------
    float
        Size in megabytes
    """
    total_size = 0
    try:
        for item in path.rglob("*"):
            if item.is_file():
                total_size += item.stat().st_size
    except Exception as e:
        logger.warning(f"Error calculating size for {path}: {e}")
    return total_size / (1024 * 1024)  # Convert to MB


@router.get("/list")
async def list_uploads():
    """
    List all uploaded video IDs.

    Returns
    -------
    dict
        List of uploaded video IDs
    """
    try:
        video_ids = [d.name for d in VIDEOS_DIR.iterdir() if d.is_dir()]
        return {"uploaded_video_ids": video_ids}
    except Exception as e:
        logger.error(f"Failed to list uploads: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list uploads: {str(e)}",
        ) from e


@router.delete("/videos/{video_id}", response_model=DeleteResponse)
async def delete_video(video_id: str) -> DeleteResponse:
    """
    Delete video files for a given video_id.

    This endpoint removes all video files in the videos/{video_id} directory
    to free up storage space. The transcript and other generated files are preserved.

    Parameters
    ----------
    video_id : str
        The video ID whose video files should be deleted

    Returns
    -------
    DeleteResponse
        Contains status, video_id, and information about deleted items
    """
    try:
        video_dir = VIDEOS_DIR / video_id

        if not video_dir.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Video directory not found for video_id: {video_id}",
            )

        # Calculate size before deletion
        size_mb = _get_directory_size(video_dir)

        # Delete the video directory
        shutil.rmtree(video_dir)
        logger.info(f"Deleted video directory: {video_dir}")

        return DeleteResponse(
            status="success",
            video_id=video_id,
            message=f"Successfully deleted video files for video_id: {video_id}",
            deleted_items={"videos": True},
            space_freed_mb=round(size_mb, 2),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete video for {video_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete video files: {str(e)}",
        ) from e


@router.delete("/frames/{video_id}", response_model=DeleteResponse)
async def delete_frames(video_id: str) -> DeleteResponse:
    """
    Delete frame images for a given video_id.

    This endpoint removes all extracted frame images in the frames/{video_id} directory
    to free up storage space. The video and other generated files are preserved.

    Parameters
    ----------
    video_id : str
        The video ID whose frame images should be deleted

    Returns
    -------
    DeleteResponse
        Contains status, video_id, and information about deleted items
    """
    try:
        frames_dir = FRAMES_DIR / video_id

        if not frames_dir.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Frames directory not found for video_id: {video_id}",
            )

        # Calculate size before deletion
        size_mb = _get_directory_size(frames_dir)

        # Delete the frames directory
        shutil.rmtree(frames_dir)
        logger.info(f"Deleted frames directory: {frames_dir}")

        return DeleteResponse(
            status="success",
            video_id=video_id,
            message=f"Successfully deleted frame images for video_id: {video_id}",
            deleted_items={"frames": True},
            space_freed_mb=round(size_mb, 2),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete frames for {video_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete frame images: {str(e)}",
        ) from e


@router.delete("/storage/{video_id}", response_model=DeleteResponse)
async def delete_storage(video_id: str) -> DeleteResponse:
    """
    Delete both video files and frame images for a given video_id.

    This endpoint removes both the videos/{video_id} and frames/{video_id} directories
    to free up maximum storage space. The transcript and generated notes are preserved.

    Parameters
    ----------
    video_id : str
        The video ID whose video and frame files should be deleted

    Returns
    -------
    DeleteResponse
        Contains status, video_id, and information about deleted items
    """
    try:
        video_dir = VIDEOS_DIR / video_id
        frames_dir = FRAMES_DIR / video_id

        video_exists = video_dir.exists()
        frames_exists = frames_dir.exists()

        if not video_exists and not frames_exists:
            raise HTTPException(
                status_code=404,
                detail=f"No video or frames found for video_id: {video_id}",
            )

        total_size_mb = 0.0
        deleted_items = {}

        # Delete video directory if exists
        if video_exists:
            size_mb = _get_directory_size(video_dir)
            total_size_mb += size_mb
            shutil.rmtree(video_dir)
            deleted_items["videos"] = True
            logger.info(f"Deleted video directory: {video_dir}")
        else:
            deleted_items["videos"] = False

        # Delete frames directory if exists
        if frames_exists:
            size_mb = _get_directory_size(frames_dir)
            total_size_mb += size_mb
            shutil.rmtree(frames_dir)
            deleted_items["frames"] = True
            logger.info(f"Deleted frames directory: {frames_dir}")
        else:
            deleted_items["frames"] = False

        return DeleteResponse(
            status="success",
            video_id=video_id,
            message=f"Successfully deleted storage for video_id: {video_id}",
            deleted_items=deleted_items,
            space_freed_mb=round(total_size_mb, 2),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete storage for {video_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete storage: {str(e)}",
        ) from e
