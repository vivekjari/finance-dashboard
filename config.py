"""Application configuration"""
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    """Base configuration"""
    # Database
    DATABASE_URL = os.getenv(
        "DATABASE_URL",
        "postgresql://localhost:5432/finance_dashboard"
    )
    DATABASE_HOST = os.getenv("DATABASE_HOST", "localhost")
    DATABASE_PORT = os.getenv("DATABASE_PORT", "5432")
    DATABASE_NAME = os.getenv("DATABASE_NAME", "finance_dashboard")
    DATABASE_USER = os.getenv("DATABASE_USER", "")
    DATABASE_PASSWORD = os.getenv("DATABASE_PASSWORD", "")
    
    # Google Sheets
    GOOGLE_SHEETS_URL = os.getenv("GOOGLE_SHEETS_URL")
    GOOGLE_AUTH_METHOD = os.getenv("GOOGLE_AUTH_METHOD", "oauth").lower()
    GOOGLE_SHEETS_JSON_KEY_PATH = os.getenv(
        "GOOGLE_SHEETS_JSON_KEY_PATH",
        "credentials/google_sheets_credentials.json"
    )
    GOOGLE_OAUTH_CLIENT_SECRET_PATH = os.getenv(
        "GOOGLE_OAUTH_CLIENT_SECRET_PATH",
        "credentials/google_oauth_client_secret.json"
    )
    GOOGLE_OAUTH_TOKEN_PATH = os.getenv(
        "GOOGLE_OAUTH_TOKEN_PATH",
        "credentials/google_oauth_token.json"
    )
    
    # API
    API_HOST = os.getenv("API_HOST", "127.0.0.1")
    API_PORT = int(os.getenv("API_PORT", "8000"))
    API_DEBUG = os.getenv("API_DEBUG", "True").lower() == "true"
    API_RELOAD = os.getenv("API_RELOAD", "True").lower() == "true"
    
    # Sync
    SYNC_INTERVAL_MINUTES = int(os.getenv("SYNC_INTERVAL_MINUTES", "60"))
    AUTO_SYNC_ON_STARTUP = os.getenv("AUTO_SYNC_ON_STARTUP", "True").lower() == "true"
    
    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

config = Config()
