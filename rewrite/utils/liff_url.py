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


def _extract_target_ids(source: Any) -> tuple[str | None, str | None]:
    """從任何形式的 source 拆出 (group_id, room_id)。

    支援兩種形式：
      1. webhook event.source 物件（snake_case 屬性: type, group_id, room_id）
      2. LIFF payload 的 source dict（camelCase keys: type, groupId, roomId）

    回傳 (None, None) 表示沒有群組/聊天室 context（私聊或無 source）。
    """
    if source is None:
        return None, None
    if isinstance(source, dict):
        s_type = source.get('type')
        if s_type == 'group':
            gid = source.get('groupId')
            return (gid.strip() if isinstance(gid, str) and gid.strip() else None), None
        if s_type == 'room':
            rid = source.get('roomId')
            return None, (rid.strip() if isinstance(rid, str) and rid.strip() else None)
        return None, None
    # attribute-style（webhook event.source）
    s_type = getattr(source, 'type', None)
    if s_type == 'group':
        return getattr(source, 'group_id', None), None
    if s_type == 'room':
        return None, getattr(source, 'room_id', None)
    return None, None


def build_liff_url(
    liff_id: str,
    form: str,
    event_source: Any = None,
    *,
    extra_params: dict[str, Any] | None = None,
) -> str:
    """組 LIFF URL，把當前對話 context（group/room）塞進 query 給前端 round-trip。

    Args:
        liff_id: LIFF App ID
        form: 表單路由（如 'import' / 'booking' / 'customer' / 'edit_schedule'）
        event_source: webhook event.source 或 LIFF payload source dict（任一）
        extra_params: 額外 query params，如 {'id': 42}（給編輯/請假 LIFF 帶 ID）

    Returns:
        https://liff.line.me/{liff_id}?form=xxx[&gid=...][&rid=...][&id=42 ...]
    """
    params: list[str] = []
    if form:
        params.append(f"form={form}")
    if extra_params:
        for k, v in extra_params.items():
            if v is not None:
                params.append(f"{k}={v}")
    gid, rid = _extract_target_ids(event_source)
    if gid:
        params.append(f"gid={gid}")
    elif rid:
        params.append(f"rid={rid}")
    qs = '&'.join(params) if params else ''
    return f"https://liff.line.me/{liff_id}?{qs}" if qs else f"https://liff.line.me/{liff_id}"


def resolve_push_target(payload_source: Any, fallback_user_id: str | None) -> str | None:
    """從 LIFF POST 進來的 source dict 決定 push 目標。

    Args:
        payload_source: body['source'] 內容，可能是 dict / None
        fallback_user_id: 私聊或拿不到 group/room 時的退回值

    Returns:
        groupId / roomId / fallback_user_id 之一，全空回 None
    """
    gid, rid = _extract_target_ids(payload_source)
    return gid or rid or fallback_user_id
