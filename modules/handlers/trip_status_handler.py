"""
處理班次狀態的模組
"""
from datetime import datetime, timedelta
from sqlalchemy.sql import text
import logging
import re
from modules.models.base import db

# 建立日誌記錄器
logger = logging.getLogger(__name__)

def remove_leave_from_modification_reason(modification_reason):
    """
    從 modification_reason 中移除請假相關的記錄，保留其他修改記錄
    """
    if not modification_reason:
        return None
    
    # 按分號分割各個修改記錄
    parts = [part.strip() for part in modification_reason.split(';')]
    
    # 過濾掉請假相關的記錄
    filtered_parts = []
    for part in parts:
        # 檢查是否為請假相關記錄
        if not ("乘客請假" in part or "請假" in part.lower()):
            filtered_parts.append(part)
    
    # 重新組合
    if not filtered_parts:
        return None
    
    return '; '.join(filtered_parts)

def handle_update_trip_status(message_text, user_id=None):
    """處理修改班次狀態的請求"""
    try:
        parts = message_text.split()
        if len(parts) < 3:
            return "命令格式不正確。正確格式：修改狀態 [班次ID] [新狀態]\n\n可用狀態：準備、取消、衝突、請假"
        
        trip_id = parts[1]
        new_status = parts[2]
        
        query_trip_info = """SELECT date, time, status, fixed_trip_id, driver_id FROM trips WHERE trip_id = :trip_id"""
        trip_info = db.session.execute(text(query_trip_info), {"trip_id": trip_id}).fetchone()

        if not trip_info:
            return f"找不到ID為 {trip_id} 的班次。"

        trip_date, trip_time, current_status, fixed_trip_id, driver_id = trip_info.date, trip_info.time, trip_info.status, trip_info.fixed_trip_id, trip_info.driver_id

        # --- 狀態有效性預先檢查 ---
        valid_statuses_for_manual_change = ["準備", "取消", "衝突", "請假"]
        if new_status not in valid_statuses_for_manual_change:
            return f"無效的目標狀態：{new_status}。可用選項：準備、取消、衝突、請假。"

        # --- 通用時間限制判斷 ---
        # 對於非「準備」狀態且要改變狀態時，執行時間檢查
        if new_status != current_status and new_status != "準備":
            if trip_date and trip_time:
                trip_datetime_naive = datetime.combine(trip_date, trip_time)
                now_naive = datetime.now()
                if trip_datetime_naive < now_naive:
                    logger.info(f"Attempt to modify past trip {trip_id} to {new_status}. Current time: {now_naive}, Trip time: {trip_datetime_naive}")
                    return f"⚠️ 無法修改已過時間的班次狀態。班次 {trip_id} 的時間 ({trip_date.strftime('%Y-%m-%d')} {trip_time.strftime('%H:%M')}) 已過。"
                if (trip_datetime_naive - now_naive) < timedelta(minutes=30):
                    logger.info(f"Attempt to modify trip {trip_id} to {new_status} within 30 minutes. Current time: {now_naive}, Trip time: {trip_datetime_naive}")
                    return f"該班次執行時間距目前時間不足30分鐘，無法將狀態從「{current_status}」修改為「{new_status}」。請聯絡管理員。"
            else:
                logger.warning(f"Trip {trip_id} is missing date or time, cannot apply time-based modification lock for status change to {new_status}.")
                return f"班次 {trip_id} 缺少日期或時間資訊，無法修改狀態。"
        
        # --- 特定狀態轉換邏輯 ---
        if new_status == "準備":
            if current_status == "待派" and not driver_id:
                return f"班次 #{trip_id} 必須先指派司機才能設為「準備」。"
            
            # 🔧 修正：檢查是否為請假狀態（需要清除請假原因）或有負數加成
            check_leave_query = """
            SELECT passenger_leave_reason, modification_reason, extra_fare 
            FROM trips 
            WHERE trip_id = :trip_id
            """
            leave_info = db.session.execute(text(check_leave_query), {"trip_id": trip_id}).fetchone()
            
            has_leave_reason = (leave_info and leave_info[0]) or (leave_info and leave_info[1] and "乘客請假" in leave_info[1])
            original_extra_fare = leave_info[2] if leave_info and leave_info[2] is not None else 0
            original_modification_reason = leave_info[1] if leave_info else None
            
            if has_leave_reason or original_extra_fare < 0:
                # 這是「改回準備」- 清除請假原因和負數加成，但保留其他修改記錄
                cleaned_modification_reason = remove_leave_from_modification_reason(original_modification_reason)
                
                update_query = """
                UPDATE trips 
                SET passenger_leave_reason = NULL,
                    modification_reason = :cleaned_reason,
                    extra_fare = CASE
                        WHEN extra_fare < 0 THEN 0
                        ELSE extra_fare
                    END
                WHERE trip_id = :trip_id 
                RETURNING trip_id, extra_fare
                """
                result = db.session.execute(text(update_query), {
                    "trip_id": trip_id,
                    "cleaned_reason": cleaned_modification_reason
                })
                db.session.commit()
                
                updated_trip = result.fetchone()
                if updated_trip:
                    success_msg = f"✅ 已成功清除班次 #{trip_id} 的請假狀態，恢復為準備狀態。"
                    if original_extra_fare < 0:
                        success_msg += f"\n💰 加成恢復：{original_extra_fare} → {updated_trip[1]} (變動+{-original_extra_fare})"
                    if cleaned_modification_reason:
                        success_msg += f"\n📝 保留其他修改記錄：{cleaned_modification_reason}"
                    return success_msg
                else:
                    return f"清除班次 #{trip_id} 請假狀態時出錯。"
            elif current_status != new_status:
                # 這是一般的狀態修改
                update_query = "UPDATE trips SET status = :new_status WHERE trip_id = :trip_id RETURNING trip_id"
                result = db.session.execute(text(update_query), {"trip_id": trip_id, "new_status": new_status})
                db.session.commit()
                if result.fetchone():
                    return f"✅ 已成功將班次 #{trip_id} 的狀態從「{current_status}」更改為「準備」。"
                else:
                    return f"更新班次 #{trip_id} 狀態為「準備」時出錯。"
            else:
                # 狀態相同且沒有請假原因，無需修改
                return f"班次 #{trip_id} 目前狀態已是「{current_status}」，無需修改。"

        if new_status == "取消":
            # 直接執行取消操作
            update_query = "UPDATE trips SET status = :new_status WHERE trip_id = :trip_id RETURNING trip_id"
            result = db.session.execute(text(update_query), {"trip_id": trip_id, "new_status": new_status})
            db.session.commit()
            if result.fetchone():
                return f"✅ 已成功將班次 #{trip_id} 的狀態從「{current_status}」更改為「取消」。"
            else:
                return f"取消班次 #{trip_id} 時出錯。"

        if new_status == "衝突":
            # 直接執行衝突操作
            update_query = "UPDATE trips SET status = :new_status WHERE trip_id = :trip_id RETURNING trip_id"
            result = db.session.execute(text(update_query), {"trip_id": trip_id, "new_status": new_status})
            db.session.commit()
            if result.fetchone():
                return f"⚠️ 已成功將班次 #{trip_id} 的狀態從「{current_status}」更改為「衝突」。\n(司機無法執行，請客戶另行安排)"
            else:
                return f"將班次 #{trip_id} 設為衝突狀態時出錯。"

        if new_status == "請假":
            # 🔧 修正：設置請假模式標記，允許簡單請假格式
            if user_id:
                try:
                    from modules.utils.conversation_context import conversation_manager
                    conversation_manager.set_leave_mode(user_id=user_id, trip_id=int(trip_id))
                    logger.info(f"設置用戶 {user_id} 進入請假模式，班次 #{trip_id}")
                except Exception as context_error:
                    logger.error(f"設置請假模式時出錯: {context_error}")
            else:
                logger.warning(f"無法設置請假模式：未提供 user_id")
            
            return f"班次 #{trip_id} 乘客請假\n\n請輸入：[原因] [加成]\n\n例如：\n新建路乘客臨時有事 -30\n中華南路乘客身體不適 -50\n\n💡 提示：先寫原因，最後寫加成金額"

        logger.error(f"Reached unexpected end of handle_update_trip_status logic for trip {trip_id} to {new_status}.")
        return f"試圖將班次 #{trip_id} 狀態改為 '{new_status}'，但此操作未被明確處理。"

    except Exception as e:
        logger.error(f"處理修改班次狀態時出錯: {e}")
        db.session.rollback()
        return f"處理修改班次狀態時出錯: {e}"

def handle_confirm_cancel_trip(message_text):
    """處理確認取消班次的請求"""
    try:
        # 解析命令格式：確認取消 [班次ID]
        parts = message_text.split()
        if len(parts) < 2:
            return "命令格式不正確。正確格式：確認取消 [班次ID]"
        
        trip_id = parts[1]
        
        # 查詢當前班次信息
        query = """
        SELECT 
            t.trip_id, 
            t.date, 
            t.time, 
            t.status,
            t.fixed_trip_id
        FROM 
            trips t
        WHERE 
            t.trip_id = :trip_id
        """
        
        trip = db.session.execute(text(query), {"trip_id": trip_id}).fetchone()
        
        if not trip:
            return f"找不到ID為 {trip_id} 的班次。"
        
        current_status = trip[3]
        fixed_trip_id = trip[4]
        
        # 更新數據庫中的班次狀態
        update_query = """
        UPDATE trips
        SET status = '取消'
        WHERE trip_id = :trip_id
        RETURNING trip_id
        """
        
        result = db.session.execute(text(update_query), {"trip_id": trip_id})
        
        # 提交事務
        db.session.commit()
        
        # 檢查是否找到並更新了班次
        updated_trip = result.fetchone()
        if not updated_trip:
            return f"取消班次 #{trip_id} 時出錯。"
        
        # 如果是固定班次，詢問是否也要修改後續週期的固定班次
        if fixed_trip_id:
            return f"已成功將班次 #{trip_id} 的狀態從「{current_status}」更改為「取消」。\n\n要將後續週期的此固定班次也設為請假狀態嗎？\n如果是，請回覆「固定請假 {fixed_trip_id}」，否則無需回覆。"
        else:
            return f"已成功將班次 #{trip_id} 的狀態從「{current_status}」更改為「取消」。"
    
    except Exception as e:
        logger.error(f"處理確認取消班次時出錯: {e}")
        db.session.rollback()
        return f"處理確認取消班次時出錯: {e}"

def handle_confirm_leave_trip(message_text):
    """處理確認請假班次的請求"""
    try:
        # 解析命令格式：確認請假 [班次ID]
        parts = message_text.split()
        if len(parts) < 2:
            return "命令格式不正確。正確格式：確認請假 [班次ID]"
        
        trip_id = parts[1]
        
        # 查詢當前班次信息
        query = """
        SELECT 
            t.trip_id, 
            t.date, 
            t.time, 
            t.status,
            t.fixed_trip_id
        FROM 
            trips t
        WHERE 
            t.trip_id = :trip_id
        """
        
        trip = db.session.execute(text(query), {"trip_id": trip_id}).fetchone()
        
        if not trip:
            return f"找不到ID為 {trip_id} 的班次。"
        
        current_status = trip[3]
        fixed_trip_id = trip[4]
        
        # 檢查是否是固定班次
        if not fixed_trip_id:
            return f"班次 #{trip_id} 不是固定班次，無法設為請假狀態。如要取消，請使用「確認取消 {trip_id}」命令。"
        
        # 更新數據庫中的班次狀態
        update_query = """
        UPDATE trips
        SET status = '請假'
        WHERE trip_id = :trip_id
        RETURNING trip_id
        """
        
        result = db.session.execute(text(update_query), {"trip_id": trip_id})
        
        # 提交事務
        db.session.commit()
        
        # 檢查是否找到並更新了班次
        updated_trip = result.fetchone()
        if not updated_trip:
            return f"將班次 #{trip_id} 設為請假狀態時出錯。"
        
        # 詢問是否也要修改後續週期的固定班次
        return f"已成功將班次 #{trip_id} 的狀態從「{current_status}」更改為「請假」。\n\n要將後續週期的此固定班次也設為請假狀態嗎？\n如果是，請回覆「固定請假 {fixed_trip_id}」，否則無需回覆。"
    
    except Exception as e:
        logger.error(f"處理確認請假班次時出錯: {e}")
        db.session.rollback()
        return f"處理確認請假班次時出錯: {e}"

def handle_confirm_conflict_trip(message_text):
    """處理確認衝突班次的請求"""
    try:
        # 解析命令格式：確認衝突 [班次ID]
        parts = message_text.split()
        if len(parts) < 2:
            return "命令格式不正確。正確格式：確認衝突 [班次ID]"
        
        trip_id = parts[1]
        
        # 查詢當前班次信息
        query = """
        SELECT 
            t.trip_id, 
            t.date, 
            t.time, 
            t.status,
            d.name as driver_name
        FROM 
            trips t
        LEFT JOIN 
            drivers d ON t.driver_id = d.id
        WHERE 
            t.trip_id = :trip_id
        """
        
        trip = db.session.execute(text(query), {"trip_id": trip_id}).fetchone()
        
        if not trip:
            return f"找不到ID為 {trip_id} 的班次。"
        
        current_status = trip[3]
        driver_name = trip[4] if trip[4] else "未指派司機"
        
        # 更新數據庫中的班次狀態
        update_query = """
        UPDATE trips
        SET status = '衝突'
        WHERE trip_id = :trip_id
        RETURNING trip_id
        """
        
        result = db.session.execute(text(update_query), {"trip_id": trip_id})
        
        # 提交事務
        db.session.commit()
        
        # 檢查是否找到並更新了班次
        updated_trip = result.fetchone()
        if not updated_trip:
            return f"將班次 #{trip_id} 設為衝突狀態時出錯。"
        
        return f"已成功將班次 #{trip_id} 的狀態從「{current_status}」更改為「衝突」。\n\n此班次的司機 ({driver_name}) 將無法執行，請客戶自行安排其他交通方式。"
    
    except Exception as e:
        logger.error(f"處理確認衝突班次時出錯: {e}")
        db.session.rollback()
        return f"處理確認衝突班次時出錯: {e}" 