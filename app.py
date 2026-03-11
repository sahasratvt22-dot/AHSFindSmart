import os
import json
import smtplib
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from email.message import EmailMessage

from dotenv import load_dotenv
from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, session, send_from_directory
)
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

from db import init_db, get_conn
MAX_REVIEW_LEN = 300   # you can change 300 to any limit you want

load_dotenv()

UPLOAD_FOLDER = Path("uploads")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}

CAMPUS_LOCATIONS = [
    {"id": "raider-stadium", "name": "Raider Stadium"},
    {"id": "stadium-entrance", "name": "Stadium-entrance"},
    {"id": "practice-field", "name": "practice-field"},
    {"id": "tennis", "name": "tennis"},
    {"id": "baseball-field", "name": "baseball field"},
    {"id": "band", "name": "band"},
    {"id": "gym", "name": "gym"},
    {"id": "fine-arts", "name": "fine arts"},
    {"id": "main-entrance", "name": "main-entrance"},
    {"id": "1000-Hall", "name": "1000-Hall"},
    {"id": "2000-Hall", "name": "2000-Hall"},
    {"id": "3000-Hall", "name": "3000-Hall"},
    {"id": "4000-Hall", "name": "4000-Hall"},
    {"id": "media-center", "name": "media-center"},
    {"id": "5000-Hall", "name": "5000-Hall"},
    {"id": "cafeteria", "name": "cafeteria"},
    {"id": "student-parking", "name": "student-parking"},
    {"id": "staff-parking", "name": "staff-parking"},
    {"id": "visitor-parking", "name": "visitor-parking"},
    {"id": "bus-lane", "name": "bus-lane"},
    # add as many as you want:
    # {"id": "tennis", "name": "Tennis Courts"},
]


# -------------------
# Admin credential storage (persistent)
# -------------------
ADMIN_FILE = "admin.json"

def load_admin():
    """Load admin credentials from admin.json (create default on first run)."""
    if not os.path.exists(ADMIN_FILE):
        admin = {
            "username": "admin",
            "email": os.getenv("ADMIN_EMAIL", ""),
            "password_hash": generate_password_hash("admin123")  # change after first login
        }
        with open(ADMIN_FILE, "w") as f:
            json.dump(admin, f, indent=2)
        return admin

    with open(ADMIN_FILE, "r") as f:
        admin = json.load(f)

    if "email" not in admin:
        admin["email"] = os.getenv("ADMIN_EMAIL", "")
        save_admin(admin)

    return admin

def save_admin(admin):
    """Save admin credentials to admin.json."""
    with open(ADMIN_FILE, "w") as f:
        json.dump(admin, f, indent=2)

# -------------------
# Upload helpers
# -------------------
def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def get_email_config() -> tuple[str, int, str, str, bool, str]:
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_username = os.getenv("SMTP_USERNAME")
    smtp_password = os.getenv("SMTP_PASSWORD")
    smtp_use_tls = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
    from_email = os.getenv("MAIL_FROM", smtp_username or "no-reply@example.com")

    if not smtp_host or not smtp_username or not smtp_password:
        raise RuntimeError(
            "Email is not configured. Set SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD, and MAIL_FROM."
        )

    return smtp_host, smtp_port, smtp_username, smtp_password, smtp_use_tls, from_email


def send_email_message(subject: str, to_email: str, body: str) -> None:
    smtp_host, smtp_port, smtp_username, smtp_password, smtp_use_tls, from_email = get_email_config()

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = to_email
    msg.set_content(body)

    with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
        if smtp_use_tls:
            server.starttls()
        server.login(smtp_username, smtp_password)
        server.send_message(msg)


def send_claim_approval_email(to_email: str, student_name: str, item_title: str, pickup_location: str) -> None:
    send_email_message(
        subject=f"Lost and Found Claim Approved: {item_title}",
        to_email=to_email,
        body=
        f"""Hello {student_name},

Your claim request for "{item_title}" has been approved.

You can pick it up at: {pickup_location}

Please bring any information needed to confirm the item belongs to you.

Lost and Found
"""
    )


def send_password_reset_email(to_email: str, account_label: str, reset_link: str) -> None:
    send_email_message(
        subject=f"{account_label} Password Reset",
        to_email=to_email,
        body=
        f"""A password reset was requested for your {account_label.lower()}.

Open this link to choose a new password:
{reset_link}

This link expires in 30 minutes. If you did not request this, you can ignore this email.
""",
    )


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "dev_secret_change_me")
    app.config["UPLOAD_FOLDER"] = str(UPLOAD_FOLDER)
    app.permanent_session_lifetime = timedelta(days=30)

    UPLOAD_FOLDER.mkdir(exist_ok=True)

    @app.route("/feedback", methods=["GET", "POST"])
    def feedback():
        if request.method == "POST":
            message = request.form.get("message", "").strip()
            rating_raw = request.form.get("rating", "5").strip()

            if not message:
                flash("Please write a review before submitting.", "error")
                return redirect(url_for("feedback"))

            if len(message) > MAX_REVIEW_LEN:
                flash(f"Review must be {MAX_REVIEW_LEN} characters or fewer.", "error")
                return redirect(url_for("feedback"))

            try:
                rating = int(rating_raw)
            except ValueError:
                rating = 5
            if rating < 1 or rating > 5:
                rating = 5

            conn = get_conn()
            try:
                conn.execute(
                    "INSERT INTO reviews (message, rating, created_at) VALUES (?, ?, ?)",
                    (message, rating, datetime.now().isoformat(timespec="seconds"))
                )
                conn.commit()
            finally:
                conn.close()

            flash("Thanks! Your anonymous review was posted.", "success")
            return redirect(url_for("feedback"))

        conn = get_conn()
        try:
            reviews = conn.execute("SELECT * FROM reviews ORDER BY id DESC").fetchall()
        finally:
            conn.close()

        return render_template("feedback.html", reviews=reviews, max_len=MAX_REVIEW_LEN)


    # init DB
    init_db()

    # -------------------
    # Auth helpers
    # -------------------
    def is_admin() -> bool:
        return session.get("is_admin") is True

    def is_student() -> bool:
        return session.get("is_student") is True

    def current_user_name() -> str | None:
        if is_admin():
            return "Admin"
        if is_student():
            return session.get("student_name")
        return None

    def apply_session_persistence(should_remember: bool) -> None:
        session.permanent = should_remember

    def create_password_reset(user_type: str, user_key: str, email: str) -> str:
        token = secrets.token_urlsafe(32)
        now = datetime.now()
        conn = get_conn()
        try:
            conn.execute(
                "DELETE FROM password_resets WHERE user_type = ? AND user_key = ? AND used_at IS NULL",
                (user_type, user_key),
            )
            conn.execute(
                """
                INSERT INTO password_resets (user_type, user_key, email, token, expires_at, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    user_type,
                    user_key,
                    email,
                    token,
                    (now + timedelta(minutes=30)).isoformat(timespec="seconds"),
                    now.isoformat(timespec="seconds"),
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return token

    def get_password_reset(token: str):
        conn = get_conn()
        try:
            row = conn.execute(
                """
                SELECT *
                FROM password_resets
                WHERE token = ?
                """,
                (token,),
            ).fetchone()
        finally:
            conn.close()

        if not row or row["used_at"]:
            return None

        try:
            if datetime.fromisoformat(row["expires_at"]) < datetime.now():
                return None
        except ValueError:
            return None

        return row

    @app.context_processor
    def inject_globals():
        return {
            "is_admin": is_admin(),
            "is_student": is_student(),
            "current_user_name": current_user_name(),
        }

    # -------------------
    # Pages
    # -------------------
    @app.route("/faq")
    def faq():
        return render_template("faq.html")
    
    @app.post("/admin/review/<int:review_id>/delete")
    def admin_delete_review(review_id: int):
        if not is_admin():
            flash("Admin access required.", "error")
            return redirect(url_for("login"))

        conn = get_conn()
        try:
            conn.execute("DELETE FROM reviews WHERE id=?", (review_id,))
            conn.commit()
        finally:
            conn.close()

        flash("Review deleted.", "success")
        return redirect(url_for("feedback"))


    @app.route("/")
    def home():
        today = datetime.now()
        today_iso = today.date().isoformat()
        conn = get_conn()
        try:
            total_found = conn.execute("SELECT COUNT(*) AS c FROM found_items").fetchone()["c"]
            approved_found = conn.execute(
                "SELECT COUNT(*) AS c FROM found_items WHERE status='approved'"
            ).fetchone()["c"]
            claimed = conn.execute(
                "SELECT COUNT(*) AS c FROM found_items WHERE status='claimed'"
            ).fetchone()["c"]
            pending = conn.execute(
                "SELECT COUNT(*) AS c FROM found_items WHERE status='pending'"
            ).fetchone()["c"]
            total_claims = conn.execute("SELECT COUNT(*) AS c FROM claims").fetchone()["c"]
            today_finds = conn.execute(
                """
                SELECT id, title, category, location_found, photo_filename, created_at
                FROM found_items
                WHERE status='approved' AND substr(created_at, 1, 10) = ?
                ORDER BY created_at DESC
                LIMIT 5
                """,
                (today_iso,),
            ).fetchall()
        finally:
            conn.close()

        today_find_cards = []
        for row in today_finds:
            created_at = row["created_at"] or ""
            display_time = "Today"
            try:
                display_time = datetime.fromisoformat(created_at).strftime("%I:%M %p").lstrip("0")
            except ValueError:
                pass

            today_find_cards.append(
                {
                    "id": row["id"],
                    "title": row["title"],
                    "category": row["category"],
                    "location_found": row["location_found"],
                    "photo_filename": row["photo_filename"],
                    "display_time": display_time,
                }
            )

        return render_template(
            "home.html",
            stats={
                "total_found": total_found,
                "approved_found": approved_found,
                "claimed": claimed,
                "pending": pending,
                "total_claims": total_claims
            },
            today_finds=today_find_cards,
            today_label=today.strftime("%A, %B %d, %Y"),
        )

    @app.route("/browse")
    def browse():
        q = request.args.get("q", "").strip()
        category = request.args.get("category", "").strip()
        date_filter = request.args.get("date", "").strip()
        today_iso = datetime.now().date().isoformat()

        conn = get_conn()
        try:
            # ✅ Show ONLY approved items in browse.
            # If an item is marked claimed, it disappears from browse.
            sql = "SELECT * FROM found_items WHERE status='approved'"
            params = []

            if q:
                sql += " AND (title LIKE ? OR description LIKE ? OR location_found LIKE ?)"
                like = f"%{q}%"
                params.extend([like, like, like])

            if category:
                sql += " AND category = ?"
                params.append(category)

            if date_filter == "today":
                sql += " AND substr(created_at, 1, 10) = ?"
                params.append(today_iso)

            sql += " ORDER BY id DESC"
            items = conn.execute(sql, params).fetchall()

            categories = conn.execute(
                "SELECT DISTINCT category FROM found_items ORDER BY category ASC"
            ).fetchall()
        finally:
            conn.close()

        return render_template(
            "browse.html",
            items=items,
            q=q,
            category=category,
            categories=categories,
            date_filter=date_filter,
        )

    @app.route("/report-found", methods=["GET", "POST"])
    def report_found():
        if request.method == "POST":
            title = request.form.get("title", "").strip()
            category = request.form.get("category", "").strip()
            location_id = request.form.get("location_id", "").strip()
            date_found = request.form.get("date_found", "").strip()
            description = request.form.get("description", "").strip()

            if not all([title, category, location_id, date_found, description]):
                flash("Please fill out all required fields.", "error")
                return redirect(url_for("report_found"))

            photo_filename = None
            file = request.files.get("photo")
            if file and file.filename:
                if not allowed_file(file.filename):
                    flash("Photo must be PNG/JPG/JPEG/WEBP.", "error")
                    return redirect(url_for("report_found"))

                safe_name = secure_filename(file.filename)
                photo_filename = f"{int(datetime.now().timestamp())}_{safe_name}"
                file.save(UPLOAD_FOLDER / photo_filename)

            # Convert location_id -> readable name
            loc_name = next(
                (l["name"] for l in CAMPUS_LOCATIONS if l["id"] == location_id),
                location_id
            )

            conn = get_conn()
            try:
                conn.execute(
                    """
                    INSERT INTO found_items (
                        title, category, location_found, location_id,
                        date_found, description, photo_filename, status, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?)
                    """,
                    (
                        title,
                        category,
                        loc_name,        # friendly text
                        location_id,     # exact map ID
                        date_found,
                        description,
                        photo_filename,
                        datetime.now().isoformat(timespec="seconds")
                    )
                )
                conn.commit()
            finally:
                conn.close()

            flash("Submitted! An admin will review and approve your post.", "success")
            return redirect(url_for("browse"))

        # GET request
        return render_template("report_found.html", campus_locations=CAMPUS_LOCATIONS)

    @app.route("/claim/<int:item_id>", methods=["GET", "POST"])
    def claim_item(item_id: int):
        conn = get_conn()
        try:
            item = conn.execute("SELECT * FROM found_items WHERE id=?", (item_id,)).fetchone()
        finally:
            conn.close()

        if not item:
            flash("Item not found.", "error")
            return redirect(url_for("browse"))

        if request.method == "POST":
            student_name = request.form.get("student_name", "").strip()
            email = request.form.get("email", "").strip()
            message = request.form.get("message", "").strip()

            if not all([student_name, email, message]):
                flash("Please fill out all required fields.", "error")
                return redirect(url_for("claim_item", item_id=item_id))

            conn = get_conn()
            try:
                conn.execute(
                    """
                    INSERT INTO claims (item_id, student_name, email, message, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (item_id, student_name, email, message, datetime.now().isoformat(timespec="seconds"))
                )
                conn.commit()
            finally:
                conn.close()

            flash("Request sent! The admin will follow up soon.", "success")
            return redirect(url_for("browse"))

        return render_template("claim_lost.html", item=item)

    @app.route("/map")
    def map_page():
        # Pins (x,y are percentages)
        campus_locations = [
            {"id": "softball-field", "name": "Softball Field", "x": 25, "y": 12},
            {"id": "raider-stadium", "name": "Raider Stadium", "x": 25, "y": 32},
            {"id": "stadium-entrance", "name": "Stadium Entrance", "x": 42, "y": 34},
            {"id": "practice-field", "name": "Practice Field", "x": 42, "y": 42},
            {"id": "tennis", "name": "Tennis Courts", "x": 65, "y": 39},
            {"id": "baseball-field", "name": "Baseball Field", "x": 22, "y": 58},
            {"id": "band", "name": "Band Room", "x": 40, "y": 57},
            {"id": "gym", "name": "Gym", "x": 50, "y": 60},
            {"id": "fine-arts", "name": "Fine Arts", "x": 50, "y": 74},
            {"id": "main-entrance", "name": "Main Entrance", "x": 54, "y": 66},
            {"id": "1000-hall", "name": "1000 Hall", "x": 65, "y": 65},
            {"id": "2000-hall", "name": "2000 Hall", "x": 60, "y": 75},
            {"id": "3000-hall", "name": "3000 Hall", "x": 67, "y": 75},
            {"id": "4000-hall", "name": "4000 Hall", "x": 73, "y": 75},
            {"id": "media-center", "name": "Media Center", "x": 62, "y": 62},
            {"id": "cafeteria", "name": "Cafeteria", "x": 72, "y": 62},
            {"id": "5000-hall", "name": "5000 Hall", "x": 90, "y": 63},
            {"id": "student-parking", "name": "Student Parking", "x": 30, "y": 80},
            {"id": "staff-parking", "name": "Staff Parking", "x": 45, "y": 85},
            {"id": "visitor-parking", "name": "Visitor Parking", "x": 54, "y": 88},
            {"id": "student-staff-parking", "name": "Student/Staff Parking", "x": 85, "y": 79},
            {"id": "bus-lane", "name": "Bus Lane", "x": 85, "y": 70},
            {"id": "unknown", "name": "Other / Unknown", "x": 5, "y": 5},
        ]

        # Pull items including location_id
        conn = get_conn()
        try:
            rows = conn.execute(
                """
                SELECT id, title, category, date_found, location_found, location_id
                FROM found_items
                WHERE status IN ('approved','claimed')
                ORDER BY id DESC
                """
            ).fetchall()
        finally:
            conn.close()

        # Build map_items dict: loc_id -> list of items
        map_items = {loc["id"]: [] for loc in campus_locations}

        for r in rows:
            item = dict(r)
            lid = item.get("location_id")

            # If location_id is missing (older posts), try to match by text as fallback
            if not lid:
                loc_text = (item.get("location_found") or "").lower()
                matched = None
                for loc in campus_locations:
                    if loc["name"].lower() in loc_text:
                        matched = loc["id"]
                        break
                lid = matched or "unknown"
                item["location_id"] = lid  # so it behaves consistently

            # Add to map group
            if lid not in map_items:
                map_items[lid] = []
            map_items[lid].append(item)

        return render_template(
            "map.html",
            campus_locations=campus_locations,
            map_items=map_items
        )



    # Serve uploaded images safely
    @app.route("/uploads/<path:filename>")
    def uploaded_file(filename: str):
        return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

    # -------------------
    # Admin auth + panel
    # -------------------
    @app.route("/login", methods=["GET", "POST"])
    @app.route("/login/admin", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "").strip()
            save_credentials = request.form.get("save_credentials") == "on"

            admin = load_admin()

            if username == admin["username"] and check_password_hash(admin["password_hash"], password):
                session.clear()
                session["is_admin"] = True
                apply_session_persistence(save_credentials)
                flash("Logged in as admin.", "success")
                return redirect(url_for("admin_panel"))

            flash("Invalid credentials.", "error")
            return redirect(url_for("login"))

        return render_template("login.html")

    @app.route("/login/student", methods=["GET", "POST"])
    def student_login():
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "").strip()
            save_credentials = request.form.get("save_credentials") == "on"

            if not email or not password:
                flash("Email and password are required.", "error")
                return redirect(url_for("student_login"))

            conn = get_conn()
            try:
                student = conn.execute(
                    "SELECT * FROM students WHERE email = ?",
                    (email,),
                ).fetchone()
            finally:
                conn.close()

            if not student or not check_password_hash(student["password_hash"], password):
                flash("Invalid student email or password.", "error")
                return redirect(url_for("student_login"))

            session.clear()
            session["is_student"] = True
            session["student_id"] = student["id"]
            session["student_name"] = student["full_name"]
            session["student_email"] = student["email"]
            apply_session_persistence(save_credentials)
            flash(f"Logged in as {student['full_name']}.", "success")
            return redirect(url_for("home"))

        return render_template("student_auth.html", mode="login")

    @app.route("/signup/student", methods=["GET", "POST"])
    def student_signup():
        if request.method == "POST":
            full_name = request.form.get("full_name", "").strip()
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "").strip()
            confirm_password = request.form.get("confirm_password", "").strip()
            save_credentials = request.form.get("save_credentials") == "on"

            if not all([full_name, email, password, confirm_password]):
                flash("Please fill out all student account fields.", "error")
                return redirect(url_for("student_signup"))

            if len(password) < 8:
                flash("Password must be at least 8 characters.", "error")
                return redirect(url_for("student_signup"))

            if password != confirm_password:
                flash("Passwords do not match.", "error")
                return redirect(url_for("student_signup"))

            conn = get_conn()
            try:
                existing = conn.execute(
                    "SELECT id FROM students WHERE email = ?",
                    (email,),
                ).fetchone()
                if existing:
                    flash("That email is already registered. Try logging in instead.", "error")
                    return redirect(url_for("student_login"))

                cursor = conn.execute(
                    """
                    INSERT INTO students (full_name, email, password_hash, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        full_name,
                        email,
                        generate_password_hash(password),
                        datetime.now().isoformat(timespec="seconds"),
                    ),
                )
                conn.commit()
            finally:
                conn.close()

            session.clear()
            session["is_student"] = True
            session["student_id"] = cursor.lastrowid
            session["student_name"] = full_name
            session["student_email"] = email
            apply_session_persistence(save_credentials)
            flash("Student account created successfully.", "success")
            return redirect(url_for("home"))

        return render_template("student_auth.html", mode="signup")

    @app.route("/forgot-password/admin", methods=["GET", "POST"])
    def admin_forgot_password():
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            admin = load_admin()

            if username != admin["username"]:
                flash("If that admin account exists, a reset link has been sent.", "success")
                return redirect(url_for("login"))

            admin_email = (admin.get("email") or os.getenv("ADMIN_EMAIL", "")).strip()
            if not admin_email:
                flash("Admin reset email is not configured yet. Set ADMIN_EMAIL first.", "error")
                return redirect(url_for("admin_forgot_password"))

            token = create_password_reset("admin", admin["username"], admin_email)
            reset_link = url_for("reset_password", token=token, _external=True)

            try:
                send_password_reset_email(admin_email, "Admin Account", reset_link)
            except Exception as exc:
                flash(f"Reset email could not be sent: {exc}", "error")
                return redirect(url_for("admin_forgot_password"))

            flash("If that admin account exists, a reset link has been sent.", "success")
            return redirect(url_for("login"))

        return render_template(
            "forgot_password.html",
            account_type="admin",
            form_action=url_for("admin_forgot_password"),
        )

    @app.route("/forgot-password/student", methods=["GET", "POST"])
    def student_forgot_password():
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            if not email:
                flash("Email is required.", "error")
                return redirect(url_for("student_forgot_password"))

            conn = get_conn()
            try:
                student = conn.execute(
                    "SELECT id, full_name, email FROM students WHERE email = ?",
                    (email,),
                ).fetchone()
            finally:
                conn.close()

            if student:
                token = create_password_reset("student", str(student["id"]), student["email"])
                reset_link = url_for("reset_password", token=token, _external=True)
                try:
                    send_password_reset_email(student["email"], "Student Account", reset_link)
                except Exception as exc:
                    flash(f"Reset email could not be sent: {exc}", "error")
                    return redirect(url_for("student_forgot_password"))

            flash("If that student account exists, a reset link has been sent.", "success")
            return redirect(url_for("student_login"))

        return render_template(
            "forgot_password.html",
            account_type="student",
            form_action=url_for("student_forgot_password"),
        )

    @app.route("/reset-password/<token>", methods=["GET", "POST"])
    def reset_password(token: str):
        reset_row = get_password_reset(token)
        if not reset_row:
            flash("That reset link is invalid or has expired.", "error")
            return redirect(url_for("home"))

        if request.method == "POST":
            password = request.form.get("password", "").strip()
            confirm_password = request.form.get("confirm_password", "").strip()

            if len(password) < 8:
                flash("Password must be at least 8 characters.", "error")
                return redirect(url_for("reset_password", token=token))

            if password != confirm_password:
                flash("Passwords do not match.", "error")
                return redirect(url_for("reset_password", token=token))

            conn = get_conn()
            try:
                if reset_row["user_type"] == "student":
                    conn.execute(
                        "UPDATE students SET password_hash = ? WHERE id = ?",
                        (generate_password_hash(password), int(reset_row["user_key"])),
                    )
                else:
                    admin = load_admin()
                    admin["password_hash"] = generate_password_hash(password)
                    save_admin(admin)

                conn.execute(
                    "UPDATE password_resets SET used_at = ? WHERE id = ?",
                    (datetime.now().isoformat(timespec="seconds"), reset_row["id"]),
                )
                conn.commit()
            finally:
                conn.close()

            flash("Password reset successfully. You can log in now.", "success")
            if reset_row["user_type"] == "student":
                return redirect(url_for("student_login"))
            return redirect(url_for("login"))

        return render_template("reset_password.html", token=token, user_type=reset_row["user_type"])

    @app.route("/logout")
    def logout():
        session.clear()
        flash("You have been logged out.", "success")
        return redirect(url_for("home"))

    @app.route("/admin")
    def admin_panel():
        if not is_admin():
            flash("Admin access required.", "error")
            return redirect(url_for("login"))

        conn = get_conn()
        try:
            items = conn.execute("SELECT * FROM found_items ORDER BY id DESC").fetchall()
            claims = conn.execute(
                """
                SELECT c.*, f.title AS item_title
                FROM claims c
                JOIN found_items f ON f.id = c.item_id
                ORDER BY c.id DESC
                LIMIT 50
                """
            ).fetchall()
        finally:
            conn.close()

        return render_template("admin.html", items=items, claims=claims)

    @app.route("/admin/change-password", methods=["GET", "POST"])
    def admin_change_password():
        if not is_admin():
            return redirect(url_for("login"))

        admin = load_admin()

        if request.method == "POST":
            current_pw = request.form.get("current_password", "")
            new_pw = request.form.get("new_password", "")
            confirm_pw = request.form.get("confirm_password", "")

            if not check_password_hash(admin["password_hash"], current_pw):
                flash("Current password is incorrect.", "error")
                return redirect(url_for("admin_change_password"))

            if len(new_pw) < 8:
                flash("New password must be at least 8 characters.", "error")
                return redirect(url_for("admin_change_password"))

            if new_pw != confirm_pw:
                flash("New password and confirm password do not match.", "error")
                return redirect(url_for("admin_change_password"))

            admin["password_hash"] = generate_password_hash(new_pw)
            save_admin(admin)

            flash("Password updated successfully.", "success")
            return redirect(url_for("admin_panel"))

        return render_template("admin_change_password.html")

    # -------------------
    # Admin item actions
    # -------------------
    @app.post("/admin/item/<int:item_id>/approve")
    def admin_approve(item_id: int):
        if not is_admin():
            flash("Admin access required.", "error")
            return redirect(url_for("login"))

        conn = get_conn()
        try:
            conn.execute("UPDATE found_items SET status='approved' WHERE id=?", (item_id,))
            conn.commit()
        finally:
            conn.close()

        flash("Item approved.", "success")
        return redirect(url_for("admin_panel"))

    @app.post("/admin/item/<int:item_id>/mark-claimed")
    def admin_mark_claimed(item_id: int):
        if not is_admin():
            flash("Admin access required.", "error")
            return redirect(url_for("login"))

        conn = get_conn()
        try:
            conn.execute("UPDATE found_items SET status='claimed' WHERE id=?", (item_id,))
            conn.commit()
        finally:
            conn.close()

        flash("Marked as claimed.", "success")
        return redirect(url_for("admin_panel"))

    @app.post("/admin/claim/<int:claim_id>/approve")
    def admin_approve_claim(claim_id: int):
        if not is_admin():
            flash("Admin access required.", "error")
            return redirect(url_for("login"))

        pickup_location = request.form.get("pickup_location", "").strip()
        if not pickup_location:
            flash("Pickup location is required before approving a claim.", "error")
            return redirect(url_for("admin_panel"))

        conn = get_conn()
        claim = None
        try:
            claim = conn.execute(
                """
                SELECT c.*, f.title AS item_title
                FROM claims c
                JOIN found_items f ON f.id = c.item_id
                WHERE c.id = ?
                """,
                (claim_id,),
            ).fetchone()

            if not claim:
                flash("Claim request not found.", "error")
                return redirect(url_for("admin_panel"))

            if claim["status"] == "approved":
                flash("This claim request has already been approved.", "error")
                return redirect(url_for("admin_panel"))

            try:
                send_claim_approval_email(
                    to_email=claim["email"],
                    student_name=claim["student_name"],
                    item_title=claim["item_title"],
                    pickup_location=pickup_location,
                )
            except Exception as exc:
                flash(f"Approval email could not be sent: {exc}", "error")
                return redirect(url_for("admin_panel"))

            approved_at = datetime.now().isoformat(timespec="seconds")
            conn.execute(
                """
                UPDATE claims
                SET status='approved', pickup_location=?, approved_at=?
                WHERE id=?
                """,
                (pickup_location, approved_at, claim_id),
            )
            conn.execute(
                "UPDATE found_items SET status='claimed' WHERE id=?",
                (claim["item_id"],),
            )
            conn.commit()
        finally:
            conn.close()

        flash(f"Claim approved and email sent to {claim['email']}.", "success")
        return redirect(url_for("admin_panel"))

    @app.post("/admin/item/<int:item_id>/delete")
    def admin_delete(item_id: int):
        if not is_admin():
            flash("Admin access required.", "error")
            return redirect(url_for("login"))

        conn = get_conn()
        try:
            row = conn.execute("SELECT photo_filename FROM found_items WHERE id=?", (item_id,)).fetchone()
            if row and row["photo_filename"]:
                try:
                    (UPLOAD_FOLDER / row["photo_filename"]).unlink(missing_ok=True)
                except Exception:
                    pass

            conn.execute("DELETE FROM found_items WHERE id=?", (item_id,))
            conn.commit()
        finally:
            conn.close()

        flash("Item deleted.", "success")
        return redirect(url_for("admin_panel"))

    return app


if __name__ == "__main__":
    app = create_app()
    
import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
