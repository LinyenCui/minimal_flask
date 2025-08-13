import logging
from typing import Optional
from modules.models.base import db
from modules.models.clinic_location import ClinicLocation

logger = logging.getLogger(__name__)


def get_for_chat(chat_id: str) -> Optional[ClinicLocation]:
    if not chat_id:
        return None
    return ClinicLocation.query.filter_by(chat_id=chat_id).first()


def set_for_chat(chat_id: str, lat: float, lng: float, address: Optional[str] = None) -> ClinicLocation:
    if not chat_id:
        raise ValueError("chat_id 不可為空")
    record = ClinicLocation.query.filter_by(chat_id=chat_id).first()
    if record is None:
        record = ClinicLocation(chat_id=chat_id, latitude=float(lat), longitude=float(lng), address=address or None)
        db.session.add(record)
    else:
        record.latitude = float(lat)
        record.longitude = float(lng)
        record.address = address or record.address
    db.session.commit()
    logger.info(f"已設定診所座標: chat_id={chat_id}, lat={lat}, lng={lng}")
    return record


def clear_for_chat(chat_id: str) -> None:
    if not chat_id:
        return
    record = ClinicLocation.query.filter_by(chat_id=chat_id).first()
    if record:
        db.session.delete(record)
        db.session.commit()
        logger.info(f"已清除診所座標: chat_id={chat_id}")
