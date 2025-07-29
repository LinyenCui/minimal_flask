from models import db

class FixedTrip(db.Model):
    __tablename__ = 'fixed_trips'
    
    fixed_trip_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    cycle = db.Column(db.String(30))  # 周期，如"monday,wednesday,friday"
    time = db.Column(db.Time, nullable=False)
    start_point = db.Column(db.String(30))
    via_point = db.Column(db.String(30), nullable=True)
    end_point = db.Column(db.String(30))
    meter_fare = db.Column(db.Integer, nullable=True)
    extra_fare = db.Column(db.Integer, nullable=True)
    actual_fare = db.Column(db.Integer, nullable=True)
    category = db.Column(db.String(30))
    driver_id = db.Column(db.Integer, db.ForeignKey('drivers.id'), nullable=True)
    
    def __repr__(self):
        return f"<FixedTrip {self.fixed_trip_id} {self.cycle} {self.time}>" 