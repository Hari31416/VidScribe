"""
Storage Service for VidScribe Backend.
Provides unified storage abstraction over MinIO with per-user bucket isolation.

Bucket Structure:
    {username}/                          # User bucket
      └── {project_id}/                  # Project folder
          ├── videos/                    # Video files
          ├── frames/                    # Extracted frames
          ├── transcripts/               # Transcript files
          └── notes/                     # Generated artifacts (MD, PDF)
"""

import tempfile
from pathlib import Path
from typing import Optional, List, Union

from app.env import S3_ENDPOINT_URL, S3_ACCESS_KEY, S3_SECRET_KEY, S3_USE_SSL
from app.services.object_storage import S3Storage
from app.utils import create_simple_logger

logger = create_simple_logger(__name__)

# Artifact type paths
ARTIFACT_VIDEOS = "videos"
ARTIFACT_FRAMES = "frames"
ARTIFACT_TRANSCRIPTS = "transcripts"
ARTIFACT_NOTES = "notes"

VALID_ARTIFACT_TYPES = [
    ARTIFACT_VIDEOS,
    ARTIFACT_FRAMES,
    ARTIFACT_TRANSCRIPTS,
    ARTIFACT_NOTES,
]


class StorageService:
    """
    Unified storage service for VidScribe with per-user bucket isolation.
    """

    def __init__(
        self,
        endpoint_url: Optional[str] = None,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        use_ssl: Optional[bool] = None,
    ):
        """
        Initialize storage service.

        Args:
            endpoint_url: MinIO/S3 endpoint URL
            access_key: S3 access key
            secret_key: S3 secret key
            use_ssl: Whether to use SSL
        """
        self.endpoint_url = endpoint_url or S3_ENDPOINT_URL
        self.access_key = access_key or S3_ACCESS_KEY
        self.secret_key = secret_key or S3_SECRET_KEY
        self.use_ssl = use_ssl if use_ssl is not None else S3_USE_SSL
        self._clients: dict[str, S3Storage] = {}

    def _sanitize_bucket_name(self, username: str) -> str:
        """
        Sanitize username to create a valid S3 bucket name.
        Bucket names must be 3-63 characters, lowercase, no underscores.
        """
        # Convert to lowercase and replace invalid characters
        bucket = username.lower().replace("_", "-").replace(" ", "-")
        # Prefix to ensure uniqueness and minimum length
        bucket = f"vidscribe-{bucket}"
        # Truncate if too long
        if len(bucket) > 63:
            bucket = bucket[:63]
        return bucket

    def _get_user_storage(self, username: str) -> S3Storage:
        """
        Get or create S3Storage client for a user's bucket.
        """
        bucket_name = self._sanitize_bucket_name(username)

        if bucket_name not in self._clients:
            logger.debug(f"Creating S3Storage client for bucket '{bucket_name}'")
            self._clients[bucket_name] = S3Storage(
                bucket=bucket_name,
                endpoint_url=self.endpoint_url,
                access_key=self.access_key,
                secret_key=self.secret_key,
                use_ssl=self.use_ssl,
            )

        return self._clients[bucket_name]

    def _get_object_key(
        self,
        project_id: str,
        artifact_type: str,
        filename: Optional[str] = None,
    ) -> str:
        """
        Build the S3 object key for an artifact.

        Format: {project_id}/{artifact_type}/{filename}
        """
        if artifact_type not in VALID_ARTIFACT_TYPES:
            raise ValueError(
                f"Invalid artifact type: {artifact_type}. "
                f"Must be one of: {VALID_ARTIFACT_TYPES}"
            )

        if filename:
            return f"{project_id}/{artifact_type}/{filename}"
        return f"{project_id}/{artifact_type}/"

    # =========================================================================
    # Upload Methods
    # =========================================================================

    def upload_video(
        self,
        username: str,
        project_id: str,
        file_data: Union[bytes, memoryview],
        filename: str = "video.mp4",
        content_type: str = "video/mp4",
    ) -> str:
        """
        Upload a video file to user's storage.

        Returns:
            S3 object key of the uploaded file
        """
        storage = self._get_user_storage(username)
        key = self._get_object_key(project_id, ARTIFACT_VIDEOS, filename)

        logger.info(f"Uploading video to '{key}' for user '{username}'")
        storage.write_bytes(key, file_data, content_type=content_type)
        return key

    def upload_transcript(
        self,
        username: str,
        project_id: str,
        data: Union[bytes, str],
        filename: str = "transcript.json",
    ) -> str:
        """
        Upload a transcript file to user's storage.

        Returns:
            S3 object key of the uploaded file
        """
        storage = self._get_user_storage(username)
        key = self._get_object_key(project_id, ARTIFACT_TRANSCRIPTS, filename)

        if isinstance(data, str):
            data = data.encode("utf-8")

        logger.info(f"Uploading transcript to '{key}' for user '{username}'")
        storage.write_bytes(key, data, content_type="application/json")
        return key

    def upload_frame(
        self,
        username: str,
        project_id: str,
        frame_name: str,
        data: Union[bytes, memoryview],
        content_type: str = "image/jpeg",
    ) -> str:
        """
        Upload an extracted frame to user's storage.

        Returns:
            S3 object key of the uploaded file
        """
        storage = self._get_user_storage(username)
        key = self._get_object_key(project_id, ARTIFACT_FRAMES, frame_name)

        logger.debug(f"Uploading frame to '{key}'")
        storage.write_bytes(key, data, content_type=content_type)
        return key

    def upload_notes(
        self,
        username: str,
        project_id: str,
        filename: str,
        data: Union[bytes, str],
        run_id: Optional[str] = None,
        content_type: Optional[str] = None,
    ) -> str:
        """
        Upload notes/PDF files to user's storage.
        If run_id is provided, stores in notes/{run_id}/ subfolder.

        Returns:
            S3 object key of the uploaded file
        """
        storage = self._get_user_storage(username)

        # Build key with optional run_id subfolder
        if run_id:
            key = f"{project_id}/{ARTIFACT_NOTES}/{run_id}/{filename}"
        else:
            key = self._get_object_key(project_id, ARTIFACT_NOTES, filename)

        if isinstance(data, str):
            data = data.encode("utf-8")

        # Determine content type from filename
        if content_type is None:
            if filename.endswith(".pdf"):
                content_type = "application/pdf"
            elif filename.endswith(".md"):
                content_type = "text/markdown"
            else:
                content_type = "application/octet-stream"

        logger.info(f"Uploading notes to '{key}' for user '{username}'")
        storage.write_bytes(key, data, content_type=content_type)
        return key

    def upload_file_from_path(
        self,
        username: str,
        project_id: str,
        artifact_type: str,
        local_path: str,
        remote_filename: Optional[str] = None,
    ) -> str:
        """
        Upload a local file to user's storage.

        Returns:
            S3 object key of the uploaded file
        """
        storage = self._get_user_storage(username)
        filename = remote_filename or Path(local_path).name
        key = self._get_object_key(project_id, artifact_type, filename)

        logger.info(f"Uploading file from '{local_path}' to '{key}'")
        storage.write_file(key, local_path)
        return key

    # =========================================================================
    # Download Methods
    # =========================================================================

    def download_file(
        self,
        username: str,
        project_id: str,
        artifact_type: str,
        filename: str,
        run_id: Optional[str] = None,
    ) -> bytes:
        """
        Download a file from user's storage.
        For notes, if run_id is provided, downloads from notes/{run_id}/ subfolder.

        Returns:
            File contents as bytes
        """
        storage = self._get_user_storage(username)

        # Handle versioned notes
        if artifact_type == ARTIFACT_NOTES and run_id:
            key = f"{project_id}/{ARTIFACT_NOTES}/{run_id}/{filename}"
        else:
            key = self._get_object_key(project_id, artifact_type, filename)

        logger.info(f"Downloading file '{key}' for user '{username}'")
        return storage.read_bytes(key)

    def download_file_to_path(
        self,
        username: str,
        project_id: str,
        artifact_type: str,
        filename: str,
        local_path: str,
    ) -> str:
        """
        Download a file to a local path.

        Returns:
            Local file path
        """
        storage = self._get_user_storage(username)
        key = self._get_object_key(project_id, artifact_type, filename)

        logger.info(f"Downloading '{key}' to '{local_path}'")
        storage.read_file(key, local_path)
        return local_path

    def download_to_temp(
        self,
        username: str,
        project_id: str,
        artifact_type: str,
        filename: str,
        suffix: Optional[str] = None,
    ) -> str:
        """
        Download a file to a temporary location.

        Returns:
            Path to temporary file (caller must cleanup)
        """
        if suffix is None:
            suffix = Path(filename).suffix

        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        temp_path = temp_file.name
        temp_file.close()

        return self.download_file_to_path(
            username, project_id, artifact_type, filename, temp_path
        )

    def get_transcript(self, username: str, project_id: str) -> Optional[bytes]:
        """
        Get transcript content for a project.

        Returns:
            Transcript bytes or None if not found
        """
        try:
            return self.download_file(
                username, project_id, ARTIFACT_TRANSCRIPTS, "transcript.json"
            )
        except Exception as e:
            logger.warning(f"Transcript not found for project '{project_id}': {e}")
            return None

    # =========================================================================
    # File Operations
    # =========================================================================

    def file_exists(
        self,
        username: str,
        project_id: str,
        artifact_type: str,
        filename: str,
        run_id: Optional[str] = None,
    ) -> bool:
        """Check if a file exists in user's storage."""
        storage = self._get_user_storage(username)

        # Handle versioned notes
        if artifact_type == ARTIFACT_NOTES and run_id:
            key = f"{project_id}/{ARTIFACT_NOTES}/{run_id}/{filename}"
        else:
            key = self._get_object_key(project_id, artifact_type, filename)

        return storage.exists(key)

    def list_files(
        self,
        username: str,
        project_id: str,
        artifact_type: str,
    ) -> List[str]:
        """
        List all files in a project's artifact folder.

        Returns:
            List of filenames (not full keys)
        """
        storage = self._get_user_storage(username)
        prefix = self._get_object_key(project_id, artifact_type)

        files = []
        for key in storage.list_files(prefix):
            # Extract just the filename from the full key
            filename = key.replace(prefix, "").lstrip("/")
            if filename:
                files.append(filename)

        return files

    def delete_file(
        self,
        username: str,
        project_id: str,
        artifact_type: str,
        filename: str,
    ) -> bool:
        """Delete a single file from user's storage."""
        try:
            storage = self._get_user_storage(username)
            key = self._get_object_key(project_id, artifact_type, filename)
            storage.delete_file(key)
            return True
        except Exception as e:
            logger.error(f"Failed to delete file '{filename}': {e}")
            return False

    def delete_artifact_type(
        self,
        username: str,
        project_id: str,
        artifact_type: str,
    ) -> int:
        """
        Delete all files of a specific artifact type for a project.

        Returns:
            Number of files deleted
        """
        storage = self._get_user_storage(username)
        prefix = self._get_object_key(project_id, artifact_type)
        return storage.delete_prefix(prefix)

    def delete_project_artifacts(
        self,
        username: str,
        project_id: str,
    ) -> int:
        """
        Delete all artifacts for a project.

        Returns:
            Total number of files deleted
        """
        storage = self._get_user_storage(username)
        prefix = f"{project_id}/"
        count = storage.delete_prefix(prefix)
        logger.info(f"Deleted {count} files for project '{project_id}'")
        return count

    # =========================================================================
    # Size Calculation
    # =========================================================================

    def get_artifact_size(
        self,
        username: str,
        project_id: str,
        artifact_type: str,
    ) -> int:
        """
        Get total size in bytes of all files in an artifact type folder.

        Returns:
            Total size in bytes
        """
        try:
            storage = self._get_user_storage(username)
            prefix = self._get_object_key(project_id, artifact_type)
            total_size = 0
            object_count = 0

            # Use list_objects_v2 with paginator for correct boto3 API
            paginator = storage.client.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=storage.bucket, Prefix=prefix):
                for obj in page.get("Contents", []):
                    total_size += obj.get("Size", 0)
                    object_count += 1

            logger.debug(
                f"get_artifact_size: bucket={storage.bucket}, prefix={prefix}, objects={object_count}, size={total_size}"
            )
            return total_size
        except Exception as e:
            logger.error(f"Failed to get artifact size for '{artifact_type}': {e}")
            return 0

    # =========================================================================
    # Notes File Status
    # =========================================================================

    def get_notes_files_status(
        self,
        username: str,
        project_id: str,
        run_id: Optional[str] = None,
    ) -> dict:
        """
        Check which notes files exist for a project/run.

        Returns:
            Dictionary with boolean status for each notes file
        """
        return {
            "final_notes_md": self.file_exists(
                username, project_id, ARTIFACT_NOTES, "final_notes.md", run_id
            ),
            "final_notes_pdf": self.file_exists(
                username, project_id, ARTIFACT_NOTES, "final_notes.pdf", run_id
            ),
            "summary_md": self.file_exists(
                username, project_id, ARTIFACT_NOTES, "summary.md", run_id
            ),
            "summary_pdf": self.file_exists(
                username, project_id, ARTIFACT_NOTES, "summary.pdf", run_id
            ),
        }

    def list_run_notes(
        self,
        username: str,
        project_id: str,
        run_id: str,
    ) -> List[str]:
        """
        List all notes files for a specific run.

        Returns:
            List of filenames in the run's notes folder
        """
        storage = self._get_user_storage(username)
        prefix = f"{project_id}/{ARTIFACT_NOTES}/{run_id}/"

        files = []
        for key in storage.list_files(prefix):
            filename = key.replace(prefix, "").lstrip("/")
            if filename:
                files.append(filename)

        return files


# Global instance for convenience
_storage_service: Optional[StorageService] = None


def get_storage_service() -> StorageService:
    """Get the global storage service instance."""
    global _storage_service
    if _storage_service is None:
        _storage_service = StorageService()
    return _storage_service
