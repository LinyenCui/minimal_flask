"""
班次「身分證」重算 — 改日期時 unique_code / week_number 的連動處理

為什麼需要這個模組：
    unique_code 是兩件事的比對主鍵，而**日期被編在裡面**：
      · scheduler_service：班次掉進 completed_trips 時
        `ON CONFLICT (unique_code) DO NOTHING`
      · sync_from_render：Render ↔ 本地同步
        `ON CONFLICT (unique_code) DO UPDATE`

    格式有兩種（都含日期）：
      預約 temp   T_{trip_id}_{YYYYMMDD}          （trip.create_temp_trip）
      固定 fixed  {fixed_id}_{day_of_year}_{iso_week}（import_fixed）

    所以「只改 date 不改 unique_code」會產生一筆**身分證說謊**的資料。
    最糟的情況不是顯示錯，是靜默掉資料：
      固定班次改掉日期 → 之後重匯那一週 → 新班次拿到跟它一樣的 code
      → 兩筆都掉進 completed_trips → 後面那筆撞 DO NOTHING 被丟掉
      → 那趟車的車資從已完成記錄裡消失，且沒有任何錯誤訊息。

    資料庫幫不上忙：全庫只有一個 trigger（customers.updated_at），
    沒有任何東西會自動補這兩個欄位。

為什麼是「改寫既有 code」而不是「重新產生」：
    前面那段識別碼（預約的原始 trip_id、固定的 fixed_schedule_id）跟日期無關，
    而且 completed_trips **沒有** fixed_trip_id 欄、它的 id 也不等於原始 trip_id，
    所以唯一取得那段的辦法就是從 code 本身取回。
    看不懂的格式一律回 None，讓呼叫端拒絕 —— 寧可不給改，
    也不要寫出一張半殘的身分證。
"""
import re
from datetime import date as _date
from typing import Optional, Tuple

# T_{原始trip_id}_{YYYYMMDD}
_TEMP_RE = re.compile(r'^(T_\d+)_(\d{8})$')
# {fixed_schedule_id}_{day_of_year}_{iso_week}
_FIXED_RE = re.compile(r'^(\d+)_(\d{1,3})_(\d{1,2})$')


def iso_week_number(d: _date) -> int:
    """week_number 欄位存的是 ISO 週（import_fixed 用 isocalendar()）。

    ⚠️ 這跟業務上的「太陽週」（星期日起算、strftime('%U')）不是同一個東西。
    這裡刻意跟既有寫入端一致，不要改成太陽週 —— 那會讓新舊資料對不起來。
    """
    return d.isocalendar()[1]


def recompute_unique_code(old_code: Optional[str],
                          new_date: _date) -> Tuple[Optional[str], Optional[str]]:
    """把 unique_code 裡的日期換成 new_date，識別碼那段原樣保留。

    Returns:
        (new_code, kind)
        kind = 'temp' / 'fixed'
        原本就沒有 code（None/空）→ (None, 'none')：本來就沒身分證，不用維護
        格式看不懂                → (None, None)：呼叫端必須拒絕這次修改
    """
    code = (old_code or '').strip()
    if not code:
        return None, 'none'

    m = _TEMP_RE.match(code)
    if m:
        return f"{m.group(1)}_{new_date.strftime('%Y%m%d')}", 'temp'

    m = _FIXED_RE.match(code)
    if m:
        doy = new_date.timetuple().tm_yday
        return f"{m.group(1)}_{doy}_{iso_week_number(new_date)}", 'fixed'

    return None, None


def describe_identity_change(old_code: Optional[str], new_code: Optional[str],
                             old_week, new_week) -> str:
    """給確認卡/回覆用的一句話，讓人看得出連帶改了什麼。"""
    bits = []
    if old_code != new_code:
        bits.append(f"識別碼 {old_code} → {new_code}")
    if old_week != new_week:
        bits.append(f"週次 {old_week} → {new_week}")
    return '；'.join(bits)
