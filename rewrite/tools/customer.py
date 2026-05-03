"""
客戶查詢 tool（v0.1 風格）

設計原則：
  R-4：純函數，session 從參數傳入，不依賴 Flask globals
  R-7：身分證預設遮罩顯示

功能：
  - query_customer：精確/結構化查詢（多欄位 cascade fallback）
  - query_customer_by_term：自然語言模糊查詢（給 AI 用）

輸出含「病歷層」（生日的日）自動計算欄位 — 服務門診人員找病歷層級。
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

    遮罩規則：national_id 預設只顯示首尾字
    計算欄位：birthday_day（病歷層）, age（年齡）
    """
    id: int
    short_name: Optional[str] = None
    name: Optional[str] = None
    address: Optional[str] = None
    category: Optional[str] = None
    contact_phone: Optional[str] = None
    remarks: Optional[str] = None

    # 個人資料 (m001 + m002)
    birthday: Optional[date] = None
    gender: Optional[str] = None
    national_id: Optional[str] = None  # 預設遮罩
    medical_record_no: Optional[str] = None
    insurance_type: Optional[str] = None

    # 座標
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    # 時間戳
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # 計算欄位
    birthday_day: Optional[int] = None  # 病歷層（生日的日）
    age: Optional[int] = None           # 年齡
    is_masked: bool = True              # 身分證是否已遮罩

    @classmethod
    def from_row(cls, row, *, mask_id: bool = True) -> "CustomerView":
        """從 SQLAlchemy row 建構"""
        d = dict(row._mapping)

        # 遮罩身分證
        nid = d.get('national_id')
        if mask_id and nid:
            d['national_id'] = nid[0] + '*' * max(0, len(nid) - 2) + nid[-1]

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

        d['is_masked'] = mask_id

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
           birthday, gender, national_id, medical_record_no, insurance_type,
           latitude, longitude, created_at, updated_at
    FROM customers
"""


def query_customer(
    *,
    session,
    short_name: Optional[str] = None,
    name: Optional[str] = None,
    address: Optional[str] = None,
    national_id: Optional[str] = None,
    medical_record_no: Optional[str] = None,
    fuzzy_name: bool = True,
    fuzzy_address: bool = True,
    mask_id: bool = True,
    limit: int = 20,
) -> ToolResult:
    """
    精確/結構化查詢，多欄位 cascade fallback。

    cascade 順序：
      1. short_name 精確
      2. national_id 精確（找到回傳）
      3. medical_record_no 精確
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
                data=[CustomerView.from_row(r, mask_id=mask_id) for r in rows],
                matched_by='short_name',
            )

    # 2. 精確 national_id
    if national_id:
        rows = session.execute(
            text(f"{_SELECT_ALL} WHERE national_id = :v"),
            {'v': national_id}
        ).fetchall()
        if rows:
            return ToolResult.success(
                data=[CustomerView.from_row(r, mask_id=mask_id) for r in rows],
                matched_by='national_id',
            )

    # 3. 病歷號
    if medical_record_no:
        rows = session.execute(
            text(f"{_SELECT_ALL} WHERE medical_record_no = :v"),
            {'v': medical_record_no}
        ).fetchall()
        if rows:
            return ToolResult.success(
                data=[CustomerView.from_row(r, mask_id=mask_id) for r in rows],
                matched_by='medical_record_no',
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
                data=[CustomerView.from_row(r, mask_id=mask_id) for r in rows],
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
                data=[CustomerView.from_row(r, mask_id=mask_id) for r in rows],
                matched_by='address' + ('(fuzzy)' if fuzzy_address else ''),
            )

    return ToolResult.fail("找不到符合條件的客戶")


def query_customer_by_term(
    term: str,
    *,
    session,
    mask_id: bool = True,
    limit: int = 20,
) -> ToolResult:
    """
    自然語言模糊查詢（給 AI 或自由輸入用）

    會嘗試把 term 當作 short_name / name / address / national_id / medical_record_no。
    cascade 找到任一就回傳。

    台灣身分證 heuristic：第一字大寫英文 + 9 位數字 (10 chars)
    """
    if not term or not term.strip():
        return ToolResult.fail("請提供查詢關鍵字")

    term = term.strip()

    # heuristic: 看 term 像不像身分證
    looks_like_id = (len(term) == 10
                     and term[0].isalpha()
                     and term[0].isupper()
                     and term[1:].isdigit())

    # heuristic: 看 term 像不像病歷號 (純數字 4-8 位)
    looks_like_mr = term.isdigit() and 4 <= len(term) <= 8

    return query_customer(
        session=session,
        short_name=term,                            # 試簡稱
        national_id=term if looks_like_id else None,
        medical_record_no=term if looks_like_mr else None,
        name=term,                                  # 模糊姓名
        address=term,                               # 模糊地址
        mask_id=mask_id,
        limit=limit,
    )


def get_customer_by_id(
    customer_id: int,
    *,
    session,
    mask_id: bool = True,
) -> ToolResult:
    """單筆 ID 查詢"""
    row = session.execute(
        text(f"{_SELECT_ALL} WHERE id = :id"),
        {'id': customer_id}
    ).fetchone()
    if row:
        return ToolResult.success(data=CustomerView.from_row(row, mask_id=mask_id))
    return ToolResult.fail(f"找不到 customer #{customer_id}")


# ============================================================
# 變更工具：create / update / delete
# ============================================================

# 允許 update 的欄位白名單（防注入 + 明確語意）
_UPDATABLE_FIELDS = {
    'name', 'short_name', 'address', 'category', 'contact_phone', 'remarks',
    'birthday', 'gender', 'national_id', 'medical_record_no', 'insurance_type',
    'latitude', 'longitude',
}


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
    national_id: Optional[str] = None,
    medical_record_no: Optional[str] = None,
    insurance_type: Optional[str] = None,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    auto_commit: bool = True,
) -> ToolResult:
    """
    建立新客戶。

    必填：name, short_name, address
    選填：其他

    驗證：
      - short_name 必須唯一
      - national_id 若有給，必須唯一
      - gender 必須是 M / F / None
    """
    # --- 必填驗證 ---
    if not name or not name.strip():
        return ToolResult.fail("name 不可空")
    if not short_name or not short_name.strip():
        return ToolResult.fail("short_name 不可空")
    if not address or not address.strip():
        return ToolResult.fail("address 不可空")

    # --- gender 驗證 ---
    if gender and gender not in ('M', 'F'):
        return ToolResult.fail(f"gender 必須是 M 或 F，收到: {gender!r}")

    # --- short_name 唯一性 ---
    dup = session.execute(
        text("SELECT id FROM customers WHERE short_name = :v"),
        {'v': short_name}
    ).fetchone()
    if dup:
        return ToolResult.fail(f"短名「{short_name}」已存在 (customer #{dup[0]})")

    # --- national_id 唯一性 ---
    if national_id:
        dup = session.execute(
            text("SELECT id FROM customers WHERE national_id = :v"),
            {'v': national_id}
        ).fetchone()
        if dup:
            return ToolResult.fail(f"身分證已存在於 customer #{dup[0]}")

    # --- INSERT ---
    result = session.execute(text("""
        INSERT INTO customers (
            name, short_name, address, category, contact_phone, remarks,
            birthday, gender, national_id, medical_record_no, insurance_type,
            latitude, longitude
        ) VALUES (
            :name, :short_name, :address, :category, :contact_phone, :remarks,
            :birthday, :gender, :national_id, :medical_record_no, :insurance_type,
            :latitude, :longitude
        ) RETURNING id
    """), {
        'name': name, 'short_name': short_name, 'address': address,
        'category': category, 'contact_phone': contact_phone, 'remarks': remarks,
        'birthday': birthday, 'gender': gender,
        'national_id': national_id, 'medical_record_no': medical_record_no,
        'insurance_type': insurance_type,
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

    # national_id 唯一性
    if 'national_id' in valid and valid['national_id']:
        dup = session.execute(
            text("SELECT id FROM customers WHERE national_id = :v AND id != :id"),
            {'v': valid['national_id'], 'id': customer_id}
        ).fetchone()
        if dup:
            return ToolResult.fail(f"身分證已存在於 #{dup[0]}")

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

    安全閘：若 customer.short_name 仍被 trips 引用，**拒絕刪除**。
    （v0.2 可改軟刪除 is_active = false，目前先硬刪）
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

    # 檢查 trips FK 引用
    if short_name:
        ref_count = session.execute(text("""
            SELECT COUNT(*) FROM trips
            WHERE start_point = :sn OR via_point = :sn OR end_point = :sn
        """), {'sn': short_name}).scalar()
        if ref_count > 0:
            return ToolResult.fail(
                f"無法刪除 #{customer_id}「{name}」：仍有 {ref_count} 筆 trip 引用簡稱「{short_name}」。"
                f" 建議先處理這些 trips（軟刪除功能 v0.2 補）"
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
