from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from functools import wraps
from sqlalchemy import func, case
from .models import Session, Booking, Attendance
from . import db
from .models import Session, Booking, Attendance, User

coach_bp = Blueprint("coach", __name__)

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

@coach_bp.route("/")
@role_required("coach")
def dashboard():
    sessions = Session.query.filter_by(coach_id=current_user.id).order_by(
        Session.session_date.asc(), Session.start_time.asc()
    ).all()
    return render_template("coach_dashboard.html", sessions=sessions)

@coach_bp.route("/reports")
@role_required("coach")
def reports():
    bookings_per_session = (
        db.session.query(Session, func.count(Booking.id))
        .outerjoin(Booking, (Booking.session_id == Session.id) & (Booking.status == "booked"))
        .filter(Session.coach_id == current_user.id)
        .group_by(Session.id, Session.title, Session.session_date, Session.start_time)
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
        .filter(Session.coach_id == current_user.id)
        .group_by(Session.id, Session.title, Session.session_date, Session.start_time)
        .order_by(Session.session_date.asc(), Session.start_time.asc())
        .all()
    )

    booking_labels = [f"{s.title} ({s.session_date})" for s, count in bookings_per_session]
    booking_values = [count for s, count in bookings_per_session]

    total_present = sum((row.present or 0) for row in attendance_summary)
    total_absent = sum((row.absent or 0) for row in attendance_summary)

    return render_template(
        "coach_reports.html",
        bookings_per_session=bookings_per_session,
        attendance_summary=attendance_summary,
        booking_labels=booking_labels,
        booking_values=booking_values,
        total_present=total_present,
        total_absent=total_absent,
    )
@coach_bp.route("/sessions/<int:session_id>/attendance", methods=["GET", "POST"])
@role_required("coach")
def attendance(session_id):
    s = Session.query.get_or_404(session_id)
    if s.coach_id != current_user.id:
        abort(403)

    bookings = Booking.query.filter_by(session_id=session_id, status="booked").all()

    # map existing attendance: player_id -> status
    existing_map = {a.player_id: a.status for a in Attendance.query.filter_by(session_id=session_id).all()}

    if request.method == "POST":
        for b in bookings:
            status = request.form.get(f"att_{b.player_id}")
            if status not in ["present", "absent"]:
                continue

            existing = Attendance.query.filter_by(session_id=session_id, player_id=b.player_id).first()
            if existing:
                existing.status = status
                existing.marked_by_coach_id = current_user.id
            else:
                a = Attendance(
                    session_id=session_id,
                    player_id=b.player_id,
                    marked_by_coach_id=current_user.id,
                    status=status
                )
                db.session.add(a)

        db.session.commit()
        flash("Attendance saved.", "success")
        return redirect(url_for("coach.dashboard"))

    # fetch player names for display
    player_ids = [b.player_id for b in bookings]
    players = {u.id: u for u in User.query.filter(User.id.in_(player_ids)).all()} if player_ids else {}

    return render_template(
        "coach_attendance.html",
        session=s,
        bookings=bookings,
        players=players,
        existing_map=existing_map
    )
