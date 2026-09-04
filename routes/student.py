import calendar as pycal
from datetime import date, datetime

from flask import Blueprint, render_template, request
from flask_login import login_required, current_user

from models import db, Student, Attendance, Subject
from utils.helpers import roles_required, guard_blueprint_role, get_thresholds, attendance_status_label, compute_overall_percentage, compute_subject_wise

student_bp = Blueprint("student", __name__, url_prefix="/student")


@student_bp.before_request
def _guard():
    guard_blueprint_role("student")


def _current_student():
    return Student.query.filter_by(user_id=current_user.id).first_or_404()


@student_bp.route("/dashboard")
def dashboard():
    student = _current_student()
    overall_pct, present, total = compute_overall_percentage(student.id)
    subject_wise = compute_subject_wise(student.id)
    warning, critical = get_thresholds()

    for row in subject_wise:
        level, label = attendance_status_label(row["percentage"], warning, critical)
        row["level"] = level
        row["label"] = label

    overall_level, overall_label = attendance_status_label(overall_pct, warning, critical)

    recent = (
        Attendance.query.filter_by(student_id=student.id).order_by(Attendance.date.desc()).limit(10).all()
    )

    return render_template(
        "student/dashboard.html", student=student, overall_pct=overall_pct, present=present, total=total,
        subject_wise=subject_wise, overall_level=overall_level, overall_label=overall_label, recent=recent,
        warning=warning, critical=critical,
    )


@student_bp.route("/calendar")
def calendar_view():
    student = _current_student()
    today = date.today()
    year = request.args.get("year", type=int) or today.year
    month = request.args.get("month", type=int) or today.month

    first_weekday, days_in_month = pycal.monthrange(year, month)
    records = Attendance.query.filter(
        Attendance.student_id == student.id,
        db.extract("year", Attendance.date) == year,
        db.extract("month", Attendance.date) == month,
    ).all()

    by_day = {}
    for r in records:
        by_day.setdefault(r.date.day, []).append(r)

    day_summary = {}
    for day, recs in by_day.items():
        statuses = {r.status for r in recs}
        if "absent" in statuses:
            day_summary[day] = "absent"
        elif "leave" in statuses and "present" not in statuses:
            day_summary[day] = "leave"
        elif "present" in statuses:
            day_summary[day] = "present"
        else:
            day_summary[day] = "mixed"

    weeks = pycal.Calendar(firstweekday=6).monthdayscalendar(year, month)

    present_count = sum(1 for v in day_summary.values() if v == "present")
    absent_count = sum(1 for v in day_summary.values() if v == "absent")
    leave_count = sum(1 for v in day_summary.values() if v == "leave")

    prev_month = month - 1 or 12
    prev_year = year - 1 if month == 1 else year
    next_month = month + 1 if month < 12 else 1
    next_year = year + 1 if month == 12 else year

    return render_template(
        "student/calendar.html", weeks=weeks, month=month, year=year, day_summary=day_summary,
        by_day=by_day, month_name=pycal.month_name[month], present_count=present_count,
        absent_count=absent_count, leave_count=leave_count,
        prev_month=prev_month, prev_year=prev_year, next_month=next_month, next_year=next_year,
        today=today,
    )


@student_bp.route("/history")
def history():
    student = _current_student()
    subject_id = request.args.get("subject_id", type=int)
    date_str = request.args.get("date")
    status = request.args.get("status")

    query = Attendance.query.filter_by(student_id=student.id)
    if subject_id:
        query = query.filter_by(subject_id=subject_id)
    if date_str:
        try:
            d = datetime.strptime(date_str, "%Y-%m-%d").date()
            query = query.filter_by(date=d)
        except ValueError:
            pass
    if status:
        query = query.filter_by(status=status)

    records = query.order_by(Attendance.date.desc()).limit(300).all()
    subjects = Subject.query.filter_by(class_id=student.division.class_id).order_by(Subject.name).all()

    return render_template(
        "student/history.html", records=records, subjects=subjects,
        subject_id=subject_id, date_str=date_str, status=status,
    )
