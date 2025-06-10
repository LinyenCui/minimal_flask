"""
處理班次狀態的模組
"""
from datetime import datetime, timedelta
from sqlalchemy.sql import text
import logging
from modules.models.base import db

# 建立日誌記錄器
logger = logging.getLogger(__name__)

def handle_update_trip_status(message_text):
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

        # --- 狀態有效性預先檢查 (因為時間檢查可能依賴 new_status != current_status) ---
        valid_statuses_for_manual_change = ["準備", "取消", "衝突", "請假"]
        if new_status not in valid_statuses_for_manual_change:
            return f"無效的目標狀態：{new_status}。可用選項：準備、取消、衝突、請假。"

        # --- 通用時間限制判斷 ---
        if new_status != current_status: # 只有當確實要改變狀態時，才執行嚴格的時間檢查
            if trip_date and trip_time:
                trip_datetime_naive = datetime.combine(trip_date, trip_time)
                now_naive = datetime.now()
                if trip_datetime_naive < now_naive:
                    logger.info(f"Attempt to modify past trip {trip_id} to {new_status}. Current time: {now_naive}, Trip time: {trip_datetime_naive}")
                    return f"⚠️ 無法修改已過時間的班次狀態。班次 {trip_id} 的時間 ({trip_date.strftime('%Y-%m-%d')} {trip_time.strftime('%H:%M')}) 已過。"
                if (trip_datetime_naive - now_naive) < timedelta(minutes=30):
                    logger.info(f"Attempt to modify trip {trip_id} to {new_status} within 30 minutes. Current time: {now_naive}, Trip time: {trip_datetime_naive}")
                    return f"該班次執行時間距目前時間不足30分鐘，無法將狀態從「{current_status}」修改為「{new_status}」。請聯絡管理員。"
            else: # 如果沒有日期時間，但嘗試修改狀態，則阻止
                logger.warning(f"Trip {trip_id} is missing date or time, cannot apply time-based modification lock for status change to {new_status}.")
                return f"班次 {trip_id} 缺少日期或時間資訊，無法修改狀態。"
        elif new_status == current_status:
             return f"班次 #{trip_id} 目前狀態已是「{current_status}」，無需修改。"
        
        # --- 特定狀態轉換邏輯和二次確認提示 (在時間檢查通過後執行) ---
        # (current_status 在這裡可能已被上面的查詢更新，但為了保險，可以考慮重新查詢或使用 trip_info.status)
        # current_status = trip_info.status # 確保 current_status 是最新的

        if new_status == "準備":
            if current_status == "待派" and not driver_id:
                return f"班次 #{trip_id} 必須先指派司機才能設為「準備」。"
            update_query = "UPDATE trips SET status = :new_status WHERE trip_id = :trip_id RETURNING trip_id"
            result = db.session.execute(text(update_query), {"trip_id": trip_id, "new_status": new_status})
            db.session.commit()
            if result.fetchone():
                return f"✅ 已成功將班次 #{trip_id} 的狀態從「{current_status}」更改為「準備」。"
            else:
                return f"更新班次 #{trip_id} 狀態為「準備」時出錯。"

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