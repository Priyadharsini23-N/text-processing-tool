"""
Compression Blueprint – compress / decompress text files using
Huffman coding (custom) and zlib as a fallback option.
"""

import io
import zlib
from flask import (Blueprint, render_template, request, flash,
                   redirect, url_for, send_file, current_app)
from flask_login import login_required, current_user

from models import db, CompressionHistory, UploadedFile
from utils.huffman import huffman_compress, huffman_decompress, compression_stats
from utils.file_utils import allowed_file, save_upload, read_upload

compress_bp = Blueprint("compression", __name__,
                         template_folder="../templates/compression")


@compress_bp.route("/")
@login_required
def index():
    """Render the compression page."""
    return render_template("compression/index.html", title="Compression")


@compress_bp.route("/compress", methods=["POST"])
@login_required
def compress():
    """Handle compression request (Huffman or zlib)."""
    algorithm = request.form.get("algorithm", "huffman")
    source     = request.form.get("source", "file")   # 'file' or 'text'

    text = ""
    orig_filename = None

    if source == "text":
        text = request.form.get("text", "").strip()
        if not text:
            flash("Please enter some text to compress.", "warning")
            return redirect(url_for("compression.index"))
        orig_filename = "manual_input.txt"
    else:
        if "file" not in request.files or not request.files["file"].filename:
            flash("Please select a .txt file.", "warning")
            return redirect(url_for("compression.index"))
        file = request.files["file"]
        if not allowed_file(file.filename):
            flash("Only .txt files are allowed.", "danger")
            return redirect(url_for("compression.index"))
        try:
            orig_name, stored_name, _ = save_upload(file)
            text = read_upload(stored_name)
            orig_filename = orig_name
        except Exception as exc:
            current_app.logger.error("Compression file read error: %s", exc)
            flash("Failed to read the uploaded file.", "danger")
            return redirect(url_for("compression.index"))

    # Perform compression
    try:
        if algorithm == "zlib":
            encoded      = text.encode("utf-8")
            compressed   = zlib.compress(encoded, level=9)
            stats        = compression_stats(text, compressed)
        else:
            compressed   = huffman_compress(text)
            stats        = compression_stats(text, compressed)
    except Exception as exc:
        current_app.logger.error("Compression error: %s", exc)
        flash("Compression failed. Please try again.", "danger")
        return redirect(url_for("compression.index"))

    # Persist history
    _persist_compression(
        operation="compress",
        algorithm=algorithm,
        orig_filename=orig_filename,
        stats=stats,
    )

    # Stream compressed bytes for download
    buf = io.BytesIO(compressed)
    buf.seek(0)
    ext = "zlib" if algorithm == "zlib" else "huff"
    dl_name = f"compressed.{ext}"
    flash(
        f"Compressed! {stats['original_size']} B → {stats['compressed_size']} B "
        f"({stats['savings_percent']}% saved)",
        "success",
    )
    return send_file(buf, mimetype="application/octet-stream",
                     as_attachment=True, download_name=dl_name)


@compress_bp.route("/decompress", methods=["POST"])
@login_required
def decompress():
    """Handle decompression request."""
    algorithm = request.form.get("algorithm", "huffman")

    if "file" not in request.files or not request.files["file"].filename:
        flash("Please upload a compressed file.", "warning")
        return redirect(url_for("compression.index"))

    file = request.files["file"]
    raw_bytes = file.read()
    orig_filename = file.filename

    try:
        if algorithm == "zlib":
            decompressed_bytes = zlib.decompress(raw_bytes)
            text = decompressed_bytes.decode("utf-8")
        else:
            text = huffman_decompress(raw_bytes)
    except Exception as exc:
        current_app.logger.error("Decompression error: %s", exc)
        flash("Decompression failed – the file may be corrupt or use a different format.",
              "danger")
        return redirect(url_for("compression.index"))

    orig_size   = len(raw_bytes)
    result_size = len(text.encode("utf-8"))
    ratio       = round(result_size / orig_size, 4) if orig_size else 1.0

    _persist_compression(
        operation="decompress",
        algorithm=algorithm,
        orig_filename=orig_filename,
        stats={
            "original_size":   orig_size,
            "compressed_size": result_size,
            "bytes_saved":     0,
            "compression_ratio": ratio,
            "savings_percent": 0.0,
        },
    )

    buf = io.BytesIO(text.encode("utf-8"))
    buf.seek(0)
    flash("Decompressed successfully!", "success")
    return send_file(buf, mimetype="text/plain",
                     as_attachment=True, download_name="decompressed.txt")


# ── Internal helper ────────────────────────────────────────────────────────────

def _persist_compression(operation: str, algorithm: str,
                          orig_filename: str, stats: dict) -> None:
    """Save compression/decompression operation to the database."""
    saved = stats.get("bytes_saved", 0)
    record = CompressionHistory(
        user_id=current_user.id,
        operation=operation,
        algorithm=algorithm,
        original_filename=orig_filename,
        original_size=stats["original_size"],
        result_size=stats["compressed_size"],
        compression_ratio=stats["compression_ratio"],
        savings_percent=stats["savings_percent"],
        bytes_saved=max(saved, 0),
    )
    db.session.add(record)
    db.session.commit()
