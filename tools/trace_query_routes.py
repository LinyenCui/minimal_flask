#!/usr/bin/env python3
"""
查询路径追踪工具
测试各种查询会走哪条路径
"""

import sys
import os

# 直接加载文件，避免 Flask 依赖
parent_dir = os.path.dirname(os.path.dirname(__file__))
router_path = os.path.join(parent_dir, 'modules', 'core', 'query_router.py')

from datetime import date
import importlib.util

# 直接加载 Python 文件
spec = importlib.util.spec_from_file_location("query_router", router_path)
router_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(router_module)
decide_query_route = router_module.decide_query_route

# 模拟当前日期为 2026-01-05
MOCK_TODAY = date(2026, 1, 5)

# 测试用例
TEST_CASES = [
    # 单日查询
    ("12/28診所班次", "单日过去态"),
    ("1/5診所班次", "单日今天"),
    ("1/10診所班次", "单日未来"),

    # 日期范围
    ("12/28-1/3診所班次", "范围过去到今天"),
    ("12/20-12/25司機61553診所班次", "范围全过去"),
    ("1/10-1/15診所班次", "范围全未来"),

    # 有/无司机
    ("12/28-1/3診所班次", "无司机"),
    ("12/28-1/3司機61553診所班次", "有司机"),

    # 有/无类别
    ("12/28-1/3司機61553班次", "无类别"),
    ("12/28-1/3司機61553診所班次", "有类别"),

    # 聚合查询
    ("12/28-1/3診所班次金額加總", "聚合-诊所"),
    ("12/28-1/3司機61553診所班次金額加總", "聚合-司机+诊所"),
    ("12/28-1/3司機61553診所班次合計", "聚合-合计"),
    ("12/28-1/3司機61553診所班次總額", "聚合-总额"),

    # 已完成关键字
    ("12/28-1/3已完成診所班次", "已完成关键字"),
    ("1/10已完成診所班次", "未来+已完成"),

    # 无日期（应走智能助手）
    ("診所班次", "无日期"),
    ("司機61553診所班次", "无日期-有司机"),
]


def trace_routes():
    """追踪所有测试用例的路由"""
    print("=" * 80)
    print("查询路径追踪报告")
    print("=" * 80)
    print(f"模拟日期: {MOCK_TODAY}\n")

    # 按类别分组
    categories = {
        "单日查询": [],
        "日期范围": [],
        "聚合查询": [],
        "特殊情况": []
    }

    for query, desc in TEST_CASES:
        route = decide_query_route(query, today=MOCK_TODAY)

        result = {
            "query": query,
            "desc": desc,
            "route": route
        }

        if "聚合" in desc:
            categories["聚合查询"].append(result)
        elif "单日" in desc:
            categories["单日查询"].append(result)
        elif "范围" in desc:
            categories["日期范围"].append(result)
        else:
            categories["特殊情况"].append(result)

    # 输出结果
    for category, results in categories.items():
        if not results:
            continue

        print(f"\n{'─' * 80}")
        print(f"【{category}】")
        print(f"{'─' * 80}\n")

        for r in results:
            route = r["route"]
            print(f"查询: {r['query']}")
            print(f"说明: {r['desc']}")
            print(f"  ├─ 直接查询: {'✅' if route.is_direct_query else '❌'}")
            print(f"  ├─ 目标表: {route.table or 'N/A'}")
            print(f"  ├─ 模式: {route.mode or 'N/A'}")
            print(f"  ├─ 处理器: {route.handler or 'N/A'}")
            print(f"  ├─ 日期: {route.parsed.get('start_date')} ~ {route.parsed.get('end_date')}")
            print(f"  ├─ 司机: {route.parsed.get('driver_id') or 'N/A'}")
            print(f"  ├─ 类别: {route.parsed.get('category') or 'N/A'}")
            print(f"  └─ 原因: {route.reason}")
            print()

    # 验证关键用例
    print(f"\n{'=' * 80}")
    print("关键验证")
    print(f"{'=' * 80}\n")

    critical_tests = [
        ("12/28-1/3司機61553診所班次金額加總",
         "date_range_query_service", "aggregate", "completed_trips"),
        ("12/28-1/3司機61553診所班次",
         "date_range_query_service", "list", "completed_trips"),
        ("12/28-1/3診所班次金額加總",
         "date_range_query_service", "aggregate", "completed_trips"),
    ]

    all_passed = True
    for query, expected_handler, expected_mode, expected_table in critical_tests:
        route = decide_query_route(query, today=MOCK_TODAY)

        passed = (
            route.handler == expected_handler and
            route.mode == expected_mode and
            route.table == expected_table
        )

        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} | {query}")
        print(f"       预期: {expected_handler}/{expected_mode}/{expected_table}")
        print(f"       实际: {route.handler}/{route.mode}/{route.table}")

        if not passed:
            all_passed = False

    print(f"\n{'=' * 80}")
    if all_passed:
        print("✅ 所有关键测试通过")
    else:
        print("❌ 部分测试失败")
    print(f"{'=' * 80}\n")


if __name__ == "__main__":
    trace_routes()
