from flask import Flask
from modules.models.base import db
from modules.config import DATABASE_URL
from modules.services.scheduler_service import update_completed_trips

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

def run_job():
    with app.app_context():
        import logging
        logging.basicConfig(level=logging.INFO)
        result = update_completed_trips()
        print(f"Result: {result}")

if __name__ == '__main__':
    run_job()
