from flask import Flask
from modules.models.base import db
from modules.config import DATABASE_URL
from sqlalchemy import text

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

def create_unique_constraints():
    with app.app_context():
        # First, remove any duplicates if they exist, but usually unique_code should be unique
        
        queries = [
            "ALTER TABLE completed_trips ADD CONSTRAINT uk_completed_trips_unique_code UNIQUE (unique_code);"
        ]
        
        for q in queries:
            try:
                db.session.execute(text(q))
                db.session.commit()
                print(f"Executed: {q}")
            except Exception as e:
                db.session.rollback()
                print(f"Skipped {q} or failed: {e}")

if __name__ == '__main__':
    create_unique_constraints()
