"""
Database initialisation script.
Run once to create all tables and seed sample data.

Usage:
    python init_db.py
"""

from app import create_app
from models import db, User, SpellCheckHistory, CorrectionRecord, CompressionHistory
import json
from datetime import datetime, timedelta
import random


def seed_sample_data(app):
    """Insert demo user and sample activity records."""
    with app.app_context():
        # ── Demo user ──────────────────────────────────────────────────────
        demo = User.query.filter_by(username="demo").first()
        if not demo:
            demo = User(
                username="demo",
                email="demo@textool.dev",
                role="user",
            )
            demo.set_password("Demo@12345")
            db.session.add(demo)
            db.session.flush()
            print("Created demo user  (demo / Demo@12345)")

        # ── Sample spell checks ────────────────────────────────────────────
        if SpellCheckHistory.query.filter_by(user_id=demo.id).count() == 0:
            sample_texts = [
                ("The quick brown fox jumpd over the lazy dog.", 1),
                ("She recieved a beautifull gift from her frend.", 3),
                ("This is a perfectly correct sentence.", 0),
            ]
            for i, (text, err_count) in enumerate(sample_texts):
                rec = SpellCheckHistory(
                    user_id=demo.id,
                    input_text=text,
                    word_count=len(text.split()),
                    errors_found=err_count,
                    corrections_made=err_count,
                    source="manual",
                    checked_at=datetime.utcnow() - timedelta(days=i),
                )
                db.session.add(rec)
            print("Inserted 3 sample spell-check records.")

        # ── Sample compressions ────────────────────────────────────────────
        if CompressionHistory.query.filter_by(user_id=demo.id).count() == 0:
            for i in range(4):
                orig = random.randint(5000, 50000)
                saved = int(orig * random.uniform(0.25, 0.55))
                comp  = orig - saved
                rec = CompressionHistory(
                    user_id=demo.id,
                    operation="compress",
                    algorithm=random.choice(["huffman", "zlib"]),
                    original_filename=f"sample_{i+1}.txt",
                    original_size=orig,
                    result_size=comp,
                    compression_ratio=round(comp / orig, 4),
                    savings_percent=round(saved / orig * 100, 2),
                    bytes_saved=saved,
                    performed_at=datetime.utcnow() - timedelta(days=i),
                )
                db.session.add(rec)
            print("Inserted 4 sample compression records.")

        db.session.commit()
        print("Sample data committed.")


if __name__ == "__main__":
    app = create_app("development")
    with app.app_context():
        db.create_all()
        print("All database tables created.")
    seed_sample_data(app)
    print("\n✅ Database initialised successfully.")
    print("   Admin login : admin / Admin@12345")
    print("   Demo login  : demo  / Demo@12345")
