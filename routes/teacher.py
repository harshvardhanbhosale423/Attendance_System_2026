from datetime import date, datetime

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

from models import db, Teacher, TeacherSubject, Division, Subject, Student, Attendance
from utils.helpers import roles_required, guard_blueprint_role, log_action, get_thresholds, attendance_status_label

teacher_bp = Blueprint("teacher", __name__, url_prefix="/teacher")


@teacher_bp.before_request
def _guard():
    guard_blueprint_role("teacher")


def _current_teacher():
    return Teacher.query.filter_by(user_id=current_user.id).first_or_404()


@teacher_bp.route("/dashboard")
def dashboard():
    teacher = _current_teacher()
    assignments = TeacherSubject.query.filter_by(teacher_id=teacher.id).all()

    today = date.today()
    today_done_pairs = set(
        (a.subject_id, a.division_id)
        for a in Attendance.query.filter_by(teacher_id=teacher.id, date=today).all()
    )
    total_assignments = len(assignments)
    completed_today = sum(1 for a in assignments if (a.subject_id, a.division_id) in today_done_pairs)
    pending_today = total_assignments - completed_today

    division_ids = {a.division_id for a in assignments}
    total_students = Student.query.filter(Student.division_id.in_(division_ids), Student.is_active_student == True).count() if division_ids else 0

    warning, critical = get_thresholds()
    low_attendance = []
    for div_id in division_ids:
        students = Student.query.filter_by(division_id=div_id, is_active_student=True).all()
        for s in students:
            total = Attendance.query.filter_by(student_id=s.id).filter(Attendance.status.in_(["present", "absent"])).count()
            if total == 0:
                continue
            present = Attendance.query.filter_by(student_id=s.id, status="present").count()
            pct = round(present * 100.0 / total, 1)
            if pct < warning:
                level, label = attendance_status_label(pct, warning, critical)
                low_attendance.append({"student": s, "percentage": pct, "level": level, "label": label})
    low_attendance.sort(key=lambda r: r["percentage"])

    recent = (
        Attendance.query.filter_by(teacher_id=teacher.id).order_by(Attendance.created_at.desc()).limit(10).all()
    )

    return render_template(
        "teacher/dashboard.html", teacher=teacher, assignments=assignments,
        completed_today=completed_today, pending_today=pending_today,
        total_students=total_students, low_attendance=low_attendance[:10], recent=recent,
    )


@teacher_bp.route("/attendance/take", methods=["GET", "POST"])
def take_attendance():
    teacher = _current_teacher()
    assignments = TeacherSubject.query.filter_by(teacher_id=teacher.id).all()

    subject_id = request.args.get("subject_id", type=int) or request.form.get("subject_id", type=int)
    division_id = request.args.get("division_id", type=int) or request.form.get("division_id", type=int)
    date_str = request.args.get("date") or request.form.get("date") or date.today().isoformat()
    session_label = request.args.get("session") or request.form.get("session") or "1"

    valid = any(a.subject_id == subject_id and a.division_id == division_id for a in assignments) if (subject_id and division_id) else False

    students = []
    existing = {}
    if valid:
        students = Student.query.filter_by(division_id=division_id, is_active_student=True).all()
        students.sort(key=lambda s: (int(s.roll_number) if s.roll_number.isdigit() else float("inf"), s.roll_number))
        try:
            att_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            att_date = date.today()
        rows = Attendance.query.filter_by(subject_id=subject_id, division_id=division_id, date=att_date, session=session_label).all()
        existing = {r.student_id: r.status for r in rows}

    if request.method == "POST" and valid:
        try:
            att_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            flash("Invalid date.", "danger")
            return redirect(url_for("teacher.take_attendance"))

        saved = 0
        for student in students:
            status = request.form.get(f"status_{student.id}")
            if status not in ("present", "absent", "leave"):
                continue
            record = Attendance.query.filter_by(
                student_id=student.id, subject_id=subject_id, date=att_date, session=session_label
            ).first()
            if record:
                if record.status != status:
                    record.status = status
                    log_action("attendance_update", "attendance", record.id, f"Changed to {status}")
            else:
                record = Attendance(
                    student_id=student.id, subject_id=subject_id, division_id=division_id,
                    teacher_id=teacher.id, date=att_date, session=session_label, status=status,
                )
                db.session.add(record)
                log_action("attendance_create", "attendance", None, f"{student.full_name} -> {status}")
            saved += 1

        db.session.commit()
        flash(f"Attendance saved for {saved} student(s).", "success")
        return redirect(url_for(
            "teacher.take_attendance", subject_id=subject_id, division_id=division_id,
            date=date_str, session=session_label
        ))

    return render_template(
        "teacher/take_attendance.html", assignments=assignments, students=students, existing=existing,
        subject_id=subject_id, division_id=division_id, date_str=date_str, session_label=session_label, valid=valid,
    )


@teacher_bp.route("/attendance/history")
def history():
    teacher = _current_teacher()
    assignments = TeacherSubject.query.filter_by(teacher_id=teacher.id).all()
    allowed_subject_ids = {a.subject_id for a in assignments}
    allowed_division_ids = {a.division_id for a in assignments}

    subject_id = request.args.get("subject_id", type=int)
    division_id = request.args.get("division_id", type=int)
    date_str = request.args.get("date")
    status = request.args.get("status")

    query = Attendance.query.filter(Attendance.teacher_id == teacher.id)
    if subject_id and subject_id in allowed_subject_ids:
        query = query.filter_by(subject_id=subject_id)
    if division_id and division_id in allowed_division_ids:
        query = query.filter_by(division_id=division_id)
    if date_str:
        try:
            d = datetime.strptime(date_str, "%Y-%m-%d").date()
            query = query.filter_by(date=d)
        except ValueError:
            pass
    if status:
        query = query.filter_by(status=status)

    records = query.order_by(Attendance.date.desc()).limit(300).all()
    return render_template(
        "teacher/history.html", records=records, assignments=assignments,
        subject_id=subject_id, division_id=division_id, date_str=date_str, status=status,
    )


@teacher_bp.route("/analytics")
def analytics():
    teacher = _current_teacher()
    assignments = TeacherSubject.query.filter_by(teacher_id=teacher.id).all()
    warning, critical = get_thresholds()

    stats = []
    for a in assignments:
        total = Attendance.query.filter_by(subject_id=a.subject_id, division_id=a.division_id).filter(
            Attendance.status.in_(["present", "absent"])
        ).count()
        present = Attendance.query.filter_by(subject_id=a.subject_id, division_id=a.division_id, status="present").count()
        pct = round(present * 100.0 / total, 1) if total else 0.0
        stats.append({
            "subject": a.subject.name, "division": f"{a.division.class_group.name}-{a.division.name}",
            "present": present, "total": total, "percentage": pct,
        })

    return render_template("teacher/analytics.html", stats=stats, warning=warning, critical=critical)
