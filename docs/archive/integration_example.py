"""
查詢路由整合範例

展示如何在 text_message_handler.py 中整合新的查詢路由系統
"""

from modules.core.query_router import decide_query_route
from modules.services.date_range_query_service import handle_query_trips_range


def example_integration(message_text, user_id):
    """
    範例：在 text_message_handler.py 中整合查詢路由

    這個函數展示完整的整合流程：
    1. 使用路由決策器判斷查詢類型
    2. 根據決策結果執行相應處理
    3. 返回格式化結果
    """

    # 步驟 1: 使用路由決策器
    route = decide_query_route(message_text)

    # 步驟 2: 檢查是否為直接查詢
    if not route.is_direct_query:
        # 無日期，走智能助手
        print(f"❌ {route.reason}")
        # return handle_smart_assistant(message_text, user_id)
        return {
            "text": "此查詢需要智能助手處理（無日期資訊）",
            "quick_reply": None,
            "meta": {"handler": "smart_assistant"}
        }

    # 步驟 3: 記錄路由決策（用於除錯）
    print(f"✅ 路由決策: {route.reason}")
    print(f"   表: {route.table}")
    print(f"   模式: {route.mode}")
    print(f"   日期: {route.parsed['start_date']} ~ {route.parsed['end_date']}")
    print(f"   司機: {route.parsed.get('driver_id', 'N/A')}")
    print(f"   類別: {route.parsed.get('category', 'N/A')}")

    # 步驟 4: 執行查詢（統一使用 date_range_query_service）
    result = handle_query_trips_range(
        start_date=route.parsed['start_date'],
        end_date=route.parsed['end_date'],
        driver_id=route.parsed.get('driver_id'),
        category=route.parsed.get('category'),
        location=route.parsed.get('location'),
        user_id=user_id,
        force_completed=route.parsed.get('has_completed_keyword', False),
        mode=route.mode  # 🔥 關鍵：傳遞 mode 參數（"list" 或 "aggregate"）
    )

    # 步驟 5: 返回結果
    return result


def example_test_cases():
    """
    測試用例範例
    """
    test_cases = [
        # 聚合查詢（應返回統計摘要，無分頁）
        ("12/28-1/3司機61553診所班次金額加總", "user123"),
        ("12/28-1/3診所班次金額加總", "user123"),
        ("12/28-1/3司機61553診所班次合計", "user123"),

        # 列表查詢（應返回班次列表，支援分頁）
        ("12/28-1/3司機61553診所班次", "user123"),
        ("12/28-1/3診所班次", "user123"),

        # 邊界情況
        ("1/5診所班次", "user123"),  # 今天，查 trips
        ("1/5已完成診所班次", "user123"),  # 今天+已完成，查 completed_trips

        # 無日期（應走智能助手）
        ("診所班次", "user123"),
        ("司機61553診所班次", "user123"),
    ]

    for message_text, user_id in test_cases:
        print("\n" + "=" * 80)
        print(f"測試: {message_text}")
        print("=" * 80)

        result = example_integration(message_text, user_id)

        if result:
            print("\n結果:")
            print(result.get('text', ''))
        else:
            print("\n結果: None")


# 實際整合時的程式碼片段（供參考）
"""
在 text_message_handler.py 中的實際整合位置：

def process_text_message(event, user_id):
    message_text = event.message.text.strip()

    # ... 前置處理 ...

    # 🔥 新增：查詢路由整合
    if is_query_command(message_text):  # 判斷是否為查詢命令
        route = decide_query_route(message_text)

        if route.is_direct_query:
            # 直接查詢路徑（date_range_query_service）
            result = handle_query_trips_range(
                start_date=route.parsed['start_date'],
                end_date=route.parsed['end_date'],
                driver_id=route.parsed.get('driver_id'),
                category=route.parsed.get('category'),
                location=route.parsed.get('location'),
                user_id=user_id,
                force_completed=route.parsed.get('has_completed_keyword', False),
                mode=route.mode  # "list" 或 "aggregate"
            )

            # 發送回應
            if result:
                send_line_message(
                    user_id,
                    result.get('text'),
                    quick_reply=result.get('quick_reply')
                )
            return
        else:
            # 無日期，走智能助手
            return handle_smart_assistant(message_text, user_id)

    # ... 其他處理邏輯 ...
"""


# 關鍵檢查點（整合後驗證）
"""
整合後驗證清單：

1. 聚合查詢測試
   [ ] 輸入: "12/28-1/3司機61553診所班次金額加總"
   [ ] 預期: 返回統計摘要，不是班次列表
   [ ] 預期: 無「下一頁」按鈕（無分頁）
   [ ] 日誌: 出現 "📊 聚合查詢模式"

2. 列表查詢測試
   [ ] 輸入: "12/28-1/3司機61553診所班次"
   [ ] 預期: 返回班次列表
   [ ] 預期: 有「下一頁」按鈕（如果超過10筆）
   [ ] 日誌: 正常查詢日誌

3. 日期邊界測試
   [ ] 輸入: "1/5診所班次"（今天）
   [ ] 預期: 查詢 trips 表

   [ ] 輸入: "1/5已完成診所班次"（今天+已完成）
   [ ] 預期: 查詢 completed_trips 表

4. 無日期測試
   [ ] 輸入: "診所班次"
   [ ] 預期: 走智能助手
   [ ] 日誌: "无日期，走智能助手"

5. 日誌驗證
   [ ] 確認沒有出現「直接查詢解析失敗，繼續走智能助手」
   [ ] 確認所有聚合查詢都有正確的模式標記
"""


if __name__ == "__main__":
    # 執行測試用例
    example_test_cases()
