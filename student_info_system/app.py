#!/usr/bin/env python3
from __future__ import annotations
import os
import re
import sqlite3
from functools import wraps
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session, g, abort
from werkzeug.security import generate_password_hash, check_password_hash

# --- App setup ---
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")
app.config["DATABASE"] = os.path.join(app.root_path, "app.db")

# --- DB helpers ---
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()

def init_db():
    db = get_db()
    db.executescript(
        """
        PRAGMA foreign_keys = ON;

        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            department TEXT NOT NULL,
            email TEXT UNIQUE,
            phone TEXT,
            created_at TEXT NOT NULL
        );
        """
    )
    # Seed default admin if not exists
    cur = db.execute("SELECT id FROM users WHERE username = ?", ("admin",))
    if cur.fetchone() is None:
        db.execute(
            "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
            ("admin", generate_password_hash("admin123"), datetime.utcnow().isoformat())
        )
        db.commit()

# --- Auth utilities ---
def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped

# Basic CSRF token
def get_csrf_token():
    token = session.get("_csrf_token")
    if not token:
        import secrets
        token = secrets.token_hex(16)
        session["_csrf_token"] = token
    return token

def validate_csrf(token_from_form: str) -> bool:
    return token_from_form and token_from_form == session.get("_csrf_token")

app.jinja_env.globals["csrf_token"] = get_csrf_token

# --- Routes ---
@app.route("/initdb")
def initdb_route():
    # Convenience route for first-time setup (can be removed in production)
    init_db()
    flash("Database initialized. Admin user created (username='admin', password='admin123'). Change the password!", "info")
    return redirect(url_for("login"))

@app.route("/")
def home():
    if "user_id" in session:
        return redirect(url_for("list_students"))
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        db = get_db()
        row = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        if row and check_password_hash(row["password_hash"], password):
            session.clear()
            session["user_id"] = row["id"]
            session["username"] = row["username"]
            flash("Welcome back!", "success")
            return redirect(request.args.get("next") or url_for("list_students"))
        flash("Invalid username or password.", "danger")
    return render_template("auth/login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))

@app.route("/register", methods=["GET", "POST"])
def register():
    # Optional: allow creating additional users when logged in as admin
    if "user_id" not in session or session.get("username") != "admin":
        abort(403)
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")

        errors = []
        if not username:
            errors.append("Username is required.")
        if not password or len(password) < 6:
            errors.append("Password must be at least 6 characters.")
        if password != confirm:
            errors.append("Passwords do not match.")

        if errors:
            for e in errors: flash(e, "danger")
        else:
            db = get_db()
            try:
                db.execute(
                    "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
                    (username, generate_password_hash(password), datetime.utcnow().isoformat()),
                )
                db.commit()
                flash(f"User '{username}' created.", "success")
                return redirect(url_for("list_students"))
            except sqlite3.IntegrityError:
                flash("Username already exists.", "danger")
    return render_template("auth/register.html")

# --- Students CRUD ---
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

def validate_student(form, updating=False, current=None):
    name = form.get("name", "").strip()
    student_id = form.get("student_id", "").strip()
    department = form.get("department", "").strip()
    email = form.get("email", "").strip()
    phone = form.get("phone", "").strip()

    errors = []
    if not name: errors.append("Name is required.")
    if not student_id: errors.append("Student ID is required.")
    if not department: errors.append("Department is required.")
    if email and not EMAIL_RE.match(email): errors.append("Invalid email format.")
    if phone and not re.fullmatch(r"[0-9+\-\s]{7,20}", phone):
        errors.append("Phone should contain digits, spaces, '+' or '-' only.")

    return errors, {"name": name, "student_id": student_id, "department": department, "email": email, "phone": phone}

@app.route("/students")
@login_required
def list_students():
    q = request.args.get("q", "").strip()
    db = get_db()
    if q:
        like = f"%{q}%"
        rows = db.execute(
            """SELECT * FROM students
               WHERE name LIKE ? OR student_id LIKE ? OR department LIKE ? OR email LIKE ?
               ORDER BY created_at DESC""",
            (like, like, like, like)
        ).fetchall()
    else:
        rows = db.execute("SELECT * FROM students ORDER BY created_at DESC").fetchall()
    return render_template("students/index.html", students=rows, q=q)

@app.route("/students/new", methods=["GET", "POST"])
@login_required
def create_student():
    if request.method == "POST":
        if not validate_csrf(request.form.get("csrf_token")):
            abort(400)
        errors, data = validate_student(request.form)
        if errors:
            for e in errors: flash(e, "danger")
            return render_template("students/new.html", data=data)
        db = get_db()
        try:
            db.execute(
                "INSERT INTO students (student_id, name, department, email, phone, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (data["student_id"], data["name"], data["department"], data["email"] or None, data["phone"] or None, datetime.utcnow().isoformat())
            )
            db.commit()
            flash("Student added.", "success")
            return redirect(url_for("list_students"))
        except sqlite3.IntegrityError as e:
            if "students.student_id" in str(e).lower():
                flash("Student ID already exists.", "danger")
            elif "students.email" in str(e).lower():
                flash("Email already exists.", "danger")
            else:
                flash("Database error while creating student.", "danger")
    return render_template("students/new.html", data={})

@app.route("/students/<int:id>")
@login_required
def view_student(id: int):
    db = get_db()
    row = db.execute("SELECT * FROM students WHERE id = ?", (id,)).fetchone()
    if not row: abort(404)
    return render_template("students/view.html", s=row)

@app.route("/students/<int:id>/edit", methods=["GET", "POST"])
@login_required
def edit_student(id: int):
    db = get_db()
    row = db.execute("SELECT * FROM students WHERE id = ?", (id,)).fetchone()
    if not row: abort(404)
    if request.method == "POST":
        if not validate_csrf(request.form.get("csrf_token")):
            abort(400)
        errors, data = validate_student(request.form, updating=True, current=row)
        if errors:
            for e in errors: flash(e, "danger")
            return render_template("students/edit.html", s=row, data=data)
        try:
            # Enforce unique constraints manually for better error messages
            existing = db.execute("SELECT id FROM students WHERE student_id = ? AND id != ?", (data["student_id"], id)).fetchone()
            if existing:
                flash("Student ID already exists.", "danger")
                return render_template("students/edit.html", s=row, data=data)
            if data["email"]:
                existing = db.execute("SELECT id FROM students WHERE email = ? AND id != ?", (data["email"], id)).fetchone()
                if existing:
                    flash("Email already exists.", "danger")
                    return render_template("students/edit.html", s=row, data=data)

            db.execute(
                "UPDATE students SET student_id=?, name=?, department=?, email=?, phone=? WHERE id=?",
                (data["student_id"], data["name"], data["department"], data["email"] or None, data["phone"] or None, id)
            )
            db.commit()
            flash("Student updated.", "success")
            return redirect(url_for("view_student", id=id))
        except sqlite3.IntegrityError:
            flash("Database error while updating student.", "danger")
    return render_template("students/edit.html", s=row, data=dict(row))

@app.route("/students/<int:id>/delete", methods=["POST"])
@login_required
def delete_student(id: int):
    if not validate_csrf(request.form.get("csrf_token")):
        abort(400)
    db = get_db()
    db.execute("DELETE FROM students WHERE id = ?", (id,))
    db.commit()
    flash("Student deleted.", "info")
    return redirect(url_for("list_students"))

# --- Error pages ---
@app.errorhandler(403)
def err403(e):
    return render_template("errors/403.html"), 403

@app.errorhandler(404)
def err404(e):
    return render_template("errors/404.html"), 404

# --- CLI ---
if __name__ == "__main__":
    # Ensure DB exists on first run
    os.makedirs(os.path.dirname(app.config["DATABASE"]), exist_ok=True)
    if not os.path.exists(app.config["DATABASE"]):
        with app.app_context():
            init_db()
            print("Initialized database and created default admin user.")
            print("Username: admin | Password: admin123  (Change after login)")
    app.run(debug=True)
