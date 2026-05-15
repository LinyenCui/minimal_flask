"""
回診日期計算 atomic tool（純函數，無 DB）

外掛性質（跟車資試算同類型）— 純算、不碰 DB、無 session、無 audit log。
用戶輸入 `!日期` 半形 / `！日期` 全形 → router 直接呼叫，零 AI 成本。

> 觸發前綴歷史：原本用 `(日期)` 括號，但 LINE 內建顏文字（emoticon）在
> webhook 的 message.text 就是 `(...)` 形式（如 `(笑)`），群組任何人傳
> 都會誤觸發。改用 `!` / `！` 前綴，且限制後面緊接數字/中文數字，避免
> `!收到` `!!!` 等非日期誤觸發。

支援的日期格式（多數仰賴 unified_date_parser）：
  !5/14        MM/DD
  !05-20       MM-DD
  !2026-5-14   YYYY-M-D
  !2026/5/14   YYYY/M/D（本工具預處理成 YYYY-M-D 再丟 parser）
  !5月14日     MM月DD日（阿拉伯數字）
  !五月二十日  中文數字（本工具預處理成 5/20 再丟 parser）
  !五月二十    中文數字 + 缺尾
  !五月二十號  中文數字 + 「號」

「廿」「卅」等台灣略寫不支援（用戶當前需求外）。

回診療程節點（看診日 = base）：
  第1週  = +7   看報告
  第4週  = +28  28天
  第11週 = +77  抽血
  第12週 = +84  回診

日期輸出用民國年格式：115年06月18日（四）

公開 API:
  is_date_calc_command(text) → bool   router / sandbox_handler 共用判斷
  parse_command(text)     → ToolResult.data = {'date_str': inner}
      只負責剝 ! / ！ 前綴，回後面的日期字串
  calculate(*, date_str)  → ToolResult.data = {'base','week1','week4','week11','week12'}
      呼叫 unified_date_parser，加 +7 / +28 / +77 / +84 天
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
_ARABIC_MD_RE = re.compile(r'^(\d{1,2})月(\d{1,2})(?:日|號)?$')
_YMD_SLASH_RE = re.compile(r'^(\d{4})/(\d{1,2})/(\d{1,2})$')


def _normalize_input(text: str) -> str:
    """把多元輸入正規化到 unified_date_parser 認的格式。

    - 中文數字「五月二十日」→ "5/20"
    - 阿拉伯月日「5月14日」/「5月14」→ "5/14"（後續邏輯統一吃 M/D）
    - YYYY/M/D → YYYY-M-D（parser 只認 YYYY-MM-DD 短橫線含年）
    - 其他原樣（parser 自己認 MM/DD / MM-DD / YYYY-M-D）
    """
    text = (text or '').strip()
    m = _CN_DATE_RE.match(text)
    if m:
        month = _cn_to_int(m.group(1))
        day = _cn_to_int(m.group(2))
        if month is not None and day is not None and 1 <= month <= 12 and 1 <= day <= 31:
            return f"{month}/{day}"
    m = _ARABIC_MD_RE.match(text)
    if m:
        return f"{int(m.group(1))}/{int(m.group(2))}"
    m = _YMD_SLASH_RE.match(text)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return text


# 短日期（沒指定年）— _normalize_input 後形如 M/D 或 M-D
SHORT_DATE_RE = re.compile(r'^\d{1,2}[-/]\d{1,2}$')


# ---- 主計算 ----

def _build_result(date_str: str, base: date) -> ToolResult:
    """看診日 base → 4 個療程節點"""
    return ToolResult.success(data={
        'input': date_str,
        'base': base,                              # 看診日
        'week1': base + timedelta(days=7),         # 第1週 看報告
        'week4': base + timedelta(days=28),        # 第4週 28天
        'week11': base + timedelta(days=77),       # 第11週 抽血
        'week12': base + timedelta(days=84),       # 第12週 回診
    })


def calculate(*, date_str: str) -> ToolResult:
    """從日期字串算 看診日 + 第1/4/11/12 週。

    短日期語境（沒指定年份）：
      1) 一律取「當年」— unified_date_parser 的「>180 天推上下年」邏輯
         對醫療回診語境不對：12-30 距今 229 天會被推到去年，
         但用戶語意是「今年 12-30 的下次回診」。
      2) 2/29 非閏年自動 fallback 到 3/1 — 在 +7 推算語境下，閏年的
         2/29 等於非閏年的 3/1（2/22 + 7 在閏年=2/29、非閏年=3/1）。

    含年明示 2025-2-29 / 2025-12-30 不受影響 — 用戶明確指定，
    無效就 fail，不 silent fallback。
    """
    if not isinstance(date_str, str) or not date_str.strip():
        return ToolResult.fail("date_str 不能為空")
    normalized = _normalize_input(date_str)

    # 短日期 2/29 非閏年特例 — 早於 parser，避免 parser 內拋 ValueError
    if SHORT_DATE_RE.match(normalized):
        sep = '/' if '/' in normalized else '-'
        m, d = map(int, normalized.split(sep))
        if m == 2 and d == 29:
            import calendar
            from modules.utils.taiwan_time import get_taiwan_date
            today = get_taiwan_date()
            if not calendar.isleap(today.year):
                return _build_result(date_str, date(today.year, 3, 1))

    try:
        base = UnifiedDateParser.parse(normalized)
    except Exception as e:
        return ToolResult.fail(f"無法解析日期「{date_str}」：{e}")

    if SHORT_DATE_RE.match(normalized):
        from modules.utils.taiwan_time import get_taiwan_date
        today = get_taiwan_date()
        try:
            base = base.replace(year=today.year)
        except ValueError:
            return ToolResult.fail(
                f"日期「{date_str}」在 {today.year} 年無對應日"
            )

    return _build_result(date_str, base)


# ---- 指令解析（router / sandbox_handler 共用）----

# ! / ！ 前綴，且後面緊接數字或中文數字（日期一定數字/中文開頭）
# 限制是為了避免 !收到 !!! 等非日期訊息誤觸發
BANG_RE = re.compile(r'^[!！]\s*([\d一二三四五六七八九十].*)$')


def is_date_calc_command(text: str) -> bool:
    """訊息是否為 !日期 外掛格式。router 跟 sandbox_handler 共用判斷。"""
    return bool(BANG_RE.match((text or '').strip()))


def parse_command(text: str) -> ToolResult:
    """從訊息 `!日期` / `！日期` 抽日期字串。只剝前綴，parsing 交給 calculate。"""
    if not isinstance(text, str):
        return ToolResult.fail("text 必須是字串")
    m = BANG_RE.match(text.strip())
    if not m:
        return ToolResult.fail("用法：!日期 例 !5/14 !五月二十日 !2026-5-14")
    inner = m.group(1).strip()
    if not inner:
        return ToolResult.fail("! 後面要接日期")
    return ToolResult.success(data={'date_str': inner})


# ---- 渲染輔助 ----

_WEEKDAY_CN = ['一', '二', '三', '四', '五', '六', '日']


def format_date_full(d: date) -> str:
    """日期 → 民國年格式「115年06月18日（四）」"""
    minguo = d.year - 1911
    return f"{minguo}年{d.month:02d}月{d.day:02d}日（{_WEEKDAY_CN[d.weekday()]}）"


def format_text(data: Dict[str, Any]) -> str:
    """渲染純文字（fallback）"""
    return (
        f"📅 回診日期計算\n"
        f"看診日　{format_date_full(data['base'])}\n"
        f"第1週　{format_date_full(data['week1'])}　看報告\n"
        f"第4週　{format_date_full(data['week4'])}　28天\n"
        f"第11週　{format_date_full(data['week11'])}　抽血\n"
        f"第12週　{format_date_full(data['week12'])}　回診"
    )
