from flask import Flask
from modules.models.base import db
from modules.config import DATABASE_URL
from modules.models.models import Customer
from sqlalchemy import text

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

def restore_placeholder_customers():
    with app.app_context():
        temp_locs = ['臨時地點']
        for loc in temp_locs:
            existing = db.session.query(Customer).filter_by(short_name=loc).first()
            if not existing:
                try:
                    # Execute raw SQL or use SQLAlchemy since we might have sequence drift
                    db.session.execute(text("SELECT setval('customers_id_seq', (SELECT MAX(id) FROM customers) + 1)"))
                    max_id = db.session.execute(text("SELECT MAX(id) FROM customers")).scalar() or 0
                    
                    new_cust = Customer(
                        id=max_id + 1,
                        name=f"({loc})",
                        short_name=loc,
                        address='(系統自動復原)',
                        category='系統專用'
                    )
                    db.session.add(new_cust)
                    db.session.commit()
                    print(f"✅ Successfully restored placeholder customer: {loc}")
                except Exception as e:
                    db.session.rollback()
                    print(f"❌ Failed to restore {loc}: {e}")
            else:
                print(f"ℹ️ Placeholder {loc} already exists.")

if __name__ == '__main__':
    restore_placeholder_customers()
