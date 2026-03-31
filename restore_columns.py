from flask import Flask
from modules.models.base import db
from modules.config import DATABASE_URL
from sqlalchemy import text

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

def restore_missing_columns():
    with app.app_context():
        # Columns to add to trips
        trip_cols = [
            "custom_start_point VARCHAR(100)",
            "custom_via_point VARCHAR(100)",
            "custom_end_point VARCHAR(100)",
            "modified_by TEXT",
            "modification_reason TEXT",
            "modification_time TIMESTAMP WITHOUT TIME ZONE",
            "passenger_name TEXT"
        ]
        
        for col in trip_cols:
            query = f"ALTER TABLE trips ADD COLUMN IF NOT EXISTS {col};"
            try:
                db.session.execute(text(query))
                db.session.commit()
                print(f"Executed: {query}")
            except Exception as e:
                db.session.rollback()
                print(f"Skipped {query}: {e}")

        # Columns to add to completed_trips
        ct_cols = [
            "status VARCHAR(20)",
            "modified_by TEXT",
            "modification_reason TEXT",
            "modification_time TIMESTAMP WITHOUT TIME ZONE",
            "passenger_name TEXT"
        ]
        
        for col in ct_cols:
            query = f"ALTER TABLE completed_trips ADD COLUMN IF NOT EXISTS {col};"
            try:
                db.session.execute(text(query))
                db.session.commit()
                print(f"Executed: {query}")
            except Exception as e:
                db.session.rollback()
                print(f"Skipped {query}: {e}")

        # Re-add foreign key constraints to start_point and end_point
        fks = [
            "ALTER TABLE trips ADD CONSTRAINT trips_start_point_fkey FOREIGN KEY (start_point) REFERENCES customers(short_name);",
            "ALTER TABLE trips ADD CONSTRAINT trips_end_point_fkey FOREIGN KEY (end_point) REFERENCES customers(short_name);",
            "ALTER TABLE completed_trips ADD CONSTRAINT completed_trips_start_point_fkey FOREIGN KEY (start_point) REFERENCES customers(short_name);",
            "ALTER TABLE completed_trips ADD CONSTRAINT completed_trips_end_point_fkey FOREIGN KEY (end_point) REFERENCES customers(short_name);"
        ]

        for query in fks:
            try:
                db.session.execute(text(query))
                db.session.commit()
                print(f"Executed Constraint: {query}")
            except Exception as e:
                db.session.rollback()
                print(f"Skipped Constraint {query}: {e}")

if __name__ == '__main__':
    restore_missing_columns()
