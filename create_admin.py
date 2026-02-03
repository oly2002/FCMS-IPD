from app import create_app, db
from app.models import User

app = create_app()

with app.app_context():
    email = "admin@fcms.com"
    existing = User.query.filter_by(email=email).first()
    if existing:
        print("Admin already exists:", email)
    else:
        u = User(
            full_name="Admin User",
            email=email,
            role="admin",
            profile_emoji="🛡️"
        )
        u.set_password("Admin123!")
        db.session.add(u)
        db.session.commit()
        print("Admin created:", email, "Password: Admin123!")
