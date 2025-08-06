"""
處理班次查詢的模塊
"""
import logging
from datetime import datetime, timedelta
from sqlalchemy.sql import text
import re
from flask import current_app

from modules.models.base import db
from modules.utils.line_bot import create_flex_message, create_text_message
from linebot.v3.messaging import (
    QuickReply,
    QuickReplyItem,
    PostbackAction,
    TextMessage
)
from modules.utils.quick_reply_manager import QuickReplyManager
from modules.services.trip_service import get_trips_by_date, get_trip_details
from modules.views.trip_view import format_trips_flex
from linebot.models import TextSendMessage
from modules.utils.helpers import get_taiwan_time, get_taiwan_date
from modules.utils.unified_date_parser import parse_date_input

# 建立日誌記錄器
logger = logging.getLogger(__name__)

def handle_query_today_trips():
    """
    查詢當天的所有班次
    
    Returns:
        str: 查詢結果的文本
    """
    try:
        logger.info("查詢當天所有班次")
        
        # 獲取當前日期
        today = datetime.now().date()
        
        # 查詢今天的所有班次 - 移除對persons表的依賴
        query = """
        SELECT 
            t.trip_id, 
            t.time,
            CONCAT(c_start.name, ' → ', COALESCE(CONCAT(c_via.name, ' → '), ''), c_end.name) AS location,
            t.status,
            CASE WHEN t.fixed_trip_id IS NOT NULL THEN 1 ELSE 0 END AS is_fixed,
            t.driver_id AS person_id
        FROM 
            trips t
            LEFT JOIN customers c_start ON t.start_point = c_start.short_name
            LEFT JOIN customers c_via ON t.via_point = c_via.short_name
            LEFT JOIN customers c_end ON t.end_point = c_end.short_name
        WHERE 
            t.date = :today
        ORDER BY 
            t.time
        """
        
        result = db.session.execute(
            text(query), 
            {
                "today": today
            }
        ).fetchall()
        
        # 格式化結果
        if not result:
            return f"今天({today})沒有任何班次"
        
        day_name = ["一", "二", "三", "四", "五", "六", "日"][today.weekday()]
        response = f"今天({today} 星期{day_name})的班次:\n\n"
        
        for row in result:
            trip_id, trip_time, location, status, is_fixed, person_id = row
            
            # 格式化時間
            time_str = trip_time.strftime("%H:%M")
            
            # 添加班次信息
            response += f"#{trip_id} {time_str} {location} - {status}"
            if is_fixed:
                response += " [固定]"
            if person_id:
                response += f" (司機ID: {person_id})"
            response += "\n"
        
        return response
    
    except Exception as e:
        logger.error(f"查詢當天班次時出錯: {e}")
        return f"查詢班次錯誤: {str(e)}"

def handle_query_fixed_trips(message_text=None):
    """
    處理查詢固定班次的文本命令
    
    Args:
        message_text: 查詢命令，格式為"查詢固定班次 [日期]"
    
    Returns:
        str: 查詢結果的文本
    """
    try:
        logger.info(f"處理查詢固定班次: {message_text}")
        
        # 解析查詢參數
        date_param = None
        if message_text and len(message_text) > 6:
            params = message_text[6:].strip()
            if params:
                date_param = params
        
        # 決定查詢日期
        query_date = None
        if not date_param or date_param == "今天":
            query_date = datetime.now().date()
            display_date = "今天"
        elif date_param == "明天":
            query_date = (datetime.now() + timedelta(days=1)).date()
            display_date = "明天"
        elif date_param == "後天":
            query_date = (datetime.now() + timedelta(days=2)).date()
            display_date = "後天"
        elif date_param == "本週":
            # 獲取本週的日期範圍
            today = datetime.now().date()
            days_since_monday = today.weekday()
            monday = today - timedelta(days=days_since_monday)
            sunday = monday + timedelta(days=6)
            
            # 查詢本週的班次 - 移除對persons表的依賴
            query = """
            SELECT 
                t.trip_id, 
                t.date, 
                t.time,
                CONCAT(c_start.name, ' → ', COALESCE(CONCAT(c_via.name, ' → '), ''), c_end.name) AS location,
                t.status,
                t.driver_id AS person_id
            FROM 
                trips t
                LEFT JOIN customers c_start ON t.start_point = c_start.short_name
                LEFT JOIN customers c_via ON t.via_point = c_via.short_name
                LEFT JOIN customers c_end ON t.end_point = c_end.short_name
            WHERE 
                t.date BETWEEN :start_date AND :end_date
                AND t.fixed_trip_id IS NOT NULL
            ORDER BY 
                t.date, t.time
            """
            
            result = db.session.execute(
                text(query), 
                {
                    "start_date": monday,
                    "end_date": sunday
                }
            ).fetchall()
            
            # 格式化結果
            if not result:
                return f"本週({monday}至{sunday})沒有固定班次"
            
            response = f"本週({monday}至{sunday})固定班次:\n\n"
            
            # 按日期分組顯示
            current_date = None
            for row in result:
                trip_id, trip_date, trip_time, location, status, person_id = row
                
                if current_date != trip_date:
                    current_date = trip_date
                    day_name = ["一", "二", "三", "四", "五", "六", "日"][trip_date.weekday()]
                    response += f"【{trip_date} (星期{day_name})】\n"
                
                # 格式化時間
                time_str = trip_time.strftime("%H:%M")
                
                # 添加班次信息
                response += f"  #{trip_id} {time_str} {location} - {status}"
                if person_id:
                    response += f" (司機ID: {person_id})"
                response += "\n"
            
            return response
            
        else:
            # 嘗試解析自定義日期格式
            try:
                # 支持的格式: YYYY-MM-DD, MM-DD, MM/DD
                if re.match(r'^\d{4}-\d{1,2}-\d{1,2}$', date_param):
                    query_date = datetime.strptime(date_param, "%Y-%m-%d").date()
                elif re.match(r'^\d{1,2}-\d{1,2}$', date_param):
                    month, day = map(int, date_param.split('-'))
                    current_year = datetime.now().year
                    query_date = datetime(current_year, month, day).date()
                elif re.match(r'^\d{1,2}/\d{1,2}$', date_param):
                    month, day = map(int, date_param.split('/'))
                    current_year = datetime.now().year
                    query_date = datetime(current_year, month, day).date()
                else:
                    return f"無法解析日期: {date_param}\n請使用格式: YYYY-MM-DD, MM-DD 或 MM/DD"
                
                display_date = query_date.strftime("%Y-%m-%d")
            except ValueError:
                return f"無法解析日期: {date_param}\n請使用格式: YYYY-MM-DD, MM-DD 或 MM/DD"
        
        # 如果是指定日期的查詢
        if query_date:
            # 查詢固定班次 - 移除對persons表的依賴
            query = """
            SELECT 
                t.trip_id, 
                t.time,
                CONCAT(c_start.name, ' → ', COALESCE(CONCAT(c_via.name, ' → '), ''), c_end.name) AS location,
                t.status,
                t.driver_id AS person_id
            FROM 
                trips t
                LEFT JOIN customers c_start ON t.start_point = c_start.short_name
                LEFT JOIN customers c_via ON t.via_point = c_via.short_name
                LEFT JOIN customers c_end ON t.end_point = c_end.short_name
            WHERE 
                t.date = :query_date
                AND t.fixed_trip_id IS NOT NULL
            ORDER BY 
                t.time
            """
            
            result = db.session.execute(
                text(query), 
                {
                    "query_date": query_date
                }
            ).fetchall()
            
            # 格式化結果
            if not result:
                return f"{display_date}沒有固定班次"
            
            day_name = ["一", "二", "三", "四", "五", "六", "日"][query_date.weekday()]
            response = f"{display_date} (星期{day_name}) 固定班次:\n\n"
            
            for row in result:
                trip_id, trip_time, location, status, person_id = row
                
                # 格式化時間
                time_str = trip_time.strftime("%H:%M")
                
                # 添加班次信息
                response += f"#{trip_id} {time_str} {location} - {status}"
                if person_id:
                    response += f" (司機ID: {person_id})"
                response += "\n"
            
            return response
    
    except Exception as e:
        logger.error(f"查詢固定班次時出錯: {e}")
        return f"查詢固定班次錯誤: {str(e)}"

def create_query_fixed_trips_quick_reply():
    """
    創建查詢固定班次的Quick Reply選項
    
    Returns:
        QuickReply: Quick Reply對象
    """
    try:
        # 使用新的 Quick Reply 標準格式
        buttons = [
            {"label": "今天", "text": "查詢固定班次 今天", "type": "postback", "data": "action=query_fixed_trips&date=today"},
            {"label": "明天", "text": "查詢固定班次 明天", "type": "postback", "data": "action=query_fixed_trips&date=tomorrow"},
            {"label": "後天", "text": "查詢固定班次 後天", "type": "postback", "data": "action=query_fixed_trips&date=day_after_tomorrow"},
            {"label": "本週", "text": "查詢固定班次 本週", "type": "postback", "data": "action=query_fixed_trips&date=this_week"}
        ]
        
        # 建立 Quick Reply 數據並轉換為 LINE SDK 格式
        quick_reply_data = QuickReplyManager._build_quick_reply_data(buttons)
        quick_reply = QuickReplyManager.convert_to_line_sdk_object(quick_reply_data)
        
        return quick_reply
    
    except Exception as e:
        logger.error(f"創建Quick Reply時出錯: {e}")
        return None

def handle_trip_details(message_text=None):
    """
    處理班次詳情查詢命令
    
    Args:
        message_text: 查詢命令，格式為"班次詳情 [班次ID]"
    
    Returns:
        str: 查詢結果的文本
    """
    try:
        logger.info(f"處理班次詳情查詢: {message_text}")
        
        # 從命令中提取班次ID
        trip_id = None
        if message_text and len(message_text) > 4:
            trip_id_str = message_text[4:].strip()
            if trip_id_str.isdigit():
                trip_id = int(trip_id_str)
            else:
                return f"無效的班次ID: {trip_id_str}"
        else:
            return "請提供班次ID，例如：班次詳情 123"
        
        # 查詢班次詳情 - 移除對persons表的依賴
        query = """
        SELECT 
            t.trip_id, 
            t.date,
            t.time,
            CONCAT(c_start.name, ' → ', COALESCE(CONCAT(c_via.name, ' → '), ''), c_end.name) AS location,
            t.status,
            NULL AS notes,
            CASE WHEN t.fixed_trip_id IS NOT NULL THEN 1 ELSE 0 END AS is_fixed,
            t.unique_code,
            t.driver_id AS person_id
        FROM 
            trips t
            LEFT JOIN customers c_start ON t.start_point = c_start.short_name
            LEFT JOIN customers c_via ON t.via_point = c_via.short_name
            LEFT JOIN customers c_end ON t.end_point = c_end.short_name
        WHERE 
            t.trip_id = :trip_id
        """
        
        result = db.session.execute(
            text(query), 
            {
                "trip_id": trip_id
            }
        ).fetchone()
        
        # 如果沒找到班次
        if not result:
            return f"找不到班次 #{trip_id}"
        
        # 解析結果
        trip_id, trip_date, trip_time, location, status, notes, is_fixed, unique_code, person_id = result
        
        # 格式化日期和時間
        date_str = trip_date.strftime("%Y-%m-%d")
        day_name = ["一", "二", "三", "四", "五", "六", "日"][trip_date.weekday()]
        time_str = trip_time.strftime("%H:%M")
        
        # 構建回覆
        response = f"班次 #{trip_id} 詳情:\n\n"
        response += f"日期: {date_str} (星期{day_name})\n"
        response += f"時間: {time_str}\n"
        response += f"地點: {location}\n"
        response += f"狀態: {status}\n"
        
        if person_id:
            response += f"司機ID: {person_id}\n"
            
        if notes:
            response += f"備註: {notes}\n"
            
        response += f"固定班次: {'是' if is_fixed else '否'}\n"
        
        if unique_code:
            response += f"識別碼: {unique_code}"
        
        return response
        
    except Exception as e:
        logger.error(f"查詢班次詳情時出錯: {e}")
        return f"查詢班次詳情錯誤: {str(e)}"


def handle_query_trips(message_text=None):
    """處理班次查詢命令，並始終返回Flex Message"""
    date = None
    category = None
    
        # 解析命令參數
    if message_text and len(message_text.strip()) > 4:  # 排除只有"東洋班次"的情況
        parts = message_text.strip().split()
        if len(parts) > 1:
            date_input = parts[1]
            date = parse_date_input(date_input)
            
            # 檢查是否有類別參數
            if len(parts) > 2:
                category = parts[2]
    
    # 如果沒有有效日期，使用今天
    if not date:
        date = datetime.now().strftime('%Y-%m-%d')
    
    # 獲取班次數據
    trips = get_trips_by_date(date, category)
    
    # 生成Flex Message
    return format_trips_flex(trips, date)

def handle_trip_details_flex(trip_id):
    """處理班次詳情查詢，並返回Flex Message"""
    # 使用 trip_detail_service 中的實現
    from modules.services.trip_detail_service import handle_trip_details_flex as service_handle_trip_details_flex
    return service_handle_trip_details_flex(trip_id)

def handle_query_trips_flex(text):
    # 從命令文本中提取日期
    date_str = None
    # 嘗試匹配格式如"查詢班次 4/10"或"查詢班次 2025-04-10"的日期
    date_match = re.search(r'(\d{1,4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2})', text)
    
    if date_match:
        date_str = date_match.group(1)
        # 轉換日期格式
        try:
            # 處理 MM/DD 格式
            if re.match(r'\d{1,2}/\d{1,2}', date_str):
                month, day = map(int, date_str.split('/'))
                query_date = datetime(datetime.now().year, month, day).date()
            # 處理 YYYY-MM-DD 格式
            else:
                query_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            # 日期格式錯誤
            return None, f"日期格式錯誤: {date_str}，請使用 MM/DD 或 YYYY-MM-DD 格式"
    else:
        # 使用今天的日期
        query_date = datetime.now().date()
    
    return query_date, None 