"""
Project Database Management using MongoDB.
Provides CRUD operations for project metadata with user isolation (per-user collections).
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import DuplicateKeyError
from pymongo.database import Database
from pymongo.collection import Collection

from app.env import MONGO_URI
from app.utils import create_simple_logger

logger = create_simple_logger(__name__)

# Database name
PROJECTS_DB_NAME = "vidscribe"


def get_projects_db_connection(mongo_uri: str = MONGO_URI):
    """Get MongoDB connection for projects database"""
    try:
        client = MongoClient(
            mongo_uri, authSource="admin", serverSelectionTimeoutMS=5000
        )
        db = client[PROJECTS_DB_NAME]

        # Test connection
        client.admin.command("ping")
        # logger.debug("Connected to MongoDB projects database successfully.")

        return client, db
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB projects database: {e}")
        raise e


def get_user_collection(db: Database, user_id: str) -> Collection:
    """
    Get the project collection for a specific user.
    Ensures indexes exist.
    """
    collection_name = f"projects_{user_id}"
    collection = db[collection_name]

    # Ensure indexes (idempotent, fast if already exist)
    # Unique index on project_id for this user's collection
    collection.create_index([("project_id", ASCENDING)], unique=True)
    # Index on created_at for sorting
    collection.create_index([("created_at", DESCENDING)])

    return collection


def create_project(
    user_id: str,
    project_id: str,
    name: Optional[str] = None,
    has_video: bool = False,
    has_transcript: bool = False,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Create a new project in MongoDB.
    """
    try:
        _, db = get_projects_db_connection()
        collection = get_user_collection(db, user_id)

        now = datetime.utcnow()
        project_doc = {
            "user_id": user_id,
            "project_id": project_id,
            "name": name or project_id,
            "created_at": now,
            "updated_at": now,
            "status": "pending",
            "has_video": has_video,
            "has_transcript": has_transcript,
            "has_notes": False,
            "current_run_id": None,  # ID of the latest/active run
            "runs": [],  # Array of run metadata
            "notes_files": {
                "final_notes_md": False,
                "final_notes_pdf": False,
                "summary_md": False,
                "summary_pdf": False,
            },
            "metadata": metadata or {},
        }

        result = collection.insert_one(project_doc)
        logger.info(
            f"Project '{project_id}' created for user '{user_id}' in collection '{collection.name}'"
        )

        # Return without _id for cleaner response
        project_doc.pop("_id", None)
        project_doc["created_at"] = project_doc["created_at"].isoformat()
        project_doc["updated_at"] = project_doc["updated_at"].isoformat()

        return project_doc

    except DuplicateKeyError:
        logger.warning(f"Project '{project_id}' already exists for user '{user_id}'")
        raise ValueError(f"Project '{project_id}' already exists")
    except Exception as e:
        logger.error(f"Error creating project '{project_id}': {e}")
        raise e


def get_project(user_id: str, project_id: str) -> Optional[Dict[str, Any]]:
    """
    Get a project by user_id and project_id.
    """
    try:
        _, db = get_projects_db_connection()
        collection = get_user_collection(db, user_id)

        project = collection.find_one({"project_id": project_id})

        if project:
            project.pop("_id", None)
            if isinstance(project.get("created_at"), datetime):
                project["created_at"] = project["created_at"].isoformat()
            if isinstance(project.get("updated_at"), datetime):
                project["updated_at"] = project["updated_at"].isoformat()
            return project

        return None
    except Exception as e:
        logger.error(f"Error fetching project '{project_id}': {e}")
        return None


def list_user_projects(
    user_id: str,
    limit: int = 50,
    skip: int = 0,
    status: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    List all projects for a user.
    """
    try:
        _, db = get_projects_db_connection()
        collection = get_user_collection(db, user_id)

        query: Dict[str, Any] = {}
        if status:
            query["status"] = status

        cursor = (
            collection.find(query, {"_id": 0})
            .sort("created_at", DESCENDING)
            .skip(skip)
            .limit(limit)
        )

        projects = []
        for project in cursor:
            if isinstance(project.get("created_at"), datetime):
                project["created_at"] = project["created_at"].isoformat()
            if isinstance(project.get("updated_at"), datetime):
                project["updated_at"] = project["updated_at"].isoformat()
            projects.append(project)

        return projects
    except Exception as e:
        logger.error(f"Error listing projects for user '{user_id}': {e}")
        return []


def update_project(
    user_id: str,
    project_id: str,
    updates: Dict[str, Any],
) -> bool:
    """
    Update a project's fields.
    """
    try:
        _, db = get_projects_db_connection()
        collection = get_user_collection(db, user_id)

        # Always update the updated_at timestamp
        updates["updated_at"] = datetime.utcnow()

        result = collection.update_one({"project_id": project_id}, {"$set": updates})

        if result.matched_count > 0:
            logger.info(f"Project '{project_id}' updated for user '{user_id}'")
            return True
        else:
            logger.warning(f"Project '{project_id}' not found for user '{user_id}'")
            return False
    except Exception as e:
        logger.error(f"Error updating project '{project_id}': {e}")
        return False


def update_project_status(
    user_id: str,
    project_id: str,
    status: str,
) -> bool:
    """
    Update project status.
    """
    return update_project(user_id, project_id, {"status": status})


def update_project_notes_status(
    user_id: str,
    project_id: str,
    notes_files: Dict[str, bool],
) -> bool:
    """
    Update project notes file availability.
    """
    # has_notes is true only if both final_notes.md and final_notes.pdf exist
    has_notes = notes_files.get("final_notes_md", False) and notes_files.get(
        "final_notes_pdf", False
    )

    return update_project(
        user_id,
        project_id,
        {"notes_files": notes_files, "has_notes": has_notes},
    )


def delete_project(user_id: str, project_id: str) -> bool:
    """
    Delete a project from MongoDB.
    """
    try:
        _, db = get_projects_db_connection()
        collection = get_user_collection(db, user_id)

        result = collection.delete_one({"project_id": project_id})

        if result.deleted_count > 0:
            logger.info(f"Project '{project_id}' deleted for user '{user_id}'")
            return True
        else:
            logger.warning(f"Project '{project_id}' not found for user '{user_id}'")
            return False
    except Exception as e:
        logger.error(f"Error deleting project '{project_id}': {e}")
        return False


def project_exists(user_id: str, project_id: str) -> bool:
    """Check if a project exists for a user."""
    try:
        _, db = get_projects_db_connection()
        collection = get_user_collection(db, user_id)
        count = collection.count_documents({"project_id": project_id})
        return count > 0
    except Exception as e:
        logger.error(f"Error checking project existence: {e}")
        return False


# =============================================================================
# Run Management (Notes Versioning)
# =============================================================================


def create_run(
    user_id: str,
    project_id: str,
    run_id: str,
    provider: str = "google",
    model: str = "gemini-2.0-flash",
    user_feedback: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a new run for a project (notes versioning).
    """
    try:
        _, db = get_projects_db_connection()
        collection = get_user_collection(db, user_id)

        now = datetime.utcnow()
        run_doc = {
            "run_id": run_id,
            "created_at": now,
            "status": "processing",  # processing, completed, failed
            "provider": provider,
            "model": model,
            "user_feedback": user_feedback,
            "notes_files": {
                "final_notes_md": False,
                "final_notes_pdf": False,
                "summary_md": False,
                "summary_pdf": False,
            },
        }

        # Add run to project's runs array and set as current
        result = collection.update_one(
            {"project_id": project_id},
            {
                "$push": {"runs": run_doc},
                "$set": {
                    "current_run_id": run_id,
                    "status": "processing",
                    "updated_at": now,
                },
            },
        )

        if result.matched_count > 0:
            logger.info(f"Created run '{run_id}' for project '{project_id}'")
            run_doc["created_at"] = run_doc["created_at"].isoformat()
            return run_doc
        else:
            raise ValueError(f"Project '{project_id}' not found")

    except Exception as e:
        logger.error(f"Error creating run: {e}")
        raise e


def update_run_status(
    user_id: str,
    project_id: str,
    run_id: str,
    status: str,
    notes_files: Optional[Dict[str, bool]] = None,
) -> bool:
    """
    Update a run's status and optionally notes files.
    """
    try:
        _, db = get_projects_db_connection()
        collection = get_user_collection(db, user_id)

        update_fields = {
            "runs.$.status": status,
            "updated_at": datetime.utcnow(),
        }

        if notes_files:
            update_fields["runs.$.notes_files"] = notes_files
            # Also update project-level notes_files if this is current run
            update_fields["notes_files"] = notes_files
            # Update has_notes
            has_notes = notes_files.get("final_notes_md", False) and notes_files.get(
                "final_notes_pdf", False
            )
            update_fields["has_notes"] = has_notes

        if status == "completed":
            update_fields["status"] = "completed"
        elif status == "failed":
            update_fields["status"] = "failed"

        result = collection.update_one(
            {
                "project_id": project_id,
                "runs.run_id": run_id,
            },
            {"$set": update_fields},
        )

        if result.matched_count > 0:
            logger.info(f"Updated run '{run_id}' status to '{status}'")
            return True
        return False

    except Exception as e:
        logger.error(f"Error updating run status: {e}")
        return False


def get_run(
    user_id: str,
    project_id: str,
    run_id: str,
) -> Optional[Dict[str, Any]]:
    """Get a specific run by ID."""
    try:
        project = get_project(user_id, project_id)
        if not project:
            return None

        for run in project.get("runs", []):
            if run.get("run_id") == run_id:
                return run
        return None
    except Exception as e:
        logger.error(f"Error getting run: {e}")
        return None


def list_runs(
    user_id: str,
    project_id: str,
) -> List[Dict[str, Any]]:
    """List all runs for a project."""
    try:
        project = get_project(user_id, project_id)
        if not project:
            return []
        return project.get("runs", [])
    except Exception as e:
        logger.error(f"Error listing runs: {e}")
        return []


def set_current_run(
    user_id: str,
    project_id: str,
    run_id: str,
) -> bool:
    """Set the current/active run for a project."""
    try:
        # Verify run exists
        run = get_run(user_id, project_id, run_id)
        if not run:
            return False

        _, db = get_projects_db_connection()
        collection = get_user_collection(db, user_id)

        result = collection.update_one(
            {"project_id": project_id},
            {
                "$set": {
                    "current_run_id": run_id,
                    "notes_files": run.get("notes_files", {}),
                    "has_notes": run.get("notes_files", {}).get("final_notes_md", False)
                    and run.get("notes_files", {}).get("final_notes_pdf", False),
                    "updated_at": datetime.utcnow(),
                }
            },
        )

        return result.matched_count > 0
    except Exception as e:
        logger.error(f"Error setting current run: {e}")
        return False
