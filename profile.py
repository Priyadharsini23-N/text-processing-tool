"""
Profile Blueprint – view/update account information and preferences.
"""

from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SelectField, SubmitField
from wtforms.validators import (DataRequired, Email, Length, EqualTo,
                                 Optional, ValidationError, Regexp)

from models import db, User

profile_bp = Blueprint("profile", __name__,
                        template_folder="../templates/profile")


# ── Forms ──────────────────────────────────────────────────────────────────────

class ProfileForm(FlaskForm):
    """Update display name / email."""
    username = StringField(
        "Username",
        validators=[
            DataRequired(),
            Length(min=3, max=64),
            Regexp(r"^[A-Za-z0-9_]+$",
                   message="Only letters, numbers, and underscores allowed."),
        ],
    )
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=120)])
    theme = SelectField("Theme", choices=[("light", "Light"), ("dark", "Dark")])
    submit = SubmitField("Save Changes")

    def __init__(self, original_username, original_email, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._original_username = original_username
        self._original_email = original_email

    def validate_username(self, field):
        if field.data != self._original_username:
            if User.query.filter_by(username=field.data).first():
                raise ValidationError("Username already taken.")

    def validate_email(self, field):
        if field.data.lower() != self._original_email:
            if User.query.filter_by(email=field.data.lower()).first():
                raise ValidationError("Email already registered.")


class ChangePasswordForm(FlaskForm):
    """Change account password."""
    current_password = PasswordField("Current Password", validators=[DataRequired()])
    new_password = PasswordField(
        "New Password",
        validators=[
            DataRequired(),
            Length(min=8),
            Regexp(r"^(?=.*[A-Za-z])(?=.*\d)",
                   message="Must contain at least one letter and one number."),
        ],
    )
    confirm_password = PasswordField(
        "Confirm New Password",
        validators=[DataRequired(), EqualTo("new_password", message="Passwords must match.")],
    )
    submit = SubmitField("Change Password")


# ── Routes ─────────────────────────────────────────────────────────────────────

@profile_bp.route("/", methods=["GET", "POST"])
@login_required
def index():
    """View and update profile details."""
    form = ProfileForm(
        original_username=current_user.username,
        original_email=current_user.email,
        obj=current_user,
    )
    pw_form = ChangePasswordForm()

    if form.validate_on_submit() and "save_profile" in request.form:
        current_user.username = form.username.data.strip()
        current_user.email = form.email.data.strip().lower()
        current_user.theme_preference = form.theme.data
        db.session.commit()
        flash("Profile updated successfully.", "success")
        return redirect(url_for("profile.index"))

    return render_template(
        "profile/index.html",
        title="My Profile",
        form=form,
        pw_form=pw_form,
        stats=current_user.get_stats(),
    )


@profile_bp.route("/change-password", methods=["POST"])
@login_required
def change_password():
    """Handle password change form submission."""
    pw_form = ChangePasswordForm()
    if pw_form.validate_on_submit():
        if not current_user.check_password(pw_form.current_password.data):
            flash("Current password is incorrect.", "danger")
        else:
            current_user.set_password(pw_form.new_password.data)
            db.session.commit()
            flash("Password changed successfully.", "success")
    else:
        for field, errors in pw_form.errors.items():
            for error in errors:
                flash(f"{field}: {error}", "danger")

    return redirect(url_for("profile.index"))
