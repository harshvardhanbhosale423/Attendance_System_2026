import os
import shutil
from datetime import datetime, date, timedelta

from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, send_file
from flask_login import login_required, current_user

from models import (
    db, User, Student, Teacher, ClassGroup, Division, Subject, AcademicYear,
    TeacherSubject, TeacherClass, Attendance, AuditLog, SystemSetting,
    get_setting, set_setting,
)
from utils.helpers import roles_required, guard_blueprint_role, log_action, get_thresholds, attendance_status_label

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.before_request
def _guard():
    guard_blueprint_role("admin")


# ---------------------------------------------------------------- dashboard
@admin_bp.route("/dashboard")
def dashboard():
    total_students = Student.query.filter_by(is_active_student=True).count()
    total_teachers = Teacher.query.filter_by(is_active_staff=True).count()
    total_subjects = Subject.query.count()
    total_divisions = Division.query.count()

    today = date.today()
    today_records = Attendance.query.filter_by(date=today).count()

    warning, critical = get_thresholds()
    students = Student.query.filter_by(is_active_student=True).all()
    low_attendance = []
    for s in students:
        total = Attendance.query.filter_by(student_id=s.id).filter(
            Attendance.status.in_(["present", "absent"])
        ).count()
        if total == 0:
            continue
        present = Attendance.query.filter_by(student_id=s.id, status="present").count()
        pct = round(present * 100.0 / total, 1)
        if pct < warning:
            level, label = attendance_status_label(pct, warning, critical)
            low_attendance.append({"student": s, "percentage": pct, "level": level, "label": label})
    low_attendance.sort(key=lambda r: r["percentage"])

    recent = (
        Attendance.query.order_by(Attendance.created_at.desc()).limit(10).all()
    )

    return render_template(
        "admin/dashboard.html",
        total_students=total_students,
        total_teachers=total_teachers,
        total_subjects=total_subjects,
        total_divisions=total_divisions,
        today_records=today_records,
        low_attendance=low_attendance[:10],
        recent=recent,
    )


# ---------------------------------------------------------------- students
@admin_bp.route("/students")
def students_list():
    q = request.args.get("q", "").strip()
    division_id = request.args.get("division_id", type=int)

    query = Student.query
    if q:
        like = f"%{q}%"
        query = query.filter(
            db.or_(Student.full_name.ilike(like), Student.roll_number.ilike(like), Student.student_code.ilike(like))
        )
    if division_id:
        query = query.filter_by(division_id=division_id)

    students = query.order_by(Student.full_name).all()
    divisions = Division.query.join(ClassGroup).order_by(ClassGroup.name, Division.name).all()
    return render_template("admin/students_list.html", students=students, divisions=divisions, q=q, division_id=division_id)


@admin_bp.route("/students/add", methods=["GET", "POST"])
def student_add():
    divisions = Division.query.join(ClassGroup).order_by(ClassGroup.name, Division.name).all()
    years = AcademicYear.query.order_by(AcademicYear.label.desc()).all()

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        student_code = request.form.get("student_code", "").strip()
        roll_number = request.form.get("roll_number", "").strip()
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip() or None
        division_id = request.form.get("division_id", type=int)
        academic_year_id = request.form.get("academic_year_id", type=int)
        password = request.form.get("password", "").strip() or "student123"

        errors = []
        if not full_name or not student_code or not roll_number or not username or not division_id or not academic_year_id:
            errors.append("Please fill in all required fields.")
        if User.query.filter_by(username=username).first():
            errors.append("Username already exists.")
        if Student.query.filter_by(student_code=student_code).first():
            errors.append("Student ID already exists.")
        if Student.query.filter_by(roll_number=roll_number, division_id=division_id).first():
            errors.append("Roll number already used in this division.")

        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("admin/student_form.html", divisions=divisions, years=years, form=request.form)

        user = User(username=username, email=email, role="student")
        user.set_password(password)
        db.session.add(user)
        db.session.flush()

        student = Student(
            user_id=user.id, student_code=student_code, roll_number=roll_number,
            full_name=full_name, division_id=division_id, academic_year_id=academic_year_id,
        )
        db.session.add(student)
        log_action("admin_change", "student", None, f"Created student {full_name} ({student_code})")
        db.session.commit()
        flash(f"Student '{full_name}' added. Temporary password: {password}", "success")
        return redirect(url_for("admin.students_list"))

    return render_template("admin/student_form.html", divisions=divisions, years=years, form={})


@admin_bp.route("/students/<int:student_id>/edit", methods=["GET", "POST"])
def student_edit(student_id):
    student = Student.query.get_or_404(student_id)
    divisions = Division.query.join(ClassGroup).order_by(ClassGroup.name, Division.name).all()
    years = AcademicYear.query.order_by(AcademicYear.label.desc()).all()

    if request.method == "POST":
        student.full_name = request.form.get("full_name", "").strip()
        student.roll_number = request.form.get("roll_number", "").strip()
        student.division_id = request.form.get("division_id", type=int)
        student.academic_year_id = request.form.get("academic_year_id", type=int)
        student.user.email = request.form.get("email", "").strip() or None
        log_action("admin_change", "student", student.id, "Edited student profile")
        db.session.commit()
        flash("Student updated.", "success")
        return redirect(url_for("admin.students_list"))

    return render_template("admin/student_form.html", divisions=divisions, years=years, student=student, form={})


@admin_bp.route("/students/<int:student_id>/view")
def student_view(student_id):
    student = Student.query.get_or_404(student_id)
    from utils.helpers import compute_overall_percentage, compute_subject_wise
    overall_pct, present, total = compute_overall_percentage(student.id)
    subject_wise = compute_subject_wise(student.id)
    return render_template(
        "admin/student_view.html", student=student, overall_pct=overall_pct,
        present=present, total=total, subject_wise=subject_wise,
    )


@admin_bp.route("/students/<int:student_id>/toggle", methods=["POST"])
def student_toggle(student_id):
    student = Student.query.get_or_404(student_id)
    student.is_active_student = not student.is_active_student
    student.user.is_active_account = student.is_active_student
    log_action("admin_change", "student", student.id, f"Set active={student.is_active_student}")
    db.session.commit()
    flash(f"Student {'activated' if student.is_active_student else 'deactivated'}. Attendance history preserved.", "info")
    return redirect(url_for("admin.students_list"))


# ---------------------------------------------------------------- teachers
@admin_bp.route("/teachers")
def teachers_list():
    teachers = Teacher.query.order_by(Teacher.full_name).all()
    return render_template("admin/teachers_list.html", teachers=teachers)


@admin_bp.route("/teachers/add", methods=["GET", "POST"])
def teacher_add():
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        employee_id = request.form.get("employee_id", "").strip()
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip() or None
        phone = request.form.get("phone", "").strip() or None
        password = request.form.get("password", "").strip() or "teacher123"

        errors = []
        if not full_name or not employee_id or not username:
            errors.append("Please fill in all required fields.")
        if User.query.filter_by(username=username).first():
            errors.append("Username already exists.")
        if Teacher.query.filter_by(employee_id=employee_id).first():
            errors.append("Employee ID already exists.")

        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("admin/teacher_form.html", form=request.form)

        user = User(username=username, email=email, role="teacher")
        user.set_password(password)
        db.session.add(user)
        db.session.flush()

        teacher = Teacher(user_id=user.id, employee_id=employee_id, full_name=full_name, phone=phone)
        db.session.add(teacher)
        log_action("admin_change", "teacher", None, f"Created teacher {full_name}")
        db.session.commit()
        flash(f"Teacher '{full_name}' added. Temporary password: {password}", "success")
        return redirect(url_for("admin.teachers_list"))

    return render_template("admin/teacher_form.html", form={})


@admin_bp.route("/teachers/<int:teacher_id>/toggle", methods=["POST"])
def teacher_toggle(teacher_id):
    teacher = Teacher.query.get_or_404(teacher_id)
    teacher.is_active_staff = not teacher.is_active_staff
    teacher.user.is_active_account = teacher.is_active_staff
    log_action("admin_change", "teacher", teacher.id, f"Set active={teacher.is_active_staff}")
    db.session.commit()
    flash(f"Teacher {'activated' if teacher.is_active_staff else 'deactivated'}.", "info")
    return redirect(url_for("admin.teachers_list"))


@admin_bp.route("/teachers/<int:teacher_id>/assign", methods=["GET", "POST"])
def teacher_assign(teacher_id):
    teacher = Teacher.query.get_or_404(teacher_id)
    subjects = Subject.query.join(ClassGroup).order_by(ClassGroup.name, Subject.name).all()
    divisions = Division.query.join(ClassGroup).order_by(ClassGroup.name, Division.name).all()

    if request.method == "POST":
        subject_id = request.form.get("subject_id", type=int)
        division_id = request.form.get("division_id", type=int)
        if subject_id and division_id:
            exists = TeacherSubject.query.filter_by(
                teacher_id=teacher.id, subject_id=subject_id, division_id=division_id
            ).first()
            if exists:
                flash("This assignment already exists.", "warning")
            else:
                db.session.add(TeacherSubject(teacher_id=teacher.id, subject_id=subject_id, division_id=division_id))
                log_action("admin_change", "teacher_subject", teacher.id, "Assigned subject/division")
                db.session.commit()
                flash("Assignment added.", "success")
        return redirect(url_for("admin.teacher_assign", teacher_id=teacher.id))

    return render_template("admin/teacher_assign.html", teacher=teacher, subjects=subjects, divisions=divisions)


@admin_bp.route("/teachers/assignments/<int:link_id>/remove", methods=["POST"])
def teacher_assignment_remove(link_id):
    link = TeacherSubject.query.get_or_404(link_id)
    teacher_id = link.teacher_id
    db.session.delete(link)
    log_action("admin_change", "teacher_subject", link_id, "Removed assignment")
    db.session.commit()
    flash("Assignment removed.", "info")
    return redirect(url_for("admin.teacher_assign", teacher_id=teacher_id))


# ---------------------------------------------------------------- classes / divisions / subjects
@admin_bp.route("/academics", methods=["GET", "POST"])
def academics():
    if request.method == "POST":
        form_type = request.form.get("form_type")
        if form_type == "class":
            name = request.form.get("class_name", "").strip()
            if name and not ClassGroup.query.filter_by(name=name).first():
                db.session.add(ClassGroup(name=name))
                db.session.commit()
                flash(f"Class '{name}' added.", "success")
            else:
                flash("Class name required and must be unique.", "danger")
        elif form_type == "division":
            name = request.form.get("division_name", "").strip()
            class_id = request.form.get("class_id", type=int)
            if name and class_id and not Division.query.filter_by(name=name, class_id=class_id).first():
                db.session.add(Division(name=name, class_id=class_id))
                db.session.commit()
                flash(f"Division '{name}' added.", "success")
            else:
                flash("Division name required and must be unique within the class.", "danger")
        elif form_type == "subject":
            name = request.form.get("subject_name", "").strip()
            code = request.form.get("subject_code", "").strip()
            class_id = request.form.get("class_id", type=int)
            if name and code and class_id and not Subject.query.filter_by(code=code).first():
                db.session.add(Subject(name=name, code=code, class_id=class_id))
                db.session.commit()
                flash(f"Subject '{name}' added.", "success")
            else:
                flash("Subject name/code required and code must be unique.", "danger")
        elif form_type == "year":
            label = request.form.get("year_label", "").strip()
            if label and not AcademicYear.query.filter_by(label=label).first():
                make_current = request.form.get("make_current") == "on"
                if make_current:
                    AcademicYear.query.update({AcademicYear.is_current: False})
                db.session.add(AcademicYear(label=label, is_current=make_current))
                db.session.commit()
                flash(f"Academic year '{label}' added.", "success")
            else:
                flash("Year label required and must be unique.", "danger")
        return redirect(url_for("admin.academics"))

    classes = ClassGroup.query.order_by(ClassGroup.name).all()
    divisions = Division.query.join(ClassGroup).order_by(ClassGroup.name, Division.name).all()
    subjects = Subject.query.join(ClassGroup).order_by(ClassGroup.name, Subject.name).all()
    years = AcademicYear.query.order_by(AcademicYear.label.desc()).all()
    return render_template(
        "admin/academics.html", classes=classes, divisions=divisions, subjects=subjects, years=years
    )


# ---------------------------------------------------------------- attendance / analytics view
@admin_bp.route("/attendance")
def attendance_view():
    division_id = request.args.get("division_id", type=int)
    subject_id = request.args.get("subject_id", type=int)
    date_str = request.args.get("date")
    status = request.args.get("status")

    query = Attendance.query
    if division_id:
        query = query.filter_by(division_id=division_id)
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
    divisions = Division.query.join(ClassGroup).order_by(ClassGroup.name, Division.name).all()
    subjects = Subject.query.order_by(Subject.name).all()

    return render_template(
        "admin/attendance_view.html", records=records, divisions=divisions, subjects=subjects,
        division_id=division_id, subject_id=subject_id, date_str=date_str, status=status,
    )


@admin_bp.route("/analytics")
def analytics():
    warning, critical = get_thresholds()
    subjects = Subject.query.order_by(Subject.name).all()
    subject_stats = []
    for subj in subjects:
        total = Attendance.query.filter_by(subject_id=subj.id).filter(
            Attendance.status.in_(["present", "absent"])
        ).count()
        present = Attendance.query.filter_by(subject_id=subj.id, status="present").count()
        pct = round(present * 100.0 / total, 1) if total else 0.0
        subject_stats.append({"subject": subj.name, "present": present, "total": total, "percentage": pct})

    divisions = Division.query.join(ClassGroup).order_by(ClassGroup.name, Division.name).all()
    division_stats = []
    for div in divisions:
        total = Attendance.query.filter_by(division_id=div.id).filter(
            Attendance.status.in_(["present", "absent"])
        ).count()
        present = Attendance.query.filter_by(division_id=div.id, status="present").count()
        pct = round(present * 100.0 / total, 1) if total else 0.0
        division_stats.append({"division": f"{div.class_group.name}-{div.name}", "percentage": pct, "total": total})

    return render_template(
        "admin/analytics.html", subject_stats=subject_stats, division_stats=division_stats,
        warning=warning, critical=critical,
    )


# ---------------------------------------------------------------- settings
@admin_bp.route("/settings", methods=["GET", "POST"])
def settings():
    if request.method == "POST":
        warning = request.form.get("warning_threshold", type=float)
        critical = request.form.get("critical_threshold", type=float)
        if warning is not None and critical is not None and critical < warning:
            set_setting("warning_threshold", warning)
            set_setting("critical_threshold", critical)
            log_action("admin_change", "settings", None, f"Thresholds set to warning={warning}, critical={critical}")
            db.session.commit()
            flash("Thresholds updated.", "success")
        else:
            flash("Critical threshold must be lower than warning threshold.", "danger")
        return redirect(url_for("admin.settings"))

    warning, critical = get_thresholds()
    return render_template("admin/settings.html", warning=warning, critical=critical)


# ---------------------------------------------------------------- backup
@admin_bp.route("/backup", methods=["GET", "POST"])
def backup():
    backup_dir = current_app.config["BACKUP_DIR"]
    os.makedirs(backup_dir, exist_ok=True)

    if request.method == "POST":
        uri = current_app.config["SQLALCHEMY_DATABASE_URI"]
        try:
            if uri.startswith("sqlite"):
                db_path = uri.replace("sqlite:///", "")
                stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                dest = os.path.join(backup_dir, f"attendance_backup_{stamp}.db")
                shutil.copyfile(db_path, dest)
                log_action("admin_change", "backup", None, f"Backup created: {os.path.basename(dest)}")
                db.session.commit()
                flash(f"Backup created: {os.path.basename(dest)}", "success")
            else:
                flash(
                    "For MariaDB/MySQL, run mysqldump from the server PC "
                    "(see README section 'How to create a backup') to export a .sql file into the backups/ folder.",
                    "info",
                )
        except Exception as exc:
            flash(f"Backup failed: {exc}", "danger")
        return redirect(url_for("admin.backup"))

    files = sorted(os.listdir(backup_dir), reverse=True) if os.path.isdir(backup_dir) else []
    return render_template("admin/backup.html", files=files)


@admin_bp.route("/backup/download/<path:filename>")
def backup_download(filename):
    backup_dir = current_app.config["BACKUP_DIR"]
    return send_file(os.path.join(backup_dir, filename), as_attachment=True)


# ---------------------------------------------------------------- audit log
@admin_bp.route("/audit-log")
def audit_log():
    logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(200).all()
    return render_template("admin/audit_log.html", logs=logs)


# ---------------------------------------------------------------- reports (admin can access all report types)
@admin_bp.route("/reports")
def reports():
    divisions = Division.query.join(ClassGroup).order_by(ClassGroup.name, Division.name).all()
    subjects = Subject.query.order_by(Subject.name).all()
    return render_template("admin/reports.html", divisions=divisions, subjects=subjects)
