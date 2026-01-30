import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from dotenv import load_dotenv


db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = "auth.login"

def create_app():
    load_dotenv()
    app = Flask(__name__)

    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev")

    user = os.getenv("DB_USER")
    pw = os.getenv("DB_PASS")
    host = os.getenv("DB_HOST", "localhost")
    name = os.getenv("DB_NAME")

    app.config["SQLALCHEMY_DATABASE_URI"] = f"mysql+pymysql://{user}:{pw}@{host}/{name}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)
    login_manager.init_app(app)

    # import and register routes
    from .auth import auth_bp
    from .admin import admin_bp
    from .player import player_bp
    from .coach import coach_bp
    from .public import public_bp


    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(player_bp, url_prefix="/player")
    app.register_blueprint(coach_bp, url_prefix="/coach")
    app.register_blueprint(public_bp)


    with app.app_context():
        from . import models
        db.create_all()

    return app
