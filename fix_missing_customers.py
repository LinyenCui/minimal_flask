from flask import Flask
from modules.models.base import db
from modules.config import DATABASE_URL
from modules.models.models import Customer
from modules.models.trip import FixedSchedule, Trip, CompletedTrip

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

def restore_missing_customers():
    with app.app_context():
        # Collect all unique locations used anywhere
        locations = set()
        
        print("Collecting locations from FixedSchedule...")
        for fs in db.session.query(FixedSchedule).all():
            if fs.start_point: locations.add(fs.start_point)
            if fs.via_point: locations.add(fs.via_point)
            if fs.end_point: locations.add(fs.end_point)
            
        print("Collecting locations from Trip...")
        for t in db.session.query(Trip).all():
            if t.start_point: locations.add(t.start_point)
            if t.via_point: locations.add(t.via_point)
            if t.end_point: locations.add(t.end_point)
            
        print("Collecting locations from CompletedTrip...")
        for ct in db.session.query(CompletedTrip).all():
            if ct.start_point: locations.add(ct.start_point)
            if ct.via_point: locations.add(ct.via_point)
            if ct.end_point: locations.add(ct.end_point)

        # Check existing customers
        existing = set([c.short_name for c in db.session.query(Customer).all() if c.short_name])
        
        # Find missing
        missing = locations - existing
        
        print(f"Found {len(missing)} missing customer locations. Inserting...")
        
        from sqlalchemy import func
        max_id = db.session.query(func.max(Customer.id)).scalar() or 0
        
        for i, loc in enumerate(missing, 1):
            if loc:
                new_cust = Customer(
                    id=max_id + i,
                    name=loc,
                    short_name=loc,
                    address='(系統自動復原)',
                    category='未分類'
                )
                db.session.add(new_cust)
                print(f"Added missing customer location: {loc} with ID {max_id + i}")
        
        try:
            db.session.commit()
            print("Successfully restored missing customers.")
        except Exception as e:
            db.session.rollback()
            print(f"Error saving missing customers: {e}")

if __name__ == "__main__":
    restore_missing_customers()
