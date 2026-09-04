import traceback
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, session, current_app
from flask_login import login_user, logout_user, login_required, current_user
from models import db, User
from utils.helpers import log_action

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


def _role_home(role):
    return {
        "admin": "admin.dashboard",
        "teacher": "teacher.dashboard",
        "student": "student.dashboard",
    }.get(role, "auth.login")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for(_role_home(current_user.role)))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        try:
            user = User.query.filter_by(username=username).first()
        except Exception as exc:
            # Almost always means the database isn't reachable/initialized yet
            # (e.g. MariaDB not running). Show the real error on the page
            # itself so it's visible no matter what, plus log it fully.
            db.session.rollback()
            current_app.logger.error(
                "Login failed while querying the database:\n%s", traceback.format_exc()
            )
            flash(
                "Cannot reach the database. Technical detail: "
                f"{type(exc).__name__}: {exc}",
                "danger",
            )
            return render_template("auth/login.html")

        if user is None or not user.check_password(password):
            flash("Invalid username or password.", "danger")
            return render_template("auth/login.html")

        if not user.is_active_account:
            flash("This account has been deactivated. Contact the administrator.", "danger")
            return render_template("auth/login.html")

        try:
            login_user(user)
            session.permanent = True
            user.last_login_at = datetime.utcnow()
            log_action("login", entity_type="user", entity_id=user.id)
            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            current_app.logger.error(
                "Login failed while saving session/audit log:\n%s", traceback.format_exc()
            )
            flash(f"Login error. Technical detail: {type(exc).__name__}: {exc}", "danger")
            return render_template("auth/login.html")

        next_page = request.args.get("next")
        return redirect(next_page or url_for(_role_home(user.role)))

    return render_template("auth/login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    log_action("logout", entity_type="user", entity_id=current_user.id)
    db.session.commit()
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))
