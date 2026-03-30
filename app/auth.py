import os
import re
import uuid

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_user, logout_user, current_user, login_required
from werkzeug.utils import secure_filename

from . import db
from .models import User, Booking, Session, Fixture, News

auth_bp = Blueprint("auth", __name__)

EMAIL_REGEX = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
PASSWORD_REGEX = r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,}$"

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@auth_bp.route("/")
def home():
    if current_user.is_authenticated:
        if current_user.role == "admin":
            return redirect(url_for("admin.dashboard"))
        if current_user.role == "coach":
            return redirect(url_for("coach.dashboard"))
        return redirect(url_for("player.dashboard"))

    return render_template("landing.html")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        role = "player"  # public registration locked to player only

        if not full_name or not email or not password:
            flash("All fields are required.", "danger")
            return redirect(url_for("auth.register"))

        if not re.match(EMAIL_REGEX, email):
            flash("Please enter a valid email address.", "danger")
            return redirect(url_for("auth.register"))

        if not re.match(PASSWORD_REGEX, password):
            flash("Password must be at least 8 characters and include: uppercase, lowercase, number, and symbol.", "danger")
            return redirect(url_for("auth.register"))

        if User.query.filter_by(email=email).first():
            flash("Email already registered.", "danger")
            return redirect(url_for("auth.register"))

        u = User(
            full_name=full_name,
            email=email,
            role=role,
            profile_photo=None
        )
        u.set_password(password)

        db.session.add(u)
        db.session.commit()

        flash("Account created. Please log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("register.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not re.match(EMAIL_REGEX, email):
            flash("Please enter a valid email address.", "danger")
            return redirect(url_for("auth.login"))

        user = User.query.filter_by(email=email).first()

        if not user or not user.check_password(password):
            flash("Invalid email or password.", "danger")
            return redirect(url_for("auth.login"))

        login_user(user)

        if user.role == "admin":
            return redirect(url_for("admin.dashboard"))
        if user.role == "coach":
            return redirect(url_for("coach.dashboard"))
        return redirect(url_for("player.dashboard"))

    return render_template("login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))

@auth_bp.route("/forgot-password")
def forgot_password():
    return render_template("forgot_password.html")


@auth_bp.route("/profile")
@login_required
def profile():
    stats = {}

    if current_user.role == "player":
        stats["Active bookings"] = Booking.query.filter_by(
            player_id=current_user.id, status="booked"
        ).count()
        stats["Cancelled bookings"] = Booking.query.filter_by(
            player_id=current_user.id, status="cancelled"
        ).count()

    elif current_user.role == "coach":
        stats["Assigned sessions"] = Session.query.filter_by(coach_id=current_user.id).count()
        stats["Total bookings (your sessions)"] = (
            Booking.query.join(Session, Booking.session_id == Session.id)
            .filter(Session.coach_id == current_user.id, Booking.status == "booked")
            .count()
        )

    elif current_user.role == "admin":
        stats["Total users"] = User.query.count()
        stats["Total sessions"] = Session.query.count()
        stats["Total bookings"] = Booking.query.count()
        stats["Total news posts"] = News.query.count()
        stats["Total fixtures"] = Fixture.query.count()

    return render_template("profile.html", stats=stats)


@auth_bp.route("/profile/photo", methods=["POST"])
@login_required
def upload_profile_photo():
    file = request.files.get("profile_photo")

    if not file or file.filename == "":
        flash("Please choose an image to upload.", "danger")
        return redirect(url_for("auth.profile"))

    if not allowed_file(file.filename):
        flash("Only PNG, JPG, JPEG, and WEBP files are allowed.", "danger")
        return redirect(url_for("auth.profile"))

    upload_folder = current_app.config["UPLOAD_FOLDER"]
    os.makedirs(upload_folder, exist_ok=True)

    ext = file.filename.rsplit(".", 1)[1].lower()
    filename = f"{uuid.uuid4().hex}.{ext}"
    filepath = os.path.join(upload_folder, secure_filename(filename))

    file.save(filepath)

    current_user.profile_photo = filename
    db.session.commit()

    flash("Profile photo updated.", "success")
    return redirect(url_for("auth.profile"))