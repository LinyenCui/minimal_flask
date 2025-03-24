# modules/models/driver.py
from modules.models.base import db

class Driver(db.Model):
    __tablename__ = 'drivers'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    plate_number = db.Column(db.String(20))
    car_brand = db.Column(db.String(50))
    car_model = db.Column(db.String(50))
    
    def __repr__(self):
        return f"<Driver {self.id} {self.name}>"
