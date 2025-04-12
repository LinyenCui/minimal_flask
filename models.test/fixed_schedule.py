from models import db

class FixedSchedule(db.Model):
    __tablename__ = 'fixed_schedules'
    
    id = db.Column(db.Integer, primary_key=True)
    route_number = db.Column(db.String(10))
    departure_time = db.Column(db.Time, nullable=False)
    start_point = db.Column(db.String(100))
    via_point = db.Column(db.String(100))
    end_point = db.Column(db.String(100))
    base_fare = db.Column(db.Integer)
    surcharge = db.Column(db.Integer)
    total_fare = db.Column(db.Integer)
    category = db.Column(db.String(50))
    driver_id = db.Column(db.String(10))
    
    def __repr__(self):
        return f"<FixedSchedule {self.id} {self.route_number} {self.departure_time}>" 