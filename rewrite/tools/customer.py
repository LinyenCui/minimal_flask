"""
客戶查詢 tool（v0.1 風格）

設計原則：
  R-4：純函數，session 從參數傳入，不依賴 Flask globals

功能：
  - query_customer：精確/結構化查詢（多欄位 cascade fallback）
  - query_customer_by_term：自然語言模糊查詢（給 AI 用）

輸出含「病歷層」（生日的日）自動計算欄位 — 服務門診人員找病歷層級。

⚠️ 2026-05-08: drop national_id / insurance_type 兩欄（用戶決定不收身分證、
   健保身份 99% 都健保等於廢欄；自費少數 case 寫 remarks 即可）。
"""

from dataclasses import dataclass, field, asdict
from datetime import date, datetime
from typing import Optional, List, Any
from sqlalchemy import text

from rewrite.tools.base import ToolResult


# ============================================================
# View 結構
# ============================================================

@dataclass
class CustomerView:
    """
    客戶展示用結構（含計算欄位）

    計算欄位：birthday_day（病歷層）, age（年齡）
    """
    id: int
    short_name: Optional[str] = None
    name: Optional[str] = None
    address: Optional[str] = None
    category: Optional[str] = None
    contact_phone: Optional[str] = None
    remarks: Optional[str] = None

    # 個人資料
    birthday: Optional[date] = None
    gender: Optional[str] = None
    medical_record_no: Optional[str] = None
    dm_care_no: Optional[str] = None  # 糖尿病共同照護網代號（診所內部編號）

    # 座標
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    # 時間戳
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # 計算欄位
    birthday_day: Optional[int] = None  # 病歷層（生日的日）
    age: Optional[int] = None           # 年齡

    @classmethod
    def from_row(cls, row, *, mask_id: bool = True) -> "CustomerView":
        """從 SQLAlchemy row 建構

        mask_id 參數保留作 backward-compat 但不再使用（national_id drop 了）
        """
        d = dict(row._mapping)

        # 計算病歷層
        bd = d.get('birthday')
        d['birthday_day'] = bd.day if bd else None

        # 計算年齡
        if bd:
            today = date.today()
            d['age'] = today.year - bd.year - ((today.month, today.day) < (bd.month, bd.day))
        else:
            d['age'] = None

        # 浮點化
        for k in ('latitude', 'longitude'):
            if d.get(k) is not None:
                d[k] = float(d[k])

        # 過濾出 dataclass 認的欄位
        valid = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        return cls(**valid)

    def to_dict(self) -> dict:
        return asdict(self)


# ============================================================
# 主要查詢工具
# ============================================================

# 共用 SELECT
_SELECT_ALL = """
    SELECT id, short_name, name, address, category, contact_phone, remarks,
           birthday, gender, medical_record_no, dm_care_no,
           latitude, longitude, created_at, updated_at
    FROM customers
"""


def query_customer(
    *,
    session,
    short_name: Optional[str] = None,
    name: Optional[str] = None,
    address: Optional[str] = None,
    medical_record_no: Optional[str] = None,
    dm_care_no: Optional[str] = None,
    fuzzy_name: bool = True,
    fuzzy_address: bool = True,
    mask_id: bool = True,  # backward-compat，不再使用
    limit: int = 20,
) -> ToolResult:
    """
    精確/結構化查詢，多欄位 cascade fallback。

    cascade 順序：
      1. short_name 精確
      2. medical_record_no 精確
      3. dm_care_no 精確（糖尿病共同照護網代號）
      4. name（精確或模糊）
      5. address 模糊

    任一階段命中 = 回傳，後面不再嘗試。
    """
    # 1. 精確 short_name
    if short_name:
        rows = session.execute(
            text(f"{_SELECT_ALL} WHERE short_name = :v"),
            {'v': short_name}
        ).fetchall()
        if rows:
            return ToolResult.success(
                data=[CustomerView.from_row(r) for r in rows],
                matched_by='short_name',
            )

    # 2. 病歷號
    if medical_record_no:
        rows = session.execute(
            text(f"{_SELECT_ALL} WHERE medical_record_no = :v"),
            {'v': medical_record_no}
        ).fetchall()
        if rows:
            return ToolResult.success(
                data=[CustomerView.from_row(r) for r in rows],
                matched_by='medical_record_no',
            )

    # 3. 糖尿病共同照護網代號
    if dm_care_no:
        rows = session.execute(
            text(f"{_SELECT_ALL} WHERE dm_care_no = :v"),
            {'v': dm_care_no}
        ).fetchall()
        if rows:
            return ToolResult.success(
                data=[CustomerView.from_row(r) for r in rows],
                matched_by='dm_care_no',
            )

    # 4. name
    if name:
        sql = (f"{_SELECT_ALL} WHERE name LIKE :v ORDER BY id LIMIT :l"
               if fuzzy_name else
               f"{_SELECT_ALL} WHERE name = :v ORDER BY id LIMIT :l")
        v = f'%{name}%' if fuzzy_name else name
        rows = session.execute(text(sql), {'v': v, 'l': limit}).fetchall()
        if rows:
            return ToolResult.success(
                data=[CustomerView.from_row(r) for r in rows],
                matched_by='name' + ('(fuzzy)' if fuzzy_name else ''),
            )

    # 5. address 模糊
    if address:
        sql = (f"{_SELECT_ALL} WHERE address LIKE :v ORDER BY id LIMIT :l"
               if fuzzy_address else
               f"{_SELECT_ALL} WHERE address = :v ORDER BY id LIMIT :l")
        v = f'%{address}%' if fuzzy_address else address
        rows = session.execute(text(sql), {'v': v, 'l': limit}).fetchall()
        if rows:
            return ToolResult.success(
                data=[CustomerView.from_row(r) for r in rows],
                matched_by='address' + ('(fuzzy)' if fuzzy_address else ''),
            )

    return ToolResult.fail("找不到符合條件的客戶")


def query_customer_by_term(
    term: str,
    *,
    session,
    mask_id: bool = True,  # backward-compat，不再使用
    limit: int = 20,
) -> ToolResult:
    """
    自然語言模糊查詢（給 AI 或自由輸入用）

    會嘗試把 term 當作 short_name / medical_record_no / dm_care_no /
    name / address。cascade 找到任一就回傳。
    """
    if not term or not term.strip():
        return ToolResult.fail("請提供查詢關鍵字")

    term = term.strip()

    # heuristic: 純數字 4-8 位 → 可能是病歷號或共照網代號（cascade 內依序試）
    looks_like_code = term.isdigit() and 4 <= len(term) <= 8

    return query_customer(
        session=session,
        short_name=term,                            # 試簡稱
        medical_record_no=term if looks_like_code else None,
        dm_care_no=term if looks_like_code else None,
        name=term,                                  # 模糊姓名
        address=term,                               # 模糊地址
        limit=limit,
    )


def get_customer_by_id(
    customer_id: int,
    *,
    session,
    mask_id: bool = True,  # backward-compat，不再使用
) -> ToolResult:
    """單筆 ID 查詢"""
    row = session.execute(
        text(f"{_SELECT_ALL} WHERE id = :id"),
        {'id': customer_id}
    ).fetchone()
    if row:
        return ToolResult.success(data=CustomerView.from_row(row))
    return ToolResult.fail(f"找不到 customer #{customer_id}")


def query_customers_by_birthday_day(
    *,
    session,
    day: int,
    mask_id: bool = True,  # backward-compat，不再使用
) -> ToolResult:
    """
    依「生日的日」查客戶（病歷層查詢）

    用途：門診人員看到生日的日就知道病歷在哪一層，
         需要列出某一層的所有客戶（例如「病歷層 23 日」有誰）。

    Args:
        day: 1–31

    回傳：依完整生日（年月日）排序的客戶列表。
    """
    if not isinstance(day, int) or not 1 <= day <= 31:
        return ToolResult.fail(f"day 必須是 1-31 的整數，收到: {day!r}")

    rows = session.execute(
        text(f"""
            {_SELECT_ALL}
            WHERE birthday IS NOT NULL
              AND EXTRACT(DAY FROM birthday)::int = :day
            ORDER BY birthday
        """),
        {'day': day}
    ).fetchall()

    if not rows:
        return ToolResult.fail(f"沒有客戶生日是 {day} 日（病歷層 {day} 為空）")

    return ToolResult.success(
        data=[CustomerView.from_row(r) for r in rows],
        day=day,
        count=len(rows),
        matched_by='birthday_day',
    )


def query_birthday_day_summary(*, session) -> ToolResult:
    """
    病歷層總覽：每一層各有多少客戶

    回傳：[(day, count), ...]
    """
    rows = session.execute(text("""
        SELECT EXTRACT(DAY FROM birthday)::int AS day, COUNT(*) AS cnt
        FROM customers
        WHERE birthday IS NOT NULL
        GROUP BY EXTRACT(DAY FROM birthday)
        ORDER BY day
    """)).fetchall()
    summary = [(r[0], r[1]) for r in rows]
    return ToolResult.success(
        data=summary,
        total_layers=len(summary),
        total_customers_with_birthday=sum(c for _, c in summary),
    )


# ============================================================
# 變更工具：create / update / delete
# ============================================================

# 允許 update 的欄位白名單（防注入 + 明確語意）
_UPDATABLE_FIELDS = {
    'name', 'short_name', 'address', 'category', 'contact_phone', 'remarks',
    'birthday', 'gender', 'medical_record_no', 'dm_care_no',
    'latitude', 'longitude',
}


def prepare_create_customer(
    *,
    session,
    name: str,
    short_name: str,
    address: str,
    category: Optional[str] = None,
    contact_phone: Optional[str] = None,
    remarks: Optional[str] = None,
    birthday: Optional[date] = None,
    gender: Optional[str] = None,
    medical_record_no: Optional[str] = None,
    dm_care_no: Optional[str] = None,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
) -> ToolResult:
    """Validate and prepare a customer create payload without writing.

    This is the SELECT-only half of :func:`create_customer`.  Keeping the
    validation and exact ``short_name`` duplicate check here gives import
    previews the same contract as the formal mutation path without issuing an
    INSERT (``auto_commit=False`` is not a dry-run because it still inserts).
    """
    if not name or not name.strip():
        return ToolResult.fail("name 不可空")
    if not short_name or not short_name.strip():
        return ToolResult.fail("short_name 不可空")
    if not address or not address.strip():
        return ToolResult.fail("address 不可空")

    if gender and gender not in ('M', 'F'):
        return ToolResult.fail(f"gender 必須是 M 或 F，收到: {gender!r}")

    dup = session.execute(
        text("SELECT id FROM customers WHERE short_name = :v"),
        {'v': short_name}
    ).fetchone()
    if dup:
        return ToolResult.fail(f"短名「{short_name}」已存在 (customer #{dup[0]})")

    return ToolResult.success(data={
        'name': name,
        'short_name': short_name,
        'address': address,
        'category': category,
        'contact_phone': contact_phone,
        'remarks': remarks,
        'birthday': birthday,
        'gender': gender,
        'medical_record_no': medical_record_no,
        'dm_care_no': dm_care_no,
        'latitude': latitude,
        'longitude': longitude,
    })


def create_customer(
    *,
    session,
    name: str,
    short_name: str,
    address: str,
    category: Optional[str] = None,
    contact_phone: Optional[str] = None,
    remarks: Optional[str] = None,
    birthday: Optional[date] = None,
    gender: Optional[str] = None,
    medical_record_no: Optional[str] = None,
    dm_care_no: Optional[str] = None,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    auto_commit: bool = True,
    # 接受並忽略已 drop 的欄位（避免上游送舊 payload 時 TypeError）
    **_deprecated,
) -> ToolResult:
    """
    建立新客戶。

    必填：name, short_name, address
    選填：其他

    驗證：
      - short_name 必須唯一
      - gender 必須是 M / F / None

    ⚠️ 2026-05-08：drop national_id / insurance_type；舊 payload 從 **_deprecated
       吞掉不報錯（漸進過渡）
    """
    prepared = prepare_create_customer(
        session=session,
        name=name,
        short_name=short_name,
        address=address,
        category=category,
        contact_phone=contact_phone,
        remarks=remarks,
        birthday=birthday,
        gender=gender,
        medical_record_no=medical_record_no,
        dm_care_no=dm_care_no,
        latitude=latitude,
        longitude=longitude,
    )
    if not prepared:
        return prepared

    # --- INSERT ---
    result = session.execute(text("""
        INSERT INTO customers (
            name, short_name, address, category, contact_phone, remarks,
            birthday, gender, medical_record_no, dm_care_no,
            latitude, longitude
        ) VALUES (
            :name, :short_name, :address, :category, :contact_phone, :remarks,
            :birthday, :gender, :medical_record_no, :dm_care_no,
            :latitude, :longitude
        ) RETURNING id
    """), {
        'name': name, 'short_name': short_name, 'address': address,
        'category': category, 'contact_phone': contact_phone, 'remarks': remarks,
        'birthday': birthday, 'gender': gender,
        'medical_record_no': medical_record_no, 'dm_care_no': dm_care_no,
        'latitude': latitude, 'longitude': longitude,
    })
    new_id = result.fetchone()[0]

    if auto_commit:
        session.commit()

    # 取回完整資料
    return get_customer_by_id(new_id, session=session)


def update_customer(
    *,
    session,
    customer_id: int,
    auto_commit: bool = True,
    **fields,
) -> ToolResult:
    """
    部分更新客戶。

    傳什麼欄位就更新什麼，沒傳的不動。
    使用白名單 `_UPDATABLE_FIELDS` 防注入。

    注意：updated_at 由 DB trigger 自動更新（不在白名單）。
    """
    # 寬容 drop 已淘汰欄位（national_id / insurance_type）— 不報錯，當 noop
    _DEPRECATED_FIELDS = {'national_id', 'insurance_type'}
    fields = {k: v for k, v in fields.items() if k not in _DEPRECATED_FIELDS}

    # 拒絕未知欄位（防呆）
    rejected = set(fields.keys()) - _UPDATABLE_FIELDS
    if rejected:
        return ToolResult.fail(f"不允許更新的欄位: {sorted(rejected)}")

    # 過濾出有意義的更新（key 在白名單，且值有給）
    valid = {k: v for k, v in fields.items() if k in _UPDATABLE_FIELDS}
    if not valid:
        return ToolResult.fail("沒有任何欄位可更新")

    # 確認存在
    existing = session.execute(
        text("SELECT id FROM customers WHERE id = :id"),
        {'id': customer_id}
    ).fetchone()
    if not existing:
        return ToolResult.fail(f"找不到 customer #{customer_id}")

    # gender 驗證
    if 'gender' in valid:
        g = valid['gender']
        if g and g not in ('M', 'F'):
            return ToolResult.fail(f"gender 必須是 M 或 F，收到: {g!r}")

    # short_name 唯一性（排除自己）
    if 'short_name' in valid and valid['short_name']:
        dup = session.execute(
            text("SELECT id FROM customers WHERE short_name = :v AND id != :id"),
            {'v': valid['short_name'], 'id': customer_id}
        ).fetchone()
        if dup:
            return ToolResult.fail(f"短名「{valid['short_name']}」已被 #{dup[0]} 使用")

    # 動態 UPDATE
    set_clauses = ", ".join(f"{k} = :{k}" for k in valid.keys())
    sql = f"UPDATE customers SET {set_clauses} WHERE id = :id"
    params = {**valid, 'id': customer_id}
    session.execute(text(sql), params)

    if auto_commit:
        session.commit()

    return get_customer_by_id(customer_id, session=session)


def delete_customer(
    *,
    session,
    customer_id: int,
    auto_commit: bool = True,
) -> ToolResult:
    """
    刪除客戶（硬刪除）。

    安全閘（整備層綁定原則）：客戶是簡稱起源,若仍被 **fixed_schedules（未來態
    整備層）** 的起/終點引用 → **拒絕刪除**,請先刪相關固定班次。
    刻意**不檢查 trips（現在態）**：trips 是已匯出的獨立實例,刪客戶不受其阻擋
    （trips 起終點對 customers 的 FK 已移除）。
    """
    # 確認存在
    customer = session.execute(
        text("SELECT id, short_name, name FROM customers WHERE id = :id"),
        {'id': customer_id}
    ).fetchone()
    if not customer:
        return ToolResult.fail(f"找不到 customer #{customer_id}")

    short_name = customer[1]
    name = customer[2]

    # 檢查 fixed_schedules（整備層）起/終點引用;via_point 不在此約束範圍。
    # （DB 層 fixed_schedules FK ON DELETE RESTRICT 也會擋,這裡先給友善訊息）
    if short_name:
        ref_count = session.execute(text("""
            SELECT COUNT(*) FROM fixed_schedules
            WHERE start_point = :sn OR end_point = :sn
        """), {'sn': short_name}).scalar()
        if ref_count > 0:
            return ToolResult.fail(
                f"無法刪除 #{customer_id}「{name}」：仍有 {ref_count} 筆固定班次（整備層）"
                f"引用簡稱「{short_name}」。請先刪除這些固定班次再刪客戶。"
            )

    # DELETE
    session.execute(
        text("DELETE FROM customers WHERE id = :id"),
        {'id': customer_id}
    )

    if auto_commit:
        session.commit()

    return ToolResult.success(
        data={'deleted_id': customer_id, 'name': name, 'short_name': short_name}
    )
