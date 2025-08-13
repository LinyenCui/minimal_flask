from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime
from modules.models.base import db


class ClinicLocation(db.Model):
    __tablename__ = "clinic_locations"

    id = Column(Integer, primary_key=True)
    chat_id = Column(String(128), unique=True, index=True, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    address = Column(String(255))
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
