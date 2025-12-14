"""
Environment configuration for VidScribe backend.
Centralized location for all environment variables.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# MongoDB Configuration
# =============================================================================
MONGO_URI = os.getenv("MONGO_URI", "mongodb://admin:password@localhost:27018")
DEFAULT_USERNAME = os.getenv("DEFAULT_USERNAME", "default")

# =============================================================================
# S3/MinIO Configuration
# =============================================================================
S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL", "http://localhost:9000")
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY", "minioadmin")
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY", "minioadmin")
S3_REGION = os.getenv("S3_REGION", "us-east-1")
S3_USE_SSL = os.getenv("S3_USE_SSL", "false").lower() == "true"

# =============================================================================
# Authentication Configuration
# =============================================================================
SECRET_KEY = os.getenv("SECRET_KEY", "your-super-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("TOKEN_EXPIRE_MINUTES", "1440"))  # 24 hours

# =============================================================================
# Admin User Configuration
# =============================================================================
ADMIN_USER_NAME = os.getenv("ADMIN_USER_NAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "PassWord@1234")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", None)
ADMIN_FULL_NAME = os.getenv("ADMIN_FULL_NAME", "System Administrator")
SKIP_ADMIN_SETUP = os.getenv("SKIP_ADMIN_SETUP", "false").lower() == "true"

# =============================================================================
# Logging Configuration
# =============================================================================
LOG_LEVEL = os.getenv("LOG_LEVEL", "warning").upper()
