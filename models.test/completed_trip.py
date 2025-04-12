from models import db
from datetime import datetime

class CompletedTrip(db.Model):
    __tablename__ = 'completed_trips'
    
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    start_point = db.Column(db.String(100), db.ForeignKey('customers.short_name'))
    via_point = db.Column(db.String(100), db.ForeignKey('customers.short_name'))
    end_point = db.Column(db.String(100), db.ForeignKey('customers.short_name'))
    meter_fare = db.Column(db.Integer)
    extra_fare = db.Column(db.Integer)
    actual_fare = db.Column(db.Integer)
    category = db.Column(db.String(50))
    driver_id = db.Column(db.Integer, db.ForeignKey('drivers.id'))
    remarks = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.now)
    
    # 關聯
    start = db.relationship('Customer', foreign_keys=[start_point])
    via = db.relationship('Customer', foreign_keys=[via_point])
    end = db.relationship('Customer', foreign_keys=[end_point])
    driver = db.relationship('Driver', foreign_keys=[driver_id])
    
    def __repr__(self):
        return f"<CompletedTrip {self.id} {self.date}>" 