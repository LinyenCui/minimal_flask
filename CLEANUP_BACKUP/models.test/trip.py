from models import db

class Trip(db.Model):
    __tablename__ = 'trips'
    
    trip_id = db.Column(db.Integer, primary_key=True)
    fixed_trip_id = db.Column(db.Integer, db.ForeignKey('fixed_schedules.id'))
    week_number = db.Column(db.Integer)
    date = db.Column(db.Date)
    time = db.Column(db.Time)
    start_point = db.Column(db.String(100), db.ForeignKey('customers.short_name'))
    via_point = db.Column(db.String(100), db.ForeignKey('customers.short_name'))
    end_point = db.Column(db.String(100), db.ForeignKey('customers.short_name'))
    meter_fare = db.Column(db.Integer)
    extra_fare = db.Column(db.Integer)
    actual_fare = db.Column(db.Integer)
    category = db.Column(db.String(50))
    driver_id = db.Column(db.Integer, db.ForeignKey('drivers.id'))
    status = db.Column(db.String(20))
    
    # 關聯
    fixed_schedule = db.relationship('FixedSchedule', foreign_keys=[fixed_trip_id])
    start = db.relationship('Customer', foreign_keys=[start_point])
    via = db.relationship('Customer', foreign_keys=[via_point])
    end = db.relationship('Customer', foreign_keys=[end_point])
    driver = db.relationship('Driver', foreign_keys=[driver_id])
    
    def __repr__(self):
        return f"<Trip {self.trip_id} {self.date} {self.time}>" 