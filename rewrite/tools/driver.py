"""司機 atomic tools — 司機管理 + 司機自助回報車資

用途分兩塊：

  A. 司機管理（LINE 指令「司機列表 / 新增司機 / 停用司機 / 啟用司機 / 解綁司機」）
     - 司機清單一律從 DB 動態撈，不寫死 → 增減司機不用改程式
     - 停用 = is_active=False，**不真刪**（歷史班次的 driver_id 要留著）

  B. 司機自助回報車資（LIFF 表單 rewrite/handlers/liff/driver_fare.py）
     - line_user_id 綁定：司機第一次開表單點自己的名字，之後就認得人
     - query_driver_pending_fares 同時撈現在態 trips 與過去態 completed_trips
     - query_driver_week_fares 本太陽週（週日～今天）的車資清單＋合計

  C. 管理司機（drivers.is_manager）
     - 可切換檢視任何一位司機（含已停用的 9999「其他」）、代填車資
     - 一般司機維持現狀：只看得到、只改得到自己的

⚠️ 本檔**不做**車資寫入。寫車資一律呼叫既有工具：
     現在態 → rewrite.tools.trip.record_fare_current
     過去態 → rewrite.tools.completed_trip.update_completed_trip_fare
   本檔只負責「這筆是不是這位司機的」授權檢查（check_driver_owns_record）。

依賴 migrations/010_drivers_line_binding.sql（drivers.line_user_id / is_active）
   ＋ migrations/011_drivers_is_manager.sql（drivers.is_manager）。
"""
from dataclasses import dataclass, asdict
from datetime import date as _date, timedelta
from typing import List, Optional

from sqlalchemy import text

from modules.utils.taiwan_time import get_taiwan_time
from rewrite.tools.base import ToolResult, diff_fields, write_audit
from rewrite.utils.sun_week import sun_week_start


# ============================================================
# View 結構
# ============================================================

# 不是「人」的司機列 —— 派車照用（叫外車資源），但不該出現在
# 「請問你是哪一位？」的身分選單裡，也不接受綁定 LINE 帳號。
# 管理司機（老闆/春妃）的切換選單仍看得到，可代填車資。
NON_BINDABLE_DRIVER_IDS = {9999}   # 9999 = 其他（外車）


# 車號的佔位字（歷史資料留下的），顯示時視同空值
_PLACEHOLDER_PLATES = {'留空後補', '待補', '未填', '無', '-', '其他'}


@dataclass
class DriverView:
    """司機展示用結構"""
    id: int
    name: Optional[str] = None
    plate_number: Optional[str] = None
    line_user_id: Optional[str] = None
    is_active: bool = True
    is_manager: bool = False        # 可代任何司機填車資／看車資（老闆、內勤）

    # 計算欄位
    is_bound: bool = False          # 已綁 LINE 帳號
    display_name: str = ''          # 「編號　姓名」— LIFF 大按鈕用（編號為主）

    @classmethod
    def from_row(cls, row) -> "DriverView":
        d = dict(row._mapping)
        d['is_active'] = bool(d.get('is_active')) if d.get('is_active') is not None else True
        d['is_manager'] = bool(d.get('is_manager'))
        d['is_bound'] = bool(d.get('line_user_id'))
        name = d.get('name') or f"#{d.get('id')}"
        plate = (d.get('plate_number') or '').strip()
        # 佔位字視同沒填 — 否則大按鈕會寫「黃清池（留空後補）」
        if plate in _PLACEHOLDER_PLATES or plate == name:
            plate = ''
        # 用戶定調（2026-08-02）：抬頭與選單一律以**司機編號**為主
        #（有些司機老闆也不知道姓名，但編號人人記得）
        raw_name = (d.get('name') or '').strip()
        if raw_name and raw_name != f"#{d.get('id')}":
            d['display_name'] = f"{d.get('id')}　{raw_name}"
        else:
            d['display_name'] = str(d.get('id'))
        valid = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        return cls(**valid)

    def to_dict(self) -> dict:
        return asdict(self)


_SELECT_DRIVER = """
    SELECT id, name, plate_number, line_user_id, is_active,
           COALESCE(is_manager, FALSE) AS is_manager
    FROM drivers
"""


def _coerce_int(v):
    """AI / 表單偶爾把 integer 傳成字串 → 轉 int；轉不動回 None。"""
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, str):
        s = v.strip()
        neg = s.startswith('-')
        digits = s[1:] if neg else s
        if digits.isdigit():
            return int(s)
    return None


def _fetch_driver(*, session, driver_id: int) -> Optional[dict]:
    row = session.execute(
        text(_SELECT_DRIVER + " WHERE id = :id"), {'id': driver_id},
    ).fetchone()
    return dict(row._mapping) if row else None


# ============================================================
# 查詢
# ============================================================

def query_drivers(
    *, session, active_only: bool = True, include_inactive: bool = False,
) -> ToolResult:
    """司機清單（動態撈，增減司機不用改程式）。

    Args:
        active_only: True（預設）只回啟用中的；False 連停用的一起回（司機列表用）
        include_inactive: True 一律連停用的一起回（覆蓋 active_only）。
            管理司機的「檢視誰」切換選單要用 —— 停用的 9999「其他」也得看得到，
            舊班次還掛在它名下。

    Returns:
        ToolResult.success(data=[DriverView, ...], count=n)
    """
    sql = _SELECT_DRIVER
    if active_only and not include_inactive:
        sql += " WHERE COALESCE(is_active, TRUE) = TRUE"
    # 停用的排後面，管理員的選單才不會被 9999 卡在中間
    sql += " ORDER BY COALESCE(is_active, TRUE) DESC, id"
    rows = session.execute(text(sql)).fetchall()
    views = [DriverView.from_row(r) for r in rows]
    return ToolResult.success(data=views, count=len(views))


def get_driver_by_id(*, session, driver_id: int) -> ToolResult:
    """單一司機（管理司機切換檢視對象時用）。

    Returns:
        ok=True, data=DriverView — 找得到（停用的也回，管理員要看 9999）
        ok=False               — 找不到
    """
    driver_id = _coerce_int(driver_id)
    if driver_id is None:
        return ToolResult.fail("driver_id 必填且要是數字")
    row = _fetch_driver(session=session, driver_id=driver_id)
    if not row:
        return ToolResult.fail(f"找不到司機 #{driver_id}")
    return ToolResult.success(data=_view_from_dict(row))


def get_driver_by_line_user(*, session, line_user_id: str) -> ToolResult:
    """用 LINE userId 查綁定的司機。

    Returns:
        ok=True, data=DriverView  — 已綁定
        ok=True, data=None        — 沒綁定（**不是錯誤**，前端要顯示「請問你是哪一位？」）
    """
    if not line_user_id or not str(line_user_id).strip():
        return ToolResult.fail("line_user_id 必填")
    row = session.execute(
        text(_SELECT_DRIVER + " WHERE line_user_id = :luid"),
        {'luid': str(line_user_id).strip()},
    ).fetchone()
    if not row:
        return ToolResult.success(data=None, bound=False)
    return ToolResult.success(data=DriverView.from_row(row), bound=True)


# ============================================================
# 綁定 / 解綁
# ============================================================

def bind_driver_line_user(
    *,
    session,
    driver_id: int,
    line_user_id: str,
    user_id: Optional[str] = None,
    user_name: Optional[str] = None,
    via: str = 'unknown',
    auto_commit: bool = True,
) -> ToolResult:
    """把 LINE 帳號綁到司機身上（司機在 LIFF 點自己的名字時觸發）。

    防呆（兩個方向都擋，避免「兩個人共用一個名字」或「一人佔兩個名字」）：
      - 該司機已綁**別的** LINE 帳號 → fail（要先「解綁司機 N」）
      - 該 LINE 帳號已綁**別的**司機 → fail（同上）
      - 已停用的司機 → fail
      - 綁的是同一組（重複點）→ success，不重寫、不寫 audit
    """
    if driver_id in NON_BINDABLE_DRIVER_IDS:
        return ToolResult.fail(
            f"司機 {driver_id} 是外車代碼，不能綁定 LINE 帳號；"
            f"這類班次的車資由公司代填")
    driver_id = _coerce_int(driver_id)
    if driver_id is None:
        return ToolResult.fail("driver_id 必填且要是數字")
    luid = (line_user_id or '').strip()
    if not luid:
        return ToolResult.fail("line_user_id 必填")

    before = _fetch_driver(session=session, driver_id=driver_id)
    if not before:
        return ToolResult.fail(f"找不到司機 #{driver_id}")
    if before.get('is_active') is False:
        return ToolResult.fail(
            f"司機 #{driver_id} {before.get('name') or ''} 已停用，"
            f"請先「啟用司機 {driver_id}」"
        )

    current = before.get('line_user_id')
    if current == luid:
        # 重複點同一位（例如按兩下）→ 視為成功，不重寫也不寫 audit
        return ToolResult.success(data=_view_from_dict(before), already_bound=True)
    if current:
        return ToolResult.fail(
            f"司機 #{driver_id} {before.get('name') or ''} 已綁定其他 LINE 帳號。\n"
            f"若要換人／換手機，請先打「解綁司機 {driver_id}」"
        )

    other = session.execute(
        text("SELECT id, name FROM drivers WHERE line_user_id = :luid"),
        {'luid': luid},
    ).fetchone()
    if other:
        return ToolResult.fail(
            f"這個 LINE 帳號已經綁定司機 #{other[0]} {other[1] or ''}。\n"
            f"若要改綁，請先打「解綁司機 {other[0]}」"
        )

    session.execute(
        text("UPDATE drivers SET line_user_id = :luid WHERE id = :id"),
        {'luid': luid, 'id': driver_id},
    )
    after = _fetch_driver(session=session, driver_id=driver_id)
    write_audit(
        session=session, user_id=user_id or luid, user_name=user_name or before.get('name'),
        action_type='bind_driver_line_user', target_table='drivers', target_id=driver_id,
        before_state=before, after_state=after,
        changed_fields=diff_fields(before, after),
        extra={'line_user_id_tail': luid[-6:]},
        via=via,
    )
    if auto_commit:
        session.commit()
    return ToolResult.success(data=_view_from_dict(after))


def unbind_driver(
    *,
    session,
    driver_id: int,
    user_id: Optional[str] = None,
    user_name: Optional[str] = None,
    via: str = 'unknown',
    auto_commit: bool = True,
) -> ToolResult:
    """解除司機的 LINE 綁定（司機換手機 / 綁錯人時用）"""
    driver_id = _coerce_int(driver_id)
    if driver_id is None:
        return ToolResult.fail("driver_id 必填且要是數字")

    before = _fetch_driver(session=session, driver_id=driver_id)
    if not before:
        return ToolResult.fail(f"找不到司機 #{driver_id}")
    if not before.get('line_user_id'):
        return ToolResult.fail(f"司機 #{driver_id} {before.get('name') or ''} 本來就沒有綁定")

    session.execute(
        text("UPDATE drivers SET line_user_id = NULL WHERE id = :id"),
        {'id': driver_id},
    )
    after = _fetch_driver(session=session, driver_id=driver_id)
    write_audit(
        session=session, user_id=user_id, user_name=user_name,
        action_type='unbind_driver', target_table='drivers', target_id=driver_id,
        before_state=before, after_state=after,
        changed_fields=diff_fields(before, after),
        via=via,
    )
    if auto_commit:
        session.commit()
    return ToolResult.success(data=_view_from_dict(after))


# ============================================================
# 增 / 停用 / 啟用
# ============================================================

def create_driver(
    *,
    session,
    name: str,
    plate_number: Optional[str] = None,
    driver_id: Optional[int] = None,
    user_id: Optional[str] = None,
    user_name: Optional[str] = None,
    via: str = 'unknown',
    auto_commit: bool = True,
) -> ToolResult:
    """新增司機。

    Args:
        driver_id: 可指定（本系統的司機編號 = 有意義的車號，如 5386）；
                   不指定就走 drivers_id_seq。
    """
    name = (name or '').strip()
    if not name:
        return ToolResult.fail("司機姓名必填")
    plate = (plate_number or '').strip() or None

    if driver_id is not None:
        driver_id = _coerce_int(driver_id)
        if driver_id is None or driver_id <= 0:
            return ToolResult.fail("司機編號要是正整數")
        exists = _fetch_driver(session=session, driver_id=driver_id)
        if exists:
            return ToolResult.fail(
                f"司機編號 #{driver_id} 已存在（{exists.get('name')}），請換一個編號"
            )
        session.execute(
            text("""
                INSERT INTO drivers (id, name, plate_number, is_active)
                VALUES (:id, :name, :plate, TRUE)
            """),
            {'id': driver_id, 'name': name, 'plate': plate},
        )
        # 手動指定 id 不會推進序列 → 補推，之後沒指定 id 的新增才不會撞號
        try:
            session.execute(text("""
                SELECT setval(
                    pg_get_serial_sequence('drivers', 'id'),
                    GREATEST((SELECT MAX(id) FROM drivers), 1)
                )
            """))
        except Exception:  # 序列不存在（非 serial 欄位）不擋主流程
            pass
        new_id = driver_id
    else:
        row = session.execute(
            text("""
                INSERT INTO drivers (name, plate_number, is_active)
                VALUES (:name, :plate, TRUE)
                RETURNING id
            """),
            {'name': name, 'plate': plate},
        ).fetchone()
        new_id = row[0]

    after = _fetch_driver(session=session, driver_id=new_id)
    write_audit(
        session=session, user_id=user_id, user_name=user_name,
        action_type='create_driver', target_table='drivers', target_id=new_id,
        before_state=None, after_state=after,
        extra={'name': name, 'plate_number': plate},
        via=via,
    )
    if auto_commit:
        session.commit()
    return ToolResult.success(data=_view_from_dict(after))


def set_driver_active(
    *,
    session,
    driver_id: int,
    active: bool,
    user_id: Optional[str] = None,
    user_name: Optional[str] = None,
    via: str = 'unknown',
    auto_commit: bool = True,
) -> ToolResult:
    """停用 / 啟用司機。

    停用**不刪 row** —— 歷史班次（trips / completed_trips）的 driver_id 要留著，
    只是不再出現在 LIFF 的司機選單、司機列表會標「⏸️ 停用」。
    """
    driver_id = _coerce_int(driver_id)
    if driver_id is None:
        return ToolResult.fail("driver_id 必填且要是數字")
    active = bool(active)

    before = _fetch_driver(session=session, driver_id=driver_id)
    if not before:
        return ToolResult.fail(f"找不到司機 #{driver_id}")
    current = True if before.get('is_active') is None else bool(before.get('is_active'))
    if current == active:
        word = '啟用中' if active else '停用中'
        return ToolResult.fail(f"司機 #{driver_id} {before.get('name') or ''} 已經是{word}")

    session.execute(
        text("UPDATE drivers SET is_active = :act WHERE id = :id"),
        {'act': active, 'id': driver_id},
    )
    after = _fetch_driver(session=session, driver_id=driver_id)
    write_audit(
        session=session, user_id=user_id, user_name=user_name,
        action_type='set_driver_active', target_table='drivers', target_id=driver_id,
        before_state=before, after_state=after,
        changed_fields=diff_fields(before, after),
        extra={'active': active},
        via=via,
    )
    if auto_commit:
        session.commit()
    return ToolResult.success(data=_view_from_dict(after))


# ============================================================
# 司機自助回報車資：待補清單 + 授權檢查
# ============================================================

# 「缺車資」：錶價空或 0（加成不算 —— 加成常態就是 0）
_MISSING_FARE = "(meter_fare IS NULL OR meter_fare = 0)"
# 請假班次的車資由老闆用加成處理，司機沒跑不用回報 → 不列入待補
_NOT_LEAVE = "(passenger_leave_reason IS NULL OR passenger_leave_reason = '')"


def _route_of(start, via, end) -> str:
    parts = [start or '?']
    if via:
        parts.append(f"經{via}")
    parts.append(end or '?')
    return ' → '.join(p for p in parts if p)


def query_driver_pending_fares(*, session, driver_id: int, days: int = 1) -> ToolResult:
    """該司機「今天（可含前 N-1 天）」缺車資的班次 —— 現在態＋過去態一起撈。

    為什麼要撈兩張表：班次執行時間一到會由排程從 trips 掉進 completed_trips，
    司機打開表單的當下，同一天的班次可能一半在生產線、一半已入庫（今天是流動的邊界）。

    現在態（trips）只取執行時間已過、且**還沒**被排程掃成「已完成」的
    （status='已完成' 的 trips row 已經複製一份到 completed_trips，
      兩邊都列會變成同一趟車出現兩次）。
    註銷 / 衝突 / 請假的班次不列入。

    Args:
        days: 1 = 只有今天（預設）；3 = 今天 + 前 2 天

    Returns:
        ToolResult.success(data=[{
            source: 'trip'|'completed', id, date('YYYY-MM-DD'), time('HH:MM'|None),
            route('起 → 終'), category, meter_fare, extra_fare, passenger_name,
        }, ...], count=n, date_from=..., date_to=...)
        排序：日期→時間（過去態無時間欄位，排在同日最後）
    """
    driver_id = _coerce_int(driver_id)
    if driver_id is None:
        return ToolResult.fail("driver_id 必填且要是數字")
    days = _coerce_int(days) or 1
    if days < 1:
        days = 1
    if days > 31:
        days = 31

    now = get_taiwan_time()
    today: _date = now.date()
    date_from = today - timedelta(days=days - 1)

    trip_rows = session.execute(
        text(f"""
            SELECT trip_id, date, time, category, meter_fare, extra_fare,
                   start_point, via_point, end_point,
                   custom_start_point, custom_via_point, custom_end_point,
                   trip_type, passenger_name
            FROM trips
            WHERE driver_id = :did
              AND date BETWEEN :d_from AND :today
              AND (date < :today OR time <= :now_t)
              AND status NOT IN ('已完成', '註銷', '衝突')
              AND {_MISSING_FARE}
              AND {_NOT_LEAVE}
            ORDER BY date, time
        """),
        {'did': driver_id, 'd_from': date_from, 'today': today, 'now_t': now.time()},
    ).fetchall()

    completed_rows = session.execute(
        text(f"""
            SELECT id, date, category, meter_fare, extra_fare,
                   start_point, via_point, end_point, passenger_name
            FROM completed_trips
            WHERE driver_id = :did
              AND date BETWEEN :d_from AND :today
              AND (status IS NULL OR status <> '已取消')
              AND {_MISSING_FARE}
              AND {_NOT_LEAVE}
            ORDER BY date, id
        """),
        {'did': driver_id, 'd_from': date_from, 'today': today},
    ).fetchall()

    items: List[dict] = []
    for r in trip_rows:
        d = dict(r._mapping)
        is_temp = d.get('trip_type') == 'temp'
        sp = (d.get('custom_start_point') or d.get('start_point')) if is_temp else d.get('start_point')
        vp = (d.get('custom_via_point') or d.get('via_point')) if is_temp else d.get('via_point')
        ep = (d.get('custom_end_point') or d.get('end_point')) if is_temp else d.get('end_point')
        items.append({
            'source': 'trip',
            'id': d['trip_id'],
            'date': d['date'].isoformat() if d.get('date') else None,
            'time': d['time'].strftime('%H:%M') if d.get('time') else None,
            'route': _route_of(sp, vp, ep),
            'category': d.get('category'),
            'meter_fare': d.get('meter_fare'),
            'extra_fare': d.get('extra_fare'),
            'passenger_name': d.get('passenger_name'),
        })
    for r in completed_rows:
        d = dict(r._mapping)
        items.append({
            'source': 'completed',
            'id': d['id'],
            'date': d['date'].isoformat() if d.get('date') else None,
            'time': None,   # completed_trips 沒有 time 欄位
            'route': _route_of(d.get('start_point'), d.get('via_point'), d.get('end_point')),
            'category': d.get('category'),
            'meter_fare': d.get('meter_fare'),
            'extra_fare': d.get('extra_fare'),
            'passenger_name': d.get('passenger_name'),
        })

    # 日期 → 時間（無時間的過去態排同日最後）→ id
    items.sort(key=lambda it: (it['date'] or '', it['time'] or '99:99', it['id']))
    return ToolResult.success(
        data=items, count=len(items),
        date_from=date_from.isoformat(), date_to=today.isoformat(),
    )


def query_driver_week_fares(*, session, driver_id: int) -> ToolResult:
    """本太陽週（星期日 ~ 今天）該司機的車資清單 ＋ 合計。

    ⚠️ 週界一律走 rewrite/utils/sun_week.sun_week_start（星期日起算），**不自己算**
       （CLAUDE.md：ISO 週會錯一天，週結算會對不上）。

    收錄範圍跟待補清單同一套判定，只是不限「缺車資」——
    司機要看的是「這星期到目前跑了什麼、賺了多少、哪幾筆還沒填」：
      現在態 trips           週日 ~ 今天、執行時間已過、status 不在（已完成／註銷／衝突）
      過去態 completed_trips 週日 ~ 今天、非「已取消」
      兩張表都排除請假班次（司機沒跑，加成由老闆處理，不是司機的車資）
    status='已完成' 的 trips row 已複製一份到 completed_trips，只取過去態那份，
    否則同一趟車會出現兩次。

    Returns:
        ToolResult.success(
            data=[{source, id, date('YYYY-MM-DD'), time('HH:MM'|None), route,
                   category, meter_fare, extra_fare, total, has_fare}, ...],
            week_start='YYYY-MM-DD'（星期日）, week_end='YYYY-MM-DD'（今天，資料截止日）,
            count=總筆數, filled_count=已填車資筆數, sum_amount=已填車資的錶價+加成加總,
        )
        has_fare=False 的筆數就是「還沒填的」，total 為 0，不計入 sum_amount。
    """
    driver_id = _coerce_int(driver_id)
    if driver_id is None:
        return ToolResult.fail("driver_id 必填且要是數字")

    now = get_taiwan_time()
    today: _date = now.date()
    week_start = sun_week_start(today)      # ← 太陽週 helper，不自己算

    trip_rows = session.execute(
        text(f"""
            SELECT trip_id, date, time, category, meter_fare, extra_fare,
                   start_point, via_point, end_point,
                   custom_start_point, custom_via_point, custom_end_point,
                   trip_type, passenger_name
            FROM trips
            WHERE driver_id = :did
              AND date BETWEEN :ws AND :today
              AND (date < :today OR time <= :now_t)
              AND status NOT IN ('已完成', '註銷', '衝突')
              AND {_NOT_LEAVE}
            ORDER BY date, time
        """),
        {'did': driver_id, 'ws': week_start, 'today': today, 'now_t': now.time()},
    ).fetchall()

    completed_rows = session.execute(
        text(f"""
            SELECT id, date, category, meter_fare, extra_fare,
                   start_point, via_point, end_point, passenger_name
            FROM completed_trips
            WHERE driver_id = :did
              AND date BETWEEN :ws AND :today
              AND (status IS NULL OR status <> '已取消')
              AND {_NOT_LEAVE}
            ORDER BY date, id
        """),
        {'did': driver_id, 'ws': week_start, 'today': today},
    ).fetchall()

    def _pack(*, source, rid, d, tm, route, category, meter, extra) -> dict:
        # 「已填」的判定跟待補清單一致：錶價空或 0 就是還沒填
        has_fare = meter is not None and meter != 0
        return {
            'source': source,
            'id': rid,
            'date': d.isoformat() if d else None,
            'time': tm,
            'route': route,
            'category': category,
            'meter_fare': meter,
            'extra_fare': extra,
            'total': (meter or 0) + (extra or 0) if has_fare else 0,
            'has_fare': has_fare,
        }

    items: List[dict] = []
    for r in trip_rows:
        d = dict(r._mapping)
        is_temp = d.get('trip_type') == 'temp'
        sp = (d.get('custom_start_point') or d.get('start_point')) if is_temp else d.get('start_point')
        vp = (d.get('custom_via_point') or d.get('via_point')) if is_temp else d.get('via_point')
        ep = (d.get('custom_end_point') or d.get('end_point')) if is_temp else d.get('end_point')
        items.append(_pack(
            source='trip', rid=d['trip_id'], d=d.get('date'),
            tm=d['time'].strftime('%H:%M') if d.get('time') else None,
            route=_route_of(sp, vp, ep), category=d.get('category'),
            meter=d.get('meter_fare'), extra=d.get('extra_fare'),
        ))
    for r in completed_rows:
        d = dict(r._mapping)
        items.append(_pack(
            source='completed', rid=d['id'], d=d.get('date'),
            tm=None,   # completed_trips 沒有 time 欄位
            route=_route_of(d.get('start_point'), d.get('via_point'), d.get('end_point')),
            category=d.get('category'),
            meter=d.get('meter_fare'), extra=d.get('extra_fare'),
        ))

    items.sort(key=lambda it: (it['date'] or '', it['time'] or '99:99', it['id']))
    filled = [it for it in items if it['has_fare']]
    return ToolResult.success(
        data=items,
        week_start=week_start.isoformat(),
        week_end=today.isoformat(),
        count=len(items),
        filled_count=len(filled),
        sum_amount=sum(it['total'] for it in filled),
    )


_VALID_SOURCES = ('trip', 'completed')


def check_driver_owns_record(
    *, session, driver_id: int, source: str, record_id: int, acting_driver=None,
) -> ToolResult:
    """授權檢查：這筆班次確實是「目前檢視的那位司機」的嗎？

    Args:
        driver_id: 目前檢視的司機（車資要寫到誰頭上）
        acting_driver: 實際在操作的人（DriverView，可省略 = 就是本人）。
            管理司機（is_manager）可以代任何司機填 → 放行 driver_id ≠ 自己；
            一般司機只能是自己（handler 本來就只傳自己的 id，這裡再擋一層）。

    ⚠️ 管理司機**不是**無條件放行 —— 仍要驗這筆確實屬於「檢視中的那位」，
       否則切到 A 司機卻手殘送出 B 司機的班次編號就寫到第三人頭上了。

    司機表單送上來的 (source, id) 是 client 端資料，必須回頭驗一次，
    不然改 payload 就能動到別人的班次。
    """
    driver_id = _coerce_int(driver_id)
    record_id = _coerce_int(record_id)
    if driver_id is None or record_id is None:
        return ToolResult.fail("driver_id / id 必填且要是數字")
    if source not in _VALID_SOURCES:
        return ToolResult.fail(f"source 必須是 {' / '.join(_VALID_SOURCES)}")

    acting_id = _coerce_int(getattr(acting_driver, 'id', None))
    acting_is_manager = bool(getattr(acting_driver, 'is_manager', False))
    on_behalf = acting_id is not None and acting_id != driver_id
    if on_behalf and not acting_is_manager:
        return ToolResult.fail("只能填自己的班次車資")

    if source == 'trip':
        row = session.execute(
            text("SELECT driver_id FROM trips WHERE trip_id = :id"), {'id': record_id},
        ).fetchone()
        label = f"班次 #{record_id}"
    else:
        row = session.execute(
            text("SELECT driver_id FROM completed_trips WHERE id = :id"), {'id': record_id},
        ).fetchone()
        label = f"已完成班次 #{record_id}"

    if not row:
        return ToolResult.fail(f"找不到{label}")
    if row[0] != driver_id:
        whose = '這位司機' if on_behalf else '你'
        return ToolResult.fail(f"{label} 不是{whose}的班次，不能修改")
    return ToolResult.success(data=True)


# ============================================================
# 內部 helper
# ============================================================

class _RowLike:
    """把 dict 包成有 _mapping 的物件，讓 DriverView.from_row 通吃"""
    __slots__ = ('_mapping',)

    def __init__(self, d: dict):
        self._mapping = d


def _view_from_dict(d: Optional[dict]) -> Optional[DriverView]:
    return DriverView.from_row(_RowLike(d)) if d else None
