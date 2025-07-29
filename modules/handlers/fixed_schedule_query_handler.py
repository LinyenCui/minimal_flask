"""
處理固定班表查詢功能的模組
根據客戶 short_name 查詢相關的固定班次，並提供操作選項
"""
from datetime import datetime
from sqlalchemy.sql import text
import logging
from modules.models.base import db
from modules.utils.line_bot import get_user_display_name

# 建立日誌記錄器
logger = logging.getLogger(__name__)

def handle_fixed_schedule_query(message_text, user_id):
    """處理固定班表查詢命令"""
    try:
        # 解析格式：固定班表 [客戶簡稱]
        # 例如：固定班表 新建路（前綴已在上級處理中去除）
        if not message_text.startswith('固定班表'):
            return None
        
        parts = message_text.split(maxsplit=1)
        
        if len(parts) < 2:
            return "請輸入客戶簡稱。格式：/固定班表 [客戶簡稱]\n例如：/固定班表 新建路"
        
        customer_name = parts[1].strip()
        if not customer_name:
            return "請提供客戶簡稱"
        
        return query_fixed_schedules_by_customer(customer_name, user_id)
        
    except Exception as e:
        logger.error(f"處理固定班表查詢命令時出錯: {e}")
        return f"處理固定班表查詢命令時出錯: {e}"

def query_fixed_schedules_by_customer(customer_name, user_id):
    """根據客戶簡稱查詢固定班次"""
    try:
        # 查詢固定班次信息（在起點、經由點或終點包含該客戶名稱）
        query = """
        SELECT 
            fs.id, 
            fs.route_number, 
            fs.departure_time, 
            fs.start_point,
            fs.via_point,
            fs.end_point,
            fs.base_fare,
            fs.surcharge,
            fs.total_fare,
            fs.category,
            fs.driver_id,
            fs.direction,
            fs.status,
            fs.note,
            fs.modified_by,
            fs.modification_time
        FROM 
            fixed_schedules fs
        WHERE 
            fs.start_point = :customer_name 
            OR fs.via_point = :customer_name 
            OR fs.end_point = :customer_name
        ORDER BY fs.departure_time
        """
        
        schedules = db.session.execute(text(query), {"customer_name": customer_name}).fetchall()
        
        if not schedules:
            return f"找不到與「{customer_name}」相關的固定班次。\n請確認客戶簡稱是否正確。"
        
        # 構建查詢結果訊息
        result_message = f"🔍 找到 {len(schedules)} 個與「{customer_name}」相關的固定班次：\n\n"
        
        quick_reply_options = []
        
        for schedule in schedules:
            schedule_id = schedule[0]
            route_number = schedule[1] or '未設定'
            departure_time = schedule[2]
            start_point = schedule[3]
            via_point = schedule[4]
            end_point = schedule[5]
            base_fare = schedule[6] or 0
            surcharge = schedule[7] or 0
            total_fare = schedule[8] or 0
            category = schedule[9] or '未分類'
            driver_id = schedule[10] or '未指派'
            direction = schedule[11] or '未設定'
            status = schedule[12] or '準備'
            note = schedule[13]
            modified_by = schedule[14]
            modification_time = schedule[15]
            
            # 建立路線描述
            route_desc = start_point
            if via_point:
                route_desc += f" → {via_point}"
            route_desc += f" → {end_point}"
            
            # 狀態圖示
            status_icon = "🔵" if status == "請假" else "🟢"
            
            result_message += f"📋 **班次 #{schedule_id}**\n"
            result_message += f"🚌 路線：{route_number} ({direction})\n"
            result_message += f"🕐 時間：{departure_time}\n"
            result_message += f"📍 路線：{route_desc}\n"
            result_message += f"💰 車資：{base_fare}"
            if surcharge != 0:
                result_message += f" + {surcharge}"
            result_message += f" = {total_fare}\n"
            result_message += f"📊 類別：{category}\n"
            result_message += f"{status_icon} 狀態：{status}"
            if note:
                result_message += f" ({note})"
            result_message += f"\n"
            result_message += f"🚗 司機：{driver_id}\n"
            
            # 如果有修改記錄，顯示修改者名稱和時間
            if modified_by and modification_time:
                user_name = get_user_display_name(modified_by)
                result_message += f"👤 修改者：{user_name}\n"
                result_message += f"🕐 修改時間：{modification_time.strftime('%Y-%m-%d %H:%M')}\n"
            
            result_message += "\n"
            
            # 為每個班次創建操作選項
            if status == '準備':
                quick_reply_options.append({
                    "type": "action",
                    "action": {
                        "type": "message",
                        "label": f"設定班次#{schedule_id}請假",
                        "text": f"固定班次#{schedule_id}請假"
                    }
                })
            elif status == '請假':
                quick_reply_options.append({
                    "type": "action", 
                    "action": {
                        "type": "message",
                        "label": f"恢復班次#{schedule_id}",
                        "text": f"固定班次恢復 {schedule_id}"
                    }
                })
        
        # 添加放棄選項
        quick_reply_options.append({
            "type": "action",
            "action": {
                "type": "message", 
                "label": "放棄",
                "text": "放棄操作"
            }
        })
        
        # 如果只有一個班次，提供更清楚的操作說明
        if len(schedules) == 1:
            schedule = schedules[0]
            status = schedule[12] or '準備'
            
            if status == '準備':
                result_message += f"💡 點擊下方按鈕後，輸入：【原因】【加成】\n\n"
                result_message += f"📋 範例：\n"
                result_message += f"長期住院 -50\n"
                result_message += f"出國一個月 0"
            else:
                result_message += f"💡 如需恢復班次，請點擊下方按鈕"
        else:
            # 多個班次的情況
            result_message += f"💡 點擊按鈕後輸入：【原因】【加成】"
        
        return {
            "type": "quick_reply",
            "text": result_message,
            "quick_reply": {
                "items": quick_reply_options[:13]  # LINE 限制最多13個選項
            }
        }
        
    except Exception as e:
        logger.error(f"查詢固定班次時出錯: {e}")
        return f"查詢固定班次時出錯: {e}"

def is_fixed_schedule_query(message_text):
    """檢查是否為固定班表查詢命令"""
    return message_text.strip().startswith('固定班表') 