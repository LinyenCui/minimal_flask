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

from modules.models.base import db
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
            if action == "clarify_user_intent":
                # 🔥 核心：意圖不明確時，先找班次再詢問用戶
                return self._handle_clarify_intent(params, user_id, reply_token)
            
            elif action == "passenger_leave":
                return self._handle_passenger_leave(params, user_id, reply_token)
            
            elif action == "update_fare":
                return self._handle_update_fare(params, user_id, reply_token)
            
            elif action == "query_trips":
                return self._handle_query_trips(params, user_id, reply_token)
            
            elif action == "confirm_operation":
                return self._handle_confirm_operation(user_id, reply_token)
            
            elif action == "cancel_operation":
                return self._handle_cancel_operation(user_id, reply_token)
            
            elif action == "update_trip_status":
                return self._handle_update_trip_status(params, user_id, reply_token)
            
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
    
    def _handle_clarify_intent(self, params: Dict[str, Any], user_id: str, reply_token: str) -> Dict[str, Any]:
        """
        🔥 核心對話功能：意圖不明確時，先找班次再詢問用戶想做什麼
        
        根據班次狀態動態生成選項：
        - 準備/待派 → 請假、註銷、衝突、查詢
        - 請假/註銷/衝突 → 改回準備、查詢
        """
        logger.info(f"🤔 澄清用戶意圖: {params}")
        
        # 1. 解析日期
        date_str = params.get("date", "今天")
        parsed_date = self.date_parser.parse(date_str)
        
        if not parsed_date:
            reply_text(reply_token, f"❌ 無法解析日期：{date_str}\n請使用明確的日期格式，如：明天、12/11")
            return {"success": False, "message": f"無法解析日期：{date_str}"}
        
        # 2. 判斷時間態
        # 🔥 三時間態設計：
        # - 過去態 (completed_trips)：日期 < 今天
        # - 現在態 (trips)：日期 >= 今天（包含今天和未來已匯入的班次）
        # - 未來態 (fixed_schedules)：模板，尚未匯入
        from modules.utils.taiwan_time import get_taiwan_date
        today = get_taiwan_date()
        
        if parsed_date < today:
            table_name = "completed_trips"
            time_status = "過去態"
        else:
            # 🔥 今天和未來已匯入的班次都在 trips 表，都是「現在態」
            table_name = "trips"
            time_status = "現在態 (如來者，如其本來，如實而來)"
        
        # 3. 查詢相關班次（包含所有狀態）
        location = params.get("location", "")
        driver_id = params.get("driver_id")
        category = params.get("category")
        
        trips = self._query_trips_for_clarify(
            table_name=table_name,
            date=parsed_date,
            location=location,
            driver_id=driver_id,
            category=category
        )
        
        if not trips:
            reply_text(reply_token, f"📭 {date_str}「{location}」沒有找到相關班次\n\n💡 請確認日期和地點是否正確")
            return {"success": False, "message": "沒有找到班次"}
        
        # 4. 分析班次狀態，決定提供的選項
        from linebot.v3.messaging import QuickReply, QuickReplyItem, MessageAction
        
        trip_ids = [t.get("id") or t.get("trip_id") for t in trips]
        
        # 保存上下文
        conversation_manager.set_pending_operation(user_id, {
            "action": "clarify_context",
            "trips": [{"id": t.get("id") or t.get("trip_id"), 
                      "route": f"{t.get('start_point')}→{t.get('end_point')}",
                      "status": t.get("status", ""),
                      "leave_reason": t.get("passenger_leave_reason", "")} for t in trips],
            "date": date_str,
            "location": location,
            "table": table_name
        })
        
        # 5. 根據狀態生成 Quick Reply
        if table_name == "trips":
            # 現在態：根據狀態動態生成選項
            quick_reply = self._generate_clarify_quick_reply(trips, date_str, location)
            message = self._format_clarify_with_status(trips, date_str, location, time_status)
        else:
            # 過去態：只提供查詢和車資修改選項
            first_trip_id = trip_ids[0]
            quick_reply = QuickReply(items=[
                QuickReplyItem(action=MessageAction(label="📋 查看詳情", text=f"查看 {first_trip_id}")),
                QuickReplyItem(action=MessageAction(label="💰 修改車資", text=f"修改班次#{first_trip_id}車資")),
                QuickReplyItem(action=MessageAction(label="🔍 查詢全部", text=f"查已完成 {date_str} {location}")),
                QuickReplyItem(action=MessageAction(label="❌ 算了", text="取消操作"))
            ])
            message = self._format_clarify_multiple_trips(trips, date_str, location, time_status)
        
        reply_message_with_quick_reply(reply_token, message, quick_reply)
        return {"success": True, "message": "已詢問用戶意圖"}
    
    def _generate_clarify_quick_reply(self, trips: List[Dict], date_str: str, location: str):
        """
        根據班次狀態動態生成 Quick Reply 選項
        
        🔥 兩層邏輯：
        第一層：詢問要做什麼操作
        - 準備狀態 → 請假？註銷？衝突？只是查詢？
        - 非準備狀態 → 改回準備？
        第二層：用戶選擇後進入對應模式
        
        🔥 2025-12 修復：
        - 全部註銷/衝突/請假狀態時，正確顯示「改回準備」選項
        - 混合狀態時，提供班次詳情按鈕讓用戶單獨處理
        """
        from linebot.v3.messaging import QuickReply, QuickReplyItem, MessageAction
        
        trip_ids = [t.get("id") or t.get("trip_id") for t in trips]
        
        # 分類狀態
        ready_trips = []      # 準備/待派（無請假原因）
        leave_trips = []      # 請假（有請假原因）
        cancelled_trips = []  # 註銷
        conflict_trips = []   # 衝突
        
        for t in trips:
            tid = t.get("id") or t.get("trip_id")
            status = t.get("status", "")
            leave_reason = t.get("passenger_leave_reason", "")
            
            # 判斷實際狀態
            if status in ("準備", "待派"):
                if leave_reason:  # 有請假原因視為請假
                    leave_trips.append(tid)
                else:
                    ready_trips.append(tid)
            elif status == "註銷":
                cancelled_trips.append(tid)
            elif status == "衝突":
                conflict_trips.append(tid)
            else:
                ready_trips.append(tid)  # 預設為準備
        
        items = []
        
        # 🔥 計算非準備狀態的班次數量
        non_ready_count = len(leave_trips) + len(cancelled_trips) + len(conflict_trips)
        
        if len(trips) == 1:
            # === 單一班次 ===
            tid = trip_ids[0]
            if ready_trips:
                # 準備狀態 → 三種操作選項
                items.extend([
                    QuickReplyItem(action=MessageAction(label="🏥 請假", text=f"班次 {tid} 乘客請假")),
                    QuickReplyItem(action=MessageAction(label="🚫 註銷", text=f"修改狀態 {tid} 註銷")),
                    QuickReplyItem(action=MessageAction(label="⚠️ 衝突", text=f"修改狀態 {tid} 衝突")),
                ])
            else:
                # 非準備狀態 → 只有改回準備選項
                items.append(QuickReplyItem(action=MessageAction(label="✅ 改回準備", text=f"修改狀態 {tid} 準備")))
            
            items.append(QuickReplyItem(action=MessageAction(label="📋 查看詳情", text=f"班次詳情 {tid}")))
        
        else:
            # === 多個班次 ===
            if ready_trips and len(ready_trips) == len(trips):
                # 🔥 全部準備狀態 → 第一層：問「要做什麼操作」
                items.extend([
                    QuickReplyItem(action=MessageAction(label="🏥 請假", text="選擇請假")),
                    QuickReplyItem(action=MessageAction(label="🚫 註銷", text="選擇註銷")),
                    QuickReplyItem(action=MessageAction(label="⚠️ 衝突", text="選擇衝突")),
                ])
            
            elif non_ready_count == len(trips):
                # 🔥 全部非準備狀態（註銷/衝突/請假） → 提供改回準備選項
                items.append(QuickReplyItem(action=MessageAction(label="✅ 全部改回準備", text="全部改回準備")))
                # 也提供單個改回選項
                for tid in trip_ids[:2]:
                    items.append(QuickReplyItem(action=MessageAction(label=f"#{tid}改回", text=f"修改狀態 {tid} 準備")))
                # 提供班次詳情
                for tid in trip_ids[:2]:
                    items.append(QuickReplyItem(action=MessageAction(label=f"📋 #{tid}詳情", text=f"班次詳情 {tid}")))
            
            else:
                # 🔥 混合狀態 → 提供班次詳情讓用戶單獨處理
                # 先提供每個班次的詳情按鈕
                for tid in trip_ids[:3]:
                    items.append(QuickReplyItem(action=MessageAction(label=f"📋 #{tid}詳情", text=f"班次詳情 {tid}")))
                
                # 如果有準備狀態的班次，提供批量操作選項
                if ready_trips:
                    items.append(QuickReplyItem(action=MessageAction(label="🏥 請假", text="選擇請假")))
                
                # 如果有非準備狀態的班次，提供改回準備選項
                if non_ready_count > 0:
                    items.append(QuickReplyItem(action=MessageAction(label="✅ 改回準備", text="全部改回準備")))
            
            items.append(QuickReplyItem(action=MessageAction(label="🔍 查詢全部", text=f"查詢班次 {date_str} {location}")))
        
        items.append(QuickReplyItem(action=MessageAction(label="❌ 算了", text="取消操作")))
        
        return QuickReply(items=items[:13])  # LINE 限制最多13個
    
    def _format_clarify_with_status(self, trips: List[Dict], date_str: str, location: str, time_status: str) -> str:
        """格式化班次訊息（包含狀態信息）"""
        message = f"📍 找到 {date_str}「{location}」的 {len(trips)} 個班次：\n\n"
        
        for i, trip in enumerate(trips[:5], 1):
            trip_id = trip.get("id") or trip.get("trip_id")
            time = trip.get("time", "")
            start = trip.get("start_point", "")
            end = trip.get("end_point", "")
            status = trip.get("status", "")
            leave_reason = trip.get("passenger_leave_reason", "")
            
            # 顯示實際狀態
            if leave_reason:
                status_display = f"🔵請假({leave_reason})"
            elif status == "註銷":
                status_display = "🚫註銷"
            elif status == "衝突":
                status_display = "⚠️衝突"
            else:
                status_display = f"✅{status}"
            
            message += f"{i}. #{trip_id}｜{time}｜{start}→{end}｜{status_display}\n"
        
        message += f"\n🕒 {time_status}"
        message += "\n\n❓ 請問您想做什麼？"
        message += "\n💡 點選下方按鈕操作，或直接輸入新命令"
        
        return message
    
    def _query_trips_for_clarify(self, table_name: str, date, location: str, 
                                  driver_id: Optional[int] = None, category: str = None) -> List[Dict]:
        """
        查詢班次用於澄清意圖
        
        🔥 查詢所有狀態的班次（包含已請假、已註銷、已衝突）
        """
        try:
            if table_name == "trips":
                # 🔥 查詢所有狀態，包含 passenger_leave_reason
                base_query = """
                    SELECT trip_id as id, date, time, start_point, via_point, end_point,
                           driver_id, passenger_name, status, category, passenger_leave_reason
                    FROM trips
                    WHERE date = :date
                """
            else:
                base_query = """
                    SELECT id, date, start_point, via_point, end_point,
                           driver_id, passenger_name, meter_fare, extra_fare, category, passenger_leave_reason
                    FROM completed_trips
                    WHERE date = :date
                """
            
            params = {"date": date.strftime("%Y-%m-%d")}
            
            if location:
                base_query += " AND (start_point LIKE :location OR via_point LIKE :location OR end_point LIKE :location)"
                params["location"] = f"%{location}%"
            
            if driver_id:
                base_query += " AND driver_id = :driver_id"
                params["driver_id"] = driver_id
            
            if category:
                base_query += " AND category = :category"
                params["category"] = category
            
            base_query += " ORDER BY time" if table_name == "trips" else " ORDER BY id"
            base_query += " LIMIT 5"
            
            result = db.session.execute(text(base_query), params)
            return [dict(row._mapping) for row in result]
        
        except Exception as e:
            logger.error(f"查詢班次失敗: {e}", exc_info=True)
            return []
    
    def _format_clarify_single_trip(self, trip: Dict, date_str: str, location: str, time_status: str) -> str:
        """格式化單個班次的澄清訊息"""
        trip_id = trip.get("id") or trip.get("trip_id")
        time = trip.get("time", "")
        start = trip.get("start_point", "")
        via = trip.get("via_point", "")
        end = trip.get("end_point", "")
        status = trip.get("status", "")
        
        route = f"{start}→{end}" if not via else f"{start}經{via}→{end}"
        
        return f"""📍 找到 {date_str}「{location}」的班次：

🚕 班次 #{trip_id}
⏰ 時間：{time}
📍 路線：{route}
📊 狀態：{status}
🕒 時間態：{time_status}

❓ 請問您想做什麼？"""
    
    def _format_clarify_multiple_trips(self, trips: List[Dict], date_str: str, location: str, time_status: str) -> str:
        """格式化多個班次的澄清訊息"""
        message = f"📍 找到 {date_str}「{location}」的 {len(trips)} 個班次：\n\n"
        
        for i, trip in enumerate(trips[:5], 1):
            trip_id = trip.get("id") or trip.get("trip_id")
            time = trip.get("time", "")
            start = trip.get("start_point", "")
            end = trip.get("end_point", "")
            message += f"{i}. #{trip_id}｜{time}｜{start}→{end}\n"
        
        message += f"\n🕒 時間態：{time_status}"
        message += "\n\n❓ 請問您想對哪個班次做什麼操作？"
        
        return message
    
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
        parsed_date = self.date_parser.parse(date_str)
        
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
        else:
            # 現在態：今天和未來已匯入的班次都在 trips 表
            table_name = "trips"
            time_status = "現在態 (如來者，如其本來，如實而來)"
        
        # 3. 查詢相關班次（包含已請假的）
        location = params.get("location", "")
        driver_id = params.get("driver_id")
        
        trips = self._query_trips_for_leave(
            table_name=table_name,
            date=parsed_date,
            location=location,
            driver_id=driver_id
        )
        
        if not trips:
            reply_text(reply_token, f"📭 沒有找到 {date_str}「{location}」的相關班次")
            return {"success": False, "message": "沒有找到班次"}
        
        # 4. 分類：已請假 vs 準備狀態
        already_on_leave = [t for t in trips if t.get('passenger_leave_reason')]
        ready_trips = [t for t in trips if not t.get('passenger_leave_reason')]
        
        from linebot.v3.messaging import QuickReply, QuickReplyItem, MessageAction
        
        # 情況1：所有班次都已請假 → 問是否恢復
        if already_on_leave and not ready_trips:
            trip_ids = [t.get('id') for t in already_on_leave]
            
            if len(already_on_leave) == 1:
                trip = already_on_leave[0]
                trip_id = trip.get('id')
                reason = trip.get('passenger_leave_reason', '未知原因')
                message = f"""📍 {date_str}「{location}」的班次：

🚕 班次 #{trip_id}
📍 {trip.get('start_point')}→{trip.get('end_point')}
⏰ {trip.get('time', '')}

⚠️ 這班已經是請假狀態了
📝 原因：{reason}

是否要改回「準備」狀態？"""
                
                # 保存恢復上下文
                conversation_manager.set_pending_operation(user_id, {
                    "action": "restore_from_leave",
                    "trip_ids": trip_ids,
                    "table": table_name
                })
                
                quick_reply = QuickReply(items=[
                    QuickReplyItem(action=MessageAction(label="✅ 改回準備", text="確認請假")),
                    QuickReplyItem(action=MessageAction(label=f"📋 #{trip_id}詳情", text=f"班次詳情 {trip_id}")),
                    QuickReplyItem(action=MessageAction(label="❌ 放棄操作", text="取消操作"))
                ])
            else:
                # 多個已請假班次
                message = f"📍 {date_str}「{location}」找到 {len(already_on_leave)} 個班次，都已經請假了：\n\n"
                for trip in already_on_leave[:5]:
                    tid = trip.get('id')
                    reason = trip.get('passenger_leave_reason', '')
                    message += f"• #{tid} {trip.get('start_point')}→{trip.get('end_point')} ({reason})\n"
                message += "\n請選擇要改回準備的班次："
                
                # 保存恢復上下文（全部）
                conversation_manager.set_pending_operation(user_id, {
                    "action": "restore_from_leave",
                    "trip_ids": trip_ids,
                    "table": table_name
                })
                
                # 🔥 生成選項：全部改回 + 單獨改回
                items = [
                    QuickReplyItem(action=MessageAction(label="✅ 全部改回準備", text="確認請假"))
                ]
                for tid in trip_ids[:2]:  # 最多顯示2個單獨選項
                    items.append(QuickReplyItem(action=MessageAction(label=f"#{tid}改回", text=f"班次詳情 {tid}")))
                items.append(QuickReplyItem(action=MessageAction(label="❌ 放棄操作", text="取消操作")))
                
                quick_reply = QuickReply(items=items)
            
            reply_message_with_quick_reply(reply_token, message, quick_reply)
            return {"success": True, "message": "班次已請假"}
        
        # 🔥 情況2：混合狀態（部分已請假、部分準備）
        if already_on_leave and ready_trips:
            # 顯示混合狀態信息
            message = f"📍 {date_str}「{location}」找到 {len(trips)} 個班次：\n\n"
            
            # 已請假的班次
            message += f"🔵 已請假 ({len(already_on_leave)}個)：\n"
            for trip in already_on_leave[:3]:
                tid = trip.get('id')
                reason = trip.get('passenger_leave_reason', '')
                message += f"  • #{tid} {trip.get('start_point')}→{trip.get('end_point')} ({reason})\n"
            
            # 準備狀態的班次
            message += f"\n✅ 可請假 ({len(ready_trips)}個)：\n"
            for trip in ready_trips[:3]:
                tid = trip.get('id')
                message += f"  • #{tid} {trip.get('time', '')} {trip.get('start_point')}→{trip.get('end_point')}\n"
            
            message += "\n請選擇操作："
            
            # 生成選項
            items = []
            
            # 如果有多個準備班次，顯示全部請假
            if len(ready_trips) > 1:
                trip_ids = [t.get('id') for t in ready_trips]
                conversation_manager.set_leave_mode(user_id=user_id, trip_ids=trip_ids)
                items.append(QuickReplyItem(action=MessageAction(label=f"🏥 全部請假({len(ready_trips)}班)", text="全部請假")))
            
            # 單獨請假選項
            for trip in ready_trips[:2]:
                tid = trip.get('id')
                items.append(QuickReplyItem(action=MessageAction(label=f"#{tid}請假", text=f"#{tid}請假")))
            
            # 改回準備選項（已請假的）
            if len(already_on_leave) == 1:
                tid = already_on_leave[0].get('id')
                items.append(QuickReplyItem(action=MessageAction(label=f"#{tid}改回準備", text=f"#{tid}改回")))
            else:
                items.append(QuickReplyItem(action=MessageAction(label="全部改回準備", text="全部改回準備")))
            
            items.append(QuickReplyItem(action=MessageAction(label="❌ 放棄", text="放棄操作")))
            
            # 保存上下文
            conversation_manager.set_pending_operation(user_id, {
                "action": "mixed_leave_status",
                "ready_trip_ids": [t.get('id') for t in ready_trips],
                "leave_trip_ids": [t.get('id') for t in already_on_leave],
                "table": table_name
            })
            
            quick_reply = QuickReply(items=items)
            reply_message_with_quick_reply(reply_token, message, quick_reply)
            return {"success": True, "message": "混合狀態"}
        
        # 情況3：有準備狀態的班次可以請假 → 進入請假模式
        if len(ready_trips) == 1:
            trip = ready_trips[0]
            trip_id = trip.get('id')
            
            # 🔥 使用現有的請假模式（讓用戶輸入理由+加成）
            conversation_manager.set_leave_mode(user_id=user_id, trip_id=trip_id)
            
            message = f"""📍 找到 {date_str}「{location}」的班次：

🚕 班次 #{trip_id}
📍 {trip.get('start_point')}→{trip.get('end_point')}
⏰ {trip.get('time', '')}

🏥 已進入請假模式
請輸入「請假原因 加成金額」
例如：出國旅遊 -50

💡 輸入「放棄操作」取消"""
            
            quick_reply = QuickReply(items=[
                QuickReplyItem(action=MessageAction(label="📋 查看詳情", text=f"班次詳情 {trip_id}")),
                QuickReplyItem(action=MessageAction(label="❌ 放棄操作", text="放棄操作"))
            ])
            
            reply_message_with_quick_reply(reply_token, message, quick_reply)
            return {"success": True, "message": "已進入請假模式"}
        
        else:
            # 🔥 多個準備狀態班次：進入批量請假模式
            trip_ids = [t.get('id') for t in ready_trips]
            
            # 進入批量請假模式
            conversation_manager.set_leave_mode(user_id=user_id, trip_ids=trip_ids)
            
            message = f"📍 {date_str}「{location}」找到 {len(ready_trips)} 個班次：\n\n"
            
            for trip in ready_trips[:5]:
                trip_id = trip.get('id')
                message += f"• #{trip_id} {trip.get('time', '')} {trip.get('start_point')}→{trip.get('end_point')}\n"
            
            message += f"\n🏥 請選擇請假方式："
            
            # 🔥 修復：生成正確的 Quick Reply 選項
            items = [
                # 全部請假按鈕（最重要！）
                QuickReplyItem(action=MessageAction(label=f"🏥 全部請假({len(trip_ids)}班)", text="全部請假"))
            ]
            # 也提供單獨請假選項
            for tid in trip_ids[:2]:
                items.append(QuickReplyItem(action=MessageAction(label=f"只#{tid}請假", text=f"#{tid}請假")))
            # 放棄按鈕放最後
            items.append(QuickReplyItem(action=MessageAction(label="❌ 放棄", text="放棄操作")))
            
            quick_reply = QuickReply(items=items)
            reply_message_with_quick_reply(reply_token, message, quick_reply)
            return {"success": True, "message": "已進入批量請假模式"}
    
    def _query_trips_for_leave(self, table_name: str, date, location: str, 
                                driver_id: Optional[int] = None) -> List[Dict]:
        """查詢班次用於請假操作（包含已請假的班次）"""
        try:
            if table_name == "trips":
                base_query = """
                    SELECT trip_id as id, date, time, start_point, via_point, end_point,
                           driver_id, passenger_name, status, passenger_leave_reason
                    FROM trips
                    WHERE date = :date
                    AND status IN ('待派', '準備')
                """
            else:
                base_query = """
                    SELECT id, date, start_point, via_point, end_point,
                           driver_id, passenger_name, meter_fare, extra_fare, passenger_leave_reason
                    FROM completed_trips
                    WHERE date = :date
                """
            
            params = {"date": date.strftime("%Y-%m-%d")}
            
            if location:
                base_query += " AND (start_point LIKE :location OR via_point LIKE :location OR end_point LIKE :location)"
                params["location"] = f"%{location}%"
            
            if driver_id:
                base_query += " AND driver_id = :driver_id"
                params["driver_id"] = driver_id
            
            base_query += " ORDER BY time" if table_name == "trips" else " ORDER BY id"
            base_query += " LIMIT 10"
            
            result = db.session.execute(text(base_query), params)
            return [dict(row._mapping) for row in result]
        
        except Exception as e:
            logger.error(f"查詢班次失敗: {e}", exc_info=True)
            return []
    
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
        
        支持兩種模式：
        1. 設定模式：$550+250 → 錶價=550, 加成=250
        2. 累加模式：+75 → 在現有基礎上加75
        
        處理流程：
        1. 查詢班次
        2. 顯示當前與調整後車資
        3. 請求確認
        4. 執行修改
        """
        logger.info(f"💰 處理車資修改: {params}")
        
        trip_id = params.get("trip_id")
        # 🔥 支持直接設定錶價和加成
        new_meter_fare = params.get("meter_fare")  # 設定錶價
        new_extra_fare = params.get("extra_fare")  # 設定加成
        adjustment = params.get("adjustment", 0)   # 累加金額（舊模式）
        reason = params.get("reason", "")
        
        if not trip_id:
            return {
                "success": False,
                "message": "請指定要修改的班次號碼"
            }
        
        # 查詢班次（先查 completed_trips）
        try:
            query = text("""
                SELECT id, date, start_point, via_point, end_point,
                       meter_fare, extra_fare, driver_id, category
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
            current_meter = trip.get("meter_fare") or 0
            current_extra = trip.get("extra_fare") or 0
            
            # 🔥 計算新車資
            if new_meter_fare is not None or new_extra_fare is not None:
                final_meter = new_meter_fare if new_meter_fare is not None else current_meter
                final_extra = new_extra_fare if new_extra_fare is not None else current_extra
                if new_extra_fare is None and adjustment != 0:
                    final_extra = adjustment
            else:
                final_meter = current_meter
                final_extra = current_extra + adjustment
            
            # 🔥 關鍵：檢查是否為預設原因，複用 ai_fare_service.py 的邏輯
            default_reasons = [
                '透過AI智能修改', '錶價260加成', '費用調整要求',
                '一般記帳', '一般記賬', '記帳', '記賬',  # Gemini FC 常填的預設原因
                '車資調整', '修改車資', '車資修改', '費用修改',
            ]
            is_default_reason = not reason or reason.strip() in default_reasons or len(reason.strip()) < 3
            
            if is_default_reason:
                # 🔥 需要追問原因，使用現有的對話系統（ai_modification_reason）
                logger.info(f"🔍 檢測到預設原因 '{reason}'，啟動追問模式")
                
                context_data = {
                    'trip_id': trip['id'],
                    'meter_fare': final_meter,
                    'extra_fare': final_extra,
                    'trip': trip,
                    'original_meter': current_meter,
                    'original_extra': current_extra
                }
                
                conversation_manager.start_conversation(
                    user_id, "ai_modification_reason", 
                    current_step="waiting_reason",
                    context_data=context_data,
                    prompt_message=f"請提供修改班次#{trip['id']}車資的原因",
                    duration_minutes=3
                )
                
                confirmation_message = f"""🎯 AI理解您要修改班次#{trip['id']}的車資：

📊 當前記錄：錶價 {current_meter}, 加成 {current_extra}
🔄 修改為：錶價 {final_meter}, 加成 {final_extra}

⚠️ 請說明修改原因（例如：客戶要求調整、等候時間過長等）"""
                
                # 返回追問訊息（帶放棄按鈕）
                from linebot.v3.messaging import QuickReply, QuickReplyItem, MessageAction
                quick_reply = QuickReply(items=[
                    QuickReplyItem(action=MessageAction(label="❌ 放棄修改", text="放棄AI修改"))
                ])
                reply_message_with_quick_reply(reply_token, confirmation_message, quick_reply)
                
                return {"success": True, "message": "已發送追問原因訊息", "waiting_reason": True}
            
            # 🔥 有明確原因，調用現有的 execute_fare_modification 生成確認框
            from modules.services.ai_fare_service import execute_fare_modification
            
            modification_intent = {
                'meter_fare': final_meter,
                'extra_fare': final_extra,
                'reason': reason
            }
            
            flex_result = execute_fare_modification(trip, modification_intent, user_id)
            
            if flex_result and isinstance(flex_result, dict):
                # 返回 Flex Message 確認框
                from modules.handlers.text_message_handler import handle_ai_fare_result
                handle_ai_fare_result(flex_result, reply_token)
                return {"success": True, "message": "已發送確認訊息"}
            else:
                # 降級為文字回覆
                reply_text(reply_token, str(flex_result) if flex_result else "❌ 生成確認框失敗")
                return {"success": False, "message": "生成確認框失敗"}
        
        except Exception as e:
            logger.error(f"查詢班次失敗: {e}", exc_info=True)
            return {
                "success": False,
                "message": f"查詢班次時發生錯誤: {str(e)}"
            }
    
    def _handle_query_trips(self, params: Dict[str, Any], user_id: str, reply_token: str) -> Dict[str, Any]:
        """
        處理查詢班次意圖 - 直接查詢並返回結果
        🔥 2025-12-17 修復：實現真正的查詢，不再降級
        """
        logger.info(f"🔍 處理班次查詢: {params}")
        
        date_str = params.get("date", "今天")
        location = params.get("location", "")
        driver_id = params.get("driver_id")
        category = params.get("category")
        
        # 解析日期
        parsed_date = self.date_parser.parse_to_date(date_str)
        if not parsed_date:
            parsed_date = get_taiwan_date()
        
        # 判斷時間態
        today = get_taiwan_date()
        if parsed_date < today:
            table_name = "completed_trips"
        else:
            table_name = "trips"
        
        # 查詢班次
        trips = self._query_trips_by_location(table_name, parsed_date, location, driver_id)
        
        if not trips:
            reply_text(reply_token, f"❌ 找不到符合條件的班次\n\n📅 日期：{date_str}\n📍 地點：{location or '全部'}")
            return {"success": True, "message": "查無結果"}
        
        # 格式化結果
        message = f"🔍 查詢結果\n\n"
        message += f"📅 日期：{parsed_date.strftime('%Y-%m-%d')} ({date_str})\n"
        if location:
            message += f"📍 地點：{location}\n"
        message += f"📊 找到 {len(trips)} 筆班次\n"
        message += "-" * 25 + "\n\n"
        
        for trip in trips[:10]:  # 最多顯示10筆
            tid = trip.get('id') or trip.get('trip_id')
            route = trip.get('route', f"{trip.get('start_point', '?')}→{trip.get('end_point', '?')}")
            status = trip.get('status', '未知')
            driver = trip.get('driver_id', '未指派')
            leave_reason = trip.get('leave_reason') or trip.get('passenger_leave_reason')
            
            # 狀態圖示
            if status == '準備' and leave_reason:
                status_icon = "🔵請假"
            elif status == '準備':
                status_icon = "🟢準備"
            elif status == '待派':
                status_icon = "🔴待派"
            elif status == '註銷':
                status_icon = "❌註銷"
            elif status == '衝突':
                status_icon = "🟠衝突"
            else:
                status_icon = status
            
            message += f"#{tid} {route} | 🚕{driver} | {status_icon}\n"
        
        if len(trips) > 10:
            message += f"\n... 還有 {len(trips) - 10} 筆\n"
        
        reply_text(reply_token, message)
        return {"success": True, "message": "查詢成功"}
    
    def _handle_confirm_operation(self, user_id: str, reply_token: str) -> Dict[str, Any]:
        """
        處理確認操作
        執行待確認的請假或車資修改
        """
        logger.info(f"✅ 處理確認操作: user_id={user_id}")
        
        # 獲取待執行的操作
        pending_op = conversation_manager.get_pending_operation(user_id)
        
        if not pending_op:
            reply_text(reply_token, "❌ 沒有待確認的操作\n\n請先發起請假或修改車資的請求")
            return {"success": False, "message": "無待確認操作"}
        
        action = pending_op.get("action")
        
        try:
            if action == "passenger_leave":
                return self._execute_passenger_leave(pending_op, user_id, reply_token)
            elif action == "restore_from_leave":
                return self._execute_restore_from_leave(pending_op, user_id, reply_token)
            elif action == "batch_leave":
                return self._execute_batch_leave(pending_op, user_id, reply_token)
            elif action == "update_fare":
                return self._execute_update_fare(pending_op, user_id, reply_token)
            else:
                reply_text(reply_token, f"❌ 未知的操作類型: {action}")
                return {"success": False, "message": f"未知操作類型: {action}"}
        
        finally:
            # 清除待執行操作
            conversation_manager.clear_pending_operation(user_id)
    
    def _handle_cancel_operation(self, user_id: str, reply_token: str) -> Dict[str, Any]:
        """
        處理取消操作
        """
        logger.info(f"❌ 處理取消操作: user_id={user_id}")
        
        # 清除待執行的操作
        conversation_manager.clear_pending_operation(user_id)
        
        reply_text(reply_token, "✅ 已取消操作\n\n如有需要，可以重新發起請求")
        return {"success": True, "message": "已取消"}
    
    def _handle_update_trip_status(self, params: Dict[str, Any], user_id: str, reply_token: str) -> Dict[str, Any]:
        """
        處理修改班次狀態意圖（註銷、衝突等）
        
        🔥 2025-12-17 新增：用戶明確說「今天新建路的要註銷」時，直接找到班次並執行
        """
        logger.info(f"🔄 處理修改狀態: {params}")
        
        date_str = params.get("date", "今天")
        location = params.get("location", "")
        new_status = params.get("new_status", "")
        
        if not new_status:
            reply_text(reply_token, "❌ 請指定要修改的狀態（如：註銷、衝突）")
            return {"success": False, "message": "未指定狀態"}
        
        # 解析日期
        parsed_date = self.date_parser.parse(date_str)
        if not parsed_date:
            reply_text(reply_token, f"❌ 無法解析日期：{date_str}")
            return {"success": False, "message": f"無法解析日期：{date_str}"}
        
        # 查詢相關班次
        trips = self._query_trips_for_leave("trips", parsed_date, location)
        
        if not trips:
            reply_text(reply_token, f"📭 {date_str}「{location}」沒有找到相關班次")
            return {"success": False, "message": "沒有找到班次"}
        
        from linebot.v3.messaging import QuickReply, QuickReplyItem, MessageAction
        
        trip_ids = [t.get('id') for t in trips]
        
        # 狀態圖示
        status_icons = {
            '註銷': '🚫',
            '衝突': '⚠️',
            '準備': '✅',
            '待派': '🔴'
        }
        status_icon = status_icons.get(new_status, '🔄')
        
        if len(trips) == 1:
            # 單一班次：直接執行
            trip = trips[0]
            trip_id = trip.get('id')
            
            try:
                update_query = text("""
                    UPDATE trips
                    SET status = :new_status
                    WHERE trip_id = :trip_id
                    RETURNING trip_id, status
                """)
                result = db.session.execute(update_query, {
                    "trip_id": trip_id,
                    "new_status": new_status
                })
                updated_row = result.fetchone()
                db.session.commit()
                
                if updated_row:
                    message = f"""✅ 狀態修改成功！

🚕 班次 #{trip_id}
📍 {trip.get('start_point')}→{trip.get('end_point')}
{status_icon} 狀態：{new_status}

💡 如需修改，請使用「班次詳情 {trip_id}」查看"""
                    reply_text(reply_token, message)
                    return {"success": True, "message": f"已修改為{new_status}"}
                else:
                    reply_text(reply_token, f"❌ 找不到班次 #{trip_id}")
                    return {"success": False, "message": "班次不存在"}
                    
            except Exception as e:
                db.session.rollback()
                logger.error(f"修改狀態失敗: {e}", exc_info=True)
                reply_text(reply_token, f"❌ 修改失敗: {str(e)}")
                return {"success": False, "message": str(e)}
        
        else:
            # 多個班次：讓用戶選擇
            message = f"📍 {date_str}「{location}」找到 {len(trips)} 個班次：\n\n"
            
            for trip in trips[:5]:
                tid = trip.get('id')
                message += f"• #{tid} {trip.get('time', '')} {trip.get('start_point')}→{trip.get('end_point')}\n"
            
            message += f"\n{status_icon} 要將哪些班次設為「{new_status}」？"
            
            # 保存上下文
            conversation_manager.set_pending_operation(user_id, {
                "action": "batch_update_status",
                "trip_ids": trip_ids,
                "new_status": new_status,
                "date": date_str,
                "location": location,
                "table": "trips"
            })
            
            # 生成 Quick Reply
            items = [
                QuickReplyItem(action=MessageAction(label=f"{status_icon} 全部{new_status}", text=f"全部{new_status}"))
            ]
            for tid in trip_ids[:2]:
                items.append(QuickReplyItem(action=MessageAction(label=f"#{tid}{new_status}", text=f"修改狀態 {tid} {new_status}")))
            items.append(QuickReplyItem(action=MessageAction(label="❌ 放棄", text="放棄操作")))
            
            quick_reply = QuickReply(items=items)
            reply_message_with_quick_reply(reply_token, message, quick_reply)
            return {"success": True, "message": f"已進入批量{new_status}模式"}
    
    def _execute_passenger_leave(self, pending_op: Dict[str, Any], user_id: str, reply_token: str) -> Dict[str, Any]:
        """
        執行乘客請假操作
        """
        trip_id = pending_op.get("trip_id")
        table_name = pending_op.get("table")
        reason = pending_op.get("reason", "乘客請假")
        allowance = pending_op.get("allowance", 0)
        
        logger.info(f"🏥 執行請假: trip_id={trip_id}, table={table_name}, reason={reason}, allowance={allowance}")
        
        try:
            if table_name == "trips":
                # 現在態：更新 trips 表
                update_query = text("""
                    UPDATE trips
                    SET passenger_leave_reason = :reason,
                        extra_fare = COALESCE(extra_fare, 0) + :allowance
                    WHERE trip_id = :trip_id
                    RETURNING trip_id, passenger_leave_reason, extra_fare
                """)
                result = db.session.execute(update_query, {
                    "trip_id": trip_id,
                    "reason": reason,
                    "allowance": allowance
                })
                updated_row = result.fetchone()
                db.session.commit()
                
                if updated_row:
                    allowance_text = f"，加成調整 {allowance:+d} 元" if allowance != 0 else ""
                    message = f"""✅ 請假設定成功！

🚕 班次 #{trip_id}
📝 請假原因：{reason}{allowance_text}

💡 班次狀態保持「準備」，系統會記錄請假原因
如需修改，請使用「班次詳情 {trip_id}」查看"""
                    
                    reply_text(reply_token, message)
                    return {"success": True, "message": "請假成功"}
                else:
                    reply_text(reply_token, f"❌ 找不到班次 #{trip_id}")
                    return {"success": False, "message": "班次不存在"}
            
            else:
                # 過去態：更新 completed_trips 表
                update_query = text("""
                    UPDATE completed_trips
                    SET passenger_leave_reason = :reason,
                        extra_fare = COALESCE(extra_fare, 0) + :allowance
                    WHERE id = :trip_id
                    RETURNING id, passenger_leave_reason, extra_fare
                """)
                result = db.session.execute(update_query, {
                    "trip_id": trip_id,
                    "reason": reason,
                    "allowance": allowance
                })
                updated_row = result.fetchone()
                db.session.commit()
                
                if updated_row:
                    allowance_text = f"，加成調整 {allowance:+d} 元" if allowance != 0 else ""
                    message = f"""✅ 已完成班次請假記錄成功！

🚕 班次 #{trip_id}
📝 請假原因：{reason}{allowance_text}

💡 如需修改，請使用「查看 {trip_id}」查看詳情"""
                    
                    reply_text(reply_token, message)
                    return {"success": True, "message": "請假記錄成功"}
                else:
                    reply_text(reply_token, f"❌ 找不到已完成班次 #{trip_id}")
                    return {"success": False, "message": "班次不存在"}
        
        except Exception as e:
            db.session.rollback()
            logger.error(f"執行請假失敗: {e}", exc_info=True)
            reply_text(reply_token, f"❌ 請假操作失敗: {str(e)}")
            return {"success": False, "message": str(e)}
    
    def _execute_restore_from_leave(self, pending_op: Dict[str, Any], user_id: str, reply_token: str) -> Dict[str, Any]:
        """
        執行恢復（從請假改回準備狀態）- 支持批量
        """
        trip_id = pending_op.get("trip_id")
        trip_ids = pending_op.get("trip_ids", [])
        table_name = pending_op.get("table")
        
        # 兼容單一 trip_id
        if trip_id and not trip_ids:
            trip_ids = [trip_id]
        
        logger.info(f"🔄 執行恢復: trip_ids={trip_ids}, table={table_name}")
        
        try:
            if table_name == "trips":
                success_count = 0
                restored_trips = []
                
                for tid in trip_ids:
                    # 🔥 清除所有請假相關欄位
                    update_query = text("""
                        UPDATE trips
                        SET passenger_leave_reason = NULL,
                            extra_fare = 0,
                            modification_reason = NULL
                        WHERE trip_id = :trip_id
                        RETURNING trip_id, start_point, end_point
                    """)
                    result = db.session.execute(update_query, {"trip_id": tid})
                    updated_row = result.fetchone()
                    if updated_row:
                        success_count += 1
                        restored_trips.append(f"#{tid}")
                
                db.session.commit()
                
                if success_count > 0:
                    if len(trip_ids) == 1:
                        message = f"""✅ 已恢復為準備狀態！

🚕 班次 {restored_trips[0]}
📊 狀態：準備（已清除請假原因和加成）

💡 如需再次請假，請使用相同方式操作"""
                    else:
                        message = f"""✅ 批量恢復完成！

🚕 班次：{', '.join(restored_trips)}
📊 狀態：準備（已清除請假原因和加成）
✅ 成功：{success_count}/{len(trip_ids)} 個"""
                    
                    reply_text(reply_token, message)
                    return {"success": True, "message": f"已恢復 {success_count} 個班次"}
                else:
                    reply_text(reply_token, f"❌ 找不到指定班次")
                    return {"success": False, "message": "班次不存在"}
            else:
                reply_text(reply_token, "❌ 已完成班次無法恢復狀態")
                return {"success": False, "message": "已完成班次無法恢復"}
        
        except Exception as e:
            db.session.rollback()
            logger.error(f"執行恢復失敗: {e}", exc_info=True)
            reply_text(reply_token, f"❌ 恢復操作失敗: {str(e)}")
            return {"success": False, "message": str(e)}
    
    def _execute_batch_leave(self, pending_op: Dict[str, Any], user_id: str, reply_token: str) -> Dict[str, Any]:
        """
        執行批量請假
        """
        trip_ids = pending_op.get("trip_ids", [])
        table_name = pending_op.get("table")
        reason = pending_op.get("reason", "乘客請假")
        
        logger.info(f"🏥 執行批量請假: trip_ids={trip_ids}, table={table_name}, reason={reason}")
        
        if not trip_ids:
            reply_text(reply_token, "❌ 沒有指定班次")
            return {"success": False, "message": "沒有指定班次"}
        
        try:
            if table_name == "trips":
                success_count = 0
                for trip_id in trip_ids:
                    update_query = text("""
                        UPDATE trips
                        SET passenger_leave_reason = :reason
                        WHERE trip_id = :trip_id
                        RETURNING trip_id
                    """)
                    result = db.session.execute(update_query, {
                        "trip_id": trip_id,
                        "reason": reason
                    })
                    if result.fetchone():
                        success_count += 1
                
                db.session.commit()
                
                if success_count > 0:
                    trip_list = ", ".join([f"#{tid}" for tid in trip_ids[:success_count]])
                    message = f"""✅ 批量請假成功！

🏥 已請假班次：{trip_list}
📝 請假原因：{reason}
📊 成功：{success_count} 個班次

💡 如需恢復，請使用「班次詳情 #ID」查看後操作"""
                    
                    reply_text(reply_token, message)
                    return {"success": True, "message": f"批量請假成功: {success_count}個"}
                else:
                    reply_text(reply_token, "❌ 沒有班次被更新")
                    return {"success": False, "message": "沒有班次被更新"}
            else:
                reply_text(reply_token, "❌ 已完成班次請使用單獨操作")
                return {"success": False, "message": "已完成班次不支援批量請假"}
        
        except Exception as e:
            db.session.rollback()
            logger.error(f"執行批量請假失敗: {e}", exc_info=True)
            reply_text(reply_token, f"❌ 批量請假失敗: {str(e)}")
            return {"success": False, "message": str(e)}
    
    def _execute_update_fare(self, pending_op: Dict[str, Any], user_id: str, reply_token: str) -> Dict[str, Any]:
        """
        執行車資修改操作
        
        支持設定模式：直接設定 meter_fare 和 extra_fare
        """
        trip_id = pending_op.get("trip_id")
        meter_fare = pending_op.get("meter_fare")
        extra_fare = pending_op.get("extra_fare")
        reason = pending_op.get("reason", "車資調整")
        
        logger.info(f"💰 執行車資修改: trip_id={trip_id}, meter_fare={meter_fare}, extra_fare={extra_fare}, reason={reason}")
        
        try:
            # 🔥 直接設定錶價和加成
            update_query = text("""
                UPDATE completed_trips
                SET meter_fare = :meter_fare,
                    extra_fare = :extra_fare,
                    modification_reason = :reason
                WHERE id = :trip_id
                RETURNING id, meter_fare, extra_fare
            """)
            result = db.session.execute(update_query, {
                "trip_id": trip_id,
                "meter_fare": meter_fare,
                "extra_fare": extra_fare,
                "reason": reason
            })
            
            updated_row = result.fetchone()
            db.session.commit()
            
            if updated_row:
                total_fare = (updated_row.meter_fare or 0) + (updated_row.extra_fare or 0)
                message = f"""✅ 車資修改成功！

🚕 班次 #{trip_id}
💵 錶價：${updated_row.meter_fare or 0}
➕ 加成：${updated_row.extra_fare or 0}
💰 總計：${total_fare}
📝 原因：{reason}"""
                
                reply_text(reply_token, message)
                return {"success": True, "message": "車資修改成功"}
            else:
                reply_text(reply_token, f"❌ 找不到班次 #{trip_id}")
                return {"success": False, "message": "班次不存在"}
        
        except Exception as e:
            db.session.rollback()
            logger.error(f"執行車資修改失敗: {e}", exc_info=True)
            reply_text(reply_token, f"❌ 車資修改失敗: {str(e)}")
            return {"success": False, "message": str(e)}
