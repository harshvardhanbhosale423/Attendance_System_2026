# Smart Offline College Attendance & Academic Management System

A Flask + MariaDB attendance and academic management system built to run entirely
on a college LAN, with no internet connection required for normal operation.

Roles: **Admin**, **Teacher**, **Student** — each with their own dashboard,
permissions, and views. Core features: bulk attendance, attendance calendar,
low-attendance early warning, analytics, reports (CSV/Excel/PDF), audit log,
and database backup.

---

## 1. Prerequisites

On the **server PC** only:

- Python 3.10+ (python.org)
- MariaDB or MySQL Server (mariadb.org)

Client PCs (teacher/student/admin computers) need **nothing installed** — just
a web browser, connected to the same LAN/Wi-Fi as the server.

---

## 2. Install Python packages

Open a terminal in the `AttendanceSystem` folder on the server PC:

```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

pip install -r requirements.txt
```

---

## 3. Set up MariaDB

Open the MariaDB/MySQL command line (or a GUI tool like HeidiSQL/phpMyAdmin) and run:

```sql
CREATE DATABASE attendance_system CHARACTER SET utf8mb4;
CREATE USER 'attendance_user'@'localhost' IDENTIFIED BY 'choose-a-strong-password';
GRANT ALL PRIVILEGES ON attendance_system.* TO 'attendance_user'@'localhost';
FLUSH PRIVILEGES;
```

Only the server PC needs direct database access in the setup described in this README —
client PCs only talk to the Flask web app over HTTP.

---

## 4. Configure environment variables

```bash
cp .env.example .env      # macOS/Linux
copy .env.example .env    # Windows
```

Edit `.env` and fill in:

- `FLASK_SECRET_KEY` — any long random string
- `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, `DB_NAME` — matching what you created in step 3

`.env` is never committed to source control and is only read locally.

> **Quick local testing without MariaDB:** set `DB_ENGINE=sqlite` in `.env`
> to use a local SQLite file instead — useful for a first look before setting
> up MariaDB.

---

## 5. Vendor the frontend libraries (for true offline use)

The app deliberately does not load Bootstrap/Chart.js from an internet CDN at
runtime — see `static/vendor/README.txt` for the one-time download steps (run
once, on any PC with internet, then copy the 3 files into `static/vendor/` on
the server PC). Until those files are present, pages will load without
styling/charts.

---

## 6. Initialize the database

```bash
# Windows (cmd):
set FLASK_APP=app.py
# macOS/Linux:
export FLASK_APP=app.py

flask init-db
```

This creates all tables and default attendance thresholds (Warning 75%,
Critical 65% — changeable later from Admin > Settings).

### Optional: load demo data

```bash
flask seed-demo
```

Creates a demo admin, 3 demo teachers, 20 demo students across two divisions,
and roughly 25 sessions of sample attendance history (including a couple of
students deliberately below the warning threshold, so the low-attendance
features are visible immediately).

**Demo credentials (change all passwords before real use):**

| Role    | Username        | Password      |
|---------|-----------------|---------------|
| Admin   | admin           | Admin@123     |
| Teacher | anita.sharma    | Teacher@123   |
| Teacher | ravi.kulkarni   | Teacher@123   |
| Teacher | neha.joshi      | Teacher@123   |
| Student | student001      | Student@123   |
| Student | student002 … student020 | Student@123 |

All demo names, IDs, and records are fictional.

---

## 7. Start the Flask server

```bash
python app.py
```

By default this listens on `0.0.0.0:5000`, meaning it accepts connections
from any device on the LAN, not just the server PC itself.

---

## 8. Access the application

**From the server PC itself:**

```
http://localhost:5000
```

**From another PC on the same LAN/Wi-Fi (teacher, student, or admin machine):**

1. On the server PC, find its local IP address:
   - Windows: `ipconfig` (look for IPv4 Address, e.g. 192.168.1.50)
   - macOS/Linux: `ifconfig` or `ip addr`
2. On the client PC's browser, go to:

   ```
   http://SERVER-IP:5000
   ```

   e.g. `http://192.168.1.50:5000`

Both devices must be connected to the same local network. No internet
connection is required for this to work.

If a client PC can't connect, check the server PC's firewall — allow inbound
connections on port 5000 (or whichever port you configure).

---

## 9. Creating a backup

Go to **Admin > Backup** and click "Create Backup Now".

- If `DB_ENGINE=sqlite`, this copies the database file into `backups/`.
- If using MariaDB/MySQL (the recommended production setup), run this from
  the server PC's terminal instead, then place the resulting file in
  `backups/` if you'd like it listed on the Backup page:

  ```bash
  mysqldump -u attendance_user -p attendance_system > backups/attendance_backup_YYYYMMDD.sql
  ```

  To restore:

  ```bash
  mysql -u attendance_user -p attendance_system < backups/attendance_backup_YYYYMMDD.sql
  ```

---

## 10. Project structure

```
AttendanceSystem/
├── app.py                  Flask app factory, CLI commands, entrypoint
├── config.py                Configuration (env-driven)
├── requirements.txt
├── .env.example
├── models/__init__.py        All SQLAlchemy models
├── routes/                   Blueprints: auth, admin, teacher, student, reports, errors
├── services/seed.py          Demo data seeding
├── utils/helpers.py          Role guards, audit logging, attendance calculations
├── templates/                 Jinja2 templates (auth/admin/teacher/student/errors)
├── static/                    css/js/vendor (locally hosted, no CDN dependency)
├── database/                  SQLite file lives here if DB_ENGINE=sqlite
├── backups/                   Backup files
└── reports/                   Reserved for server-side report caching
```

---

## 11. Security notes

- Passwords are hashed with Werkzeug's `generate_password_hash` (never stored in plain text).
- All database queries use the SQLAlchemy ORM (parameterized), preventing SQL injection.
- Sessions are server-side (Flask-Login) with a configurable timeout (`SESSION_LIFETIME_MINUTES` in `.env`).
- Role-based route guards (`@roles_required`) block admin/teacher/student pages from being accessed by the wrong role.
- Deactivating a student or teacher disables their login but **preserves** their attendance history — nothing is deleted.
- Change every demo password before using this system with real student data.

---

## 12. Verification notes

This project was built and statically verified (every Python file compiles;
every template was rendered successfully against realistic mock data matching
the actual model relationships; every `url_for()` reference in the templates
was checked against the registered Flask routes) in an environment without
internet or MariaDB access, so it could not be run end-to-end there. Before
relying on it in production, please:

1. Run `flask init-db` and `flask seed-demo`, then manually walk through:
   login (all 3 roles) → dashboard → take attendance → student calendar →
   analytics → reports export (CSV/Excel/PDF) → backup.
2. Double-check MariaDB connection settings for your environment.
3. For very large classes (100+ students), consider adding pagination to the
   students list if load time becomes noticeable.
