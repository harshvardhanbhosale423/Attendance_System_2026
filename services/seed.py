"""
Populate optional demo/sample data so the system can be explored immediately.
DEMO DATA ONLY - all names are fictional. Change all demo passwords before
using this system with real students, teachers, or attendance data.
"""
import random
from datetime import date, timedelta

from models import (
    db, User, AcademicYear, ClassGroup, Division, Subject, Teacher,
    Student, TeacherSubject, Attendance, SystemSetting,
)


def _get_or_create_setting(key, value):
    if not SystemSetting.query.get(key):
        db.session.add(SystemSetting(key=key, value=str(value)))


def run_seed():
    db.create_all()
    _get_or_create_setting("warning_threshold", 75)
    _get_or_create_setting("critical_threshold", 65)

    # ---- Academic year
    year = AcademicYear.query.filter_by(label="2026-2027").first()
    if not year:
        year = AcademicYear(label="2026-2027", is_current=True)
        db.session.add(year)
        db.session.flush()

    # ---- Admin account
    if not User.query.filter_by(username="admin").first():
        admin = User(username="admin", email="admin@college.local", role="admin")
        admin.set_password("Admin@123")
        db.session.add(admin)

    # ---- Classes & Divisions
    class_names = ["FY-CS", "SY-CS"]
    classes = {}
    for cname in class_names:
        c = ClassGroup.query.filter_by(name=cname).first()
        if not c:
            c = ClassGroup(name=cname)
            db.session.add(c)
            db.session.flush()
        classes[cname] = c

    divisions = {}
    for cname, c in classes.items():
        for dname in ["A", "B"]:
            d = Division.query.filter_by(name=dname, class_id=c.id).first()
            if not d:
                d = Division(name=dname, class_id=c.id)
                db.session.add(d)
                db.session.flush()
            divisions[f"{cname}-{dname}"] = d

    # ---- Subjects (per class)
    subject_defs = [
        ("Database Systems", "DB101"),
        ("Mathematics", "MA101"),
        ("Programming Fundamentals", "PR101"),
    ]
    subjects = {}
    for cname, c in classes.items():
        for sname, base_code in subject_defs:
            code = f"{base_code}-{cname}"
            s = Subject.query.filter_by(code=code).first()
            if not s:
                s = Subject(name=sname, code=code, class_id=c.id)
                db.session.add(s)
                db.session.flush()
            subjects[(cname, sname)] = s

    db.session.flush()

    # ---- Teachers
    teacher_defs = [
        ("T001", "Anita Sharma", "anita.sharma"),
        ("T002", "Ravi Kulkarni", "ravi.kulkarni"),
        ("T003", "Neha Joshi", "neha.joshi"),
    ]
    teachers = []
    for emp_id, name, username in teacher_defs:
        t = Teacher.query.filter_by(employee_id=emp_id).first()
        if not t:
            u = User(username=username, email=f"{username}@college.local", role="teacher")
            u.set_password("Teacher@123")
            db.session.add(u)
            db.session.flush()
            t = Teacher(user_id=u.id, employee_id=emp_id, full_name=name)
            db.session.add(t)
            db.session.flush()
        teachers.append(t)

    db.session.flush()

    # Assign: each teacher teaches one subject across both divisions of FY-CS, and SY-CS for variety
    assignment_plan = [
        (teachers[0], "Database Systems"),
        (teachers[1], "Mathematics"),
        (teachers[2], "Programming Fundamentals"),
    ]
    for teacher, subject_name in assignment_plan:
        for cname in class_names:
            subj = subjects[(cname, subject_name)]
            for dname in ["A", "B"]:
                div = divisions[f"{cname}-{dname}"]
                exists = TeacherSubject.query.filter_by(
                    teacher_id=teacher.id, subject_id=subj.id, division_id=div.id
                ).first()
                if not exists:
                    db.session.add(TeacherSubject(teacher_id=teacher.id, subject_id=subj.id, division_id=div.id))

    db.session.flush()

    # ---- Students (10 per division in FY-CS-A, FY-CS-B for demo)
    demo_first_names = ["Aarav", "Vivaan", "Aditi", "Diya", "Ishaan", "Kabir", "Meera", "Sara", "Yash", "Zara",
                         "Arjun", "Kiara", "Rohan", "Tanvi", "Dev", "Ira", "Manav", "Nisha", "Om", "Pooja"]
    students = []
    roll = 1
    for dkey in ["FY-CS-A", "FY-CS-B"]:
        div = divisions[dkey]
        for i in range(10):
            code = f"STU{roll:04d}"
            existing = Student.query.filter_by(student_code=code).first()
            if not existing:
                name = f"{random.choice(demo_first_names)} {['Patel','Singh','Rao','Nair','Iyer'][roll % 5]}"
                username = f"student{roll:03d}"
                u = User(username=username, email=f"{username}@college.local", role="student")
                u.set_password("Student@123")
                db.session.add(u)
                db.session.flush()
                s = Student(
                    user_id=u.id, student_code=code, roll_number=str(roll), full_name=name,
                    division_id=div.id, academic_year_id=year.id,
                )
                db.session.add(s)
                db.session.flush()
                students.append(s)
            roll += 1

    db.session.flush()
    if not students:
        students = Student.query.filter(Student.division_id.in_([divisions["FY-CS-A"].id, divisions["FY-CS-B"].id])).all()

    # ---- Sample attendance for the last 25 college days across FY-CS subjects
    if Attendance.query.count() == 0:
        fy_subjects = [subjects[("FY-CS", n)] for n, _ in subject_defs]
        today = date.today()
        day = today - timedelta(days=40)
        sessions_created = 0
        while day <= today and sessions_created < 25:
            if day.weekday() < 5:  # weekdays only
                for subj in fy_subjects:
                    teacher = next(t for t, sname in assignment_plan if sname == subj.name)
                    for dkey in ["FY-CS-A", "FY-CS-B"]:
                        div = divisions[dkey]
                        div_students = [s for s in students if s.division_id == div.id]
                        for s in div_students:
                            # give a couple of students deliberately low attendance for the demo
                            low_attender = s.roll_number in ("3", "14")
                            roll_chance = random.random()
                            if low_attender:
                                status = "present" if roll_chance > 0.5 else "absent"
                            else:
                                status = "present" if roll_chance > 0.12 else "absent"
                            db.session.add(Attendance(
                                student_id=s.id, subject_id=subj.id, division_id=div.id,
                                teacher_id=teacher.id, date=day, session="1", status=status,
                            ))
                sessions_created += 1
            day += timedelta(days=1)

    db.session.commit()
