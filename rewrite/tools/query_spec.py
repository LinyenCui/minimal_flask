"""過去態 completed_trips 唯讀受護欄查詢規格編譯器（spec docs/specs/04）。

AI 生「查詢規格 JSON」→ 本模組編譯成參數化 SELECT。**AI 永不寫 SQL**：
- 欄位只能來自 ALLOWED_COLUMNS 白名單
- 運算子只能來自該欄宣告的 ops
- 值一律 named param 綁定（:p0, :p1…），永不進 SQL 結構（注入面為零）
- 未知欄 / 運算子 / 型別錯 → 拋 QuerySpecError（呼叫端轉 ToolResult.fail，不默默忽略）

只負責 SELECT；FROM 固定 completed_trips（過去態），AI 不能指定表。
"""
import re
from dataclasses import dataclass, field
from typing import Any, Optional

from modules.utils.unified_date_parser import UnifiedDateParser

VALID_CATEGORIES = ('診所', '東洋', '臨時')
MAX_LIMIT = 80
DEFAULT_LIMIT = 80
MAX_GROUP_ROWS = 80

# 車資總額虛擬欄
_TOTAL = "(COALESCE(meter_fare, 0) + COALESCE(extra_fare, 0))"

_AGG_FNS = ('count', 'sum', 'avg', 'min', 'max')
_CMP_OPS = ('=', '!=', '>', '<', '>=', '<=')


class QuerySpecError(ValueError):
    """查詢規格不合法。message 會回給使用者，要友善可懂。"""


@dataclass(frozen=True)
class ColSpec:
    sql: str            # SQL 表達式（實體欄或虛擬式）；special predicate 時為 ''
    type: str           # int / date / enum / text / bool
    ops: tuple          # 允許的運算子
    can_group: bool = False
    can_sort: bool = False
    enum: tuple = ()
    predicate: str = ''  # 'customer' / 'location' 等特殊多欄謂語


# ── 欄位白名單（唯一可被 AI 指定的欄；其餘含 PII 一律拒絕）─────────────
ALLOWED_COLUMNS: dict[str, ColSpec] = {
    'date':           ColSpec('date', 'date', ('=', '>=', '<=', 'between'), can_group=True, can_sort=True),
    'driver_id':      ColSpec('driver_id', 'int', ('=', 'in'), can_group=True, can_sort=True),
    'category':       ColSpec('category', 'enum', ('=', 'in'), can_group=True, can_sort=True, enum=VALID_CATEGORIES),
    'total_fare':     ColSpec(_TOTAL, 'int', _CMP_OPS + ('between',), can_sort=True),
    'has_fare':       ColSpec(f"({_TOTAL} > 0)", 'bool', ('=',), can_group=True),
    'is_leave':       ColSpec("(passenger_leave_reason IS NOT NULL)", 'bool', ('=',), can_group=True),
    'start_point':    ColSpec('start_point', 'text', ('=', 'ilike'), can_group=True, can_sort=True),
    'end_point':      ColSpec('end_point', 'text', ('=', 'ilike'), can_group=True, can_sort=True),
    'passenger_name': ColSpec('passenger_name', 'text', ('=', 'ilike')),
    # 特殊多欄謂語（AI 只填值，謂語固定內建）
    'location':       ColSpec('', 'text', ('ilike',), predicate='location'),
    'customer':       ColSpec('', 'text', ('=',), predicate='customer'),
}

# 可作聚合對象的數值欄（sum/avg/min/max）
_AGG_NUMERIC_COLS = {'total_fare'}


@dataclass
class CompiledQuery:
    mode: str                       # 'detail' | 'grouped'
    sql: str
    params: dict
    group_display: list = field(default_factory=list)   # grouped: group 欄顯示名
    agg_display: list = field(default_factory=list)      # grouped: 聚合輸出名
    agg_kinds: dict = field(default_factory=dict)        # grouped: {聚合名: 'count'|'money'}


class _ParamBag:
    """遞增 named param（:p0, :p1…），確保唯一、值全綁定。"""
    def __init__(self):
        self.params: dict = {}
        self._n = 0

    def add(self, value) -> str:
        key = f"p{self._n}"
        self._n += 1
        self.params[key] = value
        return f":{key}"


# ── 值 coerce ────────────────────────────────────────────────
def _coerce_value(col: str, cspec: ColSpec, value):
    t = cspec.type
    if t == 'int':
        if isinstance(value, bool):
            raise QuerySpecError(f"「{col}」要數字")
        if isinstance(value, str):
            # 用 int() 守門兼解析（一致）：isdigit() 對 '²' 等 Unicode 數字回 True
            # 但 int('²') 會拋裸 ValueError 逃過 QuerySpecError 契約
            try:
                return int(value.strip())
            except (ValueError, TypeError):
                raise QuerySpecError(f"「{col}」要數字，收到 {value!r}")
        if isinstance(value, (int, float)):
            return int(value)
        raise QuerySpecError(f"「{col}」要數字")
    if t == 'date':
        try:
            return UnifiedDateParser.parse(value) if not hasattr(value, 'isoformat') else value
        except Exception:
            raise QuerySpecError(f"「{col}」日期格式不對：{value!r}")
    if t == 'enum':
        v = str(value).strip()
        if v not in cspec.enum:
            raise QuerySpecError(f"「{col}」只能是 {'/'.join(cspec.enum)}，收到 {value!r}")
        return v
    if t == 'bool':
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in ('1', 'true', 'yes', 'on', '是', 'y')
    return str(value)


# ── filter 編譯 ──────────────────────────────────────────────
def _compile_filter(f: dict, bag: _ParamBag) -> str:
    if not isinstance(f, dict):
        raise QuerySpecError(f"filter 格式錯：{f!r}")
    col = f.get('col')
    op = (f.get('op') or '=')
    value = f.get('value')
    if not isinstance(col, str) or col not in ALLOWED_COLUMNS:
        raise QuerySpecError(f"不支援用「{col}」篩選")
    cspec = ALLOWED_COLUMNS[col]
    if op not in cspec.ops:
        raise QuerySpecError(f"「{col}」不支援「{op}」（可用：{'/'.join(cspec.ops)}）")

    # 特殊謂語
    if cspec.predicate == 'customer':
        p = bag.add(_coerce_value(col, cspec, value))
        return (f"(start_point = {p} OR end_point = {p} "
                f"OR {p} = ANY(string_to_array(COALESCE(via_point, ''), '+')))")
    if cspec.predicate == 'location':
        p = bag.add(f"%{_coerce_value(col, cspec, value)}%")
        return f"(start_point ILIKE {p} OR via_point ILIKE {p} OR end_point ILIKE {p})"

    expr = cspec.sql
    if op == 'between':
        vals = value
        if isinstance(value, str):  # schema 把 value 宣告成 string，容忍 "X~Y" / "X,Y"
            vals = [v for v in re.split(r'\s*[~,，到]\s*', value.strip()) if v]
        if not (isinstance(vals, (list, tuple)) and len(vals) == 2):
            raise QuerySpecError(f"「{col}」between 要給 [下限, 上限]")
        lo = bag.add(_coerce_value(col, cspec, vals[0]))
        hi = bag.add(_coerce_value(col, cspec, vals[1]))
        return f"{expr} BETWEEN {lo} AND {hi}"
    if op == 'in':
        vals = value
        if isinstance(value, str):
            vals = [v for v in re.split(r'\s*[,，]\s*', value.strip()) if v]
        if not isinstance(vals, (list, tuple)) or not vals:
            raise QuerySpecError(f"「{col}」in 要給非空清單")
        if len(vals) > 100:
            raise QuerySpecError(f"「{col}」in 清單過長（上限 100）")
        ps = [bag.add(_coerce_value(col, cspec, v)) for v in vals]
        return f"{expr} IN ({', '.join(ps)})"
    if op == 'ilike':
        p = bag.add(f"%{_coerce_value(col, cspec, value)}%")
        return f"{expr} ILIKE {p}"
    # 比較運算子
    p = bag.add(_coerce_value(col, cspec, value))
    return f"{expr} {op} {p}"


# ── 聚合 / group / sort ─────────────────────────────────────
def _compile_aggregate(a: dict) -> tuple[str, str, str]:
    """回 (select_expr, display_name, kind)。kind：'count' | 'money'（給 render 決定 筆/元）。"""
    if not isinstance(a, dict):
        raise QuerySpecError(f"aggregate 格式錯：{a!r}")
    fn = str(a.get('fn') or '').lower()   # str() 容錯 list/None，落到下方白名單檢查
    if fn not in _AGG_FNS:
        raise QuerySpecError(f"不支援聚合「{fn}」（可用：{'/'.join(_AGG_FNS)}）")
    alias = a.get('as') or (fn if fn == 'count' else f"{fn}_{a.get('col', '')}")
    # 別名只能是安全字元（純顯示，雙引號包；防識別字逃逸）
    safe_alias = ''.join(ch for ch in str(alias) if ch.isalnum() or ch in ('_', '金', '額', '數', '計', '筆', '車', '資', '均', '高', '低', '總'))[:20] or fn
    if fn == 'count':
        return f'COUNT(*) AS "{safe_alias}"', safe_alias, 'count'
    col = a.get('col')
    if not isinstance(col, str) or col not in _AGG_NUMERIC_COLS:
        raise QuerySpecError(f"「{fn}」只能對 {'/'.join(_AGG_NUMERIC_COLS)} 計算，收到「{col}」")
    expr = ALLOWED_COLUMNS[col].sql
    if fn == 'avg':
        return f'ROUND(AVG({expr})) AS "{safe_alias}"', safe_alias, 'money'
    sql_fn = {'sum': 'SUM', 'min': 'MIN', 'max': 'MAX'}[fn]
    return f'{sql_fn}({expr}) AS "{safe_alias}"', safe_alias, 'money'


def _compile_group_col(col: str) -> tuple[str, str]:
    if not isinstance(col, str) or col not in ALLOWED_COLUMNS or not ALLOWED_COLUMNS[col].can_group:
        raise QuerySpecError(f"不支援用「{col}」分組")
    cspec = ALLOWED_COLUMNS[col]
    return f'{cspec.sql} AS "{col}"', col


def _compile_order(o: dict, sortable: set, grouped: bool = False) -> str:
    if not isinstance(o, dict):
        raise QuerySpecError(f"order_by 格式錯：{o!r}")
    col = o.get('col')
    direction = (o.get('dir') or 'asc').lower()
    if direction not in ('asc', 'desc'):
        raise QuerySpecError(f"排序方向只能 asc/desc，收到 {direction!r}")
    if isinstance(col, str) and col in sortable:
        # 聚合別名 / group 別名 → 用雙引號引用
        return f'"{col}" {direction.upper()}'
    # 分組模式只能依「分組欄/聚合結果」排序；依其它實體欄排會違反 GROUP BY → DB 報錯
    if not grouped and isinstance(col, str) and col in ALLOWED_COLUMNS and ALLOWED_COLUMNS[col].can_sort:
        return f'{ALLOWED_COLUMNS[col].sql} {direction.upper()}'
    suffix = "（分組模式只能依分組欄或聚合結果排序）" if grouped else ""
    raise QuerySpecError(f"不支援用「{col}」排序{suffix}")


def _cap_limit(value) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return DEFAULT_LIMIT
    return max(1, min(n, MAX_LIMIT))


def compile_query_spec(spec: dict, *, detail_columns: str, table: str = 'completed_trips') -> CompiledQuery:
    """查詢規格 → CompiledQuery（參數化 SQL）。違規拋 QuerySpecError。"""
    if not isinstance(spec, dict):
        raise QuerySpecError("查詢規格要是物件")

    bag = _ParamBag()
    filters = spec.get('filters') or []
    if not isinstance(filters, list):
        raise QuerySpecError("filters 要是清單")
    where = [_compile_filter(f, bag) for f in filters]
    where_sql = ('\nWHERE ' + ' AND '.join(where)) if where else ''

    group_by = spec.get('group_by') or []
    aggregates = spec.get('aggregates') or []
    order_by = spec.get('order_by') or []
    if not isinstance(group_by, list) or not isinstance(aggregates, list):
        raise QuerySpecError("group_by / aggregates 要是清單")

    grouped = bool(group_by or aggregates)

    if grouped:
        # group_by 無 aggregates → 預設補 count
        if group_by and not aggregates:
            aggregates = [{'fn': 'count', 'as': '筆數'}]
        group_sel, group_names, group_exprs = [], [], []
        for col in group_by:
            sel, name = _compile_group_col(col)
            group_sel.append(sel)
            group_names.append(name)
            group_exprs.append(ALLOWED_COLUMNS[col].sql)
        agg_sel, agg_names, agg_kinds = [], [], {}
        for a in aggregates:
            sel, name, kind = _compile_aggregate(a)
            agg_sel.append(sel)
            agg_names.append(name)
            agg_kinds[name] = kind
        # 別名唯一性：group/agg 輸出欄名不可碰撞，否則 SELECT 出兩個同名欄
        # → ORDER BY 別名歧義(DB 報錯) 或 dict(row._mapping) 靜默吃掉一欄(資料錯)
        all_names = group_names + agg_names
        if len(all_names) != len(set(all_names)):
            raise QuerySpecError("輸出欄/別名重複，請換一個顯示名（as）")
        sortable = set(all_names)
        # 分組模式只能依分組欄/聚合結果排序（grouped=True）
        order = [_compile_order(o, sortable, grouped=True) for o in order_by]
        order_sql = ('\nORDER BY ' + ', '.join(order)) if order else (
            f'\nORDER BY "{agg_names[0]}" DESC' if agg_names else '')
        group_sql = ('\nGROUP BY ' + ', '.join(group_exprs)) if group_exprs else ''
        select_sql = 'SELECT ' + ', '.join(group_sel + agg_sel)
        sql = (f"{select_sql}\nFROM {table}{where_sql}{group_sql}{order_sql}"
               f"\nLIMIT {MAX_GROUP_ROWS}")
        return CompiledQuery('grouped', sql, bag.params, group_names, agg_names, agg_kinds)

    # 明細模式
    sortable = set()
    order = [_compile_order(o, sortable) for o in order_by]
    order_sql = ('\nORDER BY ' + ', '.join(order)) if order else '\nORDER BY date, id'
    limit = _cap_limit(spec.get('limit', DEFAULT_LIMIT))
    pl = bag.add(limit)
    sql = f"SELECT {detail_columns}\nFROM {table}{where_sql}{order_sql}\nLIMIT {pl}"
    return CompiledQuery('detail', sql, bag.params, [], [])
