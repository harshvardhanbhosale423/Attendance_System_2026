import os
import sys
import traceback
import click
from flask import Flask, redirect, url_for
from flask_login import LoginManager, current_user

from config import Config
from models import db, User, SystemSetting

from routes.auth import auth_bp
from routes.admin import admin_bp
from routes.teacher import teacher_bp
from routes.student import student_bp
from routes.reports import reports_bp
from routes.errors import register_error_handlers

login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "Please log in to access this page."
login_manager.login_message_category = "warning"


def _bootstrap_database(app):
    """
    Make sure the database has all tables and at least one admin account,
    every time the app starts. This means the app works immediately with
    just 'python app.py' - no separate 'flask init-db' / 'flask seed-demo'
    step is required. Safe to run every startup: it only creates things
    that don't already exist.
    """
    with app.app_context():
        db.create_all()

        if not SystemSetting.query.get("warning_threshold"):
            db.session.add(SystemSetting(
                key="warning_threshold", value=str(app.config["DEFAULT_WARNING_THRESHOLD"])
            ))
        if not SystemSetting.query.get("critical_threshold"):
            db.session.add(SystemSetting(
                key="critical_threshold", value=str(app.config["DEFAULT_CRITICAL_THRESHOLD"])
            ))
        db.session.commit()

        # If there is no admin account at all yet, create the default one so
        # the very first login always works. Change this password immediately
        # after logging in (Admin > Settings does not change your own login
        # password yet, so update it directly in Admin > Teachers/Students
        # style flows or contact your system administrator process).
        if User.query.filter_by(role="admin").count() == 0:
            admin_user = User(username="admin", email="admin@college.local", role="admin")
            admin_user.set_password("Admin@123")
            db.session.add(admin_user)
            db.session.commit()
            print("=" * 70)
            print("No admin account existed, so a default one was created:")
            print("   username: admin")
            print("   password: Admin@123")
            print("Please log in and change this password immediately.")
            print("=" * 70)


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    os.makedirs(os.path.join(os.path.dirname(__file__), "database"), exist_ok=True)
    os.makedirs(app.config["BACKUP_DIR"], exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(teacher_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(reports_bp)
    register_error_handlers(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    @app.route("/")
    def index():
        if current_user.is_authenticated:
            home = {"admin": "admin.dashboard", "teacher": "teacher.dashboard", "student": "student.dashboard"}
            return redirect(url_for(home.get(current_user.role, "auth.login")))
        return redirect(url_for("auth.login"))

    @app.context_processor
    def inject_globals():
        from datetime import datetime
        return {"current_year": datetime.utcnow().year, "app_name": "College Attendance System"}

    register_cli(app)

    try:
        _bootstrap_database(app)
    except Exception:
        print("=" * 70)
        print("STARTUP ERROR: could not set up the database.")
        print("This is almost always one of:")
        print("  - MariaDB/MySQL is not running (if DB_ENGINE=mysql in .env)")
        print("  - The database/user/password in .env don't match a real DB")
        print("  - The 'database' folder could not be created/written to")
        print("Full technical error below:")
        traceback.print_exc()
        print("=" * 70)
        sys.stdout.flush()

    return app


def register_cli(app):
    @app.cli.command("init-db")
    def init_db():
        """Create all database tables (also runs automatically on startup)."""
        _bootstrap_database(app)
        click.echo("Database initialized.")

    @app.cli.command("seed-demo")
    def seed_demo():
        """Populate demo data: admin, teachers, students, classes, subjects, attendance."""
        from services.seed import run_seed
        with app.app_context():
            run_seed()
        click.echo("Demo data created. See README for demo credentials.")


if __name__ == "__main__":
    app = create_app()
    host = os.environ.get("SERVER_HOST", "0.0.0.0")
    port = int(os.environ.get("SERVER_PORT", 5000))
    app.run(host=host, port=port, debug=app.config["DEBUG"])
