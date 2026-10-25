"""
Configuration module for Text Processing Tool.
Defines base, development, and production configurations.
"""

import os
import secrets
from datetime import timedelta

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    """Base configuration with shared settings."""

    # --- Security ---
    SECRET_KEY = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600  # 1 hour

    # --- Database ---
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL") or \
        f"sqlite:///{os.path.join(BASE_DIR, 'text_tool.db')}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = False

    # --- Session ---
    PERMANENT_SESSION_LIFETIME = timedelta(hours=2)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    # --- File Uploads ---
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
    REPORTS_FOLDER = os.path.join(BASE_DIR, "reports")
    LOGS_FOLDER = os.path.join(BASE_DIR, "logs")
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024   # 5 MB max upload
    ALLOWED_EXTENSIONS = {"txt"}

    # --- Pagination ---
    ITEMS_PER_PAGE = 10

    # --- Logging ---
    LOG_FILE = os.path.join(BASE_DIR, "logs", "app.log")


class DevelopmentConfig(Config):
    """Development-specific settings."""
    DEBUG = True
    SQLALCHEMY_ECHO = False


class ProductionConfig(Config):
    """Production-specific settings."""
    DEBUG = False
    SESSION_COOKIE_SECURE = True  # Requires HTTPS


# Map string names to config classes
config_map = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
