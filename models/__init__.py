from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class TimestampMixin:
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class User(UserMixin, db.Model, TimestampMixin):
    """Base account used for login. role decides which profile table applies."""
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=True, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # admin | teacher | student
    is_active_account = db.Column(db.Boolean, default=True, nullable=False)
    last_login_at = db.Column(db.DateTime, nullable=True)

    teacher = db.relationship("Teacher", backref="user", uselist=False, cascade="all, delete-orphan")
    student = db.relationship("Student", backref="user", uselist=False, cascade="all, delete-orphan")

    def set_password(self, raw_password):
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        return check_password_hash(self.password_hash, raw_password)

    # Flask-Login uses is_active
    @property
    def is_active(self):
        return self.is_active_account

    def display_name(self):
        if self.role == "teacher" and self.teacher:
            return self.teacher.full_name
        if self.role == "student" and self.student:
            return self.student.full_name
        return self.username


class AcademicYear(db.Model, TimestampMixin):
    __tablename__ = "academic_years"
    id = db.Column(db.Integer, primary_key=True)
    label = db.Column(db.String(20), unique=True, nullable=False)  # e.g. "2026-2027"
    is_current = db.Column(db.Boolean, default=False, nullable=False)


class ClassGroup(db.Model, TimestampMixin):
    """e.g. FY-CS, SY-CS, TY-CS"""
    __tablename__ = "classes"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)

    divisions = db.relationship("Division", backref="class_group", cascade="all, delete-orphan")


class Division(db.Model, TimestampMixin):
    __tablename__ = "divisions"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(10), nullable=False)  # A, B, C
    class_id = db.Column(db.Integer, db.ForeignKey("classes.id"), nullable=False)

    __table_args__ = (db.UniqueConstraint("name", "class_id", name="uq_division_per_class"),)

    students = db.relationship("Student", backref="division", lazy="dynamic")


class Subject(db.Model, TimestampMixin):
    __tablename__ = "subjects"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    code = db.Column(db.String(20), unique=True, nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey("classes.id"), nullable=False)

    class_group = db.relationship("ClassGroup")


class Teacher(db.Model, TimestampMixin):
    __tablename__ = "teachers"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, unique=True)
    employee_id = db.Column(db.String(30), unique=True, nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20), nullable=True)
    is_active_staff = db.Column(db.Boolean, default=True, nullable=False)

    subject_links = db.relationship("TeacherSubject", backref="teacher", cascade="all, delete-orphan")
    class_links = db.relationship("TeacherClass", backref="teacher", cascade="all, delete-orphan")


class TeacherSubject(db.Model, TimestampMixin):
    __tablename__ = "teacher_subjects"
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey("teachers.id"), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey("subjects.id"), nullable=False)
    division_id = db.Column(db.Integer, db.ForeignKey("divisions.id"), nullable=False)

    subject = db.relationship("Subject")
    division = db.relationship("Division")

    __table_args__ = (
        db.UniqueConstraint("teacher_id", "subject_id", "division_id", name="uq_teacher_subject_division"),
    )


class TeacherClass(db.Model, TimestampMixin):
    """Simple convenience mapping: which divisions a teacher is a class-in-charge/mentor for (optional)."""
    __tablename__ = "teacher_classes"
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey("teachers.id"), nullable=False)
    division_id = db.Column(db.Integer, db.ForeignKey("divisions.id"), nullable=False)

    division = db.relationship("Division")

    __table_args__ = (db.UniqueConstraint("teacher_id", "division_id", name="uq_teacher_division"),)


class Student(db.Model, TimestampMixin):
    __tablename__ = "students"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, unique=True)
    student_code = db.Column(db.String(30), unique=True, nullable=False)  # Student ID
    roll_number = db.Column(db.String(20), nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    division_id = db.Column(db.Integer, db.ForeignKey("divisions.id"), nullable=False)
    academic_year_id = db.Column(db.Integer, db.ForeignKey("academic_years.id"), nullable=False)
    is_active_student = db.Column(db.Boolean, default=True, nullable=False)  # deactivate, not delete

    academic_year = db.relationship("AcademicYear")

    __table_args__ = (
        db.UniqueConstraint("roll_number", "division_id", name="uq_roll_per_division"),
    )


class Attendance(db.Model, TimestampMixin):
    __tablename__ = "attendance"
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False, index=True)
    subject_id = db.Column(db.Integer, db.ForeignKey("subjects.id"), nullable=False, index=True)
    division_id = db.Column(db.Integer, db.ForeignKey("divisions.id"), nullable=False, index=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey("teachers.id"), nullable=False)
    date = db.Column(db.Date, nullable=False, index=True)
    session = db.Column(db.String(20), nullable=False, default="1")  # lecture/session number or slot
    status = db.Column(db.String(10), nullable=False)  # present | absent | leave

    student = db.relationship("Student")
    subject = db.relationship("Subject")
    division = db.relationship("Division")
    teacher = db.relationship("Teacher")

    __table_args__ = (
        db.UniqueConstraint(
            "student_id", "subject_id", "date", "session", name="uq_attendance_no_duplicate"
        ),
        db.CheckConstraint("status in ('present','absent','leave')", name="ck_attendance_status"),
    )


class AuditLog(db.Model):
    __tablename__ = "audit_logs"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    action = db.Column(db.String(50), nullable=False)  # login, attendance_create, attendance_update, admin_change...
    entity_type = db.Column(db.String(50), nullable=True)
    entity_id = db.Column(db.Integer, nullable=True)
    details = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    user = db.relationship("User")


class SystemSetting(db.Model):
    """Simple key-value settings store (attendance thresholds, etc.)."""
    __tablename__ = "system_settings"
    key = db.Column(db.String(50), primary_key=True)
    value = db.Column(db.String(255), nullable=False)


def get_setting(key, default=None):
    row = SystemSetting.query.get(key)
    return row.value if row else default


def set_setting(key, value):
    row = SystemSetting.query.get(key)
    if row:
        row.value = str(value)
    else:
        row = SystemSetting(key=key, value=str(value))
        db.session.add(row)
