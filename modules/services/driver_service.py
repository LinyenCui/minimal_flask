"""
處理司機指派相關的服務函數
"""
from datetime import datetime
from sqlalchemy import text as sql_text
import logging
import traceback

from modules.models.base import db
from modules.models.trip import Trip
from modules.models.driver import Driver
from modules.flex_designs.driver_assign_flex import get_driver_assign_flex, get_driver_assign_confirm_flex
from modules.utils.line_bot import create_text_message, QuickReply, QuickReplyItem, MessageAction
from linebot.v3.messaging import TextMessage # 確保導入

# 設置日誌
logger = logging.getLogger(__name__)

def handle_driver_assign_request(trip_id):
    """處理指派司機請求，返回帶 Quick Reply 的文本消息"""
    try:
        # 檢查班次是否存在
        query = """
        SELECT 
            t.trip_id, 
            t.date, 
            t.time, 
            t.start_point, 
            t.end_point, 
            t.status,
            t.driver_id
        FROM 
            trips t
        WHERE 
            t.trip_id = :trip_id
        """
        
        trip = db.session.execute(sql_text(query), {"trip_id": trip_id}).fetchone()
        
        if not trip:
            return None, f"找不到ID為 {trip_id} 的班次"
        
        # 檢查班次狀態
        if trip[5] == "取消":
            return None, f"班次 {trip_id} 已取消，無法指派司機"
        
        if trip[5] == "已完成":
            return None, f"班次 {trip_id} 已完成，無法修改司機指派"
        
        # 檢查是否已有司機
        if trip[6]:
            # 查詢現有司機信息
            driver_query = """
            SELECT id, name, plate_number
            FROM drivers
            WHERE id = :driver_id
            """
            
            driver = db.session.execute(sql_text(driver_query), {"driver_id": trip[6]}).fetchone()
            
            if driver:
                driver_name = driver[1]
                return None, f"班次 {trip_id} 已經指派給司機 {driver_name}，如需更改請先取消原指派"
            else:
                return None, f"班次 {trip_id} 已有司機指派(ID: {trip[6]})，但找不到該司機信息"
        
        # 查詢所有可用司機 (假設有一個 is_available 標誌或直接查詢所有)
        drivers_query = """
        SELECT id FROM drivers ORDER BY id
        """
        drivers = db.session.execute(sql_text(drivers_query)).fetchall()
        
        if not drivers:
            return None, "目前沒有可用的司機"
            
        # 創建 Quick Reply 按鈕
        quick_reply_items = []
        for driver in drivers:
            driver_id = driver[0]
            quick_reply_items.append(
                QuickReplyItem(
                    action=MessageAction(
                        label=str(driver_id), # 按鈕顯示司機ID
                        text=f"指派司機 {trip_id} {driver_id}" # 點擊後發送的文本
                    )
                )
            )
            
        # 添加取消選項
        quick_reply_items.append(
            QuickReplyItem(
                action=MessageAction(
                    label="取消",
                    text="取消"
                )
            )
        )
        
        # 創建 QuickReply 對象
        quick_reply = QuickReply(items=quick_reply_items)
        
        # 準備要發送的文本消息
        date_str = trip[1].strftime("%Y-%m-%d") if trip[1] else "--"
        time_str = trip[2].strftime("%H:%M") if trip[2] else "--"
        reply_text_content = f"請為班次 #{trip_id} ({date_str} {time_str}) 選擇要指派的司機ID："
        
        # --- 修改：直接創建 TextMessage 對象 --- 
        message_to_send = TextMessage(
            text=reply_text_content,
            quick_reply=quick_reply # 直接傳遞 QuickReply 對象
        )

        # 返回 TextMessage 對象和 None
        return message_to_send, None
        
    except Exception as e:
        logger.error(f"處理指派司機請求時出錯: {e}")
        traceback.print_exc()
        # 返回 None 和錯誤消息
        return None, f"處理指派司機請求時出錯: {str(e)}"

def handle_driver_assign_select(trip_id, driver_id):
    """處理選擇司機的請求，返回確認界面"""
    try:
        # 檢查班次是否存在 (查詢更多字段)
        trip_query = """
        SELECT 
            t.trip_id, t.date, t.time, 
            t.start_point, t.end_point, t.status,
            t.trip_type, t.custom_start_point, t.custom_end_point
        FROM 
            trips t
        WHERE 
            t.trip_id = :trip_id
        """
        
        trip = db.session.execute(sql_text(trip_query), {"trip_id": trip_id}).fetchone()
        
        if not trip:
            return None, f"找不到ID為 {trip_id} 的班次"
        
        # 檢查司機是否存在
        driver_query = """
        SELECT id, name, plate_number
        FROM drivers
        WHERE id = :driver_id
        """
        
        driver = db.session.execute(sql_text(driver_query), {"driver_id": driver_id}).fetchone()
        
        if not driver:
            return None, f"找不到ID為 {driver_id} 的司機"
        
        # 準備司機信息
        driver_info = {
            "id": driver[0],
            "name": driver[1],
            "plate_number": driver[2] or ""
        }
        
        # 準備班次信息 (包含新字段)
        date_str = trip[1].strftime("%Y-%m-%d") if trip[1] else "未設置"
        time_str = trip[2].strftime("%H:%M") if trip[2] else "未設置"
        trip_type = trip[6] # 假設 trip_type 在索引 6
        
        trip_info = {
            "date": date_str,
            "time": time_str,
            "start_point": trip[3] or "未設置", # 標準起點
            "end_point": trip[4] or "未設置",   # 標準終點
            "status": trip[5] or "未設置",
            "trip_type": trip_type,
            "custom_start_point": trip[7], # 假設 custom_start 在索引 7
            "custom_end_point": trip[8]    # 假設 custom_end 在索引 8
        }
        
        # 生成確認界面 (現在傳遞了更多信息)
        flex_content = get_driver_assign_confirm_flex(trip_id, driver_id, driver_info, trip_info)
        
        return flex_content, None
        
    except Exception as e:
        logger.error(f"處理選擇司機請求時出錯: {e}")
        traceback.print_exc()
        return None, f"處理選擇司機請求時出錯: {str(e)}"

def handle_driver_assign_confirm(trip_id, driver_id):
    """處理司機指派確認，更新數據庫"""
    try:
        # 檢查班次是否存在
        trip = db.session.query(Trip).filter(Trip.trip_id == trip_id).first()
        
        if not trip:
            return f"找不到ID為 {trip_id} 的班次"
        
        # 檢查司機是否存在
        driver = db.session.query(Driver).filter(Driver.id == driver_id).first()
        
        if not driver:
            return f"找不到ID為 {driver_id} 的司機"
        
        # 更新司機指派
        trip.driver_id = driver_id
        
        # 如果班次狀態是"待派"，則更新為"準備"
        if trip.status == "待派":
            trip.status = "準備"
        
        # 提交更改
        db.session.commit()
        
        # 返回成功消息
        return f"✅ 已成功將班次 {trip_id} 指派給司機 {driver.name}。"
        
    except Exception as e:
        # 回滾事務
        db.session.rollback()
        logger.error(f"確認指派司機時出錯: {e}")
        traceback.print_exc()
        return f"確認指派司機時出錯: {str(e)}"

def handle_driver_assign_cancel(trip_id):
    """處理取消司機指派"""
    try:
        # 檢查班次是否存在
        trip = db.session.query(Trip).filter(Trip.trip_id == trip_id).first()
        
        if not trip:
            return f"找不到ID為 {trip_id} 的班次"
        
        # 檢查是否有司機指派
        if not trip.driver_id:
            return f"班次 {trip_id} 目前尚未指派司機"
        
        # 記錄當前司機信息
        old_driver_id = trip.driver_id
        driver = db.session.query(Driver).filter(Driver.id == old_driver_id).first()
        driver_name = driver.name if driver else f"ID: {old_driver_id}"
        
        # 取消司機指派
        trip.driver_id = None
        
        # 如果班次狀態是"準備"，更新為"待派"
        if trip.status == "準備":
            trip.status = "待派"
        
        # 提交更改
        db.session.commit()
        
        # 返回成功消息
        return f"✅ 已取消班次 {trip_id} 的司機指派 ({driver_name})。"
        
    except Exception as e:
        # 回滾事務
        db.session.rollback()
        logger.error(f"取消指派司機時出錯: {e}")
        traceback.print_exc()
        return f"取消指派司機時出錯: {str(e)}" 