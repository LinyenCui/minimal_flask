import logging
from typing import Optional
from modules.models.base import db
from modules.models.chat_settings import ChatSettings

logger = logging.getLogger(__name__)


def get_or_create(chat_id: str) -> ChatSettings:
    record = ChatSettings.query.filter_by(chat_id=chat_id).first()
    if record:
        return record
    record = ChatSettings(chat_id=chat_id)
    db.session.add(record)
    db.session.commit()
    return record


def set_avg_speed(chat_id: str, kmh: float) -> ChatSettings:
    rec = get_or_create(chat_id)
    rec.avg_speed_kmh = float(kmh)
    db.session.commit()
    logger.info(f"已設定群組平均車速: chat_id={chat_id}, kmh={kmh}")
    return rec


def get_avg_speed(chat_id: str) -> Optional[float]:
    rec = ChatSettings.query.filter_by(chat_id=chat_id).first()
    if not rec:
        return None
    return rec.avg_speed_kmh
