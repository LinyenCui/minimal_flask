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
        
        trip = db.session.execute(text(query), {"trip_id": trip_id}).fetchone()
        
        if not trip:
            return f"找不到ID為 {trip_id} 的班次。"
        
        current_status = trip[3]
        fixed_trip_id = trip[4]
        driver_id = trip[5]
        trip_date = trip[1]
        trip_time = trip[2]
        
        # 檢查時間限制（取消和請假需要在距離執行時間一個小時以上）
        if new_status in ["取消", "請假"]:
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
        
        result = db.session.execute(text(update_query), {
            "trip_id": trip_id,
            "new_status": new_status
        })
        
        # 提交事務
        db.session.commit()
        
        # 檢查是否找到並更新了班次
        updated_trip = result.fetchone()
        if not updated_trip:
            return f"更新班次 #{trip_id} 的狀態時出錯。"
        
        return f"已成功將班次 #{trip_id} 的狀態從「{current_status}」更改為「{new_status}」。"
    
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