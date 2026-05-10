"""LIFF URL builder

關鍵：LIFF SDK 的 `liff.getContext().groupId` 回傳的是 **LIFF-internal UUID**
（如 `3677e217-8619-445a-b8b1-604e02c2cfa3`，36 字元），
**不是** LINE Messaging API 認的 group ID（如 `C8fc24bca48034e550d56eec9ba9587bf`，
33 字元，C+32 hex）。

所以前端拿不到能 push 用的 ID。解法：bot 在 webhook 觸發那一刻已經有正確的 ID，
把它放進 LIFF URL 當 query param，前端 round-trip 回 backend，backend 就能 push。

Helper 函數：
  build_liff_url(liff_id, form, event_source=None)
    回傳 https://liff.line.me/{liff_id}?form=xxx[&gid=...][&rid=...]
"""
from __future__ import annotations
from typing import Any


def build_liff_url(liff_id: str, form: str, event_source: Any = None) -> str:
    """組 LIFF URL，從 webhook event.source 抓 group_id / room_id 塞進 query。

    Args:
        liff_id: LIFF App ID
        form: 表單路由（如 'import' / 'booking' / 'customer'）
        event_source: linebot v3 event.source 物件，有 type / group_id / room_id 屬性

    Returns:
        完整 LIFF URL，例如:
          https://liff.line.me/{liff_id}?form=import&gid=C8fc24...
          https://liff.line.me/{liff_id}?form=booking&rid=R8fc24...
          https://liff.line.me/{liff_id}?form=customer  (1-on-1 chat 沒 gid/rid)
    """
    params = [f"form={form}"]
    if event_source is not None:
        src_type = getattr(event_source, 'type', None)
        if src_type == 'group':
            gid = getattr(event_source, 'group_id', None)
            if gid:
                params.append(f"gid={gid}")
        elif src_type == 'room':
            rid = getattr(event_source, 'room_id', None)
            if rid:
                params.append(f"rid={rid}")
    return f"https://liff.line.me/{liff_id}?{'&'.join(params)}"


def resolve_push_target(payload_source: Any, fallback_user_id: str | None) -> str | None:
    """從 LIFF POST 進來的 source dict 決定 push 目標。

    LIFF 表單 submit 時帶的 source 形如:
        {'type': 'group', 'groupId': 'C8fc24...', 'roomId': null}
        {'type': 'room',  'groupId': null, 'roomId': 'R8fc24...'}
        null  (1-on-1 chat 或前端未送)

    Args:
        payload_source: body['source'] 內容，可能是 dict / None
        fallback_user_id: 私聊或拿不到 group/room 時的退回值

    Returns:
        groupId / roomId / fallback_user_id 之一，全空回 None
    """
    if isinstance(payload_source, dict):
        s_type = payload_source.get('type')
        if s_type == 'group':
            gid = (payload_source.get('groupId') or '').strip() if isinstance(payload_source.get('groupId'), str) else ''
            if gid:
                return gid
        elif s_type == 'room':
            rid = (payload_source.get('roomId') or '').strip() if isinstance(payload_source.get('roomId'), str) else ''
            if rid:
                return rid
    return fallback_user_id
