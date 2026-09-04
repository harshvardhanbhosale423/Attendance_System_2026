from functools import wraps
from flask import abort, request
from flask_login import current_user
from models import db, AuditLog, Attendance, SystemSetting, get_setting


def roles_required(*roles):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if current_user.role not in roles:
                abort(403)
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def guard_blueprint_role(*roles):
    """Plain (non-decorator-stacked) check used as a blueprint before_request
    hook. Returns None to let the request continue, or aborts with 401/403.
    """
    if not current_user.is_authenticated:
        abort(401)
    if current_user.role not in roles:
        abort(403)


def log_action(action, entity_type=None, entity_id=None, details=None):
    entry = AuditLog(
        user_id=current_user.id if current_user.is_authenticated else None,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
    )
    db.session.add(entry)


def get_thresholds():
    warning = float(get_setting("warning_threshold", 75))
    critical = float(get_setting("critical_threshold", 65))
    return warning, critical


def attendance_status_label(percentage, warning, critical):
    if percentage < critical:
        return "critical", "Critical"
    if percentage < warning:
        return "warning", "Warning"
    return "normal", "Normal"


def compute_overall_percentage(student_id):
    total = Attendance.query.filter_by(student_id=student_id).filter(
        Attendance.status.in_(["present", "absent"])
    ).count()
    present = Attendance.query.filter_by(student_id=student_id, status="present").count()
    if total == 0:
        return 0.0, 0, 0
    return round(present * 100.0 / total, 1), present, total


def compute_subject_wise(student_id):
    """Returns list of dicts: subject, present, total, percentage"""
    from models import Subject
    rows = (
        db.session.query(
            Subject.id, Subject.name, Attendance.status
        )
        .join(Attendance, Attendance.subject_id == Subject.id)
        .filter(Attendance.student_id == student_id, Attendance.status.in_(["present", "absent"]))
        .all()
    )
    stats = {}
    for sid, sname, status in rows:
        if sid not in stats:
            stats[sid] = {"subject": sname, "present": 0, "total": 0}
        stats[sid]["total"] += 1
        if status == "present":
            stats[sid]["present"] += 1
    result = []
    for sid, data in stats.items():
        pct = round(data["present"] * 100.0 / data["total"], 1) if data["total"] else 0.0
        result.append({
            "subject_id": sid,
            "subject": data["subject"],
            "present": data["present"],
            "total": data["total"],
            "percentage": pct,
        })
    result.sort(key=lambda r: r["subject"])
    return result
