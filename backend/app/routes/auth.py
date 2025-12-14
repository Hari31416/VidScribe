"""
Authentication Routes for VidScribe Backend.
Provides login, user management, and token validation endpoints.
"""

from datetime import timedelta
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.env import ACCESS_TOKEN_EXPIRE_MINUTES
from app.services.auth import (
    Token,
    UserResponse,
    UserCreate,
    UserUpdate,
    authenticate_user,
    create_access_token,
    create_user,
    get_current_user,
    require_admin,
    user_to_response,
)
from app.services.database.user_database import (
    list_all_users,
    delete_user_from_db,
    update_user_in_db,
)
from app.utils import create_simple_logger

router = APIRouter(prefix="/auth", tags=["auth"])
logger = create_simple_logger(__name__)


# =============================================================================
# Login Endpoint
# =============================================================================


@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Authenticate user and return JWT access token.
    
    Use form data with username and password fields.
    """
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        logger.warning(f"Failed login attempt for user: {form_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["username"]},
        expires_delta=access_token_expires,
    )

    logger.info(f"User '{form_data.username}' logged in successfully")
    return Token(access_token=access_token, token_type="bearer")


# =============================================================================
# Current User Endpoints
# =============================================================================


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_user)):
    """Get current authenticated user's profile."""
    return user_to_response(current_user)


# =============================================================================
# Admin User Management Endpoints
# =============================================================================


@router.get("/users", response_model=List[UserResponse])
async def list_users(admin_user: dict = Depends(require_admin)):
    """
    List all users (admin only).
    """
    users = list_all_users()
    return [user_to_response(user) for user in users]


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_new_user(
    user_data: UserCreate,
    admin_user: dict = Depends(require_admin),
):
    """
    Create a new user (admin only).

    Only administrators can create new user accounts.
    """
    try:
        new_user = create_user(
            username=user_data.username,
            password=user_data.password,
            email=user_data.email,
            full_name=user_data.full_name,
            role=user_data.role,
            account_validity_days=user_data.account_validity_days,
        )
        logger.info(
            f"Admin '{admin_user['username']}' created new user: {user_data.username}"
        )
        return user_to_response(new_user)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/users/{username}", response_model=UserResponse)
async def get_user_by_username(
    username: str,
    admin_user: dict = Depends(require_admin),
):
    """
    Get a specific user by username (admin only).
    """
    from app.services.auth import get_user

    user = get_user(username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User '{username}' not found",
        )
    return user_to_response(user)


@router.put("/users/{username}", response_model=UserResponse)
async def update_user(
    username: str,
    user_update: UserUpdate,
    admin_user: dict = Depends(require_admin),
):
    """
    Update a user (admin only).
    """
    from app.services.auth import get_user

    # Check if user exists
    user = get_user(username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User '{username}' not found",
        )

    # Build update dict from non-None fields
    update_fields = {}
    if user_update.email is not None:
        update_fields["email"] = user_update.email
    if user_update.full_name is not None:
        update_fields["full_name"] = user_update.full_name
    if user_update.disabled is not None:
        update_fields["disabled"] = user_update.disabled
    if user_update.role is not None:
        update_fields["role"] = user_update.role

    if not update_fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update",
        )

    success = update_user_in_db(username, update_fields)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user",
        )

    # Fetch updated user
    updated_user = get_user(username)
    logger.info(f"Admin '{admin_user['username']}' updated user: {username}")
    return user_to_response(updated_user)


@router.delete("/users/{username}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    username: str,
    admin_user: dict = Depends(require_admin),
):
    """
    Delete a user (admin only).
    
    Admins cannot delete their own account.
    """
    # Prevent self-deletion
    if username == admin_user["username"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account",
        )

    success = delete_user_from_db(username)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User '{username}' not found",
        )

    logger.info(f"Admin '{admin_user['username']}' deleted user: {username}")
    return None
