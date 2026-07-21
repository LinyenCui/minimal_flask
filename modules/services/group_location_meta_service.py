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


# ============================================================
# 到院通知接送群綁定（relay_chat_id，migration 009）
# 工作群（chat_id）↔ 接送群（relay_chat_id）一對一
# ============================================================

def set_relay(work_chat_id: str, relay_chat_id: str) -> GroupLocationMeta:
    """綁定：工作群的到院通知轉發到接送群。"""
    if not relay_chat_id or not relay_chat_id.strip():
        raise ValueError("relay_chat_id 不可為空")
    rec = get_or_create(work_chat_id)
    rec.relay_chat_id = relay_chat_id.strip()
    db.session.commit()
    logger.info(f"設定到院轉發: work={work_chat_id}, relay={relay_chat_id}")
    return rec


def clear_relay(work_chat_id: str) -> None:
    """解除工作群的接送群綁定。"""
    rec = get(work_chat_id)
    if rec and rec.relay_chat_id:
        rec.relay_chat_id = None
        db.session.commit()
        logger.info(f"清除到院轉發: work={work_chat_id}")


def get_relay_of(work_chat_id: str) -> Optional[str]:
    """查工作群綁定的接送群 chat_id（無綁定 → None）。"""
    rec = get(work_chat_id)
    return rec.relay_chat_id if rec else None


def find_work_by_relay(relay_chat_id: str) -> Optional[str]:
    """查這個 chat 是不是誰的接送群 → 回綁定它的工作群 chat_id（不是 → None）。"""
    if not relay_chat_id:
        return None
    rec = GroupLocationMeta.query.filter_by(relay_chat_id=relay_chat_id).first()
    return rec.chat_id if rec else None
