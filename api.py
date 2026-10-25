"""
REST API Blueprint – JSON endpoints consumed by the frontend JavaScript.

Endpoints:
  POST /api/check-spelling   – spell-check a text payload
  POST /api/auto-correct     – auto-correct a text payload
  POST /api/compress         – compress text or uploaded file
  POST /api/decompress       – decompress an uploaded binary file
  GET  /api/history          – paginated activity history
  GET  /api/stats            – aggregated stats for current user
"""

import io
import json
import zlib
import base64
from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user

from models import db, SpellCheckHistory, CorrectionRecord, CompressionHistory
from utils.spell_utils import check_text, auto_correct, suggestions_for_word
from utils.huffman import huffman_compress, huffman_decompress, compression_stats
from utils.file_utils import allowed_file

api_bp = Blueprint("api", __name__)

MAX_TEXT_LEN = 50_000   # 50 KB character limit for inline text payloads


# ── Helper ─────────────────────────────────────────────────────────────────────

def _error(message: str, status: int = 400):
    return jsonify({"success": False, "error": message}), status


# ── Spell Check ────────────────────────────────────────────────────────────────

@api_bp.route("/check-spelling", methods=["POST"])
@login_required
def check_spelling():
    """
    Body (JSON): {"text": "..."}
    Returns spell-check results and persists a history record.
    """
    data = request.get_json(silent=True) or {}
    text = data.get("text", "").strip()

    if not text:
        return _error("No text provided.")
    if len(text) > MAX_TEXT_LEN:
        return _error(f"Text exceeds maximum length of {MAX_TEXT_LEN} characters.")

    result = check_text(text)

    # Persist
    record = SpellCheckHistory(
        user_id=current_user.id,
        input_text=text[:10000],
        errors_found=result["error_count"],
        word_count=result["word_count"],
        source="manual",
    )
    db.session.add(record)
    db.session.flush()

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

    return jsonify({
        "success":     True,
        "check_id":    record.id,
        "word_count":  result["word_count"],
        "error_count": result["error_count"],
        "errors":      result["errors"],
    })


@api_bp.route("/auto-correct", methods=["POST"])
@login_required
def api_auto_correct():
    """
    Body (JSON): {"text": "...", "check_id": <optional int>}
    Returns corrected text.
    """
    data = request.get_json(silent=True) or {}
    text = data.get("text", "").strip()

    if not text:
        return _error("No text provided.")
    if len(text) > MAX_TEXT_LEN:
        return _error(f"Text exceeds {MAX_TEXT_LEN} characters.")

    corrected, count = auto_correct(text)

    # Optionally update the linked spell-check record
    check_id = data.get("check_id")
    if check_id:
        record = SpellCheckHistory.query.filter_by(
            id=check_id, user_id=current_user.id
        ).first()
        if record:
            record.corrected_text = corrected[:10000]
            record.corrections_made = count
            db.session.commit()

    return jsonify({
        "success":           True,
        "corrected_text":    corrected,
        "corrections_made":  count,
    })


@api_bp.route("/word-suggestions", methods=["POST"])
@login_required
def word_suggestions():
    """
    Body (JSON): {"word": "..."}
    Returns suggestions for a single word.
    """
    data = request.get_json(silent=True) or {}
    word = data.get("word", "").strip()
    if not word:
        return _error("No word provided.")

    result = suggestions_for_word(word)
    return jsonify({"success": True, **result})


# ── Compression ────────────────────────────────────────────────────────────────

@api_bp.route("/compress", methods=["POST"])
@login_required
def api_compress():
    """
    Body (JSON): {"text": "...", "algorithm": "huffman"|"zlib"}
    Returns base64-encoded compressed data + stats.
    """
    data      = request.get_json(silent=True) or {}
    text      = data.get("text", "").strip()
    algorithm = data.get("algorithm", "huffman")

    if not text:
        return _error("No text provided.")
    if len(text) > MAX_TEXT_LEN:
        return _error(f"Text exceeds {MAX_TEXT_LEN} characters.")

    try:
        if algorithm == "zlib":
            compressed = zlib.compress(text.encode("utf-8"), level=9)
        else:
            compressed = huffman_compress(text)
    except Exception as exc:
        current_app.logger.error("API compress error: %s", exc)
        return _error("Compression failed.", 500)

    stats = compression_stats(text, compressed)

    # Persist
    record = CompressionHistory(
        user_id=current_user.id,
        operation="compress",
        algorithm=algorithm,
        original_filename="api_input",
        original_size=stats["original_size"],
        result_size=stats["compressed_size"],
        compression_ratio=stats["compression_ratio"],
        savings_percent=stats["savings_percent"],
        bytes_saved=max(stats["bytes_saved"], 0),
    )
    db.session.add(record)
    db.session.commit()

    return jsonify({
        "success":          True,
        "algorithm":        algorithm,
        "compressed_b64":   base64.b64encode(compressed).decode(),
        **stats,
    })


@api_bp.route("/decompress", methods=["POST"])
@login_required
def api_decompress():
    """
    Body (JSON): {"compressed_b64": "...", "algorithm": "huffman"|"zlib"}
    Returns decompressed text.
    """
    data      = request.get_json(silent=True) or {}
    b64_data  = data.get("compressed_b64", "")
    algorithm = data.get("algorithm", "huffman")

    if not b64_data:
        return _error("No compressed data provided.")

    try:
        raw = base64.b64decode(b64_data)
        if algorithm == "zlib":
            text = zlib.decompress(raw).decode("utf-8")
        else:
            text = huffman_decompress(raw)
    except Exception as exc:
        current_app.logger.error("API decompress error: %s", exc)
        return _error("Decompression failed – invalid or corrupt data.", 400)

    return jsonify({
        "success":            True,
        "decompressed_text":  text,
        "original_size":      len(raw),
        "result_size":        len(text.encode("utf-8")),
    })


# ── History & Stats ────────────────────────────────────────────────────────────

@api_bp.route("/history", methods=["GET"])
@login_required
def api_history():
    """
    Query params: ?type=spell|compress&page=1&per_page=10
    Returns paginated history records.
    """
    rec_type = request.args.get("type", "spell")
    page     = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 10, type=int), 50)

    if rec_type == "compress":
        q = (
            CompressionHistory.query
            .filter_by(user_id=current_user.id)
            .order_by(CompressionHistory.performed_at.desc())
            .paginate(page=page, per_page=per_page, error_out=False)
        )
        items = [
            {
                "id":               r.id,
                "operation":        r.operation,
                "algorithm":        r.algorithm,
                "original_filename": r.original_filename,
                "original_size":    r.original_size,
                "result_size":      r.result_size,
                "compression_ratio": r.compression_ratio,
                "savings_percent":  r.savings_percent,
                "performed_at":     r.performed_at.isoformat(),
            }
            for r in q.items
        ]
        return jsonify({"success": True, "total": q.total,
                        "pages": q.pages, "page": page, "items": items})

    # Default: spell check history
    q = (
        SpellCheckHistory.query
        .filter_by(user_id=current_user.id)
        .order_by(SpellCheckHistory.checked_at.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )
    items = [
        {
            "id":           r.id,
            "word_count":   r.word_count,
            "errors_found": r.errors_found,
            "corrections":  r.corrections_made,
            "source":       r.source,
            "filename":     r.original_filename,
            "checked_at":   r.checked_at.isoformat(),
        }
        for r in q.items
    ]
    return jsonify({"success": True, "total": q.total,
                    "pages": q.pages, "page": page, "items": items})


@api_bp.route("/stats", methods=["GET"])
@login_required
def api_stats():
    """Return aggregated stats for the current user."""
    return jsonify({"success": True, **current_user.get_stats()})


# ── PDF Reports ────────────────────────────────────────────────────────────────

@api_bp.route("/report/spell/<int:check_id>")
@login_required
def spell_report(check_id: int):
    """Generate and stream a PDF spell-check report."""
    import io
    from flask import send_file
    from utils.pdf_report import generate_spell_report

    record = SpellCheckHistory.query.filter_by(
        id=check_id, user_id=current_user.id
    ).first_or_404()
    corrections = record.corrections.all()

    pdf_bytes = generate_spell_report(record, corrections)
    buf = io.BytesIO(pdf_bytes)
    buf.seek(0)
    return send_file(
        buf,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"spell_report_{check_id}.pdf",
    )


@api_bp.route("/report/compression/<int:comp_id>")
@login_required
def compress_report(comp_id: int):
    """Generate and stream a PDF compression report."""
    import io
    from flask import send_file
    from utils.pdf_report import generate_compression_report

    record = CompressionHistory.query.filter_by(
        id=comp_id, user_id=current_user.id
    ).first_or_404()

    pdf_bytes = generate_compression_report(record)
    buf = io.BytesIO(pdf_bytes)
    buf.seek(0)
    return send_file(
        buf,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"compression_report_{comp_id}.pdf",
    )


@api_bp.route("/update-theme", methods=["POST"])
@login_required
def update_theme():
    """Persist dark/light theme preference."""
    from models import db
    data  = request.get_json(silent=True) or {}
    theme = data.get("theme", "light")
    if theme in ("light", "dark"):
        current_user.theme_preference = theme
        db.session.commit()
    return jsonify({"success": True})
