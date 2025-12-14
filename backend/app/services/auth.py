"""
Authentication Service for VidScribe Backend.
Provides JWT token-based authentication with RBAC (Role-Based Access Control).
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

from app.env import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES
from app.services.database.user_database import (
    get_user_from_db,
    create_user_in_db,
    user_exists,
    is_user_expired,
    is_admin,
    ROLE_USER,
    ROLE_ADMIN,
)

# OAuth2 scheme for token extraction
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

# Password context for hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# =============================================================================
# Pydantic Models for Auth
# =============================================================================


class Token(BaseModel):
    """JWT Token response model"""

    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    """Decoded token data"""

    username: Optional[str] = None


class UserResponse(BaseModel):
    """User response model (excludes password)"""

    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    role: str
    disabled: bool = False
    created_at: Optional[str] = None
    expires_at: Optional[str] = None


class UserCreate(BaseModel):
    """User creation request model"""

    username: str
    password: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    role: str = ROLE_USER
    account_validity_days: Optional[int] = None


class UserUpdate(BaseModel):
    """User update request model"""

    email: Optional[str] = None
    full_name: Optional[str] = None
    disabled: Optional[bool] = None
    role: Optional[str] = None


# =============================================================================
# Password Utilities
# =============================================================================


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hashed password"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password"""
    return pwd_context.hash(password)


# =============================================================================
# User Retrieval
# =============================================================================


def get_user(username: str) -> Optional[Dict[str, Any]]:
    """Get a user by username from MongoDB"""
    return get_user_from_db(username)


# =============================================================================
# Authentication
# =============================================================================


def authenticate_user(username: str, password: str) -> Optional[Dict[str, Any]]:
    """Authenticate a user with username and password"""
    user = get_user(username)
    if not user:
        return None
    if not verify_password(password, user["hashed_password"]):
        return None
    if user.get("disabled", False):
        return None
    # Check if account has expired
    if is_user_expired(user):
        return None
    return user


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode and verify a JWT token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


# =============================================================================
# FastAPI Dependencies
# =============================================================================


async def get_current_user(token: str = Depends(oauth2_scheme)) -> Dict[str, Any]:
    """
    FastAPI dependency to get the current authenticated user from JWT token.

    Raises:
        HTTPException: If token is invalid or user not found
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = decode_token(token)
    if payload is None:
        raise credentials_exception

    username: str = payload.get("sub")
    if username is None:
        raise credentials_exception

    user = get_user(username)
    if user is None:
        raise credentials_exception

    if user.get("disabled", False):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is disabled",
        )

    if is_user_expired(user):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account has expired",
        )

    return user


async def get_current_active_user(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    FastAPI dependency to get the current active (non-disabled) user.
    """
    if current_user.get("disabled", False):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user",
        )
    return current_user


async def require_admin(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    FastAPI dependency that requires the current user to be an admin.

    Raises:
        HTTPException: If user is not an admin
    """
    if not is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return current_user


# =============================================================================
# User Management
# =============================================================================


def create_user(
    username: str,
    password: str,
    email: Optional[str] = None,
    full_name: Optional[str] = None,
    role: str = ROLE_USER,
    account_validity_days: Optional[int] = None,
    max_token_limit_millions: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Create a new user in MongoDB.
    Returns the created user dict or raises ValueError if user exists.

    Args:
        username: Unique username
        password: Plain text password (will be hashed)
        email: User email (optional)
        full_name: User's full name (optional)
        role: User role (admin or user)
        account_validity_days: Number of days until account expires
        max_token_limit_millions: Maximum token limit in millions (-1 for unlimited)
    """
    # Validate username
    if not username or len(username) < 3:
        raise ValueError("Username must be at least 3 characters long")

    # Make sure that no spaces in username
    if " " in username:
        raise ValueError("Username cannot contain spaces")

    # Validate password
    if not password or len(password) < 6:
        raise ValueError("Password must be at least 6 characters long")

    # Hash password
    hashed_password = get_password_hash(password)

    # Create user in MongoDB (will raise ValueError if user exists)
    return create_user_in_db(
        username=username,
        hashed_password=hashed_password,
        email=email,
        full_name=full_name,
        disabled=False,
        role=role,
        account_validity_days=account_validity_days,
        max_token_limit_millions=max_token_limit_millions,
    )


def user_to_response(user: Dict[str, Any]) -> UserResponse:
    """Convert a user dict to a UserResponse model (excludes sensitive data)"""
    return UserResponse(
        username=user.get("username", ""),
        email=user.get("email"),
        full_name=user.get("full_name"),
        role=user.get("role", ROLE_USER),
        disabled=user.get("disabled", False),
        created_at=user.get("created_at"),
        expires_at=user.get("expires_at"),
    )
