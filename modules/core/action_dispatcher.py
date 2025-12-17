"""
ActionDispatcher - 專責分發結構化 intent（MVP 只支援查詢）

設計目標：
- 只讀查詢走結構化 intent，新管線可獨立回退。
- 任一錯誤或不支援的 action 直接返回 None，讓上層走舊流程。
"""

import logging
from typing import Optional, Dict, Any


class ActionDispatcher:
    """分發結構化意圖，MVP 只支援 query_trips_range。"""

    SUPPORTED_ACTIONS = {"query_trips_range"}

    @staticmethod
    def dispatch(intent: Dict[str, Any], user_id: str) -> Optional[Dict[str, Any]]:
        try:
            if not isinstance(intent, dict):
                return None

            action = intent.get("action")
            params = intent.get("params") or {}
            if action not in ActionDispatcher.SUPPORTED_ACTIONS:
                return None

            if action == "query_trips_range":
                return ActionDispatcher._handle_query_trips_range(params, user_id)

            return None
        except Exception as e:
            logging.getLogger(__name__).exception("ActionDispatcher fallback to legacy")
            return None

    @staticmethod
    def _handle_query_trips_range(params: Dict[str, Any], user_id: str) -> Optional[Dict[str, Any]]:
        """處理日期範圍查詢，透過既有的 date_range_query_service。"""
        try:
            start_date = params.get("start_date")
            end_date = params.get("end_date")
            if not start_date or not end_date:
                return None
            # 必須是 date 類型
            from datetime import date
            if not isinstance(start_date, date) or not isinstance(end_date, date):
                return None

            driver_id = params.get("driver_id")
            category = params.get("category")
            trip_type = params.get("trip_type")
            location = params.get("location")  # 🔥 2025-12-17 新增：支援地點過濾

            from modules.services.date_range_query_service import handle_query_trips_range

            result = handle_query_trips_range(
                start_date=start_date,
                end_date=end_date,
                driver_id=driver_id,
                category=category,
                trip_type=trip_type,
                user_id=user_id,
                location=location,  # 🔥 傳遞地點參數
            )

            if not result:
                return None

            text_result = result.get("text", "")
            quick_reply = result.get("quick_reply")
            meta = result.get("meta", {})

            return {
                "text": text_result,
                "quick_reply": quick_reply,
                "meta": meta,
            }
        except Exception as e:
            logging.getLogger(__name__).warning(f"query_trips_range fallback to legacy: {e}")
            return None


# 便捷實例
action_dispatcher = ActionDispatcher()

