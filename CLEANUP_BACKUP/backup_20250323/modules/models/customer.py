# modules/models/customer.py
from modules.models.base import db

class Customer(db.Model):
    __tablename__ = 'customers'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    address = db.Column(db.String(200), nullable=False)
    short_name = db.Column(db.String(50), unique=True)
    category = db.Column(db.String(50))
    remarks = db.Column(db.Text)
    
    def __repr__(self):
        return f"<Customer {self.id} {self.name}>"
