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
