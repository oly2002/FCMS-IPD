from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, current_app
from flask_login import login_required, current_user
from functools import wraps
from datetime import datetime
import os
import uuid

from sqlalchemy import func, case
from werkzeug.utils import secure_filename

from . import db
from .models import User, Session, Booking, Attendance, News, Fixture, ContactMessage

admin_bp = Blueprint("admin", __name__)

ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}


def role_required(*roles):
    def decorator(fn):
        @wraps(fn)
        @login_required
        def wrapper(*args, **kwargs):
            if current_user.role not in roles:
                abort(403)
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def allowed_image(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS


def save_poster_file(file):
    if not file or not file.filename:
        return None

    if not allowed_image(file.filename):
        return None

    ext = file.filename.rsplit(".", 1)[1].lower()
    filename = f"{uuid.uuid4().hex}.{ext}"

    upload_folder = os.path.join(current_app.root_path, "static", "uploads", "posters")
    os.makedirs(upload_folder, exist_ok=True)

    filepath = os.path.join(upload_folder, secure_filename(filename))
    file.save(filepath)

    return filename


@admin_bp.route("/")
@role_required("admin")
def dashboard():
    return render_template("admin_dashboard.html")


@admin_bp.route("/sessions")
@role_required("admin")
def sessions_list():
    sessions = Session.query.order_by(Session.session_date.asc(), Session.start_time.asc()).all()
    return render_template("admin_sessions.html", sessions=sessions)


@admin_bp.route("/sessions/create", methods=["GET", "POST"])
@role_required("admin")
def sessions_create():
    coaches = User.query.filter_by(role="coach").order_by(User.full_name.asc()).all()

    if request.method == "POST":
        title = request.form.get("title", "Training Session").strip()
        session_date = request.form.get("session_date")
        start_time = request.form.get("start_time")
        end_time = request.form.get("end_time") or None
        location = request.form.get("location", "").strip()
        capacity_raw = request.form.get("capacity", "").strip()
        coach_id_raw = request.form.get("coach_id") or None

        if not session_date or not start_time or not location or not capacity_raw:
            flash("Please fill in date, start time, location, and capacity.", "danger")
            return redirect(url_for("admin.sessions_create"))

        try:
            capacity = int(capacity_raw)
            if capacity <= 0:
                raise ValueError
        except ValueError:
            flash("Capacity must be a positive number.", "danger")
            return redirect(url_for("admin.sessions_create"))

        try:
            s = Session(
                title=title,
                session_date=datetime.strptime(session_date, "%Y-%m-%d").date(),
                start_time=datetime.strptime(start_time, "%H:%M").time(),
                end_time=datetime.strptime(end_time, "%H:%M").time() if end_time else None,
                location=location,
                capacity=capacity,
                coach_id=int(coach_id_raw) if coach_id_raw else None,
            )
            db.session.add(s)
            db.session.commit()
            flash("Session created.", "success")
            return redirect(url_for("admin.sessions_list"))
        except Exception:
            db.session.rollback()
            flash("Error creating session. Check inputs.", "danger")
            return redirect(url_for("admin.sessions_create"))

    return render_template("admin_session_form.html", mode="create", session=None, coaches=coaches)


@admin_bp.route("/sessions/<int:session_id>/edit", methods=["GET", "POST"])
@role_required("admin")
def sessions_edit(session_id):
    s = Session.query.get_or_404(session_id)
    coaches = User.query.filter_by(role="coach").order_by(User.full_name.asc()).all()

    if request.method == "POST":
        title = request.form.get("title", s.title).strip()
        session_date = request.form.get("session_date")
        start_time = request.form.get("start_time")
        end_time = request.form.get("end_time") or None
        location = request.form.get("location", s.location).strip()
        capacity_raw = request.form.get("capacity", str(s.capacity)).strip()
        coach_id_raw = request.form.get("coach_id") or None

        if not session_date or not start_time or not location or not capacity_raw:
            flash("Please fill in date, start time, location, and capacity.", "danger")
            return redirect(url_for("admin.sessions_edit", session_id=session_id))

        try:
            capacity = int(capacity_raw)
            if capacity <= 0:
                raise ValueError
        except ValueError:
            flash("Capacity must be a positive number.", "danger")
            return redirect(url_for("admin.sessions_edit", session_id=session_id))

        try:
            s.title = title
            s.session_date = datetime.strptime(session_date, "%Y-%m-%d").date()
            s.start_time = datetime.strptime(start_time, "%H:%M").time()
            s.end_time = datetime.strptime(end_time, "%H:%M").time() if end_time else None
            s.location = location
            s.capacity = capacity
            s.coach_id = int(coach_id_raw) if coach_id_raw else None

            db.session.commit()
            flash("Session updated.", "success")
            return redirect(url_for("admin.sessions_list"))
        except Exception:
            db.session.rollback()
            flash("Error updating session.", "danger")
            return redirect(url_for("admin.sessions_edit", session_id=session_id))

    return render_template("admin_session_form.html", mode="edit", session=s, coaches=coaches)


@admin_bp.route("/sessions/<int:session_id>/delete", methods=["POST"])
@role_required("admin")
def sessions_delete(session_id):
    s = Session.query.get_or_404(session_id)
    try:
        db.session.delete(s)
        db.session.commit()
        flash("Session deleted.", "success")
    except Exception:
        db.session.rollback()
        flash("Could not delete session (it may have bookings).", "danger")
    return redirect(url_for("admin.sessions_list"))


@admin_bp.route("/bookings")
@role_required("admin")
def bookings_list():
    bookings = Booking.query.order_by(Booking.booked_at.desc()).all()
    return render_template("admin_bookings.html", bookings=bookings)


@admin_bp.route("/reports")
@role_required("admin")
def reports():
    bookings_per_session = (
        db.session.query(Session, func.count(Booking.id))
        .outerjoin(Booking, (Booking.session_id == Session.id) & (Booking.status == "booked"))
        .group_by(Session.id)
        .order_by(Session.session_date.asc(), Session.start_time.asc())
        .all()
    )

    attendance_summary = (
        db.session.query(
            Session.id,
            Session.title,
            Session.session_date,
            func.sum(case((Attendance.status == "present", 1), else_=0)).label("present"),
            func.sum(case((Attendance.status == "absent", 1), else_=0)).label("absent"),
        )
        .outerjoin(Attendance, Attendance.session_id == Session.id)
        .group_by(Session.id, Session.title, Session.session_date, Session.start_time)
        .order_by(Session.session_date.asc(), Session.start_time.asc())
        .all()
    )

    # Chart data
    booking_labels = [f"{s.title} ({s.session_date})" for s, count in bookings_per_session]
    booking_values = [count for s, count in bookings_per_session]

    total_present = sum((row.present or 0) for row in attendance_summary)
    total_absent = sum((row.absent or 0) for row in attendance_summary)

    total_sessions = Session.query.count()
    total_bookings = Booking.query.filter_by(status="booked").count()

    return render_template(
        "admin_reports.html",
        bookings_per_session=bookings_per_session,
        attendance_summary=attendance_summary,
        booking_labels=booking_labels,
        booking_values=booking_values,
        total_present=total_present,
        total_absent=total_absent,
        total_sessions=total_sessions,
        total_bookings=total_bookings,
    )

@admin_bp.route("/news")
@role_required("admin")
def news_list():
    items = News.query.order_by(News.published_at.desc()).all()
    return render_template("admin_news.html", items=items)


@admin_bp.route("/news/create", methods=["GET", "POST"])
@role_required("admin")
def news_create():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        body = request.form.get("body", "").strip()

        if not title or not body:
            flash("Title and body are required.", "danger")
            return redirect(url_for("admin.news_create"))

        n = News(title=title, body=body)
        db.session.add(n)
        db.session.commit()
        flash("News posted.", "success")
        return redirect(url_for("admin.news_list"))

    return render_template("admin_news_form.html", mode="create", item=None)


@admin_bp.route("/news/<int:news_id>/edit", methods=["GET", "POST"])
@role_required("admin")
def news_edit(news_id):
    n = News.query.get_or_404(news_id)

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        body = request.form.get("body", "").strip()

        if not title or not body:
            flash("Title and body are required.", "danger")
            return redirect(url_for("admin.news_edit", news_id=news_id))

        n.title = title
        n.body = body
        db.session.commit()
        flash("News updated.", "success")
        return redirect(url_for("admin.news_list"))

    return render_template("admin_news_form.html", mode="edit", item=n)


@admin_bp.route("/news/<int:news_id>/delete", methods=["POST"])
@role_required("admin")
def news_delete(news_id):
    n = News.query.get_or_404(news_id)
    db.session.delete(n)
    db.session.commit()
    flash("News deleted.", "success")
    return redirect(url_for("admin.news_list"))


@admin_bp.route("/fixtures")
@role_required("admin")
def fixtures_list():
    fixtures = Fixture.query.order_by(Fixture.match_date.asc()).all()
    return render_template("admin_fixtures.html", fixtures=fixtures)


@admin_bp.route("/fixtures/create", methods=["GET", "POST"])
@role_required("admin")
def fixtures_create():
    if request.method == "POST":
        match_date = request.form.get("match_date")
        opponent = request.form.get("opponent", "").strip()
        venue = request.form.get("venue", "").strip()
        competition = request.form.get("competition", "").strip() or None
        opponent_logo = request.form.get("opponent_logo") or None

        if not match_date or not opponent or not venue:
            flash("Date, opponent, and venue are required.", "danger")
            return redirect(url_for("admin.fixtures_create"))

        poster_file = request.files.get("poster_image")
        poster_filename = None

        if poster_file and poster_file.filename:
            if not allowed_image(poster_file.filename):
                flash("Poster image must be PNG, JPG, JPEG, or WEBP.", "danger")
                return redirect(url_for("admin.fixtures_create"))
            poster_filename = save_poster_file(poster_file)

        f = Fixture(
            match_date=datetime.strptime(match_date, "%Y-%m-%d").date(),
            opponent=opponent,
            venue=venue,
            competition=competition,
            opponent_logo=opponent_logo,
            poster_image=poster_filename,
            is_played=False,
            home_score=None,
            away_score=None,
        )
        db.session.add(f)
        db.session.commit()
        flash("Fixture created.", "success")
        return redirect(url_for("admin.fixtures_list"))

    return render_template("admin_fixture_form.html", mode="create", item=None)


@admin_bp.route("/fixtures/<int:fixture_id>/edit", methods=["GET", "POST"])
@role_required("admin")
def fixtures_edit(fixture_id):
    f = Fixture.query.get_or_404(fixture_id)

    if request.method == "POST":
        match_date = request.form.get("match_date")
        opponent = request.form.get("opponent", "").strip()
        venue = request.form.get("venue", "").strip()
        competition = request.form.get("competition", "").strip() or None
        opponent_logo = request.form.get("opponent_logo") or None

        if not match_date or not opponent or not venue:
            flash("Date, opponent, and venue are required.", "danger")
            return redirect(url_for("admin.fixtures_edit", fixture_id=fixture_id))

        f.match_date = datetime.strptime(match_date, "%Y-%m-%d").date()
        f.opponent = opponent
        f.venue = venue
        f.competition = competition
        f.opponent_logo = opponent_logo

        poster_file = request.files.get("poster_image")
        if poster_file and poster_file.filename:
            if not allowed_image(poster_file.filename):
                flash("Poster image must be PNG, JPG, JPEG, or WEBP.", "danger")
                return redirect(url_for("admin.fixtures_edit", fixture_id=fixture_id))
            new_filename = save_poster_file(poster_file)
            if new_filename:
                f.poster_image = new_filename

        is_played = True if request.form.get("is_played") == "on" else False
        home_score_raw = request.form.get("home_score", "").strip()
        away_score_raw = request.form.get("away_score", "").strip()

        if is_played:
            try:
                f.home_score = int(home_score_raw)
                f.away_score = int(away_score_raw)
                if f.home_score < 0 or f.away_score < 0:
                    raise ValueError
                f.is_played = True
            except ValueError:
                flash("If match is marked as played, scores must be non-negative numbers.", "danger")
                return redirect(url_for("admin.fixtures_edit", fixture_id=fixture_id))
        else:
            f.is_played = False
            f.home_score = None
            f.away_score = None

        db.session.commit()
        flash("Fixture updated.", "success")
        return redirect(url_for("admin.fixtures_list"))

    return render_template("admin_fixture_form.html", mode="edit", item=f)


@admin_bp.route("/fixtures/<int:fixture_id>/delete", methods=["POST"])
@role_required("admin")
def fixtures_delete(fixture_id):
    f = Fixture.query.get_or_404(fixture_id)
    db.session.delete(f)
    db.session.commit()
    flash("Fixture deleted.", "success")
    return redirect(url_for("admin.fixtures_list"))


@admin_bp.route("/users/create", methods=["GET", "POST"])
@role_required("admin")
def create_user():
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        role = request.form.get("role", "player")

        if role not in ["player", "coach", "admin"]:
            flash("Invalid role.", "danger")
            return redirect(url_for("admin.create_user"))

        if not full_name or not email or not password:
            flash("All fields are required.", "danger")
            return redirect(url_for("admin.create_user"))

        if User.query.filter_by(email=email).first():
            flash("Email already exists.", "danger")
            return redirect(url_for("admin.create_user"))

        u = User(
            full_name=full_name,
            email=email,
            role=role,
            profile_photo=None
        )
        u.set_password(password)
        db.session.add(u)
        db.session.commit()

        flash(f"{role.title()} account created.", "success")
        return redirect(url_for("admin.dashboard"))

    return render_template("admin_user_form.html")

@admin_bp.route("/messages")
@role_required("admin")
def messages_list():
    messages = ContactMessage.query.order_by(ContactMessage.created_at.desc()).all()
    return render_template("admin_messages.html", messages=messages)

@admin_bp.route("/users")
@role_required("admin")
def users_list():
    players = User.query.filter_by(role="player").order_by(User.full_name.asc()).all()
    coaches = User.query.filter_by(role="coach").order_by(User.full_name.asc()).all()
    admins = User.query.filter_by(role="admin").order_by(User.full_name.asc()).all()

    return render_template(
        "admin_users.html",
        players=players,
        coaches=coaches,
        admins=admins
    )

@admin_bp.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
@role_required("admin")
def edit_user(user_id):
    user = User.query.get_or_404(user_id)

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        role = request.form.get("role", "player")

        if role not in ["player", "coach", "admin"]:
            flash("Invalid role.", "danger")
            return redirect(url_for("admin.edit_user", user_id=user.id))

        if not full_name or not email:
            flash("Full name and email are required.", "danger")
            return redirect(url_for("admin.edit_user", user_id=user.id))

        existing = User.query.filter(User.email == email, User.id != user.id).first()
        if existing:
            flash("Another user already uses that email.", "danger")
            return redirect(url_for("admin.edit_user", user_id=user.id))

        user.full_name = full_name
        user.email = email
        user.role = role

        db.session.commit()
        flash("User updated successfully.", "success")
        return redirect(url_for("admin.users_list"))

    return render_template("admin_user_edit.html", user=user)


@admin_bp.route("/users/<int:user_id>/delete", methods=["POST"])
@role_required("admin")
def delete_user(user_id):
    user = User.query.get_or_404(user_id)

    if user.id == current_user.id:
        flash("You cannot delete your own account while logged in.", "danger")
        return redirect(url_for("admin.users_list"))

    try:
        db.session.delete(user)
        db.session.commit()
        flash("User deleted successfully.", "success")
    except Exception:
        db.session.rollback()
        flash("Could not delete user. They may be linked to bookings, sessions, or attendance.", "danger")

    return redirect(url_for("admin.users_list"))

@admin_bp.route("/users/<int:user_id>/reset-password", methods=["GET", "POST"])
@role_required("admin")
def reset_password(user_id):
    user = User.query.get_or_404(user_id)

    if request.method == "POST":
        new_password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not new_password or not confirm_password:
            flash("Both password fields are required.", "danger")
            return redirect(url_for("admin.reset_password", user_id=user.id))

        if new_password != confirm_password:
            flash("Passwords do not match.", "danger")
            return redirect(url_for("admin.reset_password", user_id=user.id))

        if len(new_password) < 8:
            flash("Password must be at least 8 characters long.", "danger")
            return redirect(url_for("admin.reset_password", user_id=user.id))

        user.set_password(new_password)
        db.session.commit()

        flash("Password reset successfully.", "success")
        return redirect(url_for("admin.users_list"))

    return render_template("admin_reset_password.html", user=user)