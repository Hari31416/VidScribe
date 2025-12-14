"""
User Database Management using MongoDB
Provides CRUD operations for user authentication with RBAC and account expiry
"""

from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from pymongo import MongoClient, ASCENDING
from pymongo.errors import DuplicateKeyError
from app.env import MONGO_URI
from app.utils import create_simple_logger

logger = create_simple_logger(__name__)

# Database and collection names
AUTH_DB_NAME = "auth_db"
USERS_COLLECTION = "users"

# User roles
ROLE_ADMIN = "admin"
ROLE_USER = "user"
VALID_ROLES = [ROLE_ADMIN, ROLE_USER]

# Default account validity period (in days)
DEFAULT_ACCOUNT_VALIDITY_DAYS = 365  # 1 year
INDEFINITE_ACCOUNT_VALIDITY_DAYS = 7300  # 20 years (effectively indefinite)
NEVER_EXPIRES_SENTINEL = -1  # Use -1 to indicate account never expires

# Default token limit (in millions)
DEFAULT_TOKEN_LIMIT_MILLIONS = 10  # 10 million tokens
UNLIMITED_TOKEN_LIMIT = -1  # Use -1 to indicate unlimited tokens


def get_auth_db_connection(mongo_uri: str = MONGO_URI):
    """Get MongoDB connection for authentication database"""
    try:
        client = MongoClient(
            mongo_uri, authSource="admin", serverSelectionTimeoutMS=2000
        )
        db = client[AUTH_DB_NAME]

        # Test connection
        client.admin.command("ping")
        logger.debug("Connected to MongoDB authentication database successfully.")

        # Create unique index on username if it doesn't exist
        db[USERS_COLLECTION].create_index([("username", ASCENDING)], unique=True)

        return client, db
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB authentication database: {e}")
        raise e


def get_user_from_db(username: str) -> Optional[Dict[str, Any]]:
    """Get a user by username from MongoDB"""
    try:
        _, db = get_auth_db_connection()
        user = db[USERS_COLLECTION].find_one({"username": username})

        if user:
            # Remove MongoDB _id field from response
            user.pop("_id", None)
            logger.debug(f"User '{username}' found in database")
            if "created_at" in user and isinstance(user["created_at"], datetime):
                user["created_at"] = user["created_at"].isoformat()
            if "expires_at" in user and isinstance(user["expires_at"], datetime):
                user["expires_at"] = user["expires_at"].isoformat()
            return user

        logger.debug(f"User '{username}' not found in database")
        return None
    except Exception as e:
        logger.error(f"Error fetching user '{username}': {e}")
        return None


def create_user_in_db(
    username: str,
    hashed_password: str,
    email: Optional[str] = None,
    full_name: Optional[str] = None,
    disabled: bool = False,
    role: str = ROLE_USER,
    account_validity_days: Optional[int] = None,
    max_token_limit_millions: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Create a new user in MongoDB with role and expiry date
    Returns the created user dict or raises ValueError if user exists or invalid role

    Args:
        username: Unique username
        hashed_password: Bcrypt hashed password
        email: User email (optional)
        full_name: User's full name (optional)
        disabled: Whether account is disabled
        role: User role (admin or user)
        account_validity_days: Number of days until account expires (None uses default)
        max_token_limit_millions: Maximum token limit in millions (None uses default, -1 for unlimited)
    """
    try:
        _, db = get_auth_db_connection()

        # Validate role
        if role not in VALID_ROLES:
            raise ValueError(
                f"Invalid role '{role}'. Must be one of: {', '.join(VALID_ROLES)}"
            )

        # Calculate expiry date
        created_at = datetime.utcnow()

        # Admin accounts never expire
        if role == ROLE_ADMIN:
            account_validity_days = INDEFINITE_ACCOUNT_VALIDITY_DAYS
            expires_at = created_at + timedelta(days=account_validity_days)
        # Handle -1 as indefinite (20 years)
        elif account_validity_days == NEVER_EXPIRES_SENTINEL:
            account_validity_days = INDEFINITE_ACCOUNT_VALIDITY_DAYS
            expires_at = created_at + timedelta(days=account_validity_days)
        # Use provided or default validity
        else:
            if account_validity_days is None:
                account_validity_days = DEFAULT_ACCOUNT_VALIDITY_DAYS
            expires_at = created_at + timedelta(days=account_validity_days)

        # Set token limit (admins get unlimited by default)
        if role == ROLE_ADMIN:
            token_limit = UNLIMITED_TOKEN_LIMIT
        elif max_token_limit_millions is None:
            token_limit = DEFAULT_TOKEN_LIMIT_MILLIONS
        else:
            token_limit = max_token_limit_millions

        # Create user document
        user_doc = {
            "username": username,
            "hashed_password": hashed_password,
            "email": email or f"{username}@example.com",
            "full_name": full_name or username,
            "disabled": disabled,
            "role": role,
            "created_at": created_at,
            "expires_at": expires_at,
            "account_validity_days": account_validity_days,
            "max_token_limit_millions": token_limit,
        }

        # Insert user (unique index on username will prevent duplicates)
        result = db[USERS_COLLECTION].insert_one(user_doc)
        logger.info(
            f"User '{username}' created successfully with role '{role}', expiry {expires_at.strftime('%Y-%m-%d')}, token limit {token_limit}M"
        )

        # Return user without password and _id
        return {
            "username": user_doc["username"],
            "email": user_doc["email"],
            "full_name": user_doc["full_name"],
            "disabled": user_doc["disabled"],
            "role": user_doc["role"],
            "created_at": user_doc["created_at"].isoformat(),
            "expires_at": user_doc["expires_at"].isoformat(),
            "account_validity_days": user_doc["account_validity_days"],
            "max_token_limit_millions": user_doc["max_token_limit_millions"],
        }
    except DuplicateKeyError:
        logger.warning(f"Attempted to create duplicate user: {username}")
        raise ValueError(f"User '{username}' already exists")
    except Exception as e:
        logger.error(f"Error creating user '{username}': {e}")
        raise e


def update_user_in_db(username: str, update_fields: Dict[str, Any]) -> bool:
    """
    Update user fields in MongoDB
    Returns True if successful, False otherwise
    """
    try:
        _, db = get_auth_db_connection()

        # Remove fields that shouldn't be updated directly
        update_fields.pop("username", None)
        update_fields.pop("_id", None)

        result = db[USERS_COLLECTION].update_one(
            {"username": username}, {"$set": update_fields}
        )

        if result.matched_count > 0:
            logger.info(f"User '{username}' updated successfully")
            return True
        else:
            logger.warning(f"User '{username}' not found for update")
            return False
    except Exception as e:
        logger.error(f"Error updating user '{username}': {e}")
        return False


def delete_user_from_db(username: str) -> bool:
    """
    Delete a user from MongoDB
    Returns True if successful, False otherwise
    """
    try:
        _, db = get_auth_db_connection()

        result = db[USERS_COLLECTION].delete_one({"username": username})

        if result.deleted_count > 0:
            logger.info(f"User '{username}' deleted successfully")
            return True
        else:
            logger.warning(f"User '{username}' not found for deletion")
            return False
    except Exception as e:
        logger.error(f"Error deleting user '{username}': {e}")
        return False


def list_all_users() -> list:
    """
    Get all users from MongoDB (without passwords)
    Returns list of user dictionaries
    """
    try:
        _, db = get_auth_db_connection()

        users = list(
            db[USERS_COLLECTION].find(
                {}, {"_id": 0, "hashed_password": 0}  # Exclude _id and password
            )
        )

        # Convert datetime objects to ISO format strings
        for user in users:
            if "created_at" in user and isinstance(user["created_at"], datetime):
                user["created_at"] = user["created_at"].isoformat()
            if "expires_at" in user and isinstance(user["expires_at"], datetime):
                user["expires_at"] = user["expires_at"].isoformat()

        logger.debug(f"Retrieved {len(users)} users from database")
        return users
    except Exception as e:
        logger.error(f"Error listing users: {e}")
        return []


def user_exists(username: str) -> bool:
    """Check if a user exists in the database"""
    try:
        _, db = get_auth_db_connection()
        count = db[USERS_COLLECTION].count_documents({"username": username})
        return count > 0
    except Exception as e:
        logger.error(f"Error checking if user exists '{username}': {e}")
        return False


def is_user_expired(user: Dict[str, Any]) -> bool:
    """
    Check if a user account has expired

    Args:
        user: User dictionary from database

    Returns:
        True if account is expired, False otherwise
    """
    if "expires_at" not in user:
        return False

    expires_at = user["expires_at"]
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)

    return datetime.utcnow() > expires_at


def extend_user_expiry(username: str, additional_days: int) -> bool:
    """
    Extend a user's account expiry by additional days

    Args:
        username: Username to extend
        additional_days: Number of days to add to current expiry

    Returns:
        True if successful, False otherwise
    """
    try:
        _, db = get_auth_db_connection()

        user = db[USERS_COLLECTION].find_one({"username": username})
        if not user:
            logger.warning(f"User '{username}' not found for expiry extension")
            return False

        current_expiry = user.get("expires_at", datetime.utcnow())
        if isinstance(current_expiry, str):
            current_expiry = datetime.fromisoformat(current_expiry)

        # If already expired, extend from now, otherwise from current expiry
        if current_expiry < datetime.utcnow():
            new_expiry = datetime.utcnow() + timedelta(days=additional_days)
        else:
            new_expiry = current_expiry + timedelta(days=additional_days)

        result = db[USERS_COLLECTION].update_one(
            {"username": username}, {"$set": {"expires_at": new_expiry}}
        )

        if result.modified_count > 0:
            logger.info(
                f"Extended expiry for user '{username}' to {new_expiry.strftime('%Y-%m-%d')}"
            )
            return True
        return False
    except Exception as e:
        logger.error(f"Error extending expiry for user '{username}': {e}")
        return False


def set_user_expiry(username: str, expires_at: datetime) -> bool:
    """
    Set a specific expiry date for a user account

    Args:
        username: Username to update
        expires_at: New expiry datetime

    Returns:
        True if successful, False otherwise
    """
    try:
        _, db = get_auth_db_connection()

        result = db[USERS_COLLECTION].update_one(
            {"username": username}, {"$set": {"expires_at": expires_at}}
        )

        if result.modified_count > 0:
            logger.info(
                f"Set expiry for user '{username}' to {expires_at.strftime('%Y-%m-%d')}"
            )
            return True
        else:
            logger.warning(f"User '{username}' not found for setting expiry")
            return False
    except Exception as e:
        logger.error(f"Error setting expiry for user '{username}': {e}")
        return False


def is_admin(user: Dict[str, Any]) -> bool:
    """
    Check if a user has admin role

    Args:
        user: User dictionary from database

    Returns:
        True if user is admin, False otherwise
    """
    return user.get("role") == ROLE_ADMIN


def set_user_role(username: str, role: str) -> bool:
    """
    Set a user's role

    Args:
        username: Username to update
        role: New role (admin or user)

    Returns:
        True if successful, False otherwise
    """
    try:
        if role not in VALID_ROLES:
            logger.error(
                f"Invalid role '{role}'. Must be one of: {', '.join(VALID_ROLES)}"
            )
            return False

        _, db = get_auth_db_connection()

        result = db[USERS_COLLECTION].update_one(
            {"username": username}, {"$set": {"role": role}}
        )

        if result.modified_count > 0:
            logger.info(f"Set role for user '{username}' to '{role}'")
            return True
        else:
            logger.warning(f"User '{username}' not found for setting role")
            return False
    except Exception as e:
        logger.error(f"Error setting role for user '{username}': {e}")
        return False


def set_user_token_limit(username: str, max_token_limit_millions: float) -> bool:
    """
    Set a user's maximum token limit in millions

    Args:
        username: Username to update
        max_token_limit_millions: New token limit in millions (-1 for unlimited)

    Returns:
        True if successful, False otherwise
    """
    try:
        _, db = get_auth_db_connection()

        result = db[USERS_COLLECTION].update_one(
            {"username": username},
            {"$set": {"max_token_limit_millions": max_token_limit_millions}},
        )

        if result.modified_count > 0:
            limit_str = (
                "unlimited"
                if max_token_limit_millions == -1
                else f"{max_token_limit_millions}M"
            )
            logger.info(f"Set token limit for user '{username}' to {limit_str}")
            return True
        else:
            logger.warning(f"User '{username}' not found for setting token limit")
            return False
    except Exception as e:
        logger.error(f"Error setting token limit for user '{username}': {e}")
        return False
