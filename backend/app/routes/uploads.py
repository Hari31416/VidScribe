import json
import os
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.utils import create_simple_logger

router = APIRouter(prefix="/uploads", tags=["uploads"])

logger = create_simple_logger(__name__)

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
OUTPUTS_DIR = (BACKEND_ROOT / "outputs").resolve()
VIDEOS_DIR = (OUTPUTS_DIR / "videos").resolve()
TRANSCRIPTS_DIR = (OUTPUTS_DIR / "transcripts").resolve()

# Ensure directories exist
VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)


class UploadResponse(BaseModel):
    status: str
    video_id: str
    message: str
    video_path: Optional[str] = None
    transcript_path: Optional[str] = None


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

        # Validate and save transcript
        transcript_content = await transcript.read()
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

        # Validate transcript entries have required fields
        for idx, entry in enumerate(transcript_data):
            if not isinstance(entry, dict):
                video_path.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=400,
                    detail=f"Transcript entry {idx} must be a dictionary.",
                )
            if "text" not in entry:
                video_path.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=400,
                    detail=f"Transcript entry {idx} missing required 'text' field.",
                )
            # Ensure 'start' field exists (default to 0 if not present)
            if "start" not in entry:
                entry["start"] = 0.0
            # Ensure 'duration' field exists (default to 0 if not present)
            if "duration" not in entry:
                entry["duration"] = 0.0

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
