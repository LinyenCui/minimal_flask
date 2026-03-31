import os
from flask import Flask
from modules.models.base import db
from modules.config import DATABASE_URL
from sqlalchemy import text

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

def fix_schema():
    with app.app_context():
        # Add columns to trips if missing
        try:
            db.session.execute(text("ALTER TABLE trips ADD COLUMN passenger_leave_reason TEXT;"))
            db.session.commit()
            print("Added passenger_leave_reason to trips")
        except Exception as e:
            db.session.rollback()
            print(f"trips passenger_leave_reason exists: {e}")
            
        try:
            db.session.execute(text("ALTER TABLE trips ADD COLUMN trip_type VARCHAR(20) DEFAULT 'fixed';"))
            db.session.commit()
            print("Added trip_type to trips")
        except Exception as e:
            db.session.rollback()
            print(f"trips trip_type exists: {e}")

        # Add columns to completed_trips if missing
        try:
            db.session.execute(text("ALTER TABLE completed_trips ADD COLUMN passenger_leave_reason TEXT;"))
            db.session.commit()
            print("Added passenger_leave_reason to completed_trips")
        except Exception as e:
            db.session.rollback()
            print(f"completed_trips passenger_leave_reason exists: {e}")
            
        try:
            db.session.execute(text("ALTER TABLE completed_trips ADD COLUMN trip_type VARCHAR(20);"))
            db.session.commit()
            print("Added trip_type to completed_trips")
        except Exception as e:
            db.session.rollback()
            print(f"completed_trips trip_type exists: {e}")

if __name__ == "__main__":
    fix_schema()
    print("Schema fix done.")
