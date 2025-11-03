# Student Information System (SIS) — Flask + SQLite

A simple web application for managing student records. Features include:

- User authentication (default admin: `admin` / `admin123` — **change after login**)
- Create, read, update and delete (CRUD) student records
- Search by name, Student ID, department or email
- Basic server-side validation and CSRF protection
- SQLite database for zero-config setup

## Quick Start

```bash
# 1) Create and activate a virtual environment (recommended)
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# 2) Install dependencies
pip install -r requirements.txt

# 3) Run the app
python app.py
# App runs at http://127.0.0.1:5000
```

On first run, the database is created automatically with a default admin user. You can also visit `/initdb` to re-initialize (for demo/testing).

## Project Structure

```
student_info_system/
├── app.py
├── requirements.txt
├── templates/
│   ├── base.html
│   ├── auth/
│   │   ├── login.html
│   │   └── register.html  # Only accessible by 'admin'
│   ├── students/
│   │   ├── index.html
│   │   ├── new.html
│   │   ├── edit.html
│   │   ├── _form_fields.html
│   │   └── view.html
│   └── errors/
│       ├── 403.html
│       └── 404.html
└── README.md
```

## Notes

- This is a minimal starter. For production, consider:
  - Using Flask-Login for robust authentication and session management
  - CSRF via Flask-WTF
  - SQLAlchemy ORM instead of raw `sqlite3`
  - Input sanitization and more granular validation
  - Pagination for large datasets
  - Role-based access control (RBAC)
  - Dockerfile and unit tests

## Desktop Alternative (Tkinter/PyQt)

You can build the same CRUD features with a desktop GUI. Suggested tables are the same. Keep a DB layer module (e.g., `db.py`) so the GUI code stays clean.
