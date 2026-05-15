"""日期計算 Flex bubble — (日期) 外掛的結果渲染"""
from datetime import date
from typing import Any, Dict

from rewrite.tools.date_calc import format_date_full

PRIMARY = "#1565C0"
ACCENT = "#FF6D00"
SUCCESS = "#2E7D32"
MUTED = "#999999"
BLACK = "#333333"


def _row(label: str, value: str, tag: str = "", tag_color: str = ACCENT) -> dict:
    """單 row：左 label / 右 date / 可選右上小 tag（抽血 / 回診）"""
    contents = [
        {
            "type": "text",
            "text": label,
            "size": "sm",
            "color": MUTED,
            "flex": 2,
        },
        {
            "type": "text",
            "text": value,
            "size": "sm",
            "color": BLACK,
            "weight": "bold",
            "flex": 5,
            "wrap": True,
        },
    ]
    if tag:
        contents.append({
            "type": "text",
            "text": tag,
            "size": "xs",
            "color": tag_color,
            "weight": "bold",
            "flex": 1,
            "align": "end",
        })
    return {
        "type": "box",
        "layout": "horizontal",
        "spacing": "sm",
        "contents": contents,
    }


def render_date_calc(data: Dict[str, Any]) -> dict:
    """Flex bubble：base / +7 / +77 (抽血) / +84 (回診)"""
    base: date = data['base']
    next_week: date = data['next_week']
    week11: date = data['week11']
    week12: date = data['week12']

    return {
        "type": "flex",
        "altText": f"📅 日期計算 {base.month}/{base.day}",
        "contents": {
            "type": "bubble",
            "size": "mega",
            "header": {
                "type": "box",
                "layout": "vertical",
                "backgroundColor": PRIMARY,
                "paddingAll": "md",
                "contents": [
                    {
                        "type": "text",
                        "text": "📅 日期計算",
                        "weight": "bold",
                        "size": "lg",
                        "color": "#ffffff",
                    },
                    {
                        "type": "text",
                        "text": format_date_full(base),
                        "size": "sm",
                        "color": "#ffffff",
                        "margin": "xs",
                    },
                ],
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "md",
                "contents": [
                    _row("該日期", format_date_full(base)),
                    {"type": "separator"},
                    _row("下一週", format_date_full(next_week)),
                    {"type": "separator"},
                    _row("第 11 週", format_date_full(week11), tag="抽血", tag_color=ACCENT),
                    {"type": "separator"},
                    _row("第 12 週", format_date_full(week12), tag="回診", tag_color=SUCCESS),
                ],
            },
        },
    }
