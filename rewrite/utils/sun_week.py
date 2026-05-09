"""
太陽週 helpers + sun_week_info atomic tool

業務週定義（CLAUDE.md「業務週定義」章節）：
  - 太陽週 = 星期日 ~ 星期六（**不是** ISO 8601 週一起算）
  - 週號 = strftime('%U')（Sunday-first）

提供：
  sun_week_start(d)              純函數：給日期回該週的星期日
  sun_week_number(d)             純函數：給日期回太陽週號（同 import_fixed.sun_week_number）
  sun_week_by_number(n, year)    純函數：給週號回該週的星期日
  parse_week_offset(phrase)      純函數：「本週」/「上週」/「+3週」 → int offset
  sun_week_info(...)             atomic tool：給 AI 用，回完整週資訊 dict

⚠️ AI 不要自己算「第 N 週」/「本週」的日期 — call sun_week_info 拿正確答案。
LLM 預設會算成 ISO 週（週一起），跟業務不對。
"""
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from typing import Optional

from rewrite.tools.base import ToolResult


# ============================================================
# 純函數 helpers
# ============================================================

def sun_week_start(d: date) -> date:
    """給日期，回該日所在太陽週的起始日（星期日）。

    Python `weekday()`: Mon=0, Sun=6
    太陽週要 Sun=0，所以 sun_offset = (weekday + 1) % 7
    """
    sun_offset = (d.weekday() + 1) % 7
    return d - timedelta(days=sun_offset)


def sun_week_number(d: date) -> int:
    """給日期，回太陽週號（用 strftime('%U')，Sunday-first）。

    跟 import_fixed.sun_week_number 同算法。
    """
    return int(d.strftime('%U'))


def sun_week_by_number(n: int, year: int) -> date:
    """給太陽週號 + 年份，回該週的起算日（星期日）。

    公式：找該年第一個星期日，加 (n-1) 週。

    驗證：2026 年第 17 週
      1/1/2026 = Thursday (weekday=3)
      第一個星期日：1/1 + (6-3)%7 = 1/1 + 3 = 1/4
      第 17 週起點：1/4 + 16 週 = 4/26 ✅

    邊界：n=0（1/1 ~ 第一個 Sat 之前的 partial week）會回上一年的最後一週起算日，
          業務上極少用，先不特別處理。
    """
    jan1 = date(year, 1, 1)
    days_to_first_sun = (6 - jan1.weekday()) % 7
    first_sun = jan1 + timedelta(days=days_to_first_sun)
    return first_sun + timedelta(weeks=n - 1)


def parse_week_offset(phrase: str) -> Optional[int]:
    """「本週」/「上週」/「下週」/「+3週」 → int offset，不認的回 None"""
    if not phrase:
        return None
    p = phrase.strip()
    mapping = {
        '本週': 0, '本周': 0, '這週': 0, '這周': 0,
        '上週': -1, '上周': -1, '上一週': -1, '上一周': -1, '上星期': -1,
        '下週': 1, '下周': 1, '下一週': 1, '下一周': 1, '下星期': 1,
        '下下週': 2, '下下周': 2,
    }
    if p in mapping:
        return mapping[p]
    # 「+3週」「-2週」這類
    import re
    m = re.match(r'^([+-]?\d+)\s*週?$', p)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            return None
    return None


# ============================================================
# atomic tool（給 AI 用）
# ============================================================

def sun_week_info(
    *,
    session=None,  # 不用 DB，但跟其他 atomic tool 簽名一致
    week_number=None,    # int（AI 可能傳 str）
    week_offset=None,    # int（AI 可能傳 str）
    target_date=None,    # date 或 'YYYY-MM-DD' / 'M/D' str（AI schema 是 string）
    year=None,           # int（AI 可能傳 str）
) -> ToolResult:
    """太陽週資訊查詢工具

    三種輸入方式（三選一，預設 week_offset=0=本週）：
      week_number: 該年第 N 週（太陽週號 strftime '%U'）
      week_offset: 0=本週、-1=上週、1=下週、2=下下週、-2=兩週前 ...
      target_date: 任一日期，回該日所在週

    Args:
        year: week_number 模式才用，預設今年。

    ⚠️ AI 透過 Gemini Function Calling 呼叫時，所有參數都是 string —
       裡面 coerce 成正確型別（date / int），失敗就 ToolResult.fail。

    Returns:
        ToolResult.success(data={...})（細節見 docstring 範例）
    """
    today = date.today()

    # ---- 強制 type coerce（防 AI 送 str）----
    def _to_int(v, name):
        if v is None or isinstance(v, int):
            return v
        try:
            return int(str(v).strip())
        except (ValueError, TypeError):
            return f"❌ {name} 必須是整數，收到: {v!r}"

    def _to_date(v):
        if v is None or isinstance(v, date):
            return v
        if not isinstance(v, str):
            return f"❌ target_date 型別不對: {type(v).__name__}"
        s = v.strip()
        # 試 YYYY-MM-DD 或 M/D
        try:
            return date.fromisoformat(s)
        except ValueError:
            pass
        try:
            from modules.utils.unified_date_parser import UnifiedDateParser
            return UnifiedDateParser.parse(s)
        except Exception as e:
            return f"❌ target_date 解析失敗: {s!r} ({e})"

    week_number = _to_int(week_number, 'week_number')
    week_offset = _to_int(week_offset, 'week_offset')
    year = _to_int(year, 'year')
    target_date = _to_date(target_date)
    for v in (week_number, week_offset, year, target_date):
        if isinstance(v, str) and v.startswith('❌'):
            return ToolResult.fail(v)

    # 算該週起點 ws
    if target_date is not None:
        ws = sun_week_start(target_date)
    elif week_number is not None:
        y = year if year is not None else today.year
        ws = sun_week_by_number(week_number, y)
    elif week_offset is not None:
        ws = sun_week_start(today) + timedelta(weeks=week_offset)
    else:
        ws = sun_week_start(today)  # 預設本週

    we = ws + timedelta(days=6)
    wn = sun_week_number(ws)

    # 算 label（相對今天）
    today_ws = sun_week_start(today)
    diff_weeks = (ws - today_ws).days // 7
    if diff_weeks == 0:
        label = '本週'
    elif diff_weeks == -1:
        label = '上週'
    elif diff_weeks == 1:
        label = '下週'
    elif diff_weeks == 2:
        label = '下下週'
    elif diff_weeks < 0:
        label = f'{abs(diff_weeks)} 週前'
    else:
        label = f'+{diff_weeks} 週'

    description = (
        f'W{wn} {label} {ws.month}/{ws.day}（日）-{we.month}/{we.day}（六）'
    )

    return ToolResult.success(
        data={
            'week_number': wn,
            'week_label': label,
            'date_start': ws,
            'date_end': we,
            'description': description,
        },
    )
