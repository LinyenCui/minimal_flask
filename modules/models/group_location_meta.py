from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime
from modules.models.base import db


class GroupLocationMeta(db.Model):
    __tablename__ = "group_location_meta"

    id = Column(Integer, primary_key=True)
    chat_id = Column(String(128), unique=True, index=True, nullable=False)
    place_name = Column(String(255))
    message_template = Column(Text)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
