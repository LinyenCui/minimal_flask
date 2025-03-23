# modules/models/trip.py
from modules.models.base import db
from datetime import datetime

class Trip(db.Model):
    __tablename__ = 'trips'
    
    trip_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    fixed_trip_id = db.Column(db.Integer, db.ForeignKey('fixed_schedules.id'), nullable=True)
    week_number = db.Column(db.Integer)
    date = db.Column(db.Date)
    time = db.Column(db.Time)
    start_point = db.Column(db.String(100), db.ForeignKey('customers.short_name'))
    via_point = db.Column(db.String(100), db.ForeignKey('customers.short_name'), nullable=True)
    end_point = db.Column(db.String(100), db.ForeignKey('customers.short_name'))
    meter_fare = db.Column(db.Integer)
    extra_fare = db.Column(db.Integer)
    actual_fare = db.Column(db.Integer)
    category = db.Column(db.String(50))
    driver_id = db.Column(db.Integer, db.ForeignKey('drivers.id'))
    status = db.Column(db.String(20))
    unique_code = db.Column(db.String(50))
    
    # 關聯
    driver = db.relationship('Driver', backref='trips')
    
    def __repr__(self):
        return f"<Trip {self.trip_id} {self.date} {self.time}>"

class FixedSchedule(db.Model):
    __tablename__ = 'fixed_schedules'
    
    id = db.Column(db.Integer, primary_key=True)
    route_number = db.Column(db.String(10))
    departure_time = db.Column(db.Time, nullable=False)
    start_point = db.Column(db.String(100))
    via_point = db.Column(db.String(100), nullable=True)
    end_point = db.Column(db.String(100))
    base_fare = db.Column(db.Integer)
    surcharge = db.Column(db.Integer)
    total_fare = db.Column(db.Integer)
    category = db.Column(db.String(50))
    driver_id = db.Column(db.String(10))
    direction = db.Column(db.String(50))
    
    def __repr__(self):
        return f"<FixedSchedule {self.id} {self.departure_time}>"

class CompletedTrip(db.Model):
    __tablename__ = 'completed_trips'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    date = db.Column(db.Date, nullable=False)
    start_point = db.Column(db.String(100), db.ForeignKey('customers.short_name'))
    via_point = db.Column(db.String(100), db.ForeignKey('customers.short_name'), nullable=True)
    end_point = db.Column(db.String(100), db.ForeignKey('customers.short_name'))
    meter_fare = db.Column(db.Integer)
    extra_fare = db.Column(db.Integer)
    actual_fare = db.Column(db.Integer)
    category = db.Column(db.String(50))
    driver_id = db.Column(db.Integer, db.ForeignKey('drivers.id'))
    remarks = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.now)
    unique_code = db.Column(db.String(50))
    
    # 關聯
    driver = db.relationship('Driver', backref='completed_trips')
    
    def __repr__(self):
        return f"<CompletedTrip {self.id} {self.date}>"
