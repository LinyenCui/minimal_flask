import logging
from typing import Optional
from modules.models.base import db
from modules.models.group_location_meta import GroupLocationMeta

logger = logging.getLogger(__name__)


def get(chat_id: str) -> Optional[GroupLocationMeta]:
    if not chat_id:
        return None
    return GroupLocationMeta.query.filter_by(chat_id=chat_id).first()


essential_fields = ("chat_id", "place_name")

def get_or_create(chat_id: str) -> GroupLocationMeta:
    rec = get(chat_id)
    if rec:
        return rec
    rec = GroupLocationMeta(chat_id=chat_id)
    db.session.add(rec)
    db.session.commit()
    return rec


def set_name(chat_id: str, name: str) -> GroupLocationMeta:
    rec = get_or_create(chat_id)
    rec.place_name = name.strip()
    db.session.commit()
    logger.info(f"設定地點名稱: chat_id={chat_id}, len={len(rec.place_name or '')}")
    return rec


def set_template(chat_id: str, template: Optional[str]) -> GroupLocationMeta:
    rec = get_or_create(chat_id)
    rec.message_template = template if (template is None or template.strip() != "") else None
    db.session.commit()
    logger.info(f"更新到院訊息: chat_id={chat_id}, has_template={bool(rec.message_template)}, len={len(rec.message_template or '')}")
    return rec
