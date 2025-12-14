"""
Upload Routes for VidScribe Backend.
Provides endpoints for uploading videos, transcripts, and managing projects.
All endpoints require authentication.
"""

import json
import uuid
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.utils import create_simple_logger
from app.services.auth import get_current_user
from app.services.storage_service import (
    get_storage_service,
    ARTIFACT_VIDEOS,
    ARTIFACT_TRANSCRIPTS,
    ARTIFACT_FRAMES,
    ARTIFACT_NOTES,
)
from app.services.database.project_database import (
    create_project,
    get_project,
    list_user_projects,
    update_project,
    delete_project as delete_project_db,
    project_exists,
)
from app.services.transcript_conversion import (
    vtt_to_youtube_json,
    srt_to_youtube_json,
)

router = APIRouter(prefix="/uploads", tags=["uploads"])
logger = create_simple_logger(__name__)


# =============================================================================
# Response Models
# =============================================================================


class UploadResponse(BaseModel):
    status: str
    project_id: str
    message: str
    has_video: bool = False
    has_transcript: bool = False


class ProjectResponse(BaseModel):
    project_id: str
    name: str
    status: str
    has_video: bool
    has_transcript: bool
    has_notes: bool
    notes_files: Dict[str, bool]
    created_at: str
    updated_at: str
    current_run_id: Optional[str] = None


class ProjectListResponse(BaseModel):
    projects: List[ProjectResponse]
    total: int


class DeleteResponse(BaseModel):
    status: str
    project_id: str
    message: str
    deleted_items: Dict[str, bool]


# =============================================================================
# Helper Functions
# =============================================================================


def _generate_project_id(prefix: str = "proj") -> str:
    """Generate a unique project ID."""
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


async def _read_and_convert_transcript(transcript: UploadFile) -> list:
    """Read and convert transcript to YouTube JSON format."""
    content = await transcript.read()

    # Determine format from content type
    content_type = transcript.content_type or ""

    if "vtt" in content_type or (
        transcript.filename and transcript.filename.endswith(".vtt")
    ):
        return vtt_to_youtube_json(content.decode("utf-8"))
    elif "subrip" in content_type or (
        transcript.filename and transcript.filename.endswith(".srt")
    ):
        return srt_to_youtube_json(content.decode("utf-8"))
    else:
        # Assume JSON
        try:
            data = json.loads(content.decode("utf-8"))
            if not isinstance(data, list):
                raise ValueError("Transcript must be a JSON array")
            return data
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON format: {e}")


# =============================================================================
# Upload Endpoints
# =============================================================================


@router.post("/video-and-transcript", response_model=UploadResponse)
async def upload_video_and_transcript(
    video: UploadFile = File(..., description="Video file to upload"),
    transcript: UploadFile = File(
        ..., description="Transcript file (VTT, SRT, or JSON format)"
    ),
    project_name: Optional[str] = Form(
        None, description="Optional project display name"
    ),
    current_user: dict = Depends(get_current_user),
) -> UploadResponse:
    """
    Upload a video file and its corresponding transcript.
    Creates a new project in the user's storage.
    Project ID is always auto-generated (UUID-based).
    """
    username = current_user["username"]
    storage = get_storage_service()

    try:
        # Always generate a unique project_id (UUID-based)
        project_id = _generate_project_id("upload")
        display_name = project_name or project_id

        logger.info(
            f"User '{username}' creating project: {project_id} ('{display_name}')"
        )

        # Parse and validate transcript
        try:
            transcript_data = await _read_and_convert_transcript(transcript)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        # Upload video to MinIO
        video_content = await video.read()
        video_filename = video.filename or "video.mp4"
        storage.upload_video(
            username, project_id, video_content, filename=video_filename
        )

        # Upload transcript to MinIO
        transcript_json = json.dumps(transcript_data, ensure_ascii=False, indent=2)
        storage.upload_transcript(username, project_id, transcript_json)

        # Create project in MongoDB
        create_project(
            user_id=username,
            project_id=project_id,
            name=display_name,
            has_video=True,
            has_transcript=True,
        )

        return UploadResponse(
            status="success",
            project_id=project_id,
            message=f"Successfully uploaded video and transcript",
            has_video=True,
            has_transcript=True,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.post("/transcript-only", response_model=UploadResponse)
async def upload_transcript_only(
    transcript: UploadFile = File(
        ..., description="Transcript file (VTT, SRT, or JSON format)"
    ),
    project_name: Optional[str] = Form(
        None, description="Optional project display name"
    ),
    current_user: dict = Depends(get_current_user),
) -> UploadResponse:
    """
    Upload a transcript file only (no video required).
    Image integration will be skipped during pipeline processing.
    Project ID is always auto-generated (UUID-based).
    """
    username = current_user["username"]
    storage = get_storage_service()

    try:
        # Always generate a unique project_id (UUID-based)
        project_id = _generate_project_id("transcript")
        display_name = project_name or project_id

        logger.info(
            f"User '{username}' uploading transcript-only: {project_id} ('{display_name}')"
        )

        # Parse and validate transcript
        try:
            transcript_data = await _read_and_convert_transcript(transcript)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        # Upload transcript to MinIO
        transcript_json = json.dumps(transcript_data, ensure_ascii=False, indent=2)
        storage.upload_transcript(username, project_id, transcript_json)

        # Create project in MongoDB
        create_project(
            user_id=username,
            project_id=project_id,
            name=display_name,
            has_video=False,
            has_transcript=True,
        )

        return UploadResponse(
            status="success",
            project_id=project_id,
            message="Successfully uploaded transcript (no video - image integration will be skipped)",
            has_video=False,
            has_transcript=True,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


# =============================================================================
# Project Management Endpoints
# =============================================================================


@router.get("/check/{project_id}")
async def check_project(
    project_id: str,
    current_user: dict = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Check project status and file availability.
    """
    username = current_user["username"]
    storage = get_storage_service()

    project = get_project(username, project_id)
    if not project:
        raise HTTPException(
            status_code=404,
            detail=f"Project '{project_id}' not found",
        )

    # Get notes files status from storage using the current run_id
    current_run_id = project.get("current_run_id")
    notes_status = storage.get_notes_files_status(
        username, project_id, run_id=current_run_id
    )

    return {
        "project_id": project_id,
        "name": project.get("name", project_id),
        "status": project.get("status", "unknown"),
        "has_video": project.get("has_video", False),
        "has_transcript": project.get("has_transcript", False),
        "has_notes": notes_status.get("final_notes_md", False)
        and notes_status.get("final_notes_pdf", False),
        "notes_files": notes_status,
        "current_run_id": current_run_id,
        "ready_for_processing": project.get("has_transcript", False),
        "ready_for_processing_with_images": project.get("has_video", False)
        and project.get("has_transcript", False),
    }


@router.get("/list", response_model=ProjectListResponse)
async def list_projects(
    limit: int = 50,
    skip: int = 0,
    current_user: dict = Depends(get_current_user),
) -> ProjectListResponse:
    """
    List all projects for the current user.
    """
    username = current_user["username"]

    projects = list_user_projects(username, limit=limit, skip=skip)

    project_responses = []
    for p in projects:
        project_responses.append(
            ProjectResponse(
                project_id=p["project_id"],
                name=p.get("name", p["project_id"]),
                status=p.get("status", "unknown"),
                has_video=p.get("has_video", False),
                has_transcript=p.get("has_transcript", False),
                has_notes=p.get("has_notes", False),
                notes_files=p.get("notes_files", {}),
                created_at=p.get("created_at", ""),
                updated_at=p.get("updated_at", ""),
                current_run_id=p.get("current_run_id"),
            )
        )

    return ProjectListResponse(projects=project_responses, total=len(project_responses))


# =============================================================================
# Delete Endpoints
# =============================================================================


@router.delete("/videos/{project_id}", response_model=DeleteResponse)
async def delete_videos(
    project_id: str,
    current_user: dict = Depends(get_current_user),
) -> DeleteResponse:
    """Delete video files for a project."""
    username = current_user["username"]
    storage = get_storage_service()

    project = get_project(username, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    count = storage.delete_artifact_type(username, project_id, ARTIFACT_VIDEOS)
    update_project(username, project_id, {"has_video": False})

    return DeleteResponse(
        status="success",
        project_id=project_id,
        message=f"Deleted {count} video file(s)",
        deleted_items={"videos": count > 0},
    )


@router.delete("/frames/{project_id}", response_model=DeleteResponse)
async def delete_frames(
    project_id: str,
    current_user: dict = Depends(get_current_user),
) -> DeleteResponse:
    """Delete extracted frame images for a project."""
    username = current_user["username"]
    storage = get_storage_service()

    project = get_project(username, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    count = storage.delete_artifact_type(username, project_id, ARTIFACT_FRAMES)

    return DeleteResponse(
        status="success",
        project_id=project_id,
        message=f"Deleted {count} frame(s)",
        deleted_items={"frames": count > 0},
    )


@router.delete("/storage/{project_id}", response_model=DeleteResponse)
async def delete_storage(
    project_id: str,
    current_user: dict = Depends(get_current_user),
) -> DeleteResponse:
    """Delete video and frame files for a project (keeps transcript and notes)."""
    username = current_user["username"]
    storage = get_storage_service()

    project = get_project(username, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    videos_count = storage.delete_artifact_type(username, project_id, ARTIFACT_VIDEOS)
    frames_count = storage.delete_artifact_type(username, project_id, ARTIFACT_FRAMES)
    update_project(username, project_id, {"has_video": False})

    return DeleteResponse(
        status="success",
        project_id=project_id,
        message=f"Deleted {videos_count} video(s) and {frames_count} frame(s)",
        deleted_items={"videos": videos_count > 0, "frames": frames_count > 0},
    )


@router.delete("/project/{project_id}", response_model=DeleteResponse)
async def delete_project_completely(
    project_id: str,
    current_user: dict = Depends(get_current_user),
) -> DeleteResponse:
    """Delete entire project including all files and database record."""
    username = current_user["username"]
    storage = get_storage_service()

    project = get_project(username, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Delete all files from MinIO
    count = storage.delete_project_artifacts(username, project_id)

    # Delete from MongoDB
    delete_project_db(username, project_id)

    return DeleteResponse(
        status="success",
        project_id=project_id,
        message=f"Deleted project and {count} file(s)",
        deleted_items={
            "videos": True,
            "frames": True,
            "transcripts": True,
            "notes": True,
            "database": True,
        },
    )


# =============================================================================
# Storage Stats Endpoint
# =============================================================================


@router.get("/stats/{project_id}")
async def get_project_stats(
    project_id: str,
    current_user: dict = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get storage usage statistics for a project."""
    username = current_user["username"]
    storage = get_storage_service()

    project = get_project(username, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Get size information from storage service
    video_size = storage.get_artifact_size(username, project_id, ARTIFACT_VIDEOS)
    frames_size = storage.get_artifact_size(username, project_id, ARTIFACT_FRAMES)
    transcript_size = storage.get_artifact_size(
        username, project_id, ARTIFACT_TRANSCRIPTS
    )
    notes_size = storage.get_artifact_size(username, project_id, ARTIFACT_NOTES)

    total_size = video_size + frames_size + transcript_size + notes_size

    def format_size(size_bytes: int) -> str:
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / (1024 * 1024):.2f} MB"

    return {
        "project_id": project_id,
        "video_size_mb": round(video_size / (1024 * 1024), 2),
        "frames_size_mb": round(frames_size / (1024 * 1024), 2),
        "transcript_size_mb": round(transcript_size / (1024 * 1024), 2),
        "notes_size_mb": round(notes_size / (1024 * 1024), 2),
        "total_size_mb": round(total_size / (1024 * 1024), 2),
        "breakdown": {
            "Video": format_size(video_size),
            "Frames": format_size(frames_size),
            "Transcript": format_size(transcript_size),
            "Notes": format_size(notes_size),
            "Total": format_size(total_size),
        },
    }
