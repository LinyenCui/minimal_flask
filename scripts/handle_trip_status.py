from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text as sql_text
from models import db

def handle_update_trip_status(message_text):
    """處理修改班次狀態的請求"""
    try:
        # 解析命令格式：修改狀態 [班次ID] [新狀態]
        parts = message_text.split()
        if len(parts) < 3:
            return "命令格式不正確。正確格式：修改狀態 [班次ID] [新狀態]\n\n可用狀態：取消、衝突、請假"
        
        trip_id = parts[1]
        new_status = parts[2]
        
        # 檢查狀態是否有效
        valid_statuses = ["準備", "取消", "衝突", "請假"]
        if new_status not in valid_statuses:
            return f"無效的狀態：{new_status}\n\n可用狀態：取消、衝突、請假\n\n如需改回準備狀態，請使用文字命令：修改狀態 {trip_id} 準備"
        
        # 查詢當前班次信息
        query = """
        SELECT 
            t.trip_id, 
            t.date, 
            t.time, 
            t.status,
            t.fixed_trip_id,
            d.id as driver_id
        FROM 
            trips t
        LEFT JOIN 
            drivers d ON t.driver_id = d.id
        WHERE 
            t.trip_id = :trip_id
        """
        
        trip = db.session.execute(sql_text(query), {"trip_id": trip_id}).fetchone()
        
        if not trip:
            return f"找不到ID為 {trip_id} 的班次。"
        
        current_status = trip[3]
        fixed_trip_id = trip[4]
        driver_id = trip[5]
        trip_date = trip[1]
        trip_time = trip[2]
        
        # 檢查時間限制（取消和請假需要在距離執行時間一個小時以上）
        if new_status in ["取消", "請假"]:
            from datetime import datetime, timedelta
            
            # 獲取當前時間
            now = datetime.now()
            
            # 構建班次執行時間
            trip_datetime = datetime.combine(trip_date, trip_time)
            
            # 計算時間差
            time_diff = trip_datetime - now
            
            # 如果時間差小於一小時，拒絕操作
            if time_diff < timedelta(hours=1):
                return f"該班次執行時間距目前時間不足一小時，請聯絡管理員後台操作"
        
        # 狀態轉換邏輯
        if new_status == "準備" and current_status == "待派" and not driver_id:
            return f"無法將班次 #{trip_id} 的狀態從「{current_status}」更改為「{new_status}」。\n班次必須先指派司機才能設為準備狀態。"
        
        if new_status == "取消":
            # 確認取消操作
            # 使用更適合的確認格式：在回覆中不加前綴，系統會自動添加必要的前綴
            return f"您確定要取消班次 #{trip_id} 嗎？\n請回覆「確認取消 {trip_id}」進行確認，或回覆其他內容取消操作。\n\n注意：在群組聊天中需要加前綴（!確認取消 {trip_id}）"
        
        if new_status == "衝突":
            # 確認衝突操作
            return f"您確定要將班次 #{trip_id} 設為衝突狀態嗎？\n這表示該班次無法由原定司機完成，請診所幫忙另外叫車。\n請回覆「確認衝突 {trip_id}」進行確認，或回覆其他內容取消操作。\n\n注意：在群組聊天中需要加前綴（!確認衝突 {trip_id}）"
        
        if new_status == "請假" and fixed_trip_id:
            # 確認請假操作
            return f"您確定要將班次 #{trip_id} 設為請假狀態嗎？\n這將影響後續週期的固定班次。\n請回覆「確認請假 {trip_id}」進行確認，或回覆其他內容取消操作。\n\n注意：在群組聊天中需要加前綴（!確認請假 {trip_id}）"
        
        # 更新數據庫中的班次狀態
        update_query = """
        UPDATE trips
        SET status = :new_status
        WHERE trip_id = :trip_id
        RETURNING trip_id
        """
        
        result = db.session.execute(sql_text(update_query), {
            "trip_id": trip_id,
            "new_status": new_status
        })
        
        # 提交事務
        db.session.commit()
        
        # 檢查是否找到並更新了班次
        updated_trip = result.fetchone()
        if not updated_trip:
            return f"找不到ID為 {trip_id} 的班次。"
        
        # 根據狀態提供不同的回覆
        status_messages = {
            "準備": f"✅ 班次 #{trip_id} 的狀態已更新為「準備」，已準備執行。",
            "衝突": f"⚠️ 班次 #{trip_id} 的狀態已更新為「衝突」，表示該班次無法由原定司機完成，請診所幫忙另外叫車。"
        }
        
        # 構建基本回覆文本
        reply_text = status_messages.get(new_status, f"✅ 班次 #{trip_id} 的狀態已更新為「{new_status}」。")
        
        # 構建帶有 Quick Reply 的回覆
        reply = {
            'text': reply_text,
            'quick_reply': {
                'items': [
                    {
                        'type': 'action',
                        'action': {
                            'type': 'message',
                            'label': '查詢班次',
                            'text': '!查詢班次'
                        }
                    },
                    {
                        'type': 'action',
                        'action': {
                            'type': 'message',
                            'label': '班次詳情',
                            'text': f'!班次詳情 {trip_id}'
                        }
                    }
                ]
            }
        }
        
        return reply
        
    except Exception as e:
        # 回滾事務
        db.session.rollback()
        return f"修改班次狀態失敗: {str(e)}"

def handle_confirm_cancel_trip(message_text):
    """處理確認取消班次的請求"""
    try:
        # 解析命令格式：確認取消 [班次ID]
        parts = message_text.split()
        if len(parts) < 2:
            return "命令格式不正確。正確格式：確認取消 [班次ID]"
        
        trip_id = parts[1]
        
        # 查詢班次信息
        query = """
        SELECT 
            t.trip_id, 
            t.date, 
            t.time, 
            t.status,
            t.fixed_trip_id,
            d.id as driver_id
        FROM 
            trips t
        LEFT JOIN 
            drivers d ON t.driver_id = d.id
        WHERE 
            t.trip_id = :trip_id
        """
        
        trip = db.session.execute(sql_text(query), {"trip_id": trip_id}).fetchone()
        
        if not trip:
            return f"找不到ID為 {trip_id} 的班次。"
        
        # 更新數據庫中的班次狀態為取消
        update_query = """
        UPDATE trips
        SET status = '取消'
        WHERE trip_id = :trip_id
        RETURNING trip_id
        """
        
        result = db.session.execute(sql_text(update_query), {
            "trip_id": trip_id
        })
        
        # 提交事務
        db.session.commit()
        
        # 檢查是否找到並更新了班次
        updated_trip = result.fetchone()
        if not updated_trip:
            return f"找不到ID為 {trip_id} 的班次。"
        
        # 構建取消通知
        date_str = trip[1]
        time_str = trip[2]
        
        reply_text = f"✅ 班次 #{trip_id} 已取消。\n\n日期：{date_str}\n時間：{time_str}"
        
        # 構建帶有 Quick Reply 的回覆
        reply = {
            'text': reply_text,
            'quick_reply': {
                'items': [
                    {
                        'type': 'action',
                        'action': {
                            'type': 'message',
                            'label': '查詢班次',
                            'text': '!查詢班次'
                        }
                    },
                    {
                        'type': 'action',
                        'action': {
                            'type': 'message',
                            'label': '班次詳情',
                            'text': f'!班次詳情 {trip_id}'
                        }
                    }
                ]
            }
        }
        
        return reply
        
    except Exception as e:
        # 回滾事務
        db.session.rollback()
        return f"取消班次失敗: {str(e)}"

def handle_confirm_leave_trip(message_text):
    """處理確認請假班次的請求"""
    try:
        # 解析命令格式：確認請假 [班次ID]
        parts = message_text.split()
        if len(parts) < 2:
            return "命令格式不正確。正確格式：確認請假 [班次ID]"
        
        trip_id = parts[1]
        
        # 查詢班次信息
        query = """
        SELECT 
            t.trip_id, 
            t.date, 
            t.time, 
            t.status,
            t.fixed_trip_id,
            d.id as driver_id
        FROM 
            trips t
        LEFT JOIN 
            drivers d ON t.driver_id = d.id
        WHERE 
            t.trip_id = :trip_id
        """
        
        trip = db.session.execute(sql_text(query), {"trip_id": trip_id}).fetchone()
        
        if not trip:
            return f"找不到ID為 {trip_id} 的班次。"
        
        # 檢查是否是固定班次
        fixed_trip_id = trip[4]
        if not fixed_trip_id:
            return f"班次 #{trip_id} 不是固定班次，無法設為請假狀態。"
        
        # 更新數據庫中的班次狀態為請假
        update_query = """
        UPDATE trips
        SET status = '請假'
        WHERE trip_id = :trip_id
        RETURNING trip_id
        """
        
        result = db.session.execute(sql_text(update_query), {
            "trip_id": trip_id
        })
        
        # 提交事務
        db.session.commit()
        
        # 檢查是否找到並更新了班次
        updated_trip = result.fetchone()
        if not updated_trip:
            return f"找不到ID為 {trip_id} 的班次。"
        
        # 構建請假通知
        date_str = trip[1]
        time_str = trip[2]
        
        reply_text = f"✅ 班次 #{trip_id} 已設為請假狀態。\n\n日期：{date_str}\n時間：{time_str}\n\n注意：此操作將影響後續週期的固定班次。"
        
        # 構建帶有 Quick Reply 的回覆
        reply = {
            'text': reply_text,
            'quick_reply': {
                'items': [
                    {
                        'type': 'action',
                        'action': {
                            'type': 'message',
                            'label': '查詢班次',
                            'text': '!查詢班次'
                        }
                    },
                    {
                        'type': 'action',
                        'action': {
                            'type': 'message',
                            'label': '班次詳情',
                            'text': f'!班次詳情 {trip_id}'
                        }
                    }
                ]
            }
        }
        
        return reply
        
    except Exception as e:
        # 回滾事務
        db.session.rollback()
        return f"設置請假狀態失敗: {str(e)}"

def handle_confirm_conflict_trip(message_text):
    """處理確認衝突班次的請求"""
    try:
        # 解析命令格式：確認衝突 [班次ID]
        parts = message_text.split()
        if len(parts) < 2:
            return "命令格式不正確。正確格式：確認衝突 [班次ID]"
        
        trip_id = parts[1]
        
        # 查詢班次信息
        query = """
        SELECT 
            t.trip_id, 
            t.date, 
            t.time, 
            t.status,
            t.fixed_trip_id,
            d.id as driver_id
        FROM 
            trips t
        LEFT JOIN 
            drivers d ON t.driver_id = d.id
        WHERE 
            t.trip_id = :trip_id
        """
        
        trip = db.session.execute(sql_text(query), {"trip_id": trip_id}).fetchone()
        
        if not trip:
            return f"找不到ID為 {trip_id} 的班次。"
        
        # 更新數據庫中的班次狀態為衝突
        update_query = """
        UPDATE trips
        SET status = '衝突'
        WHERE trip_id = :trip_id
        RETURNING trip_id
        """
        
        result = db.session.execute(sql_text(update_query), {
            "trip_id": trip_id
        })
        
        # 提交事務
        db.session.commit()
        
        # 檢查是否找到並更新了班次
        updated_trip = result.fetchone()
        if not updated_trip:
            return f"找不到ID為 {trip_id} 的班次。"
        
        # 構建衝突通知
        date_str = trip[1]
        time_str = trip[2]
        driver_id = trip[5] or "未指派"
        
        reply_text = f"⚠️ 班次 #{trip_id} 已設為衝突狀態。\n\n日期：{date_str}\n時間：{time_str}\n司機：{driver_id}\n\n該班次無法由原定司機完成，請診所幫忙另外叫車。"
        
        # 構建帶有 Quick Reply 的回覆
        reply = {
            'text': reply_text,
            'quick_reply': {
                'items': [
                    {
                        'type': 'action',
                        'action': {
                            'type': 'message',
                            'label': '查詢班次',
                            'text': '!查詢班次'
                        }
                    },
                    {
                        'type': 'action',
                        'action': {
                            'type': 'message',
                            'label': '班次詳情',
                            'text': f'!班次詳情 {trip_id}'
                        }
                    }
                ]
            }
        }
        
        return reply
        
    except Exception as e:
        # 回滾事務
        db.session.rollback()
        return f"設置衝突狀態失敗: {str(e)}" 