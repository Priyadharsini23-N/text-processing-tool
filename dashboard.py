"""
Dashboard Blueprint – main user landing page after login.
Displays usage statistics and recent activity.
"""

from flask import Blueprint, render_template
from flask_login import login_required, current_user

from models import db, SpellCheckHistory, CompressionHistory

dashboard_bp = Blueprint("dashboard", __name__,
                          template_folder="../templates/dashboard")


@dashboard_bp.route("/")
@login_required
def index():
    """Render the personalised dashboard."""
    stats = current_user.get_stats()

    # Recent activity (last 5 of each)
    recent_checks = (
        SpellCheckHistory.query
        .filter_by(user_id=current_user.id)
        .order_by(SpellCheckHistory.checked_at.desc())
        .limit(5).all()
    )
    recent_compressions = (
        CompressionHistory.query
        .filter_by(user_id=current_user.id)
        .order_by(CompressionHistory.performed_at.desc())
        .limit(5).all()
    )

    return render_template(
        "dashboard/index.html",
        title="Dashboard",
        stats=stats,
        recent_checks=recent_checks,
        recent_compressions=recent_compressions,
    )
