import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from dotenv import load_dotenv

# database object used across the project
db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = "auth.login"

# handles login sessions
def create_app():
    load_dotenv()

    # create main Flask app
    app = Flask(__name__)

    # basic app settings
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev")
    app.config["UPLOAD_FOLDER"] = os.path.join(app.root_path, "static", "uploads", "profiles")
    app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024  # 2MB max
    
    # get database details from environment variables
    user = os.getenv("DB_USER")
    pw = os.getenv("DB_PASS")
    host = os.getenv("DB_HOST", "localhost")
    name = os.getenv("DB_NAME")

   # use SQLite for hosted version, otherwise use MySQL
    if os.environ.get("USE_SQLITE") == "1":
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///fcms.db"
    else:
        app.config["SQLALCHEMY_DATABASE_URI"] = f"mysql+pymysql://{user}:{pw}@{host}/{name}"

    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # connect database and login manager to the app
    db.init_app(app)
    login_manager.init_app(app)

    # import all blueprints for different parts of the system
    from .auth import auth_bp
    from .admin import admin_bp
    from .player import player_bp
    from .coach import coach_bp
    from .public import public_bp


    # register blueprints with their routes
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(player_bp, url_prefix="/player")
    app.register_blueprint(coach_bp, url_prefix="/coach")
    app.register_blueprint(public_bp)


    with app.app_context():
        # import models and create tables if they do not exist
        from . import models
        db.create_all()

    return app
