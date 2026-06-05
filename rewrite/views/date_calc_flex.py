"""回診日期計算 Flex bubble — !日期 外掛的結果渲染

排版對齊用戶手寫範本：
  看診日   115年06月18日（四）
  第1週   115年06月25日（四）  看報告
  第4週   115年07月16日（四）  28天
  第11週  115年09月03日（四）  抽血
  第12週  115年09月10日（四）  回診
"""
from datetime import date
from typing import Any, Dict

from rewrite.tools.date_calc import format_date_full

# 粉紅 / 紫色系配色（醫療回診語境）
HEADER_BG = "#EC407A"   # Material Pink 400 — header 底（預設/測試用）

# header 底色亂數色票（一組柔和耐看、白字皆清楚的深色;天天用不枯燥）
# 用「看診日」當種子 → 同一張卡固定色、不同看診日換色,穩定不亂跳
HEADER_PALETTE = [
    "#EC407A",  # 粉紅
    "#5C6BC0",  # 靛藍
    "#26A69A",  # 青綠
    "#EF6C00",  # 暖橘
    "#7E57C2",  # 紫
    "#42A5F5",  # 天藍
    "#66BB6A",  # 草綠
    "#AB47BC",  # 桃紫
]


def _pick_header_bg(seed_date: date) -> str:
    """依看診日挑 header 底色（同一張卡穩定,跨日期換色）。"""
    if not seed_date:
        return HEADER_BG
    return HEADER_PALETTE[seed_date.toordinal() % len(HEADER_PALETTE)]

TAG_REPORT = "#1565C0"  # 藍 — 看報告
TAG_28DAY = "#999999"   # 灰 — 28天（天數說明）
TAG_BLOOD = "#AD1457"   # Material Pink 800 — 抽血
TAG_VISIT = "#6A1B9A"   # Material Purple 800 — 回診
MUTED = "#999999"
BLACK = "#333333"


def _row(label: str, value: str, tag: str = "", tag_color: str = MUTED) -> dict:
    """單 row：左 label / 中 民國年日期 / 右 附註 tag"""
    contents = [
        {
            "type": "text",
            "text": label,
            "size": "xs",
            "color": MUTED,
            "flex": 2,
        },
        {
            "type": "text",
            "text": value,
            "size": "xs",
            "color": BLACK,
            "weight": "bold",
            "flex": 6,
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
            "flex": 2,
            "align": "end",
        })
    else:
        contents.append({"type": "text", "text": " ", "size": "xs", "flex": 2})
    return {
        "type": "box",
        "layout": "horizontal",
        "spacing": "sm",
        "contents": contents,
    }


def render_date_calc(data: Dict[str, Any]) -> dict:
    """Flex bubble：看診日 / 第1週(看報告) / 第4週(28天) / 第11週(抽血) / 第12週(回診)"""
    base: date = data['base']

    return {
        "type": "flex",
        "altText": f"📅 回診日期計算（看診日 {format_date_full(base)}）",
        "contents": {
            "type": "bubble",
            "size": "mega",
            "header": {
                "type": "box",
                "layout": "vertical",
                "backgroundColor": _pick_header_bg(base),
                "paddingAll": "md",
                "contents": [
                    {
                        "type": "text",
                        "text": "📅 回診日期計算",
                        "weight": "bold",
                        "size": "md",
                        "color": "#ffffff",
                    },
                ],
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "md",
                "contents": [
                    _row("看診日", format_date_full(base)),
                    {"type": "separator"},
                    _row("第1週", format_date_full(data['week1']), tag="看報告", tag_color=TAG_REPORT),
                    {"type": "separator"},
                    _row("第4週", format_date_full(data['week4']), tag="28-1", tag_color=TAG_28DAY),
                    {"type": "separator"},
                    _row("第8週", format_date_full(data['week8']), tag="28-2", tag_color=TAG_28DAY),
                    {"type": "separator"},
                    _row("第11週", format_date_full(data['week11']), tag="抽血", tag_color=TAG_BLOOD),
                    {"type": "separator"},
                    _row("第12週", format_date_full(data['week12']), tag="回診", tag_color=TAG_VISIT),
                ],
            },
        },
    }
