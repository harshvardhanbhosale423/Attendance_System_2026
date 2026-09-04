import csv
import io
from datetime import datetime

from flask import Blueprint, request, send_file, abort, Response
from flask_login import login_required, current_user

from models import db, Student, Subject, Division, Attendance, Teacher, TeacherSubject
from utils.helpers import roles_required

reports_bp = Blueprint("reports", __name__, url_prefix="/reports")


def _scope_query(base_query):
    """Restrict attendance query to what the logged-in role is allowed to see."""
    if current_user.role == "admin":
        return base_query
    if current_user.role == "teacher":
        teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
        allowed = TeacherSubject.query.filter_by(teacher_id=teacher.id).all()
        pairs = [(a.subject_id, a.division_id) for a in allowed]
        from sqlalchemy import or_, and_, false
        if not pairs:
            return base_query.filter(false())
        conditions = [and_(Attendance.subject_id == sid, Attendance.division_id == did) for sid, did in pairs]
        return base_query.filter(or_(*conditions))
    if current_user.role == "student":
        student = Student.query.filter_by(user_id=current_user.id).first_or_404()
        return base_query.filter(Attendance.student_id == student.id)
    abort(403)


def _filtered_records():
    query = Attendance.query
    student_id = request.args.get("student_id", type=int)
    subject_id = request.args.get("subject_id", type=int)
    division_id = request.args.get("division_id", type=int)
    date_str = request.args.get("date")
    month = request.args.get("month")  # format YYYY-MM

    if student_id:
        query = query.filter_by(student_id=student_id)
    if subject_id:
        query = query.filter_by(subject_id=subject_id)
    if division_id:
        query = query.filter_by(division_id=division_id)
    if date_str:
        try:
            d = datetime.strptime(date_str, "%Y-%m-%d").date()
            query = query.filter_by(date=d)
        except ValueError:
            pass
    if month:
        try:
            y, m = month.split("-")
            query = query.filter(db.extract("year", Attendance.date) == int(y))
            query = query.filter(db.extract("month", Attendance.date) == int(m))
        except ValueError:
            pass

    query = _scope_query(query)
    return query.order_by(Attendance.date.desc()).all()


@reports_bp.route("/export/csv")
@login_required
def export_csv():
    records = _filtered_records()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Date", "Student ID", "Student Name", "Roll No", "Division", "Subject", "Session", "Status"])
    for r in records:
        writer.writerow([
            r.date.isoformat(), r.student.student_code, r.student.full_name, r.student.roll_number,
            f"{r.division.class_group.name}-{r.division.name}", r.subject.name, r.session, r.status,
        ])
    buf.seek(0)
    return Response(
        buf.getvalue(), mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=attendance_report.csv"},
    )


@reports_bp.route("/export/excel")
@login_required
def export_excel():
    from openpyxl import Workbook
    records = _filtered_records()

    wb = Workbook()
    ws = wb.active
    ws.title = "Attendance Report"
    headers = ["Date", "Student ID", "Student Name", "Roll No", "Division", "Subject", "Session", "Status"]
    ws.append(headers)
    for r in records:
        ws.append([
            r.date.isoformat(), r.student.student_code, r.student.full_name, r.student.roll_number,
            f"{r.division.class_group.name}-{r.division.name}", r.subject.name, r.session, r.status,
        ])
    for col in ws.columns:
        max_len = max(len(str(c.value)) if c.value is not None else 0 for c in col)
        ws.column_dimensions[col[0].column_letter].width = max_len + 2

    out = io.BytesIO()
    wb.save(out)
    out.seek(0)
    return send_file(
        out, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True, download_name="attendance_report.xlsx",
    )


@reports_bp.route("/export/pdf")
@login_required
def export_pdf():
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet

    records = _filtered_records()
    out = io.BytesIO()
    doc = SimpleDocTemplate(out, pagesize=landscape(A4))
    styles = getSampleStyleSheet()
    elements = [Paragraph("Attendance Report", styles["Title"]), Spacer(1, 12)]

    data = [["Date", "Student ID", "Name", "Roll No", "Division", "Subject", "Session", "Status"]]
    for r in records:
        data.append([
            r.date.isoformat(), r.student.student_code, r.student.full_name, r.student.roll_number,
            f"{r.division.class_group.name}-{r.division.name}", r.subject.name, r.session, r.status.title(),
        ])

    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f4f6")]),
    ]))
    elements.append(table)
    doc.build(elements)
    out.seek(0)
    return send_file(out, mimetype="application/pdf", as_attachment=True, download_name="attendance_report.pdf")
