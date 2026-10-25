"""
Text Processing Tool - Main Application Entry Point.
Flask application factory pattern with Blueprints.
"""

import os
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask, render_template
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect

from config import config_map, Config
from models import db, bcrypt, User


# ── Extensions ────────────────────────────────────────────────────────────────
login_manager = LoginManager()
csrf = CSRFProtect()


def create_app(config_name: str = "default") -> Flask:
    """Application factory – creates and configures the Flask app."""

    app = Flask(__name__, template_folder="templates", static_folder="static")

    # ── Load config ──────────────────────────────────────────────────────────
    app.config.from_object(config_map[config_name])

    # Ensure required directories exist
    for folder in [
        app.config["UPLOAD_FOLDER"],
        app.config["REPORTS_FOLDER"],
        app.config["LOGS_FOLDER"],
    ]:
        os.makedirs(folder, exist_ok=True)

    # ── Init extensions ──────────────────────────────────────────────────────
    db.init_app(app)
    bcrypt.init_app(app)
    csrf.init_app(app)

    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please log in to access this page."
    login_manager.login_message_category = "warning"

    # ── User loader ──────────────────────────────────────────────────────────
    @login_manager.user_loader
    def load_user(user_id: str):
        return db.session.get(User, int(user_id))

    # ── Register Blueprints ──────────────────────────────────────────────────
    from blueprints.auth import auth_bp
    from blueprints.dashboard import dashboard_bp
    from blueprints.spell_checker import spell_bp
    from blueprints.compression import compress_bp
    from blueprints.history import history_bp
    from blueprints.profile import profile_bp
    from blueprints.api import api_bp

    app.register_blueprint(auth_bp,        url_prefix="/auth")
    app.register_blueprint(dashboard_bp,   url_prefix="/dashboard")
    app.register_blueprint(spell_bp,       url_prefix="/spell")
    app.register_blueprint(compress_bp,    url_prefix="/compress")
    app.register_blueprint(history_bp,     url_prefix="/history")
    app.register_blueprint(profile_bp,     url_prefix="/profile")
    app.register_blueprint(api_bp,         url_prefix="/api")

    # ── Root routes ──────────────────────────────────────────────────────────
    @app.route("/")
    def index():
        return render_template("index.html")

    # ── Error handlers ───────────────────────────────────────────────────────
    @app.errorhandler(403)
    def forbidden(e):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(413)
    def request_entity_too_large(e):
        return render_template("errors/413.html"), 413

    @app.errorhandler(500)
    def internal_error(e):
        db.session.rollback()
        return render_template("errors/500.html"), 500

    # ── Logging ──────────────────────────────────────────────────────────────
    _setup_logging(app)

    # ── Create DB tables ─────────────────────────────────────────────────────
    with app.app_context():
        db.create_all()
        _seed_admin(app)

    return app


def _setup_logging(app: Flask) -> None:
    """Configure rotating file handler + console handler."""
    log_file = app.config.get("LOG_FILE", "logs/app.log")
    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s in %(module)s: %(message)s"
    )

    # File handler – 5 MB × 5 backups
    file_handler = RotatingFileHandler(log_file, maxBytes=5_242_880, backupCount=5)
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.DEBUG if app.debug else logging.WARNING)

    app.logger.addHandler(file_handler)
    app.logger.addHandler(console_handler)
    app.logger.setLevel(logging.DEBUG if app.debug else logging.INFO)
    app.logger.info("Text Processing Tool starting up.")


def _seed_admin(app: Flask) -> None:
    """Create a default admin account if none exists."""
    admin = User.query.filter_by(role="admin").first()
    if not admin:
        admin = User(
            username="admin",
            email="admin@textool.dev",
            role="admin",
        )
        admin.set_password("Admin@12345")
        db.session.add(admin)
        db.session.commit()
        app.logger.info("Default admin account created (admin / Admin@12345).")


# ── Entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    env = os.environ.get("FLASK_ENV", "development")
    application = create_app(env)
    application.run(host="0.0.0.0", port=5000, debug=(env == "development"))
