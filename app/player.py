from flask import Blueprint, render_template, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from functools import wraps
from . import db
from .models import Session, Booking

player_bp = Blueprint("player", __name__)

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

@player_bp.route("/")
@role_required("player")
def dashboard():
    return redirect(url_for("player.sessions_list"))

@player_bp.route("/sessions")
@role_required("player")
def sessions_list():
    sessions = Session.query.order_by(Session.session_date.asc(), Session.start_time.asc()).all()

    # player’s active bookings
    my_bookings = Booking.query.filter_by(player_id=current_user.id, status="booked").all()
    my_session_ids = {b.session_id for b in my_bookings}

    # count booked seats per session (for capacity display)
    booked_counts = {}
    for s in sessions:
        booked_counts[s.id] = Booking.query.filter_by(session_id=s.id, status="booked").count()

    return render_template(
        "player_sessions.html",
        sessions=sessions,
        my_session_ids=my_session_ids,
        booked_counts=booked_counts
    )

@player_bp.route("/sessions/<int:session_id>/book", methods=["POST"])
@role_required("player")
def book_session(session_id):
    s = Session.query.get_or_404(session_id)

    # capacity check
    booked_count = Booking.query.filter_by(session_id=session_id, status="booked").count()
    if booked_count >= s.capacity:
        flash("This session is full.", "danger")
        return redirect(url_for("player.sessions_list"))

    # prevent duplicate booking
    existing = Booking.query.filter_by(session_id=session_id, player_id=current_user.id).first()
    if existing:
        if existing.status == "booked":
            flash("You already booked this session.", "warning")
            return redirect(url_for("player.sessions_list"))
        # restore cancelled booking
        existing.status = "booked"
        db.session.commit()
        flash("Booking restored.", "success")
        return redirect(url_for("player.my_bookings"))

    b = Booking(session_id=session_id, player_id=current_user.id, status="booked")
    db.session.add(b)
    db.session.commit()
    flash("Session booked successfully.", "success")
    return redirect(url_for("player.my_bookings"))

@player_bp.route("/bookings")
@role_required("player")
def my_bookings():
    bookings = Booking.query.filter_by(player_id=current_user.id).order_by(Booking.booked_at.desc()).all()
    return render_template("player_bookings.html", bookings=bookings)

@player_bp.route("/bookings/<int:booking_id>/cancel", methods=["POST"])
@role_required("player")
def cancel_booking(booking_id):
    b = Booking.query.get_or_404(booking_id)
    if b.player_id != current_user.id:
        abort(403)

    b.status = "cancelled"
    db.session.commit()
    flash("Booking cancelled.", "success")
    return redirect(url_for("player.my_bookings"))
