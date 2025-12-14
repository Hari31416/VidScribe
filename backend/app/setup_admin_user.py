"""
Automated admin user setup script for Gen-BI backend.
Creates default admin user if none exists, using environment variables.
"""

from dotenv import load_dotenv
import os
import sys
from app.services.auth import create_user
from app.services.database.user_database import ROLE_ADMIN, list_all_users
from app.utils import create_simple_logger

logger = create_simple_logger(__name__)

load_dotenv()


def setup_admin_user() -> int:
    """
    Setup admin user if it doesn't exist.
    Uses ADMIN_USER_NAME and ADMIN_PASSWORD environment variables.

    Returns:
        int: Exit code (0 for success, 1 for failure)
    """
    logger.info("=== Admin User Setup Started ===")

    # Get credentials from environment variables
    admin_username = os.environ.get("ADMIN_USER_NAME", "admin")
    admin_password = os.environ.get("ADMIN_PASSWORD", "PassWord@1234")
    admin_email = os.environ.get("ADMIN_EMAIL", None)
    admin_full_name = os.environ.get("ADMIN_FULL_NAME", "System Administrator")

    try:
        # Check if admin users already exist
        users = list_all_users()
        admin_users = [u for u in users if u.get("role") == ROLE_ADMIN]

        if admin_users:
            admin_count = len(admin_users)
            admin_names = [u.get("username") for u in admin_users]
            logger.info(
                f"✅ Admin user(s) already exist: {', '.join(admin_names)} (total: {admin_count})"
            )
            logger.info("Skipping admin user creation")
            logger.info("=== Admin User Setup COMPLETED ===")
            return 0

        # Check if the specific admin user exists (by username)
        existing_user = next(
            (u for u in users if u.get("username") == admin_username), None
        )

        if existing_user:
            logger.info(f"✅ User '{admin_username}' already exists")
            if existing_user.get("role") != ROLE_ADMIN:
                logger.warning(
                    f"⚠️  User '{admin_username}' exists but is not an admin (role: {existing_user.get('role')})"
                )
            logger.info("=== Admin User Setup COMPLETED ===")
            return 0

        # Create admin user
        logger.info(f"Creating admin user: {admin_username}")
        user = create_user(
            username=admin_username,
            password=admin_password,
            email=admin_email,
            full_name=admin_full_name,
            role=ROLE_ADMIN,
            account_validity_days=None,  # Admin accounts never expire
        )

        logger.info("=" * 60)
        logger.info("✅ ADMIN USER CREATED SUCCESSFULLY")
        logger.info("=" * 60)
        logger.info(f"Username:    {user['username']}")
        logger.info(f"Email:       {user.get('email', 'Not provided')}")
        logger.info(f"Full Name:   {user.get('full_name', 'Not provided')}")
        logger.info(f"Role:        {user['role']}")
        logger.info(f"Created At:  {user['created_at']}")
        logger.info(f"Expires At:  {user.get('expires_at', 'Never')}")
        logger.info("=" * 60)
        logger.info("=== Admin User Setup COMPLETED ===")
        return 0

    except ValueError as e:
        logger.error(f"❌ Validation error creating admin user: {e}")
        logger.error("=== Admin User Setup FAILED ===")
        return 1
    except Exception as e:
        logger.error(f"❌ Failed to create admin user: {e}")
        logger.error("Please check your MongoDB connection and try again")
        logger.error("=== Admin User Setup FAILED ===")
        return 1


def main() -> int:
    """
    Main entry point for admin user setup.

    Returns:
        int: Exit code
    """
    # Check if we should skip admin user creation
    skip_admin_setup = os.environ.get("SKIP_ADMIN_SETUP", "False").lower() == "true"

    if skip_admin_setup:
        logger.info("SKIP_ADMIN_SETUP is set to True, skipping admin user setup")
        return 0

    return setup_admin_user()


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
