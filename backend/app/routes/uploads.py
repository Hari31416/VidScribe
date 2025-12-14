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


@router.post("/transcript-only", response_model=UploadResponse)
async def upload_transcript_only(
    transcript: UploadFile = File(
        ...,
        description="Transcript file in VTT, SRT, or JSON format",
    ),
    video_id: Optional[str] = Form(
        None,
        description="Optional custom video ID. If not provided, a random UUID will be generated.",
    ),
) -> UploadResponse:
    """
    Upload a transcript file only (no video required).

    This endpoint allows users to upload transcripts without a video file,
    enabling note generation without frame extraction and image integration.
    The system will skip all image-related processing when running the pipeline.

    Parameters
    ----------
    transcript : UploadFile
        The transcript file in VTT, SRT, or JSON format. JSON should follow
        YouTube transcript API format: [{"text": "...", "start": 0.0, "duration": 2.5}, ...]
    video_id : str, optional
        Custom video ID. If not provided, generates a random UUID prefixed with 'transcript_'

    Returns
    -------
    UploadResponse
        Contains status, generated video_id, and path to saved transcript
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
            # Generate a unique video_id with 'transcript_' prefix
            video_id = f"transcript_{uuid.uuid4().hex[:12]}"

        logger.info(f"Processing transcript-only upload for video_id: {video_id}")

        # Validate content type
        if transcript.content_type not in [
            "text/vtt",
            "application/x-subrip",
            "application/json",
        ]:
            raise HTTPException(
                status_code=400,
                detail="Unsupported file type. Only VTT, SRT, and JSON are allowed.",
            )

        file_extension = (
            ".vtt"
            if transcript.content_type == "text/vtt"
            else (
                ".srt" if transcript.content_type == "application/x-subrip" else ".json"
            )
        )

        # Validate and convert transcript
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
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid transcript JSON format: {str(e)}",
                ) from e

        # Validate transcript structure
        if not isinstance(transcript_data, list):
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
            message=f"Successfully uploaded transcript with ID: {video_id}. Note: No video uploaded - image integration will be skipped.",
            video_path=None,  # No video for transcript-only uploads
            transcript_path=str(transcript_path.resolve()),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to upload transcript: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to upload transcript: {str(e)}",
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

    notes_dir = OUTPUTS_DIR / "notes" / video_id
    has_notes = notes_dir.exists() and notes_dir.is_dir()

    return {
        "video_id": video_id,
        "video_exists": video_exists,
        "transcript_exists": transcript_exists,
        "video_files": video_files,
        "transcript_path": (
            str(transcript_path.relative_to(OUTPUTS_DIR)) if transcript_exists else None
        ),
        "transcript_only": transcript_exists and not video_exists,
        "ready_for_processing": transcript_exists,  # Transcript is sufficient for text-only processing
        "ready_for_processing_with_images": video_exists and transcript_exists,
        "has_notes": has_notes,
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
    List all uploaded video IDs (from both video directories and transcript files).

    Returns
    -------
    dict
        List of uploaded video IDs
    """
    try:
        video_ids_from_dirs = {d.name for d in VIDEOS_DIR.iterdir() if d.is_dir()}
        video_ids_from_transcripts = {
            f.stem
            for f in TRANSCRIPTS_DIR.iterdir()
            if f.is_file() and f.suffix == ".json"
        }

        all_ids = sorted(list(video_ids_from_dirs | video_ids_from_transcripts))

        return {"uploaded_video_ids": all_ids}
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
            # Check if it's a transcript-only project (no video/frames ever)
            # If so, we can't "delete storage" because there is none.
            # But return success to indicate "clean".
            return DeleteResponse(
                status="success",
                video_id=video_id,
                message=f"No video storage found specifically for {video_id} (might be transcript-only).",
                deleted_items={},
                space_freed_mb=0.0,
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


@router.delete("/project/{video_id}", response_model=DeleteResponse)
async def delete_project(video_id: str) -> DeleteResponse:
    """
    Delete EVERYTHING for a given project (Video, Frames, Transcript, Notes).

    Parameters
    ----------
    video_id : str
        The video ID to delete completely.

    Returns
    -------
    DeleteResponse
        Contains status and deleted items info.
    """
    try:
        # Define all paths
        video_dir = VIDEOS_DIR / video_id
        frames_dir = FRAMES_DIR / video_id
        transcript_path = TRANSCRIPTS_DIR / f"{video_id}.json"

        # We also need to find generated notes.
        # Typically in OUTPUTS_DIR/notes/{video_id} or similar?
        # Based on graph.nodes.utils logic, notes are in OUTPUTS_DIR/notes?
        # Let's assume standard structure: OUTPUTS_DIR/notes/{video_id}.md or folder.
        # Looking at previous logs: "Notes directory set at: .../backend/outputs/notes"
        notes_dir = OUTPUTS_DIR / "notes"
        # Notes might be a file {video_id}.md or a folder. Let's try finding both.
        note_file_md = notes_dir / f"{video_id}.md"
        note_file_json = notes_dir / f"{video_id}.json"  # If any

        total_size_mb = 0.0
        deleted_items = {}

        # 1. Delete Video Dir
        if video_dir.exists():
            size_mb = _get_directory_size(video_dir)
            total_size_mb += size_mb
            shutil.rmtree(video_dir)
            deleted_items["videos"] = True

        # 2. Delete Frames Dir
        if frames_dir.exists():
            size_mb = _get_directory_size(frames_dir)
            total_size_mb += size_mb
            shutil.rmtree(frames_dir)
            deleted_items["frames"] = True

        # 3. Delete Transcript
        if transcript_path.exists():
            total_size_mb += transcript_path.stat().st_size / (1024 * 1024)
            transcript_path.unlink()
            deleted_items["transcript"] = True

        # 4. Delete Notes
        if note_file_md.exists():
            total_size_mb += note_file_md.stat().st_size / (1024 * 1024)
            note_file_md.unlink()
            deleted_items["notes_md"] = True

        if note_file_json.exists():
            total_size_mb += note_file_json.stat().st_size / (1024 * 1024)
            note_file_json.unlink()
            deleted_items["notes_json"] = True

        return DeleteResponse(
            status="success",
            video_id=video_id,
            message=f"Successfully deleted all artifacts for video_id: {video_id}",
            deleted_items=deleted_items,
            space_freed_mb=round(total_size_mb, 2),
        )

    except Exception as e:
        logger.error(f"Failed to delete project {video_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete project: {str(e)}",
        ) from e


class StorageStatsResponse(BaseModel):
    video_id: str
    video_size_mb: float
    frames_size_mb: float
    transcript_size_mb: float
    notes_size_mb: float
    total_size_mb: float
    breakdown: dict[str, str]  # formatted strings e.g. "10.5 MB"


@router.get("/stats/{video_id}", response_model=StorageStatsResponse)
async def get_storage_stats(video_id: str) -> StorageStatsResponse:
    """
    Get storage usage statistics for a given project.

    Parameters
    ----------
    video_id : str
        The video ID to check

    Returns
    -------
    StorageStatsResponse
        Breakdown of storage usage by category
    """
    try:
        # Define paths
        video_dir = VIDEOS_DIR / video_id
        frames_dir = FRAMES_DIR / video_id
        transcript_path = TRANSCRIPTS_DIR / f"{video_id}.json"

        # Notes files
        notes_dir = OUTPUTS_DIR / "notes"
        note_file_md = notes_dir / f"{video_id}.md"
        note_file_json = notes_dir / f"{video_id}.json"

        # 1. Video Size
        video_size = 0.0
        if video_dir.exists():
            video_size = _get_directory_size(video_dir)

        # 2. Frames Size
        frames_size = 0.0
        if frames_dir.exists():
            frames_size = _get_directory_size(frames_dir)

        # 3. Transcript Size
        transcript_size = 0.0
        if transcript_path.exists():
            try:
                transcript_size = transcript_path.stat().st_size / (1024 * 1024)
            except Exception:
                pass

        # 4. Notes Size
        notes_size = 0.0
        notes_subdir = notes_dir / video_id
        if notes_subdir.exists() and notes_subdir.is_dir():
            notes_size += _get_directory_size(notes_subdir)

        # Fallback for old structure or legacy files
        if note_file_md.exists():
            notes_size += note_file_md.stat().st_size / (1024 * 1024)
        if note_file_json.exists():
            notes_size += note_file_json.stat().st_size / (1024 * 1024)

        total_size = video_size + frames_size + transcript_size + notes_size

        return StorageStatsResponse(
            video_id=video_id,
            video_size_mb=round(video_size, 2),
            frames_size_mb=round(frames_size, 2),
            transcript_size_mb=round(transcript_size, 2),
            notes_size_mb=round(notes_size, 2),
            total_size_mb=round(total_size, 2),
            breakdown={
                "Video": f"{video_size:.2f} MB",
                "Frames": f"{frames_size:.2f} MB",
                "Transcript": f"{transcript_size:.2f} MB",
                "Notes": f"{notes_size:.2f} MB",
            },
        )

    except Exception as e:
        logger.error(f"Failed to get storage stats for {video_id}: {e}", exc_info=True)
        # Return zeros on error to avoid crashing UI? Or raise?
        # Let's raise for now so frontend handles error state vs empty state
        raise HTTPException(
            status_code=500,
            detail=f"Failed to calculate storage stats: {str(e)}",
        ) from e

        # Also clean up any pdfs?
        # e.g. outputs/summary/{video_id}_summary.pdf
        # This is getting complicated to track all dispersed files.
        # But this covers the main ones.

        return DeleteResponse(
            status="success",
            video_id=video_id,
            message=f"Successfully deleted all artifacts for video_id: {video_id}",
            deleted_items=deleted_items,
            space_freed_mb=round(total_size_mb, 2),
        )

    except Exception as e:
        logger.error(f"Failed to delete project {video_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete project: {str(e)}",
        ) from e
