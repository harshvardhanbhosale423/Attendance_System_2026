import os
from datetime import timedelta
from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))


def _bool(val, default=False):
    if val is None:
        return default
    return str(val).strip().lower() in ("1", "true", "yes", "on")


class Config:
    SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "dev-only-change-me")
    DEBUG = _bool(os.environ.get("FLASK_DEBUG"), False)

    # Defaults to sqlite so the app works immediately with zero setup.
    # For real college LAN deployment, set DB_ENGINE=mysql in .env and
    # configure MariaDB (see README section 4.2).
    DB_ENGINE = os.environ.get("DB_ENGINE", "sqlite").lower()

    if DB_ENGINE == "sqlite":
        SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(BASE_DIR, "database", "attendance.db")
    else:
        DB_USER = os.environ.get("DB_USER", "attendance_user")
        DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
        DB_HOST = os.environ.get("DB_HOST", "localhost")
        DB_PORT = os.environ.get("DB_PORT", "3306")
        DB_NAME = os.environ.get("DB_NAME", "attendance_system")
        SQLALCHEMY_DATABASE_URI = (
            f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"
        )

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    PERMANENT_SESSION_LIFETIME = timedelta(
        minutes=int(os.environ.get("SESSION_LIFETIME_MINUTES", 60))
    )
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    WTF_CSRF_ENABLED = True

    DEFAULT_WARNING_THRESHOLD = float(os.environ.get("ATTENDANCE_WARNING_THRESHOLD", 75))
    DEFAULT_CRITICAL_THRESHOLD = float(os.environ.get("ATTENDANCE_CRITICAL_THRESHOLD", 65))

    BACKUP_DIR = os.path.join(BASE_DIR, "backups")
    REPORTS_DIR = os.path.join(BASE_DIR, "reports")
