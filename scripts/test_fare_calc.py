from modules.services.fare_calculator import calculate_fare, format_text


def main():
    cases = [
        (10, 0, "日間"),
        (10, 5, "夜間"),
        (5.8, 3, "日間"),
    ]
    for d, w, p in cases:
        res = calculate_fare(d, w, p)
        print(res)
        print(format_text(res))
        print("-" * 40)


if __name__ == "__main__":
    main()
