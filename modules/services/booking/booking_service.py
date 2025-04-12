"""
預約服務模組 - 提供班次預約功能
"""
import re
from datetime import datetime, date, timedelta
from sqlalchemy import text as sql_text
from modules.models.base import db
from modules.utils.taiwan_time import get_taiwan_time, get_taiwan_date

# 用戶預約狀態字典，用於跟踪預約流程
booking_states = {}

# 实现自己的日期解析函数，解决循环导入问题
def parse_date_input(date_input):
    """解析各種格式的日期輸入"""
    
    today = get_taiwan_date()
    current_year = today.year
    
    # 嘗試解析完整日期格式 (YYYY-MM-DD)
    if re.match(r'^\d{4}-\d{1,2}-\d{1,2}$', date_input):
        return datetime.strptime(date_input, "%Y-%m-%d").date()
    
    # 嘗試解析簡短日期格式 (MM-DD)
    elif re.match(r'^\d{1,2}-\d{1,2}$', date_input):
        month, day = date_input.split('-')
        try:
            parsed_date = datetime(current_year, int(month), int(day)).date()
            
            # 如果日期在過去，但在最近7天內，保持當前年份
            if parsed_date < today and (today - parsed_date).days <= 7:
                return parsed_date
            # 如果日期在過去且超過7天，假設是明年的日期
            elif parsed_date < today:
                return parsed_date.replace(year=current_year + 1)
            # 日期在未來
            else:
                return parsed_date
        except ValueError:
            raise ValueError(f"無效的日期: {date_input}")
    
    # 嘗試解析斜線日期格式 (MM/DD)
    elif re.match(r'^\d{1,2}/\d{1,2}$', date_input):
        month, day = date_input.split('/')
        try:
            parsed_date = datetime(current_year, int(month), int(day)).date()
            
            # 如果日期在過去，但在最近7天內，保持當前年份
            if parsed_date < today and (today - parsed_date).days <= 7:
                return parsed_date
            # 如果日期在過去且超過7天，假設是明年的日期
            elif parsed_date < today:
                return parsed_date.replace(year=current_year + 1)
            # 日期在未來
            else:
                return parsed_date
        except ValueError:
            raise ValueError(f"無效的日期: {date_input}")
    
    # 嘗試解析中文日期格式 (MM月DD日)
    elif re.match(r'^\d{1,2}月\d{1,2}日$', date_input):
        month, day = re.findall(r'\d+', date_input)
        try:
            parsed_date = datetime(current_year, int(month), int(day)).date()
            
            # 如果日期在過去，但在最近7天內，保持當前年份
            if parsed_date < today and (today - parsed_date).days <= 7:
                return parsed_date
            # 如果日期在過去且超過7天，假設是明年的日期
            elif parsed_date < today:
                return parsed_date.replace(year=current_year + 1)
            # 日期在未來
            else:
                return parsed_date
        except ValueError:
            raise ValueError(f"無效的日期: {date_input}")
    
    # 嘗試解析數字日期格式 (MMDD)
    elif re.match(r'^\d{3,4}$', date_input):
        if len(date_input) == 3:  # 例如 "125" 表示 1月25日
            month = date_input[0]
            day = date_input[1:3]
        else:  # 例如 "0125" 表示 1月25日
            month = date_input[0:2]
            day = date_input[2:4]
            
        try:
            parsed_date = datetime(current_year, int(month), int(day)).date()
            
            # 如果日期在過去，但在最近7天內，保持當前年份
            if parsed_date < today and (today - parsed_date).days <= 7:
                return parsed_date
            # 如果日期在過去且超過7天，假設是明年的日期
            elif parsed_date < today:
                return parsed_date.replace(year=current_year + 1)
            # 日期在未來
            else:
                return parsed_date
        except ValueError:
            raise ValueError(f"無效的日期: {date_input}")
    
    # 嘗試解析星期幾 (一, 二, 三, 四, 五, 六, 日)
    elif date_input in ['一', '二', '三', '四', '五', '六', '日']:
        weekday_map = {'一': 0, '二': 1, '三': 2, '四': 3, '五': 4, '六': 5, '日': 6}
        target_weekday = weekday_map[date_input]
        current_weekday = today.weekday()
        
        # 計算到目標星期幾的天數
        days_ahead = (target_weekday - current_weekday) % 7
        if days_ahead == 0:
            days_ahead = 7  # 如果是同一天，則取下一周的同一天
        
        return today + timedelta(days=days_ahead)
    
    # 嘗試解析相對日期 ("今天", "明天", "後天")
    elif date_input == "今天":
        return today
    elif date_input == "明天":
        return today + timedelta(days=1)
    elif date_input == "後天":
        return today + timedelta(days=2)
    
    # 無法識別的格式
    else:
        raise ValueError("無法識別的日期格式")

def start_booking(user_id, category="診所"):
    """
    開始新的預約流程
    
    Args:
        user_id: 用戶ID
        category: 預約類別（默認為"診所"）
        
    Returns:
        str: 請求日期的提示消息
    """
    booking_states[user_id] = {
        'state': 'booking',
        'step': 'date',
        'data': {
            'category': category
        }
    }
    
    return "請輸入預約日期（格式：MM/DD、YYYY-MM-DD 或 '今天'/'明天'/'後天'）："

def process_booking_input(user_id, message_text):
    """
    處理預約流程中的用戶輸入
    
    Args:
        user_id: 用戶ID
        message_text: 用戶輸入的文本
        
    Returns:
        str: 回覆消息
    """
    if user_id not in booking_states or booking_states[user_id]['state'] != 'booking':
        return start_booking(user_id)
    
    current_step = booking_states[user_id]['step']
    
    try:
        # 根據當前步驟處理用戶輸入
        if current_step == 'date':
            # 驗證日期格式
            try:
                # 嘗試解析日期
                input_date = parse_date_input(message_text)
                
                # 檢查是否為過去的日期
                today = get_taiwan_date()
                if input_date < today:
                    # 如果是過去的日期，嘗試使用明年的同一天
                    if input_date.replace(year=today.year + 1) > today:
                        input_date = input_date.replace(year=today.year + 1)
                    else:
                        raise ValueError("不能預約過去的日期")
                
                booking_states[user_id]['data']['date'] = input_date
                booking_states[user_id]['step'] = 'time'
                return "請輸入預約時間（格式：HH:MM 或 HHMM）："
            except ValueError as e:
                return f"日期格式不正確或日期無效: {str(e)}\n請使用以下格式之一：\n- YYYY-MM-DD（例如：2023-03-15）\n- MM-DD（例如：03-15）"
        
        elif current_step == 'time':
            # 驗證時間格式
            try:
                # 嘗試解析時間
                if ":" in message_text:
                    hour, minute = message_text.split(":")
                    departure_time = datetime.strptime(f"{hour.zfill(2)}:{minute.zfill(2)}", "%H:%M").time()
                else:
                    # 假設格式為 HHMM 或 HMM
                    if len(message_text) == 3:  # HMM
                        hour = message_text[0]
                        minute = message_text[1:3]
                    else:  # HHMM
                        hour = message_text[0:2]
                        minute = message_text[2:4]
                    departure_time = datetime.strptime(f"{hour.zfill(2)}:{minute.zfill(2)}", "%H:%M").time()
                
                # 檢查是否為過去的時間（如果是今天）
                booking_date = booking_states[user_id]['data']['date']
                today = get_taiwan_date()
                now = get_taiwan_time().time()
                
                if booking_date == today and departure_time < now:
                    raise ValueError("不能預約過去的時間")
                
                booking_states[user_id]['data']['time'] = departure_time
                booking_states[user_id]['step'] = 'start_point'
                return "請輸入起點："
            except ValueError as e:
                return f"時間格式不正確或時間無效: {str(e)}\n請使用以下格式之一：\n- HH:MM（例如：09:30）\n- HHMM（例如：0930）"
        
        elif current_step == 'start_point':
            # 保存起點
            if not message_text.strip():
                return "起點不能為空，請輸入起點："
            else:
                booking_states[user_id]['data']['start_point'] = message_text.strip()
                booking_states[user_id]['step'] = 'via_point'
                return "請輸入途經點（如無請輸入「無」或「-」）："
        
        elif current_step == 'via_point':
            # 保存途經點（可選）
            via_point = message_text.strip()
            if via_point in ['無', '-', 'N/A', '不需要', '沒有']:
                booking_states[user_id]['data']['via_point'] = None
            else:
                booking_states[user_id]['data']['via_point'] = via_point
            
            booking_states[user_id]['step'] = 'end_point'
            return "請輸入終點（如無請輸入「無」或「-」）："
        
        elif current_step == 'end_point':
            # 保存終點（可選）
            end_point = message_text.strip()
            if end_point in ['無', '-', 'N/A', '不需要', '沒有']:
                booking_states[user_id]['data']['end_point'] = None
            else:
                booking_states[user_id]['data']['end_point'] = end_point
            
            booking_states[user_id]['step'] = 'confirm'
            
            # 顯示預約信息並請求確認
            booking_data = booking_states[user_id]['data']
            confirm_text = "請確認預約信息：\n\n"
            confirm_text += f"日期：{booking_data['date']}\n"
            confirm_text += f"時間：{booking_data['time'].strftime('%H:%M')}\n"
            confirm_text += f"起點：{booking_data['start_point']}\n"
            
            if booking_data.get('via_point'):
                confirm_text += f"途經：{booking_data['via_point']}\n"
            else:
                confirm_text += "途經：無\n"
            
            if booking_data.get('end_point'):
                confirm_text += f"終點：{booking_data['end_point']}\n"
            else:
                confirm_text += "終點：無\n"
            
            confirm_text += f"類別：{booking_data['category']}\n\n"
            confirm_text += "確認預約請回覆「確認」，取消請回覆「取消」："
            
            return confirm_text
        
        elif current_step == 'confirm':
            # 處理確認或取消
            if message_text.strip() == "確認":
                # 保存預約到數據庫
                booking_data = booking_states[user_id]['data']
                
                # 創建新的班次記錄
                insert_query = """
                INSERT INTO trips 
                (date, time, start_point, via_point, end_point, category, status, trip_type) 
                VALUES 
                (:date, :time, :start_point, :via_point, :end_point, :category, '待派', 'temp')
                RETURNING trip_id
                """
                
                result = db.session.execute(
                    sql_text(insert_query), 
                    {
                        "date": booking_data['date'],
                        "time": booking_data['time'],
                        "start_point": booking_data['start_point'],
                        "via_point": booking_data.get('via_point'),
                        "end_point": booking_data.get('end_point'),
                        "category": booking_data['category']
                    }
                )
                new_trip_id = result.fetchone()[0]
                
                # 生成唯一識別碼
                unique_code = f"T_{new_trip_id}"
                
                # 計算一年中的第幾周
                _, week_number, _ = booking_data['date'].isocalendar()
                
                # 更新班次的唯一識別碼和週數
                update_query = """
                UPDATE trips 
                SET unique_code = :unique_code, week_number = :week_number
                WHERE trip_id = :trip_id
                """
                
                db.session.execute(
                    sql_text(update_query), 
                    {
                        "unique_code": unique_code,
                        "week_number": week_number,
                        "trip_id": new_trip_id
                    }
                )
                
                db.session.commit()
                
                # 清除用戶狀態
                del booking_states[user_id]
                
                # 發送確認消息
                reply_text = (
                    "✅ 預約成功！\n\n"
                    f"班次ID: {new_trip_id}\n"
                    f"日期：{booking_data['date']}\n"
                    f"時間：{booking_data['time'].strftime('%H:%M')}\n"
                    f"起點：{booking_data['start_point']}\n"
                )
                
                if booking_data.get('via_point'):
                    reply_text += f"途經：{booking_data['via_point']}\n"
                else:
                    reply_text += "途經：無\n"
                
                if booking_data.get('end_point'):
                    reply_text += f"終點：{booking_data['end_point']}\n"
                else:
                    reply_text += "終點：無\n"
                
                reply_text += (
                    f"類別：{booking_data['category']}\n"
                    f"狀態：待派\n\n"
                    "我們會盡快為您指派司機。"
                )
                
                return reply_text
            
            elif message_text.strip() == "取消":
                # 清除用戶狀態
                del booking_states[user_id]
                return "您已取消預約。"
            
            else:
                return "請回覆「確認」或「取消」："
        
        else:
            # 未知步驟，重置狀態
            del booking_states[user_id]
            return "預約流程出錯，請重新開始預約。"
            
    except Exception as e:
        # 發生錯誤，清除用戶狀態
        if user_id in booking_states:
            del booking_states[user_id]
        
        return f"預約過程中發生錯誤: {str(e)}\n請重新開始預約流程。" 