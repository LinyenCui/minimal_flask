"""
處理乘客請假功能的模組
"""
from datetime import datetime
from sqlalchemy.sql import text
import logging
from modules.models.base import db
from modules.utils.line_bot import get_user_display_name

# 建立日誌記錄器
logger = logging.getLogger(__name__)

def handle_passenger_leave_command(message_text, user_id):
    """處理乘客請假命令"""
    try:
        # 解析格式：乘客請假 [班次ID] [加成] [原因]
        # 例如：乘客請假 139 -30 新建路乘客臨時有事
        parts = message_text.split(maxsplit=3)  # 分割成4部分：命令 班次ID 加成 原因
        
        if len(parts) < 4:
            return "格式不正確。請輸入：乘客請假 [班次ID] [加成] [原因]\n例如：乘客請假 139 -30 新建路乘客臨時有事"
        
        try:
            trip_id = int(parts[1])
        except ValueError:
            return f"班次ID格式錯誤，請輸入數字，您輸入的是：{parts[1]}"
        
        try:
            surcharge_adjustment = int(parts[2])
        except ValueError:
            return f"加成格式錯誤，請輸入數字，您輸入的是：{parts[2]}"
        
        reason = parts[3].strip()
        if not reason:
            return "請提供請假原因說明"
        
        return process_passenger_leave(trip_id, surcharge_adjustment, reason, user_id)
        
    except Exception as e:
        logger.error(f"處理乘客請假命令時出錯: {e}")
        return f"處理請假命令時出錯: {e}"

def process_passenger_leave(trip_id, surcharge_adjustment, reason, user_id):
    """執行乘客請假處理"""
    try:
        # 查詢班次信息
        query = """
        SELECT 
            t.trip_id, 
            t.date, 
            t.time, 
            t.status,
            t.extra_fare,
            t.meter_fare,
            t.start_point as start_name,
            t.end_point as end_name
        FROM 
            trips t
        WHERE 
            t.trip_id = :trip_id
        """
        
        trip = db.session.execute(text(query), {"trip_id": trip_id}).fetchone()
        
        if not trip:
            return f"找不到ID為 {trip_id} 的班次。"
        
        # 直接設定加成值，不累加（避免重複請假時累計）
        new_extra_fare = surcharge_adjustment
        
        # 更新班次信息（保持狀態為準備，使用專門的請假欄位）
        try:
            # 先嘗試使用新的passenger_leave_reason欄位
            update_query = """
            UPDATE trips
            SET extra_fare = :new_extra_fare, 
                passenger_leave_reason = :leave_reason,
                modified_by = :user_id, 
                modification_time = :mod_time
            WHERE trip_id = :trip_id
            RETURNING trip_id
            """
            
            # 獲取用戶顯示名稱
            user_display_name = get_user_display_name(user_id) if user_id else "系統用戶"
            
            result = db.session.execute(text(update_query), {
                "trip_id": trip_id,
                "new_extra_fare": new_extra_fare,
                "leave_reason": reason,
                "user_id": user_display_name,
                "mod_time": datetime.now()
            })
        except Exception as new_field_error:
            logger.info(f"passenger_leave_reason欄位不存在，使用舊欄位: {new_field_error}")
            # 回退到舊的modification_reason欄位
            update_query = """
            UPDATE trips
            SET extra_fare = :new_extra_fare, 
                modified_by = :user_id, 
                modification_reason = :reason, 
                modification_time = :mod_time
            WHERE trip_id = :trip_id
            RETURNING trip_id
            """
            
            # 獲取用戶顯示名稱
            user_display_name = get_user_display_name(user_id) if user_id else "系統用戶"
            
            result = db.session.execute(text(update_query), {
                "trip_id": trip_id,
                "new_extra_fare": new_extra_fare,
                "user_id": user_display_name,
                "reason": f"乘客請假: {reason}",
                "mod_time": datetime.now()
            })
        
        # 提交事務
        db.session.commit()
        
        # 檢查更新結果
        updated_trip = result.fetchone()
        if not updated_trip:
            return f"更新班次 #{trip_id} 資訊時出錯。"
        
        # 構建成功訊息
        adjustment_text = f"+{surcharge_adjustment}" if surcharge_adjustment >= 0 else str(surcharge_adjustment)
        success_message = f"✅ 班次 #{trip_id} 乘客請假處理完成\n\n"
        success_message += f"📝 請假原因：{reason}\n"
        success_message += f"💰 加成調整：{adjustment_text} 元\n"
        success_message += f"💰 調整後加成：{new_extra_fare} 元\n"
        success_message += f"📍 路線：{trip[6]} → {trip[7]}\n"
        success_message += f"📅 日期：{trip[1]}\n"
        success_message += f"🕐 時間：{trip[2]}"
        
        return success_message
        
    except Exception as e:
        logger.error(f"處理乘客請假時出錯: {e}")
        db.session.rollback()
        return f"處理乘客請假時出錯: {e}"

def get_display_status(trip):
    """獲取班次的顯示狀態（檢查是否為乘客請假）"""
    # 優先檢查新的passenger_leave_reason欄位
    if hasattr(trip, 'passenger_leave_reason') and trip.passenger_leave_reason:
        return f"請假 ({trip.passenger_leave_reason})"
    
    # 回退檢查舊的modification_reason欄位
    if (hasattr(trip, 'modification_reason') and trip.modification_reason and 
        ("乘客請假" in trip.modification_reason or "請假" in trip.modification_reason)):
        # 提取請假原因（去掉"乘客請假: "前綴）
        reason = trip.modification_reason
        if reason.startswith("乘客請假: "):
            reason = reason[5:]  # 移除"乘客請假: "前綴
        return f"請假 ({reason})"
    
    return trip.status 