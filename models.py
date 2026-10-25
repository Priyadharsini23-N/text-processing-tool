"""
Database models for Text Processing Tool.
Uses SQLAlchemy ORM with SQLite backend.
"""

from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from flask_bcrypt import Bcrypt

db = SQLAlchemy()
bcrypt = Bcrypt()


class User(UserMixin, db.Model):
    """User account model with hashed password storage."""
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="user")  # 'user' or 'admin'
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    theme_preference = db.Column(db.String(10), default="light")  # 'light' or 'dark'
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    last_login = db.Column(db.DateTime, nullable=True)

    # Relationships
    uploaded_files = db.relationship("UploadedFile", backref="owner", lazy="dynamic",
                                     cascade="all, delete-orphan")
    spell_checks = db.relationship("SpellCheckHistory", backref="user", lazy="dynamic",
                                   cascade="all, delete-orphan")
    compressions = db.relationship("CompressionHistory", backref="user", lazy="dynamic",
                                   cascade="all, delete-orphan")

    def set_password(self, password: str) -> None:
        """Hash and store password."""
        self.password_hash = bcrypt.generate_password_hash(password).decode("utf-8")

    def check_password(self, password: str) -> bool:
        """Verify plain-text password against stored hash."""
        return bcrypt.check_password_hash(self.password_hash, password)

    def is_admin(self) -> bool:
        """Return True if user has admin role."""
        return self.role == "admin"

    def get_stats(self) -> dict:
        """Return aggregated usage statistics for this user."""
        total_checks = self.spell_checks.count()
        total_compressions = self.compressions.count()
        total_errors_found = db.session.query(
            db.func.sum(SpellCheckHistory.errors_found)
        ).filter_by(user_id=self.id).scalar() or 0
        total_corrections = db.session.query(
            db.func.sum(SpellCheckHistory.corrections_made)
        ).filter_by(user_id=self.id).scalar() or 0
        total_bytes_saved = db.session.query(
            db.func.sum(CompressionHistory.bytes_saved)
        ).filter_by(user_id=self.id).scalar() or 0
        return {
            "total_checks": total_checks,
            "total_compressions": total_compressions,
            "total_errors_found": total_errors_found,
            "total_corrections": total_corrections,
            "total_bytes_saved": total_bytes_saved,
        }

    def __repr__(self) -> str:
        return f"<User {self.username}>"


class UploadedFile(db.Model):
    """Tracks files uploaded by users."""
    __tablename__ = "uploaded_files"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    original_filename = db.Column(db.String(256), nullable=False)
    stored_filename = db.Column(db.String(256), nullable=False)
    file_size = db.Column(db.Integer, nullable=False)  # bytes
    file_type = db.Column(db.String(20), default="txt")
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<UploadedFile {self.original_filename}>"


class SpellCheckHistory(db.Model):
    """Records each spell-check session."""
    __tablename__ = "spell_check_history"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    input_text = db.Column(db.Text, nullable=False)
    corrected_text = db.Column(db.Text, nullable=True)
    errors_found = db.Column(db.Integer, default=0)
    corrections_made = db.Column(db.Integer, default=0)
    word_count = db.Column(db.Integer, default=0)
    source = db.Column(db.String(20), default="manual")  # 'manual' or 'file'
    original_filename = db.Column(db.String(256), nullable=True)
    checked_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Child corrections
    corrections = db.relationship("CorrectionRecord", backref="spell_check",
                                  lazy="dynamic", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<SpellCheck id={self.id} errors={self.errors_found}>"


class CorrectionRecord(db.Model):
    """Individual word correction within a spell-check session."""
    __tablename__ = "correction_records"

    id = db.Column(db.Integer, primary_key=True)
    spell_check_id = db.Column(db.Integer, db.ForeignKey("spell_check_history.id"),
                               nullable=False)
    original_word = db.Column(db.String(100), nullable=False)
    corrected_word = db.Column(db.String(100), nullable=True)
    suggestions = db.Column(db.Text, nullable=True)   # JSON-encoded list
    was_corrected = db.Column(db.Boolean, default=False)
    confidence = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<Correction {self.original_word} -> {self.corrected_word}>"


class CompressionHistory(db.Model):
    """Records each compression/decompression operation."""
    __tablename__ = "compression_history"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    operation = db.Column(db.String(20), nullable=False)   # 'compress' or 'decompress'
    algorithm = db.Column(db.String(20), default="huffman")  # 'huffman' or 'zlib'
    original_filename = db.Column(db.String(256), nullable=True)
    original_size = db.Column(db.Integer, nullable=False)   # bytes
    result_size = db.Column(db.Integer, nullable=False)     # bytes
    compression_ratio = db.Column(db.Float, nullable=True)
    savings_percent = db.Column(db.Float, nullable=True)
    bytes_saved = db.Column(db.Integer, default=0)
    performed_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<Compression {self.operation} ratio={self.compression_ratio:.2f}>"
