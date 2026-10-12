import os
from pathlib import Path
from dotenv import load_dotenv

# Resolve paths to allow loading .env regardless of working directory
BACKEND_DIR = Path(__file__).resolve().parent.parent
backend_env = BACKEND_DIR / ".env"
root_env = BACKEND_DIR.parent / ".env"

if backend_env.is_file():
    load_dotenv(dotenv_path=backend_env)
elif root_env.is_file():
    load_dotenv(dotenv_path=root_env)
else:
    load_dotenv()


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")

    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL") or "sqlite:///test.db"

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Amazon Cognito Configuration
    COGNITO_REGION = os.getenv("COGNITO_REGION") or os.getenv("AWS_REGION")
    COGNITO_USER_POOL_ID = os.getenv("COGNITO_USER_POOL_ID")
    COGNITO_APP_CLIENT_ID = os.getenv("COGNITO_APP_CLIENT_ID")
    COGNITO_JWKS_URL = os.getenv("COGNITO_JWKS_URL")  # Optional override for testing