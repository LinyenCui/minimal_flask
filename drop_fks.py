from flask import Flask
from modules.models.base import db
from modules.config import DATABASE_URL
from sqlalchemy import text

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

def drop_foreign_keys():
    with app.app_context():
        queries = [
            "ALTER TABLE trips DROP CONSTRAINT trips_start_point_fkey;",
            "ALTER TABLE trips DROP CONSTRAINT trips_via_point_fkey;",
            "ALTER TABLE trips DROP CONSTRAINT trips_end_point_fkey;",
            "ALTER TABLE completed_trips DROP CONSTRAINT completed_trips_start_point_fkey;",
            "ALTER TABLE completed_trips DROP CONSTRAINT completed_trips_via_point_fkey;",
            "ALTER TABLE completed_trips DROP CONSTRAINT completed_trips_end_point_fkey;",
            "ALTER TABLE fixed_schedules DROP CONSTRAINT fixed_schedules_start_point_fkey;",
            "ALTER TABLE fixed_schedules DROP CONSTRAINT fixed_schedules_via_point_fkey;",
            "ALTER TABLE fixed_schedules DROP CONSTRAINT fixed_schedules_end_point_fkey;"
        ]
        
        for q in queries:
            try:
                db.session.execute(text(q))
                db.session.commit()
                print(f"Executed: {q}")
            except Exception as e:
                db.session.rollback()
                print(f"Skipped {q} or does not exist: {e}")

if __name__ == '__main__':
    drop_foreign_keys()
