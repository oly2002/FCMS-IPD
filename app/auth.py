import random
import re

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, current_user, login_required

from . import db
from .models import User, Booking, Session, Fixture, News

auth_bp = Blueprint("auth", __name__)

ROLE_EMOJIS = {
    "player": ["😀", "😎", "🤩", "👦", "👧", "🧑‍🦱", "🧔"],
    "coach":  ["🧑‍🏫", "📋", "🧠", "🧑‍💼", "😤"],
    "admin":  ["🛡️", "⚙️", "🧾", "🗂️", "👑"]
}

EMAIL_REGEX = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
PASSWORD_REGEX = r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,}$"


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
        role = "player"
        chosen_emoji = request.form.get("profile_emoji")

        # role safety (keeps your current behavior)
        if role not in ["player", "coach", "admin"]:
            role = "player"

        # required fields
        if not full_name or not email or not password:
            flash("All fields are required.", "danger")
            return redirect(url_for("auth.register"))

        # email format validation
        if not re.match(EMAIL_REGEX, email):
            flash("Please enter a valid email address.", "danger")
            return redirect(url_for("auth.register"))

        # password validation (simple IPD-friendly rule)
        if not re.match(PASSWORD_REGEX, password):
          flash("Password must be at least 8 characters and include: uppercase, lowercase, number, and symbol.", "danger")
          return redirect(url_for("auth.register"))


        # unique email
        if User.query.filter_by(email=email).first():
            flash("Email already registered.", "danger")
            return redirect(url_for("auth.register"))

        # emoji assignment
        if role == "player":
            emoji = chosen_emoji if chosen_emoji else random.choice(ROLE_EMOJIS["player"])
        else:
            emoji = random.choice(ROLE_EMOJIS.get(role, ["🙂"]))

        # create user
        u = User(full_name=full_name, email=email, role=role, profile_emoji=emoji)
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

        # email format validation (cleaner feedback)
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
