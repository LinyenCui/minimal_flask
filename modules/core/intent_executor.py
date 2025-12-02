"""
意圖執行器 - 基於第一性原則（操作資料庫）的智能對話系統

核心能力：
1. 理解三時間態（未來態、現在態、過去態）
2. 知道資料庫結構（trips, completed_trips, fixed_schedules等）
3. 查詢 → 確認 → 執行的智能流程

設計理念：
AI 不是翻譯官，而是真正的決策者和助手
- 理解用戶意圖
- 查詢相關數據
- 提供智能建議
- 執行數據庫操作
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy import text

from database import db
from modules.utils.unified_date_parser import UnifiedDateParser
from modules.utils.conversation_context import conversation_manager
from modules.utils.line_bot import reply_text, reply_message_with_quick_reply

logger = logging.getLogger(__name__)


class IntentExecutor:
    """
    意圖執行器：將 AI 理解的意圖轉換為資料庫操作
    
    工作流程：
    1. 接收 AI 解析的結構化意圖
    2. 根據三時間態判斷操作的表
    3. 查詢相關數據
    4. 生成確認訊息（含 Quick Reply）
    5. 等待用戶確認後執行
    """
    
    def __init__(self):
        self.date_parser = UnifiedDateParser()
    
    def execute(self, intent: Dict[str, Any], user_id: str, reply_token: str) -> Dict[str, Any]:
        """
        執行意圖
        
        Args:
            intent: AI 解析的意圖，格式如：
                {
                    "action": "passenger_leave",
                    "params": {
                        "date": "明天",
                        "location": "公園南路",
                        "reason": "病患請假"
                    },
                    "confidence": 0.95
                }
            user_id: 用戶ID
            reply_token: LINE 回覆 token
        
        Returns:
            執行結果
        """
        action = intent.get("action")
        params = intent.get("params", {})
        
        logger.info(f"🎯 IntentExecutor 執行意圖: action={action}, params={params}")
        
        try:
            # 根據不同的意圖類型執行
            if action == "passenger_leave":
                return self._handle_passenger_leave(params, user_id, reply_token)
            
            elif action == "update_fare":
                return self._handle_update_fare(params, user_id, reply_token)
            
            elif action == "query_trips":
                return self._handle_query_trips(params, user_id, reply_token)
            
            else:
                logger.warning(f"未知的意圖類型: {action}")
                return {
                    "success": False,
                    "message": f"抱歉，我還不會處理「{action}」類型的操作"
                }
        
        except Exception as e:
            logger.error(f"執行意圖失敗: {e}", exc_info=True)
            return {
                "success": False,
                "message": f"執行操作時發生錯誤: {str(e)}"
            }
    
    def _handle_passenger_leave(self, params: Dict[str, Any], user_id: str, reply_token: str) -> Dict[str, Any]:
        """
        處理乘客請假意圖
        
        範例場景：
        用戶："明天公園南路的病患請假一次不用去載"
        
        處理流程：
        1. 解析日期（明天 → 2025-12-03）
        2. 判斷時間態（明天 → 現在態 → trips表）
        3. 查詢相關班次（公園南路）
        4. 顯示結果並請求確認
        5. 等待用戶確認後執行
        """
        logger.info(f"🏥 處理乘客請假: {params}")
        
        # 1. 解析日期
        date_str = params.get("date", "今天")
        parsed_date = self.date_parser.parse_date_input(date_str)
        
        if not parsed_date:
            return {
                "success": False,
                "message": f"無法解析日期：{date_str}"
            }
        
        # 2. 判斷時間態
        from modules.utils.taiwan_time import get_taiwan_date
        today = get_taiwan_date()
        
        if parsed_date < today:
            # 過去態：已完成的班次
            table_name = "completed_trips"
            time_status = "過去態"
        elif parsed_date == today:
            # 現在態：今天的班次
            table_name = "trips"
            time_status = "現在態（今天）"
        else:
            # 現在態：未來已匯入的班次
            table_name = "trips"
            time_status = "現在態（未來）"
        
        # 3. 查詢相關班次
        location = params.get("location", "")
        driver_id = params.get("driver_id")
        
        trips = self._query_trips_by_location(
            table_name=table_name,
            date=parsed_date,
            location=location,
            driver_id=driver_id
        )
        
        if not trips:
            return {
                "success": False,
                "message": f"沒有找到 {date_str}「{location}」的相關班次"
            }
        
        # 4. 生成確認訊息
        if len(trips) == 1:
            trip = trips[0]
            message = self._format_passenger_leave_confirmation(trip, params, time_status)
            
            # 保存上下文供後續確認使用
            conversation_manager.set_pending_operation(user_id, {
                "action": "passenger_leave",
                "trip_id": trip["id"],
                "table": table_name,
                "reason": params.get("reason", "乘客請假"),
                "allowance": params.get("allowance", 0)
            })
            
            # 生成 Quick Reply 按鈕
            from linebot.v3.messaging import QuickReply, QuickReplyItem, MessageAction
            quick_reply = QuickReply(items=[
                QuickReplyItem(action=MessageAction(label="✅ 確認請假", text="確認請假")),
                QuickReplyItem(action=MessageAction(label="📋 查看詳情", text=f"班次詳情 {trip['id']}")),
                QuickReplyItem(action=MessageAction(label="❌ 取消", text="取消操作"))
            ])
            
            reply_message_with_quick_reply(reply_token, message, quick_reply)
            
            return {"success": True, "message": "已發送確認訊息"}
        
        else:
            # 多個班次：顯示列表供用戶選擇
            message = self._format_multiple_trips_list(trips, date_str, location, time_status)
            reply_text(reply_token, message)
            
            return {"success": True, "message": "已顯示多個班次"}
    
    def _query_trips_by_location(self, table_name: str, date: datetime, 
                                  location: str, driver_id: Optional[int] = None) -> List[Dict]:
        """
        根據地點查詢班次
        
        Args:
            table_name: trips 或 completed_trips
            date: 日期
            location: 地點關鍵字
            driver_id: 司機ID（可選）
        
        Returns:
            符合條件的班次列表
        """
        try:
            # 構建查詢
            if table_name == "trips":
                base_query = """
                    SELECT trip_id as id, date, time, start_point, via_point, end_point,
                           driver_id, passenger_name, status
                    FROM trips
                    WHERE date = :date
                    AND status IN ('待派', '準備')
                """
            else:
                base_query = """
                    SELECT id, date, start_point, via_point, end_point,
                           driver_id, passenger_name, meter_fare, extra_fare
                    FROM completed_trips
                    WHERE date = :date
                """
            
            # 添加地點條件
            if location:
                base_query += """
                    AND (start_point LIKE :location 
                         OR via_point LIKE :location 
                         OR end_point LIKE :location)
                """
            
            # 添加司機條件
            if driver_id:
                base_query += " AND driver_id = :driver_id"
            
            base_query += " ORDER BY time" if table_name == "trips" else " ORDER BY id"
            
            # 執行查詢
            params = {"date": date.strftime("%Y-%m-%d")}
            if location:
                params["location"] = f"%{location}%"
            if driver_id:
                params["driver_id"] = driver_id
            
            result = db.session.execute(text(base_query), params)
            
            # 轉換為字典列表
            trips = []
            for row in result:
                trip = dict(row._mapping)
                trips.append(trip)
            
            return trips
        
        except Exception as e:
            logger.error(f"查詢班次失敗: {e}", exc_info=True)
            return []
    
    def _format_passenger_leave_confirmation(self, trip: Dict, params: Dict, time_status: str) -> str:
        """
        格式化乘客請假確認訊息
        
        範例輸出：
        "明天公園南路的相關班次是：
        班次 658，10:10分，公園南路經海安路到診所
        
        要設為「公園南路請假」嗎？
        或是用「班次詳情 658」自行操作？"
        """
        trip_id = trip.get("id") or trip.get("trip_id")
        time = trip.get("time", "")
        start = trip.get("start_point", "")
        via = trip.get("via_point", "")
        end = trip.get("end_point", "")
        
        # 構建路線描述
        if via:
            route = f"{start}經{via}到{end}"
        else:
            route = f"{start}到{end}"
        
        date_str = params.get("date", "")
        location = params.get("location", "")
        reason = params.get("reason", "乘客請假")
        
        message = f"""📍 {date_str}{location}的相關班次：

🚕 班次 {trip_id}
⏰ 時間：{time}
📍 路線：{route}
📊 狀態：{trip.get('status', 'N/A')}
🕒 時間態：{time_status}

要設為「{reason}」嗎？
💡 或是用「班次詳情 {trip_id}」自行操作"""
        
        return message
    
    def _format_multiple_trips_list(self, trips: List[Dict], date_str: str, 
                                     location: str, time_status: str) -> str:
        """
        格式化多個班次列表
        """
        message = f"📍 {date_str}「{location}」找到 {len(trips)} 個相關班次：\n\n"
        
        for i, trip in enumerate(trips[:5], 1):  # 最多顯示5個
            trip_id = trip.get("id") or trip.get("trip_id")
            time = trip.get("time", "")
            start = trip.get("start_point", "")
            via = trip.get("via_point", "")
            end = trip.get("end_point", "")
            
            route = f"{start}→{end}" if not via else f"{start}經{via}→{end}"
            
            message += f"{i}. 班次 {trip_id}｜{time}｜{route}\n"
        
        if len(trips) > 5:
            message += f"\n...還有 {len(trips) - 5} 個班次\n"
        
        message += f"\n🕒 時間態：{time_status}"
        message += "\n\n💡 請明確指定班次號碼，例如："
        message += f"\n• 「班次 {trips[0].get('id') or trips[0].get('trip_id')} 乘客請假」"
        message += f"\n• 「班次詳情 {trips[0].get('id') or trips[0].get('trip_id')}」"
        
        return message
    
    def _handle_update_fare(self, params: Dict[str, Any], user_id: str, reply_token: str) -> Dict[str, Any]:
        """
        處理修改車資意圖
        
        範例場景：
        用戶："把 4914 加 75，加載湖美街"
        
        處理流程：
        1. 查詢班次 #4914
        2. 顯示當前車資
        3. 請求確認
        4. 執行修改
        """
        logger.info(f"💰 處理車資修改: {params}")
        
        trip_id = params.get("trip_id")
        adjustment = params.get("adjustment", 0)  # 調整金額
        reason = params.get("reason", "車資調整")
        
        if not trip_id:
            return {
                "success": False,
                "message": "請指定要修改的班次號碼"
            }
        
        # 查詢班次（先查 completed_trips）
        try:
            query = text("""
                SELECT id, date, start_point, via_point, end_point,
                       meter_fare, extra_fare, driver_id
                FROM completed_trips
                WHERE id = :trip_id
            """)
            result = db.session.execute(query, {"trip_id": trip_id}).fetchone()
            
            if not result:
                return {
                    "success": False,
                    "message": f"找不到班次 #{trip_id}"
                }
            
            trip = dict(result._mapping)
            current_fare = (trip.get("meter_fare") or 0) + (trip.get("extra_fare") or 0)
            new_fare = current_fare + adjustment
            
            # 生成確認訊息
            message = f"""💰 確認修改班次 #{trip_id} 車資

📍 路線：{trip['start_point']} → {trip['end_point']}
🚕 司機：{trip['driver_id']}
💵 當前車資：${current_fare}
➕ 調整金額：{adjustment:+d} 元
💰 調整後車資：${new_fare}
📝 原因：{reason}

確認修改嗎？"""
            
            # 保存上下文
            conversation_manager.set_pending_operation(user_id, {
                "action": "update_fare",
                "trip_id": trip_id,
                "adjustment": adjustment,
                "reason": reason,
                "current_fare": current_fare,
                "new_fare": new_fare
            })
            
            # 生成 Quick Reply
            from linebot.v3.messaging import QuickReply, QuickReplyItem, MessageAction
            quick_reply = QuickReply(items=[
                QuickReplyItem(action=MessageAction(label="✅ 確認修改", text="確認修改")),
                QuickReplyItem(action=MessageAction(label="❌ 取消", text="取消操作"))
            ])
            
            reply_message_with_quick_reply(reply_token, message, quick_reply)
            
            return {"success": True, "message": "已發送確認訊息"}
        
        except Exception as e:
            logger.error(f"查詢班次失敗: {e}", exc_info=True)
            return {
                "success": False,
                "message": f"查詢班次時發生錯誤: {str(e)}"
            }
    
    def _handle_query_trips(self, params: Dict[str, Any], user_id: str, reply_token: str) -> Dict[str, Any]:
        """
        處理查詢班次意圖
        """
        logger.info(f"🔍 處理班次查詢: {params}")
        
        # TODO: 實現查詢邏輯
        return {
            "success": False,
            "message": "查詢功能正在開發中"
        }
