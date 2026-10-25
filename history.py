"""
History Blueprint – paginated view of all user activities.
"""

from flask import Blueprint, render_template, request
from flask_login import login_required, current_user

from models import SpellCheckHistory, CompressionHistory
from config import Config

history_bp = Blueprint("history", __name__,
                        template_folder="../templates/history")

PER_PAGE = Config.ITEMS_PER_PAGE


@history_bp.route("/")
@login_required
def index():
    """Unified history page with spell-check and compression tabs."""
    spell_page = request.args.get("spell_page", 1, type=int)
    comp_page  = request.args.get("comp_page",  1, type=int)

    spell_history = (
        SpellCheckHistory.query
        .filter_by(user_id=current_user.id)
        .order_by(SpellCheckHistory.checked_at.desc())
        .paginate(page=spell_page, per_page=PER_PAGE, error_out=False)
    )
    comp_history = (
        CompressionHistory.query
        .filter_by(user_id=current_user.id)
        .order_by(CompressionHistory.performed_at.desc())
        .paginate(page=comp_page, per_page=PER_PAGE, error_out=False)
    )

    return render_template(
        "history/index.html",
        title="History",
        spell_history=spell_history,
        comp_history=comp_history,
    )


@history_bp.route("/spell/<int:check_id>")
@login_required
def spell_detail(check_id: int):
    """Show full detail for a single spell-check record."""
    record = SpellCheckHistory.query.filter_by(
        id=check_id, user_id=current_user.id
    ).first_or_404()
    corrections = record.corrections.all()
    return render_template(
        "history/spell_detail.html",
        title="Spell Check Detail",
        record=record,
        corrections=corrections,
    )


@history_bp.route("/compression/<int:comp_id>")
@login_required
def compression_detail(comp_id: int):
    """Show full detail for a single compression record."""
    record = CompressionHistory.query.filter_by(
        id=comp_id, user_id=current_user.id
    ).first_or_404()
    return render_template(
        "history/compression_detail.html",
        title="Compression Detail",
        record=record,
    )
