"""
Authentication Blueprint – register, login, logout.
Uses Flask-WTF for CSRF-protected forms and Flask-Bcrypt for password hashing.
"""

from datetime import datetime
from flask import (Blueprint, render_template, redirect, url_for,
                   flash, request, current_app)
from flask_login import login_user, logout_user, login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import (DataRequired, Email, Length, EqualTo,
                                 ValidationError, Regexp)

from models import db, User

auth_bp = Blueprint("auth", __name__, template_folder="../templates/auth")


# ── Forms ──────────────────────────────────────────────────────────────────────

class RegistrationForm(FlaskForm):
    """New-user registration form."""
    username = StringField(
        "Username",
        validators=[
            DataRequired(),
            Length(min=3, max=64),
            Regexp(r"^[A-Za-z0-9_]+$",
                   message="Username may only contain letters, numbers, and underscores."),
        ],
    )
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=120)])
    password = PasswordField(
        "Password",
        validators=[
            DataRequired(),
            Length(min=8, message="Password must be at least 8 characters."),
            Regexp(
                r"^(?=.*[A-Za-z])(?=.*\d)",
                message="Password must contain at least one letter and one number.",
            ),
        ],
    )
    confirm_password = PasswordField(
        "Confirm Password",
        validators=[DataRequired(), EqualTo("password", message="Passwords must match.")],
    )
    submit = SubmitField("Create Account")

    def validate_username(self, field):
        if User.query.filter_by(username=field.data).first():
            raise ValidationError("Username already taken.")

    def validate_email(self, field):
        if User.query.filter_by(email=field.data.lower()).first():
            raise ValidationError("Email already registered.")


class LoginForm(FlaskForm):
    """Login form."""
    username = StringField("Username", validators=[DataRequired(), Length(max=64)])
    password = PasswordField("Password", validators=[DataRequired()])
    remember = BooleanField("Remember me")
    submit = SubmitField("Sign In")


# ── Routes ─────────────────────────────────────────────────────────────────────

@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    """Handle new user registration."""
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(
            username=form.username.data.strip(),
            email=form.email.data.strip().lower(),
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        current_app.logger.info("New user registered: %s", user.username)
        flash("Account created! You can now log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/register.html", form=form, title="Register")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Handle user login."""
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data.strip()).first()
        if user and user.is_active and user.check_password(form.password.data):
            login_user(user, remember=form.remember.data)
            user.last_login = datetime.utcnow()
            db.session.commit()
            current_app.logger.info("User logged in: %s", user.username)
            next_page = request.args.get("next")
            # Validate next URL to prevent open-redirect
            if next_page and next_page.startswith("/"):
                return redirect(next_page)
            return redirect(url_for("dashboard.index"))
        else:
            flash("Invalid username or password.", "danger")
            current_app.logger.warning("Failed login attempt for: %s",
                                       form.username.data)

    return render_template("auth/login.html", form=form, title="Login")


@auth_bp.route("/logout")
@login_required
def logout():
    """Log out current user."""
    username = current_user.username
    logout_user()
    current_app.logger.info("User logged out: %s", username)
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))
