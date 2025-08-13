from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime
from modules.models.base import db


class ChatSettings(db.Model):
    __tablename__ = "chat_settings"

    id = Column(Integer, primary_key=True)
    chat_id = Column(String(128), unique=True, index=True, nullable=False)
    avg_speed_kmh = Column(Float)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
