"""
Run once to create the default admin user:
  python seed_admin.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from backend.database import SessionLocal, engine, Base
from backend.models.db import User
from backend.utils.auth import hash_password

Base.metadata.create_all(bind=engine)

db = SessionLocal()
try:
    if db.query(User).filter_by(email="admin@atm-sentinel.local").first():
        print("Admin already exists.")
    else:
        admin = User(
            email="admin@atm-sentinel.local",
            full_name="System Admin",
            password_hash=hash_password("Admin@1234"),
            role="admin",
            is_active=True,
        )
        db.add(admin)
        db.commit()
        print("Admin created:")
        print("  Email:    admin@atm-sentinel.local")
        print("  Password: Admin@1234")
        print("  Role:     admin")
        print("\nChange the password immediately after first login.")
finally:
    db.close()
