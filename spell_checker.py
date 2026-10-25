"""
Spell Checker Blueprint – manual text entry and .txt file upload.
Stores results in SpellCheckHistory and CorrectionRecord.
"""

import io
import json
from flask import (Blueprint, render_template, request, flash,
                   redirect, url_for, send_file, current_app)
from flask_login import login_required, current_user

from models import db, SpellCheckHistory, CorrectionRecord, UploadedFile
from utils.spell_utils import check_text, auto_correct
from utils.file_utils import allowed_file, save_upload, read_upload

spell_bp = Blueprint("spell_checker", __name__,
                      template_folder="../templates/spell_checker")


@spell_bp.route("/", methods=["GET", "POST"])
@login_required
def index():
    """Render the spell checker page; handle manual text submission."""
    return render_template("spell_checker/index.html", title="Spell Checker")


@spell_bp.route("/upload", methods=["POST"])
@login_required
def upload_file():
    """Handle .txt file upload and redirect to check results."""
    if "file" not in request.files:
        flash("No file selected.", "warning")
        return redirect(url_for("spell_checker.index"))

    file = request.files["file"]
    if not file or not file.filename:
        flash("No file selected.", "warning")
        return redirect(url_for("spell_checker.index"))

    if not allowed_file(file.filename):
        flash("Only .txt files are allowed.", "danger")
        return redirect(url_for("spell_checker.index"))

    try:
        orig_name, stored_name, file_size = save_upload(file)
        text = read_upload(stored_name)

        # Record file upload
        upload_rec = UploadedFile(
            user_id=current_user.id,
            original_filename=orig_name,
            stored_filename=stored_name,
            file_size=file_size,
        )
        db.session.add(upload_rec)
        db.session.flush()

        result = check_text(text)
        _persist_spell_check(text, result, source="file",
                             original_filename=orig_name)
        flash(f"File '{orig_name}' checked – {result['error_count']} error(s) found.",
              "success" if result["error_count"] == 0 else "warning")
    except Exception as exc:
        current_app.logger.error("File upload spell-check error: %s", exc)
        flash("An error occurred while processing your file.", "danger")

    return redirect(url_for("spell_checker.index"))


@spell_bp.route("/download-corrected", methods=["POST"])
@login_required
def download_corrected():
    """Return the auto-corrected text as a downloadable .txt file."""
    text = request.form.get("text", "")
    if not text.strip():
        flash("No text to download.", "warning")
        return redirect(url_for("spell_checker.index"))

    corrected, _ = auto_correct(text)
    buf = io.BytesIO(corrected.encode("utf-8"))
    buf.seek(0)
    return send_file(
        buf,
        mimetype="text/plain",
        as_attachment=True,
        download_name="corrected_text.txt",
    )


# ── Internal helper ────────────────────────────────────────────────────────────

def _persist_spell_check(text: str, result: dict,
                          source: str = "manual",
                          original_filename: str = None) -> SpellCheckHistory:
    """Save a spell-check session and its individual corrections to the DB."""
    record = SpellCheckHistory(
        user_id=current_user.id,
        input_text=text[:10000],   # cap stored text at 10 KB
        errors_found=result["error_count"],
        word_count=result["word_count"],
        source=source,
        original_filename=original_filename,
    )
    db.session.add(record)
    db.session.flush()   # get record.id

    for err in result["errors"]:
        corr = CorrectionRecord(
            spell_check_id=record.id,
            original_word=err["word"],
            corrected_word=err.get("best"),
            suggestions=json.dumps(err.get("suggestions", [])),
            confidence=err.get("confidence"),
            was_corrected=False,
        )
        db.session.add(corr)

    db.session.commit()
    return record
