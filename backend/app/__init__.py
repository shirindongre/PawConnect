from pathlib import Path
from flask import Flask
import os
from dotenv import load_dotenv

from .extensions import db, migrate

# Resolve backend and root directories for reliable .env loading
BACKEND_DIR = Path(__file__).resolve().parent.parent
backend_env = BACKEND_DIR / ".env"
root_env = BACKEND_DIR.parent / ".env"

if backend_env.is_file():
    load_dotenv(dotenv_path=backend_env)
elif root_env.is_file():
    load_dotenv(dotenv_path=root_env)
else:
    load_dotenv()

from .config import Config


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Validate that DATABASE_URL is set in production environment
    if os.getenv("APP_ENV") == "production" and not os.getenv("DATABASE_URL"):
        raise RuntimeError(
            "DATABASE_URL must be set in production environment."
        )

    db.init_app(app)
    # Enable foreign key constraints for SQLite (applies to all SQLite connections)
    from sqlalchemy import event
    from sqlalchemy.engine import Engine

    @event.listens_for(Engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    # Auto-create tables and seed default roles only in testing/development environments
    if app.config.get("TESTING") and app.config.get('SQLALCHEMY_DATABASE_URI', '').startswith('sqlite'):
        with app.app_context():
            db.create_all()
            # Seed default roles if they don't exist
            from .models.role import Role, RoleName
            if not Role.query.first():
                for role_name in RoleName.ALL_ROLES:
                    db.session.add(Role(role_name=role_name))
                db.session.commit()
    migrate.init_app(app, db, directory=str(BACKEND_DIR / "migrations"))

    # Register models with SQLAlchemy metadata
    from .models import (
        Role,
        User,
        NGO,
        Animal,
        RescueCase,
        AdoptionApplication,
        Donation,
        VolunteerApplication,
    )

    from .routes import api_bp
    app.register_blueprint(api_bp)

    # ---- CORS configuration ----
    # Enable CORS only when FRONTEND_ORIGIN env var is defined.
    # Local development uses the dev_server proxy, so no CORS needed.
    frontend_origins = os.getenv("FRONTEND_ORIGIN")
    if frontend_origins:
        origins = [o.strip() for o in frontend_origins.split(",") if o.strip()]
        try:
            from flask_cors import CORS
        except ImportError as e:
            raise ImportError(
                "Flask-CORS is required for CORS support. Add it to backend/requirements.txt and reinstall."
            ) from e
        CORS(app, resources={r"/api/*": {"origins": origins}})
    # End of CORS block

    @app.get("/api/health")
    def health_check():
        return {
            "status": "success",
            "message": "PawConnect backend is running"
        }, 200

    return app