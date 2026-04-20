from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from . import db, login_manager


# stores all users in the system such as admin, coach, and player
class User(db.Model, UserMixin):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # admin/coach/player
    profile_emoji = db.Column(db.String(10), nullable=True)
    profile_photo = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # hash password before saving it
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    # check entered password during login
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

# used by Flask-Login to reload user from session
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))



# stores training session details created by admin
class Session(db.Model):
    __tablename__ = "sessions"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False, default="Training Session")
    session_date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=True)
    location = db.Column(db.String(200), nullable=False)
    capacity = db.Column(db.Integer, nullable=False)
    coach_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    coach = db.relationship("User", foreign_keys=[coach_id])


# links a player to a training session booking
class Booking(db.Model):
    __tablename__ = "bookings"
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("sessions.id"), nullable=False)
    player_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    booked_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), nullable=False, default="booked")
    session = db.relationship("Session", foreign_keys=[session_id])
    player = db.relationship("User", foreign_keys=[player_id])

    # stop same player booking same session more than once
    __table_args__ = (
        db.UniqueConstraint("session_id", "player_id", name="uniq_booking"),
    )


# stores attendance record for each player in a session
class Attendance(db.Model):
    __tablename__ = "attendance"
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("sessions.id"), nullable=False)
    player_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    marked_by_coach_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    status = db.Column(db.String(20), nullable=False)  # present/absent
    marked_at = db.Column(db.DateTime, default=datetime.utcnow)

    # stop duplicate attendance records for same player and session
    __table_args__ = (
        db.UniqueConstraint("session_id", "player_id", name="uniq_attendance"),
    )

# stores news posts shown on the fan site
class News(db.Model):
    __tablename__ = "news"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text, nullable=False)
    published_at = db.Column(db.DateTime, default=datetime.utcnow)

# stores fixture details and match results
class Fixture(db.Model):
    __tablename__ = "fixtures"
    id = db.Column(db.Integer, primary_key=True)
    match_date = db.Column(db.Date, nullable=False)
    opponent = db.Column(db.String(120), nullable=False)
    venue = db.Column(db.String(200), nullable=False)  # example: Home/Away or Stadium
    competition = db.Column(db.String(120), nullable=True)
    poster_image = db.Column(db.String(255), nullable=True)
    
    
    # optional result fields
    opponent_logo = db.Column(db.String(120), nullable=True)
    home_score = db.Column(db.Integer, nullable=True)
    away_score = db.Column(db.Integer, nullable=True)
    is_played = db.Column(db.Boolean, default=False)

# stores messages sent from the public contact form
class ContactMessage(db.Model):
    __tablename__ = "contact_messages"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)