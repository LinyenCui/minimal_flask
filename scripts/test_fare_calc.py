"""手測腳本（非 regression）— atomic tool 改用 keyword args 並回 ToolResult"""
from rewrite.tools.fare_calc import calculate_fare, format_text


def main():
    cases = [
        {"distance_km": 10, "waiting_min": 0, "period": "日間"},
        {"distance_km": 10, "waiting_min": 5, "period": "夜間"},
        {"distance_km": 5.8, "waiting_min": 3, "period": "日間"},
    ]
    for kw in cases:
        r = calculate_fare(**kw)
        print(r.data)
        print(format_text(r.data))
        print("-" * 40)


if __name__ == "__main__":
    main()
