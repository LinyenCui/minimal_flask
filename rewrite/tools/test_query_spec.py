"""test_query_spec — 過去態受護欄查詢層編譯器測試（安全性 + 正確性）。

跑法：python rewrite/tools/test_query_spec.py
重點：注入面為零（值全綁參）、未知欄/op/enum 一律拒、range/group/sort 正確、執行得動。
"""
import os
import sys
from dotenv import load_dotenv
load_dotenv('.env'); load_dotenv('.env.dev', override=True)
sys.path.insert(0, '/Users/linyancui/minimal_flask')

from rewrite.tools.query_spec import compile_query_spec, QuerySpecError

DETAIL = "id, date, start_point, via_point, end_point, meter_fare, extra_fare, category, driver_id"

_passed = 0
_failed = 0


def ok(cond, label):
    global _passed, _failed
    if cond:
        _passed += 1
    else:
        _failed += 1
        print(f"  ❌ {label}")


def rejects(spec, label):
    try:
        compile_query_spec(spec, detail_columns=DETAIL)
        ok(False, f"{label}（應被拒卻通過）")
    except QuerySpecError:
        ok(True, label)


def test_compile_safe():
    c = compile_query_spec({
        "filters": [{"col": "category", "op": "=", "value": "東洋"},
                    {"col": "total_fare", "op": ">", "value": 1400}],
        "order_by": [{"col": "total_fare", "dir": "desc"}], "limit": 5,
    }, detail_columns=DETAIL)
    ok(c.mode == 'detail', "明細模式")
    # 值全進 params（不在 SQL 字串）
    ok("東洋" not in c.sql and "1400" not in c.sql, "值不出現在 SQL 字串（注入面為零）")
    ok(c.params == {"p0": "東洋", "p1": 1400, "p2": 5}, "值全綁 named param")
    ok("ORDER BY" in c.sql and "DESC" in c.sql, "排序進 SQL")


def test_grouped():
    c = compile_query_spec({
        "filters": [{"col": "category", "op": "=", "value": "東洋"}],
        "group_by": ["driver_id"],
        "aggregates": [{"fn": "count"}, {"fn": "sum", "col": "total_fare", "as": "金額"}],
        "order_by": [{"col": "金額", "dir": "desc"}],
    }, detail_columns=DETAIL)
    ok(c.mode == 'grouped', "分組模式")
    ok("GROUP BY driver_id" in c.sql, "GROUP BY 正確")
    ok('SUM(' in c.sql and 'COUNT(*)' in c.sql, "聚合 SUM/COUNT")
    ok(c.agg_display == ['count', '金額'], "聚合輸出名")


def test_range_string():
    # 範圍用 between 字串 "1400~2000"（schema value 是 string）
    c = compile_query_spec({"filters": [{"col": "total_fare", "op": "between", "value": "1400~2000"}]},
                           detail_columns=DETAIL)
    ok(c.params == {"p0": 1400, "p1": 2000, "p2": 80}, f"between 字串解析（{c.params}）")


def test_customer_predicate():
    c = compile_query_spec({"filters": [{"col": "customer", "op": "=", "value": "二井家"}]},
                           detail_columns=DETAIL)
    # via_point 多段用 '+' 或 '→' 分隔（兩種歷史寫法並存）→ 兩者都要當分隔符拆
    ok("regexp_split_to_array" in c.sql and "via_point" in c.sql, "customer 謂語拆 via")
    ok("+" in c.sql and "→" in c.sql, "customer 謂語兩種分隔符都認")


def test_rejections():
    rejects({"filters": [{"col": "x); DROP TABLE completed_trips;--", "op": "=", "value": "1"}]}, "拒未知欄（注入）")
    rejects({"filters": [{"col": "total_fare", "op": "; DELETE", "value": 1}]}, "拒未知運算子")
    rejects({"filters": [{"col": "category", "op": "=", "value": "洗腎"}]}, "拒非法 enum 值")
    rejects({"filters": [{"col": "passenger_name", "op": "=", "value": "x"}]}, "拒不允許的 op（name 不可 =? 其實可,改測排序）") if False else None
    rejects({"order_by": [{"col": "passenger_name", "dir": "asc"}]}, "拒不可排序欄")
    rejects({"group_by": ["total_fare"]}, "拒不可分組欄")
    rejects({"aggregates": [{"fn": "sum", "col": "driver_id"}]}, "拒對非車資欄聚合")
    rejects({"filters": [{"col": "total_fare", "op": ">", "value": "abc"}]}, "拒非數字值")
    # review 補強案例
    rejects({"filters": [{"col": "total_fare", "op": ">", "value": "²"}]}, "拒 Unicode 上標數字 ²（isdigit/int 不一致）")
    rejects({"filters": [{"col": "total_fare", "op": ">", "value": "--5"}]}, "拒雙減號 --5")
    rejects({"filters": [{"col": ["x"], "op": "=", "value": 1}]}, "拒非字串 col（list→unhashable）")
    rejects({"group_by": ["driver_id"], "aggregates": [{"fn": "sum", "col": "total_fare", "as": "driver_id"}]}, "拒別名與分組欄碰撞")
    rejects({"group_by": ["driver_id"], "aggregates": [{"fn": "count", "as": "x"}, {"fn": "sum", "col": "total_fare", "as": "x"}]}, "拒聚合別名重複")
    rejects({"group_by": ["driver_id"], "aggregates": [{"fn": "count"}], "order_by": [{"col": "date", "dir": "asc"}]}, "拒分組模式依非分組實體欄排序")
    rejects({"filters": [{"col": "driver_id", "op": "in", "value": ",".join(str(i) for i in range(200))}]}, "拒 in 清單過長（>100）")


def test_limit_cap():
    c = compile_query_spec({"limit": 99999}, detail_columns=DETAIL)
    ok(c.params.get("p0") == 80, "limit 夾到 80")


def test_execute_real_db():
    """編譯出的 SQL 真的能跑（grouped + detail）。"""
    try:
        from database import Session
        from sqlalchemy import text
    except Exception as e:
        print(f"  ⚠️ 跳過 DB 執行測試：{e}")
        return
    s = Session()
    try:
        c = compile_query_spec({
            "group_by": ["category"],
            "aggregates": [{"fn": "count"}, {"fn": "sum", "col": "total_fare", "as": "金額"}],
        }, detail_columns=DETAIL)
        rows = s.execute(text(c.sql), c.params).fetchall()
        ok(len(rows) >= 1, f"grouped SQL 執行（回 {len(rows)} 組）")
        c2 = compile_query_spec({"filters": [{"col": "total_fare", "op": ">", "value": 1000}],
                                 "order_by": [{"col": "total_fare", "dir": "desc"}], "limit": 3},
                                detail_columns=DETAIL)
        rows2 = s.execute(text(c2.sql), c2.params).fetchall()
        ok(len(rows2) <= 3, f"detail SQL 執行（回 {len(rows2)} 筆）")
    finally:
        s.close()


if __name__ == '__main__':
    test_compile_safe()
    test_grouped()
    test_range_string()
    test_customer_predicate()
    test_rejections()
    test_limit_cap()
    test_execute_real_db()
    print(f"\n{'✅ 全部通過' if _failed == 0 else '❌ 有失敗'}：pass={_passed} fail={_failed}")
