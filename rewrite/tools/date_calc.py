"""
日期計算 atomic tool（純函數，無 DB）

外掛性質（跟車資試算同類型）— 純算、不碰 DB、無 session、無 audit log。
用戶輸入 `(日期)` 半形 / `（日期）` 全形 → router 直接呼叫，零 AI 成本。

支援的日期格式（多數仰賴 unified_date_parser）：
  (5/14)        MM/DD
  (05-20)       MM-DD
  (2026-5-14)   YYYY-M-D
  (2026/5/14)   YYYY/M/D（本工具預處理成 YYYY-M-D 再丟 parser）
  (5月14日)     MM月DD日（阿拉伯數字）
  (五月二十日)  中文數字（本工具預處理成 5/20 再丟 parser）
  (五月二十)    中文數字 + 缺尾
  (五月二十號)  中文數字 + 「號」

「廿」「卅」等台灣略寫不支援（用戶當前需求外）。

公開 API:
  parse_command(text)     → ToolResult.data = {'date_str': inner}
      只負責剝外圈括號，回括號內字串
  calculate(*, date_str)  → ToolResult.data = {'base', 'next_week', 'week11', 'week12'}
      呼叫 unified_date_parser，加 +7 / +77 / +84 天
  format_text(data)       → str  (fallback / 純文字訊息用)

設計判斷：中文數字 → 阿拉伯數字 算 preprocessing，不算 parsing 重建；
故不違反 CLAUDE.md「絕不跳過 unified_date_parser 自建日期解析」。
中文格式目前只此工具用，先 local 處理，需要時再 promote。
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any, Dict, Optional

from modules.utils.unified_date_parser import UnifiedDateParser
from rewrite.tools.base import ToolResult


# ---- 中文數字 normalize（只負責 1-31 範圍）----

_CN_DIGIT = {'零': 0, '一': 1, '二': 2, '三': 3, '四': 4,
             '五': 5, '六': 6, '七': 7, '八': 8, '九': 9}


def _cn_to_int(s: str) -> Optional[int]:
    """中文數字 → int。支援「一」~「三十一」。無法解析回 None。"""
    s = (s or '').strip()
    if not s:
        return None
    if s == '十':
        return 10
    if '十' in s:
        tens_part, ones_part = s.split('十', 1)
        if tens_part:
            if tens_part not in _CN_DIGIT:
                return None
            tens = _CN_DIGIT[tens_part]
        else:
            tens = 1
        if ones_part:
            if ones_part not in _CN_DIGIT:
                return None
            ones = _CN_DIGIT[ones_part]
        else:
            ones = 0
        return tens * 10 + ones
    return _CN_DIGIT.get(s)


_CN_DATE_RE = re.compile(
    r'^([一二三四五六七八九十]+)月([一二三四五六七八九十]+)(?:日|號)?$'
)
_YMD_SLASH_RE = re.compile(r'^(\d{4})/(\d{1,2})/(\d{1,2})$')


def _normalize_input(text: str) -> str:
    """把 unified_date_parser 不直接認的格式轉成它認的。

    - 中文數字「五月二十日」→ "5/20"
    - YYYY/M/D → YYYY-M-D（parser 只認 YYYY-MM-DD 短橫線含年）
    - 其他原樣（parser 自己認 MM/DD / MM-DD / MM月DD日（阿拉伯）/ 完整 YYYY-MM-DD）
    """
    text = (text or '').strip()
    m = _CN_DATE_RE.match(text)
    if m:
        month = _cn_to_int(m.group(1))
        day = _cn_to_int(m.group(2))
        if month is not None and day is not None and 1 <= month <= 12 and 1 <= day <= 31:
            return f"{month}/{day}"
    m = _YMD_SLASH_RE.match(text)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return text


# ---- 主計算 ----

def calculate(*, date_str: str) -> ToolResult:
    """從日期字串算 base / +7 / +77 / +84 四個日期。"""
    if not isinstance(date_str, str) or not date_str.strip():
        return ToolResult.fail("date_str 不能為空")
    normalized = _normalize_input(date_str)
    try:
        base = UnifiedDateParser.parse(normalized)
    except Exception as e:
        return ToolResult.fail(f"無法解析日期「{date_str}」：{e}")
    return ToolResult.success(data={
        'input': date_str,
        'base': base,
        'next_week': base + timedelta(days=7),
        'week11': base + timedelta(days=77),
        'week12': base + timedelta(days=84),
    })


# ---- 指令解析（router / sandbox_handler 共用）----

OUTER_PAREN_RE = re.compile(r'^[(（]\s*([^)）]+?)\s*[)）]$')


def is_date_calc_command(text: str) -> bool:
    """訊息是否為 (日期) 外掛格式。router 跟 sandbox_handler 共用判斷。"""
    return bool(OUTER_PAREN_RE.match((text or '').strip()))


def parse_command(text: str) -> ToolResult:
    """從訊息 `(日期)` / `（日期）` 抽內容。只剝括號，parsing 交給 calculate。"""
    if not isinstance(text, str):
        return ToolResult.fail("text 必須是字串")
    m = OUTER_PAREN_RE.match(text.strip())
    if not m:
        return ToolResult.fail("用法：(日期) 例 (5/14) (五月二十日) (2026-5-14)")
    inner = m.group(1).strip()
    if not inner:
        return ToolResult.fail("括號內不可為空")
    return ToolResult.success(data={'date_str': inner})


# ---- 渲染輔助 ----

_WEEKDAY_CN = ['一', '二', '三', '四', '五', '六', '日']


def format_date_full(d: date) -> str:
    """日期 → 「2026 年 05 月 14 日 星期四」"""
    return f"{d.year} 年 {d.month:02d} 月 {d.day:02d} 日 星期{_WEEKDAY_CN[d.weekday()]}"


def format_text(data: Dict[str, Any]) -> str:
    """渲染純文字（fallback）"""
    return (
        f"📅 日期計算\n"
        f"該日期：{format_date_full(data['base'])}\n"
        f"下一週：{format_date_full(data['next_week'])}\n"
        f"第 11 週：{format_date_full(data['week11'])}（抽血）\n"
        f"第 12 週：{format_date_full(data['week12'])}（回診）"
    )
