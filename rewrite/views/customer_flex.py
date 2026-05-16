"""
客戶相關 Flex Message 渲染器

提供函數：
  - render_customer_detail(customer)          → 單筆詳情 Bubble
  - render_birthday_layer_carousel(day, ...)  → 病歷層列表 Carousel

設計原則：
  - 純函數：輸入 CustomerView，輸出 dict（Flex JSON）
  - 不發送，不依賴 LINE SDK（單元可測）
  - 結合計算欄位（病歷層、年齡）強化視覺辨識
"""

import os
from typing import List, Optional
from rewrite.tools.customer import CustomerView


def _liff_id() -> str:
    """讀 LIFF_ID 環境變數（call 時取而非 import 時，方便 .env 重載）"""
    return os.environ.get('LIFF_ID', '').strip()


def _liff_url(customer_id: Optional[int] = None, event_source=None) -> str:
    """組 LIFF URL，帶 customer_id 就是編輯模式；event_source 帶當前 group/room context。

    群組 / 聊天室 context 會塞進 query (?gid=... / ?rid=...)，給編輯後 push 用。
    """
    from rewrite.utils.liff_url import build_liff_url
    extra = {'customer_id': customer_id} if customer_id else None
    return build_liff_url(_liff_id(), '', event_source, extra_params=extra)


# ============================================================
# 主題色
# ============================================================
PRIMARY = "#1565C0"      # 主色（深藍）
ACCENT = "#FF6D00"       # 強調色（病歷層）
MUTED = "#999999"
BLACK = "#333333"
SUCCESS = "#2E7D32"
LIGHT_BG = "#F5F5F5"


# ============================================================
# 共用元件
# ============================================================

def _row(label: str, value: str, *,
         value_color: str = BLACK,
         value_weight: str = "regular",
         label_color: str = "#666666") -> dict:
    """label : value 一行，左標右值"""
    return {
        "type": "box",
        "layout": "horizontal",
        "spacing": "sm",
        "contents": [
            {"type": "text", "text": label, "size": "sm",
             "color": label_color, "flex": 2},
            {"type": "text", "text": value, "size": "sm",
             "color": value_color, "weight": value_weight,
             "flex": 5, "wrap": True},
        ]
    }


def _separator(margin: str = "md") -> dict:
    return {"type": "separator", "margin": margin}


def _format_gender(g: Optional[str]) -> str:
    return {'M': '男', 'F': '女'}.get(g or '', '—')


def _format_birthday(c: CustomerView) -> str:
    if not c.birthday:
        return "未填"
    s = c.birthday.isoformat()
    if c.age is not None:
        s += f"（{c.age} 歲）"
    return s


def _is_placeholder_address(addr: Optional[str]) -> bool:
    return not addr or addr in ("(待補)", "（待補）", "")


# ============================================================
# 1. 客戶詳情卡（單筆）
# ============================================================

def render_customer_detail(c: CustomerView, event_source=None) -> dict:
    """單筆客戶詳情，渲染為 Flex Bubble。

    Args:
        c: CustomerView
        event_source: 當前對話 context（webhook event.source 或 LIFF payload source dict）。
            傳了，「編輯」按鈕的 LIFF URL 會帶 gid/rid，編輯後 push 才會回到群組；
            沒傳 → 編輯後 push 給操作者個人。
    """
    body_contents: List[dict] = []

    # 姓名 (含性別)
    name_text = c.name or '—'
    if c.gender:
        name_text += f"（{_format_gender(c.gender)}）"
    body_contents.append(_row("姓名", name_text, value_weight="bold"))

    # 簡稱
    body_contents.append(_row("簡稱", c.short_name or '—'))

    # 醫療資料區塊（門診客戶才有；診所/東洋 一般接送客戶通常空）
    # 全空就跳過整段（含 separator）
    medical_rows: List[dict] = []
    if c.birthday:
        medical_rows.append(_row(
            "🎂 生日", _format_birthday(c),
            value_color=PRIMARY, value_weight="bold"
        ))
        medical_rows.append(_row(
            "📋 病歷層", f"{c.birthday_day} 日",
            value_color=ACCENT, value_weight="bold"
        ))
    if c.medical_record_no:
        medical_rows.append(_row("病歷號", c.medical_record_no))
    if c.dm_care_no:
        medical_rows.append(_row("共照網代號", c.dm_care_no))
    if medical_rows:
        body_contents.append(_separator())
        body_contents.extend(medical_rows)

    body_contents.append(_separator())

    # 類別 + 聯絡資料
    if c.category:
        body_contents.append(_row("類別", c.category))

    addr = c.address or '—'
    body_contents.append(_row(
        "地址", addr,
        value_color=MUTED if _is_placeholder_address(addr) else BLACK
    ))
    if c.contact_phone:
        body_contents.append(_row("電話", c.contact_phone))

    if c.remarks:
        body_contents.append(_row("備註", c.remarks, value_color=MUTED))

    if c.latitude is not None and c.longitude is not None:
        body_contents.append(_row(
            "座標", f"{c.latitude:.5f}, {c.longitude:.5f}",
            value_color=SUCCESS
        ))

    # 時間戳
    if c.updated_at:
        body_contents.append(_separator())
        body_contents.append(_row(
            "最近異動",
            c.updated_at.strftime("%Y-%m-%d %H:%M"),
            label_color=MUTED, value_color=MUTED
        ))

    # ----- footer 按鈕 -----
    footer_buttons = []
    footer_buttons.append({
        "type": "button",
        "style": "primary",
        "height": "sm",
        "color": PRIMARY,
        "action": {
            "type": "uri",
            "label": "編輯",
            "uri": _liff_url(c.id, event_source=event_source),
        }
    })

    return {
        "type": "bubble",
        "size": "mega",
        "header": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": PRIMARY,
            "paddingAll": "md",
            "contents": [{
                "type": "text",
                "text": f"🪪 客戶詳情 #{c.id}",
                "weight": "bold",
                "size": "lg",
                "color": "#ffffff",
            }]
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": body_contents,
        },
        "footer": {
            "type": "box",
            "layout": "horizontal",
            "spacing": "sm",
            "contents": footer_buttons,
        }
    }


# ============================================================
# 1b. 新增客戶入口（!新增客戶 → 開 LIFF 表單）
# ============================================================

def render_new_customer_entry(event_source=None) -> dict:
    """!新增客戶 觸發的 LINE message：text + Quick Reply（uri action 開 LIFF）

    Args:
        event_source: webhook event.source 物件。傳了才能在群組廣播新增結果，
            因為 LIFF SDK 的 getContext() 回的是假 UUID groupId（不能 push）。

    Quick Reply 按完即消失，不留歷史殘留 — 比 Flex bubble 體驗更好。
    LIFF_ID 環境變數未設時 → 回錯誤 Flex bubble（顯示警告）。
    """
    if not _liff_id():
        return {
            'type': 'flex',
            'altText': '⚠️ LIFF 未設定',
            'contents': _liff_unavailable_bubble('新增客戶表單'),
        }

    from rewrite.utils.liff_url import build_liff_url
    return {
        'type': 'quick_reply',
        'text': '🪪 點下方按鈕新增客戶',
        'quick_reply': {
            'items': [{
                'type': 'action',
                'action': {
                    'type': 'uri',
                    'label': '📝 開填寫表單',
                    # form='customer' 是預設值，dispatcher 沒 form 參數會 fall through 到新增客戶
                    'uri': build_liff_url(_liff_id(), 'customer', event_source),
                },
            }],
        },
    }


def _liff_unavailable_bubble(action_desc: str) -> dict:
    """LIFF_ID 沒設時的紅色警示 bubble（共用）"""
    return {
        "type": "bubble",
        "size": "kilo",
        "header": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": "#D32F2F",
            "paddingAll": "md",
            "contents": [{
                "type": "text",
                "text": "⚠️ LIFF 未設定",
                "weight": "bold", "size": "lg", "color": "#ffffff",
            }],
        },
        "body": {
            "type": "box", "layout": "vertical", "spacing": "sm",
            "contents": [
                {"type": "text",
                 "text": f"LIFF_ID 環境變數沒載入，{action_desc}暫不可用",
                 "size": "sm", "color": BLACK, "wrap": True},
                {"type": "text",
                 "text": "💡 請確認 .env.dev 存在且含 LIFF_ID，並重啟 Flask",
                 "size": "xs", "color": MUTED, "wrap": True, "margin": "md"},
            ],
        },
    }


# ============================================================
# 2. 病歷層 carousel（多人）
# ============================================================

def render_birthday_layer_carousel(day: int, customers: List[CustomerView]) -> dict:
    """
    病歷層查詢結果。

    1 筆 → single bubble
    2-12 筆 → carousel
    > 12 筆 → 取前 12 + 第 12 張顯示「還有 N 筆」
    """
    if not customers:
        return _render_empty_layer(day)

    if len(customers) == 1:
        # 單筆直接給詳情卡
        return render_customer_detail(customers[0])

    # 多筆 → carousel
    visible = customers[:11] if len(customers) > 12 else customers
    bubbles = [_render_summary_bubble(c, day) for c in visible]

    if len(customers) > 12:
        bubbles.append(_render_more_indicator(len(customers) - 11, day))

    return {"type": "carousel", "contents": bubbles}


def _render_empty_layer(day: int) -> dict:
    return {
        "type": "bubble",
        "size": "kilo",
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {"type": "text",
                 "text": f"📋 病歷層 {day} 日",
                 "weight": "bold", "size": "xl", "color": ACCENT},
                {"type": "text",
                 "text": "目前無客戶",
                 "color": MUTED, "margin": "md"},
            ]
        }
    }


def _render_summary_bubble(c: CustomerView, day: int) -> dict:
    """Carousel 單張卡：簡要資訊 + 整張可 tap 至詳情"""
    return {
        "type": "bubble",
        "size": "kilo",
        "action": {
            "type": "postback",
            "label": f"客戶 #{c.id} 詳情",
            "data": f"customer_detail:{c.id}",
            "displayText": f"客戶詳情 {c.short_name or c.id}",
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": [
                {
                    "type": "box",
                    "layout": "horizontal",
                    "contents": [
                        {"type": "text",
                         "text": f"🎂 {day} 日",
                         "weight": "bold", "size": "sm",
                         "color": ACCENT, "flex": 0},
                        {"type": "text",
                         "text": f"#{c.id}",
                         "size": "xs", "color": MUTED, "align": "end"},
                    ]
                },
                _separator("sm"),
                {"type": "text",
                 "text": c.name or '—',
                 "weight": "bold", "size": "lg", "wrap": True},
                _row("性別", _format_gender(c.gender)),
                _row("生日", c.birthday.isoformat() if c.birthday else "—"),
                _row("病歷號", c.medical_record_no or "—"),
                _row("類別", c.category or "—"),
            ]
        }
    }


def _render_more_indicator(remaining: int, day: int) -> dict:
    """Carousel 最後一張：提示還有 N 筆"""
    return {
        "type": "bubble",
        "size": "kilo",
        "body": {
            "type": "box",
            "layout": "vertical",
            "alignItems": "center",
            "justifyContent": "center",
            "contents": [
                {"type": "text",
                 "text": f"還有 {remaining} 筆",
                 "weight": "bold", "size": "xl", "color": ACCENT},
                {"type": "text",
                 "text": f"病歷層 {day} 日尚有更多",
                 "size": "sm", "color": MUTED, "margin": "md"},
                {"type": "text",
                 "text": "請縮小範圍查詢",
                 "size": "xs", "color": MUTED, "margin": "sm"},
            ]
        }
    }
