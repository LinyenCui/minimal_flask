# modules/services/trip_query_service.py
from datetime import date, timedelta
from sqlalchemy import text as sql_text, Row
from flask import current_app
import traceback
import re
import logging

from modules.models.base import db
from modules.utils.helpers import parse_date_input, row_to_dict
from modules.flex_designs.trip_query_flex import generate_trips_flex
from modules.utils.taiwan_time import get_taiwan_date
from modules.utils.line_bot import QuickReply, QuickReplyItem, MessageAction, TextMessage

logger = logging.getLogger(__name__)

def handle_query_trips_flex(message_text=None):
    """返回Flex Message格式的班次查詢結果"""
    try:
        current_app.logger.info(f"handle_query_trips_flex被調用，參數: {message_text}")
        # 获取台湾时间的今天日期
        today = get_taiwan_date()  # 使用台湾时间
        current_app.logger.info(f"今天日期: {today}")
        
        # 解析日期參數（如果有）
        query_dates = []
        
        if message_text and len(message_text.split()) > 1:
            date_str = message_text.split()[1]
            current_app.logger.info(f"解析日期參數: {date_str}")
            
            # 處理特殊日期關鍵字
            if date_str == "今天":
                query_dates = [today]
                current_app.logger.info("使用今天的日期")
            elif date_str == "明天":
                query_dates = [today + timedelta(days=1)]
                current_app.logger.info("使用明天的日期")
            elif date_str == "後天":
                query_dates = [today + timedelta(days=2)]
                current_app.logger.info("使用後天的日期")
            elif date_str == "一三五":
                # 計算本周的星期一、三、五的日期
                weekday_map = {0: "一", 2: "三", 4: "五"}
                
                # 計算本周的開始日期（星期日）
                days_since_sunday = today.weekday() + 1 if today.weekday() < 6 else 0
                week_start = today - timedelta(days=days_since_sunday)
                current_app.logger.info(f"本周開始日期: {week_start}")
                
                for days_offset, weekday_name in weekday_map.items():
                    weekday_date = week_start + timedelta(days=days_offset + 1)  # +1 是因為星期日是一周的第一天
                    # 只包含今天和未來的日期
                    if weekday_date >= today:
                        query_dates.append(weekday_date)
                
                current_app.logger.info(f"一三五日期: {query_dates}")
                if not query_dates:
                    return None, "本周剩餘的星期一、三、五已經沒有班次了。"
                
            elif date_str == "二四六":
                # 計算本周的星期二、四、六的日期
                weekday_map = {1: "二", 3: "四", 5: "六"}
                
                # 計算本周的開始日期（星期日）
                days_since_sunday = today.weekday() + 1 if today.weekday() < 6 else 0
                week_start = today - timedelta(days=days_since_sunday)
                current_app.logger.info(f"本周開始日期: {week_start}")
                
                for days_offset, weekday_name in weekday_map.items():
                    weekday_date = week_start + timedelta(days=days_offset + 1)  # +1 是因為星期日是一周的第一天
                    # 只包含今天和未來的日期
                    if weekday_date >= today:
                        query_dates.append(weekday_date)
                
                current_app.logger.info(f"二四六日期: {query_dates}")
                if not query_dates:
                    return None, "本周剩餘的星期二、四、六已經沒有班次了。"
                
            else:
                # 嘗試解析單個日期，修改這部分
                try:
                    current_app.logger.info(f"嘗試解析日期: {date_str}")
                    query_date = parse_date_input(date_str)
                    query_dates = [query_date]
                    current_app.logger.info(f"解析結果: {query_date}")
                except ValueError as e:
                    current_app.logger.error(f"日期解析錯誤: {str(e)}")
                    return None, f"日期格式不正確: {str(e)}\n\n支持的格式：\n- YYYY-MM-DD (例如: 2025-03-11)\n- MM-DD (例如: 03-11)\n- MM/DD (例如: 3/11)\n- MM月DD日 (例如: 3月11日)\n- MMDD (例如: 0311)\n- 一三五 - 查詢本周星期一、三、五的班次\n- 二四六 - 查詢本周星期二、四、六的班次"
        else:
            # 默認使用今天的日期
            query_dates = [today]
            current_app.logger.info("使用默認日期（今天）")
        
        # 查詢指定日期的班次
        all_trips = []
        
        for query_date in query_dates:
            query = f"""
            SELECT 
                t.trip_id, t.date, t.time, 
                t.start_point, t.end_point, 
                COALESCE(fs.direction, '來') as direction,
                t.status, t.driver_id, t.trip_type,
                t.custom_start_point, t.custom_end_point, t.category,
                t.passenger_leave_reason, t.modification_reason
            FROM 
                trips t
            LEFT JOIN
                fixed_schedules fs ON t.fixed_trip_id = fs.id
            WHERE 
                t.date = '{query_date}'
                AND t.status != '已完成'
                AND t.category IN ('東洋', '臨時')
            ORDER BY 
                t.date, t.time
            """
            
            current_app.logger.info(f"執行SQL查詢: {query}")
            trips = db.session.execute(sql_text(query)).fetchall()
            current_app.logger.info(f"查詢結果: {len(trips)} 條記錄")
            all_trips.extend(trips)
        
        current_app.logger.info(f"總共找到 {len(all_trips)} 條班次記錄")
        if not all_trips:
            if len(query_dates) == 1:
                # 使用友好的日期格式
                weekday_names = ["一", "二", "三", "四", "五", "六", "日"]
                weekday = weekday_names[query_dates[0].weekday()]
                formatted_date = f"{query_dates[0].month}/{query_dates[0].day} (星期{weekday})"
                return None, f"{formatted_date} 沒有安排班次。"
            else:
                return None, "指定的日期沒有安排班次。"
        
        # 使用更新後的generate_trips_flex函數生成Flex Message
        current_app.logger.info(f"使用generate_trips_flex生成Flex訊息，共 {len(all_trips)} 條記錄")
        flex_content = generate_trips_flex(all_trips)
        
        current_app.logger.info("成功創建班次查詢Flex Message")
        return flex_content, None
        
    except Exception as e:
        traceback.print_exc()
        current_app.logger.error(f"處理查詢班次時出錯: {str(e)}")
        return None, f"查詢班次錯誤: {str(e)}"

def handle_query_fixed_trips_flex(message_text=None):
    """以Flex Message格式返回固定班次查詢結果"""
    try:
        # 解析日期參數（如果有）
        if message_text and len(message_text.split()) > 1:
            try:
                # 嘗試解析指定日期
                query_date = parse_date_input(message_text.split()[1])
            except ValueError as e:
                return None, f"日期格式不正確: {str(e)}\n\n支持的格式：\n- YYYY-MM-DD (例如: 2025-03-11)\n- MM-DD (例如: 03-11)\n- MM/DD (例如: 3/11)\n- MM月DD日 (例如: 3月11日)\n- MMDD (例如: 0311)\n- 今天, 明天, 後天"
        else:
            # 默認使用今天的日期
            query_date = date.today()
        
        # 查詢指定日期的固定班次
        query = f"""
        SELECT 
            t.trip_id, 
            t.date,
            t.time, 
            t.start_point, 
            t.end_point, 
            fs.direction,
            t.status,
            t.driver_id,
            t.trip_type
        FROM 
            trips t
        JOIN
            fixed_schedules fs ON t.fixed_trip_id = fs.id
        WHERE 
            t.date = '{query_date}'
            AND t.status != '已完成'
            AND t.trip_type = 'fixed'
        ORDER BY 
            t.time
        """
        
        current_app.logger.info(f"執行查詢固定班次SQL: {query}")
        trips = db.session.execute(sql_text(query)).fetchall()
        current_app.logger.info(f"查詢到 {len(trips)} 條固定班次記錄")
        
        if not trips:
            # 使用友好的日期格式
            weekday_names = ["一", "二", "三", "四", "五", "六", "日"]
            weekday = weekday_names[query_date.weekday()]
            formatted_date = f"{query_date.month}/{query_date.day} (星期{weekday})"
            return None, f"{formatted_date} 沒有固定班次。"
        
        # 使用Flex設計函數生成Flex Message
        flex_content = generate_trips_flex(trips, None, True)
        
        return flex_content, None
        
    except Exception as e:
        current_app.logger.error(f"處理查詢固定班次Flex Message時出錯: {e}")
        traceback.print_exc()
        return None, f"查詢固定班次錯誤: {str(e)}"

def handle_query_trips(message_text=None):
    """返回文本格式的班次查詢結果"""
    try:
        # 獲取今天的日期
        today = date.today()
        
        # 解析日期參數（如果有）
        query_dates = [today]  # 默認使用今天的日期
        
        if message_text and len(message_text.split()) > 1:
            date_str = message_text.split()[1]
            
            # 處理星期組合
            if date_str == "一三五":
                # 計算本周的星期一、三、五的日期
                weekday_map = {0: "一", 2: "三", 4: "五"}
                query_dates = []
                
                # 計算本周的開始日期（星期日）
                days_since_sunday = today.weekday() + 1 if today.weekday() < 6 else 0
                week_start = today - timedelta(days=days_since_sunday)
                
                for days_offset, weekday_name in weekday_map.items():
                    weekday_date = week_start + timedelta(days=days_offset + 1)  # +1 是因為星期日是一周的第一天
                    # 只包含今天和未來的日期
                    if weekday_date >= today:
                        query_dates.append(weekday_date)
                
                if not query_dates:
                    return "本周剩餘的星期一、三、五已經沒有班次了。"
                
            elif date_str == "二四六":
                # 計算本周的星期二、四、六的日期
                weekday_map = {1: "二", 3: "四", 5: "六"}
                query_dates = []
                
                # 計算本周的開始日期（星期日）
                days_since_sunday = today.weekday() + 1 if today.weekday() < 6 else 0
                week_start = today - timedelta(days=days_since_sunday)
                
                for days_offset, weekday_name in weekday_map.items():
                    weekday_date = week_start + timedelta(days=days_offset + 1)  # +1 是因為星期日是一周的第一天
                    # 只包含今天和未來的日期
                    if weekday_date >= today:
                        query_dates.append(weekday_date)
                
                if not query_dates:
                    return "本周剩餘的星期二、四、六已經沒有班次了。"
                
            else:
                # 嘗試解析單個日期
                try:
                    query_date = parse_date_input(date_str)
                    query_dates = [query_date]
                except ValueError as e:
                    return f"日期格式不正確: {str(e)}\n\n支持的格式：\n- YYYY-MM-DD (例如: 2025-03-11)\n- MM-DD (例如: 03-11)\n- MM/DD (例如: 3/11)\n- MM月DD日 (例如: 3月11日)\n- MMDD (例如: 0311)\n- 一三五 - 查詢本周星期一、三、五的班次\n- 二四六 - 查詢本周星期二、四、六的班次"
        
        # 查詢指定日期的班次，不包括"已完成"狀態的班次
        all_trips = []
        
        for query_date in query_dates:
            query = f"""
            SELECT 
                t.trip_id, t.date, t.time, 
                t.start_point, t.end_point, 
                COALESCE(fs.direction, '來') as direction,
                t.status, t.driver_id, t.trip_type,
                t.custom_start_point, t.custom_end_point, t.category,
                t.passenger_leave_reason, t.modification_reason
            FROM 
                trips t
            LEFT JOIN
                fixed_schedules fs ON t.fixed_trip_id = fs.id
            WHERE 
                t.date = '{query_date}'
                AND t.status != '已完成'
                AND t.category IN ('東洋', '臨時')
            ORDER BY 
                t.date, t.time
            """
            
            trips = db.session.execute(sql_text(query)).fetchall()
            all_trips.extend(trips)
        
        if not all_trips:
            if len(query_dates) == 1:
                # 使用友好的日期格式
                weekday_names = ["一", "二", "三", "四", "五", "六", "日"]
                weekday = weekday_names[query_dates[0].weekday()]
                formatted_date = f"{query_dates[0].month}/{query_dates[0].day} (星期{weekday})"
                return f"{formatted_date} 沒有安排班次。"
            else:
                return "指定的日期沒有安排班次。"
        
        # 格式化班次信息
        if len(query_dates) == 1:
            # 單一日期的情況
            weekday_names = ["一", "二", "三", "四", "五", "六", "日"]
            weekday = weekday_names[query_dates[0].weekday()]
            formatted_date = f"{query_dates[0].month}/{query_dates[0].day} (星期{weekday})"
            reply_text = f"📅 {formatted_date} 班次總覽：\n\n"
        else:
            # 多個日期的情況
            if date_str == "一三五":
                reply_text = f"📅 本周星期一、三、五班次總覽：\n\n"
            elif date_str == "二四六":
                reply_text = f"📅 本周星期二、四、六班次總覽：\n\n"
            else:
                reply_text = f"📅 多日班次總覽：\n\n"
        
        # 根據用戶狀態處理輸入
        current_date = None
        
        for trip in all_trips:
            trip_id = trip[0]
            trip_date = trip[1]
            time_val = trip[2].strftime("%H:%M") if trip[2] else "--:--"
            start_point = trip[3]
            end_point = trip[4]
            direction = trip[5]  # "來" 或 "回"
            status = trip[6] or "未指定"
            driver_id = trip[7] or "未指派"
            trip_type = trip[8] if len(trip) > 8 else ""  # 確保獲取trip_type
            custom_start_point = trip[9] if len(trip) > 9 else None
            custom_end_point = trip[10] if len(trip) > 10 else None
            category = trip[11] if len(trip) > 11 else None
            passenger_leave_reason = trip[12] if len(trip) > 12 else None
            modification_reason = trip[13] if len(trip) > 13 else None
            
            # 根據班次類型和方向決定顯示的地點
            if trip_type == "temp":
                # 臨時預約優先使用custom_*欄位
                if direction == "來":
                    location = custom_start_point or start_point
                else:
                    location = custom_end_point or end_point
            else:
                # 固定班次使用標準欄位
                if direction == "來":
                    location = start_point
                else:
                    location = end_point
            
            # 如果日期變了，添加日期標題
            if current_date != trip_date:
                current_date = trip_date
                weekday_names = ["一", "二", "三", "四", "五", "六", "日"]
                weekday = weekday_names[current_date.weekday()]
                date_str = f"{current_date.month}/{current_date.day} (星期{weekday})"
                reply_text += f"\n【{date_str}】\n"
            
            # 🚨 新增：檢查是否為乘客請假狀態
            display_status = status
            
            # 優先檢查新的passenger_leave_reason欄位
            if passenger_leave_reason:
                display_status = "請假"
            # 回退檢查舊的modification_reason欄位
            elif modification_reason and ("乘客請假" in modification_reason or "請假" in modification_reason):
                display_status = "請假"
            
            # 根據狀態添加不同的表情符號
            status_emoji = {
                "準備": "🟢",
                "完成": "✅",
                "取消": "❌",
                "衝突": "⚠️",
                "請假": "🔵",
                "待派": "🟠"
            }.get(display_status, "⚪")
            
            # 根據班次類型決定是否顯示方向
            if trip_type == "temp":
                # 臨時預約班次只顯示地點，不顯示方向
                reply_text += f"{status_emoji} #{trip_id} {time_val} {location} - 🚕{driver_id}\n"
            else:
                # 固定班次顯示地點和方向
                reply_text += f"{status_emoji} #{trip_id} {time_val} {location}{direction} - 🚕{driver_id}\n"
        
        reply_text += "\n輸入「班次詳情 [ID]」查看特定班次的詳細信息。"
        
        return reply_text
        
    except Exception as e:
        return f"查詢班次錯誤: {str(e)}"

def handle_query_fixed_trips(message_text=None):
    """返回文本格式的固定班次查詢結果"""
    try:
        # 獲取今天的日期
        today = date.today()
        
        # 解析日期參數（如果有）
        query_date = today  # 默認使用今天的日期
        
        if message_text and len(message_text.split()) > 1:
            date_str = message_text.split()[1]
            
            # 處理特殊日期輸入
            if date_str == "今天":
                query_date = today
            elif date_str == "明天":
                query_date = today + timedelta(days=1)
            elif date_str == "後天":
                query_date = today + timedelta(days=2)
            else:
                # 嘗試解析日期
                try:
                    query_date = parse_date_input(date_str)
                except ValueError as e:
                    return f"日期格式不正確: {str(e)}\n\n支持的格式：\n- YYYY-MM-DD (例如: 2025-03-11)\n- MM-DD (例如: 03-11)\n- MM/DD (例如: 3/11)\n- MM月DD日 (例如: 3月11日)\n- MMDD (例如: 0311)\n- 今天, 明天, 後天"
        
        # 查詢指定日期的固定班次，不包括"已完成"狀態的班次
        query = f"""
        SELECT 
            t.trip_id, 
            t.date,
            t.time, 
            t.start_point, 
            t.end_point, 
            fs.direction,
            t.status,
            t.driver_id,
            t.trip_type,
            t.passenger_leave_reason,
            t.modification_reason
        FROM 
            trips t
        JOIN
            fixed_schedules fs ON t.fixed_trip_id = fs.id
        WHERE 
            t.date = '{query_date}'
            AND t.status != '已完成'
            AND t.trip_type = 'fixed'
        ORDER BY 
            t.time
        """
        
        trips = db.session.execute(sql_text(query)).fetchall()
        
        if not trips:
            # 使用友好的日期格式
            weekday_names = ["一", "二", "三", "四", "五", "六", "日"]
            weekday = weekday_names[query_date.weekday()]
            formatted_date = f"{query_date.month}/{query_date.day} (星期{weekday})"
            return f"{formatted_date} 沒有固定班次。"
        
        # 格式化班次信息
        weekday_names = ["一", "二", "三", "四", "五", "六", "日"]
        weekday = weekday_names[query_date.weekday()]
        formatted_date = f"{query_date.month}/{query_date.day} (星期{weekday})"
        reply_text = f"📅 {formatted_date} 固定班次總覽：\n\n"
        
        for trip in trips:
            trip_id = trip[0]
            time_val = trip[2].strftime("%H:%M") if trip[2] else "--:--"
            start_point = trip[3]
            end_point = trip[4]
            direction = trip[5]  # "來" 或 "回"
            status = trip[6] or "未指定"
            driver_id = trip[7] or "未指派"
            passenger_leave_reason = trip[9] if len(trip) > 9 else None
            modification_reason = trip[10] if len(trip) > 10 else None
            
            # 根據方向決定顯示的地點
            if direction == "來":
                location = start_point
            else:
                location = end_point
            
            # 🚨 新增：檢查是否為乘客請假狀態
            display_status = status
            
            # 優先檢查新的passenger_leave_reason欄位
            if passenger_leave_reason:
                display_status = "請假"
            # 回退檢查舊的modification_reason欄位
            elif modification_reason and ("乘客請假" in modification_reason or "請假" in modification_reason):
                display_status = "請假"
            
            # 根據狀態添加不同的表情符號
            status_emoji = {
                "準備": "🟢",
                "完成": "✅",
                "取消": "❌",
                "衝突": "⚠️",
                "請假": "🔵",
                "待派": "🟠"
            }.get(display_status, "⚪")
            
            # 固定班次顯示地點和方向
            reply_text += f"{status_emoji} #{trip_id} {time_val} {location}{direction} - 🚕{driver_id}\n"
        
        reply_text += "\n輸入「班次詳情 [ID]」查看特定班次的詳細信息。"
        
        return reply_text
        
    except Exception as e:
        return f"查詢固定班次錯誤: {str(e)}"

def request_fixed_trip_date_selection():
    """生成用於查詢固定班次的日期選擇 Quick Reply (本週日到週六)"""
    try:
        today = get_taiwan_date()
        quick_reply_items = []
        weekday_names = ["日", "一", "二", "三", "四", "五", "六"]
        
        days_since_sunday = today.isoweekday() % 7 
        week_start_sunday = today - timedelta(days=days_since_sunday)

        today_button = None # 用於存放今天的按鈕
        other_day_buttons = [] # 存放其他天的按鈕

        # 生成本週日到週六的日期和按鈕
        for i in range(7):
            current_day = week_start_sunday + timedelta(days=i)
            date_str_iso = current_day.strftime("%Y-%m-%d")
            weekday_index = (current_day.weekday() + 1) % 7 
            weekday = weekday_names[weekday_index]
            label = f"{current_day.month}/{current_day.day}({weekday})"
            
            button_item = QuickReplyItem(
                action=MessageAction(
                    label=label, # 先用基本標籤
                    text=f"查詢固定班次 {date_str_iso}"
                )
            )

            if current_day == today:
                button_item.action.label = f"今天 {label}" # 為今天的按鈕添加前綴
                today_button = button_item # 保存今天的按鈕
            else:
                other_day_buttons.append(button_item) # 保存其他天的按鈕
                
        # 將今天的按鈕放在最前面
        if today_button:
             quick_reply_items = [today_button] + other_day_buttons
        else: # 理論上不會發生，除非計算錯誤
             quick_reply_items = other_day_buttons
            
        quick_reply = QuickReply(items=quick_reply_items)
        
        reply_msg = TextMessage(
            text="請選擇要查詢固定班次的日期 (本週日-週六)：", 
            quick_reply=quick_reply
        )
        return reply_msg, None

    except Exception as e:
        current_app.logger.error(f"生成固定班次日期選擇時出錯: {e}")
        traceback.print_exc()
        return None, f"生成日期選擇失敗: {str(e)}"

def handle_query_completed_trips(message_text=None):
    """返回指定日期已完成班次的文本列表，支持按類別篩選"""
    try:
        today = get_taiwan_date()
        query_date = today # 默認查詢今天
        category_filter = None # 默認不過濾類別
        
        # 解析日期和類別參數
        parts = message_text.split()
        if len(parts) > 1:
            # 第一個參數是日期
            date_str = parts[1]
            try:
                query_date = parse_date_input(date_str)
            except ValueError as e:
                 return f"日期格式不正確: {str(e)}\n支持格式：YYYY-MM-DD, MM-DD, MM/DD, 今天, 昨天等"
                 
            # 第二個參數（如果存在）是類別
            if len(parts) > 2:
                category_filter = parts[2]
                if category_filter not in ["診所", "東洋", "臨時"]: # 根據你的實際類別調整
                    return f"無效的類別: {category_filter}。請輸入 診所, 東洋 或 臨時。"
                   
        # 構建查詢語句
        query_base = """
        SELECT 
            id, date,
            start_point, end_point,
            meter_fare, extra_fare, driver_id, trip_type, category
        FROM completed_trips
        WHERE date = :query_date
        """
        query_params = {"query_date": query_date}
        
        # 添加類別過濾條件
        if category_filter:
            query_base += " AND category = :category "
            query_params["category"] = category_filter
            
        query_base += " ORDER BY id "
        
        query = sql_text(query_base)
        
        completed_trips = db.session.execute(query, query_params).fetchall()
        
        if not completed_trips:
            category_text = f" ({category_filter}類)" if category_filter else ""
            return f"{query_date.strftime('%Y-%m-%d')} 沒有已完成的班次記錄{category_text}。"
            
        # 格式化結果
        weekday_names = ["一", "二", "三", "四", "五", "六", "日"]
        weekday = weekday_names[query_date.weekday()]
        formatted_date = f"{query_date.month}/{query_date.day} (星期{weekday})"
        category_title = f" ({category_filter}類)" if category_filter else ""
        reply_text = f"📅 {formatted_date} 已完成班次{category_title}：\n---\n"
        
        for trip in completed_trips:
            trip_dict = row_to_dict(trip)
            if not trip_dict: continue
            
            trip_id = trip_dict.get('id')
            driver_id = trip_dict.get('driver_id') or "N/A"
            # 格式化金額，處理 None
            meter_fare = trip_dict.get('meter_fare')
            extra_fare = trip_dict.get('extra_fare')
            meter_fare_str = str(meter_fare) if meter_fare is not None else "未記錄"
            extra_fare_str = str(extra_fare) if extra_fare is not None else "未記錄"
            # trip_type = trip_dict.get('trip_type') # 不再需要根據 trip_type 判斷

            # 直接使用 start_point 和 end_point
            start = trip_dict.get('start_point') or "?"
            end = trip_dict.get('end_point') or "?"

            # 添加 category 到輸出
            category = trip_dict.get('category') or "?"
            reply_text += f"ID: {trip_id} ({category})\n" # 在 ID 後面加上類別
            reply_text += f"  路線: {start} → {end}\n"
            reply_text += f"  司機: 🚕{driver_id}\n"
            reply_text += f"  錶價: {meter_fare_str} | 加成: {extra_fare_str}\n---\n"
            
        reply_text += "使用「記錄車資 [ID] [錶價] [加成]」記錄費用。"
        return reply_text
        
    except Exception as e:
        current_app.logger.error(f"查詢已完成班次時出錯: {e}")
        traceback.print_exc()
        return f"查詢已完成班次時出錯: {str(e)}"

def request_completed_trip_category_selection(query_date):
    """為指定日期生成類別選擇 Quick Reply"""
    try:
        categories = ["全部", "診所", "東洋", "臨時"] # 根據需要調整
        quick_reply_items = []
        date_str = query_date.strftime("%Y-%m-%d")
        
        for category in categories:
            quick_reply_items.append(
                QuickReplyItem(
                    action=MessageAction(
                        label=category,
                        text=f"查已完成 {date_str} {category}" # 點擊後發送帶類別的查詢命令
                    )
                )
            )
            
        quick_reply = QuickReply(items=quick_reply_items)
        
        reply_msg = TextMessage(
            text=f"請選擇要查詢 {date_str} 的哪個類別的已完成班次？",
            quick_reply=quick_reply
        )
        return reply_msg, None
        
    except Exception as e:
        current_app.logger.error(f"生成已完成班次類別選擇時出錯: {e}")
        traceback.print_exc()
        return None, f"生成類別選擇失敗: {str(e)}"

# --- 新增：診所班次日期選擇 --- 
def request_clinic_trip_date_selection():
    """生成用於查詢診所班次的日期選擇 Quick Reply (今天第一, 週日最後)"""
    try:
        today = get_taiwan_date()
        quick_reply_items = []
        weekday_names = ["日", "一", "二", "三", "四", "五", "六"]
        days_since_sunday = today.isoweekday() % 7 
        week_start_sunday = today - timedelta(days=days_since_sunday)
        
        today_button = None
        sunday_button = None
        other_day_buttons = []

        for i in range(7):
            current_day = week_start_sunday + timedelta(days=i)
            date_str_iso = current_day.strftime("%Y-%m-%d")
            weekday_index = (current_day.weekday() + 1) % 7 
            weekday = weekday_names[weekday_index]
            label = f"{current_day.month}/{current_day.day}({weekday})"
            
            button_item = QuickReplyItem(
                action=MessageAction(
                    label=label,
                    text=f"診所班次 {date_str_iso}" 
                )
            )
            
            if current_day == today:
                button_item.action.label = f"今天 {label}"
                today_button = button_item
            elif weekday_index == 0: # 如果是星期日
                sunday_button = button_item
            else:
                other_day_buttons.append(button_item)
                
        # --- 組合按鈕順序 --- 
        final_items = []
        if today_button:
            final_items.append(today_button)
        final_items.extend(other_day_buttons) # 添加中間的按鈕
        if sunday_button:
            final_items.append(sunday_button) # 添加星期日按鈕
            
        quick_reply = QuickReply(items=final_items)
        
        reply_msg = TextMessage(
            text="請選擇要查詢診所班次的日期 (本週)：", # 稍微修改提示
            quick_reply=quick_reply
        )
        return reply_msg, None
    except Exception as e:
        # ... (錯誤處理)
        # <<< 這裡的代碼需要正確縮進 >>>
        logger.error(f"生成東洋/臨時班次日期選擇時出錯: {e}", exc_info=True)
        return None, f"生成日期選擇失敗: {str(e)}"

# --- 重命名並修改：查詢診所班次 (Flex) ---
def handle_query_clinic_trips_flex(message_text=None):
    """以Flex Message格式返回診所班次查詢結果"""
    try:
        today = get_taiwan_date() # <--- 獲取今天日期
        query_dates = [] # <--- 初始化日期列表
        date_str = None # <--- 初始化日期字符串
        
        # --- 修改：重新加入對 一三五/二四六 的處理 --- 
        if message_text and len(message_text.split()) > 1:
            date_str = message_text.split()[1]
            if date_str == "今天":
                query_dates = [today]
            elif date_str == "明天":
                query_dates = [today + timedelta(days=1)]
            elif date_str == "後天":
                query_dates = [today + timedelta(days=2)]
            elif date_str == "一三五":
                weekday_map = {0: "一", 2: "三", 4: "五"}
                days_since_sunday = today.weekday() + 1 if today.weekday() < 6 else 0
                week_start = today - timedelta(days=days_since_sunday)
                for days_offset, _ in weekday_map.items():
                    weekday_date = week_start + timedelta(days=days_offset + 1)
                    if weekday_date >= today:
                        query_dates.append(weekday_date)
                if not query_dates:
                    return None, "本周剩餘的星期一、三、五已經沒有診所班次了。"
            elif date_str == "二四六":
                weekday_map = {1: "二", 3: "四", 5: "六"}
                days_since_sunday = today.weekday() + 1 if today.weekday() < 6 else 0
                week_start = today - timedelta(days=days_since_sunday)
                for days_offset, _ in weekday_map.items():
                    weekday_date = week_start + timedelta(days=days_offset + 1)
                    if weekday_date >= today:
                        query_dates.append(weekday_date)
                if not query_dates:
                    return None, "本周剩餘的星期二、四、六已經沒有診所班次了。"
            else:
                try:
                    query_date = parse_date_input(date_str)
                    query_dates = [query_date]
                except ValueError as e:
                    return None, f"日期格式不正確: {str(e)} ..."
        else:
            # 如果命令只有 "診所班次"，理論上應該由 text_handler 觸發 Quick Reply
            # 但作為保險，這裡可以查今天
            query_dates = [today]
            
        # --- 使用 query_dates 列表進行查詢 --- 
        all_clinic_trips = []
        for query_date in query_dates:
            query = sql_text(f"""
            SELECT 
                t.trip_id, t.date, t.time, 
                t.start_point, t.end_point, 
                fs.direction, 
                t.status, t.driver_id, t.trip_type,
                t.custom_start_point, t.custom_end_point, t.category,
                t.passenger_leave_reason, t.modification_reason
            FROM trips t
            LEFT JOIN fixed_schedules fs ON t.fixed_trip_id = fs.id 
            WHERE 
                t.date = :query_date
                AND t.status != '已完成'
                AND t.category = '診所' 
            ORDER BY t.time
            """)
            trips = db.session.execute(query, {"query_date": query_date}).fetchall()
            all_clinic_trips.extend(trips)
            
        current_app.logger.info(f"查詢到 {len(all_clinic_trips)} 條診所班次記錄")
        if not all_clinic_trips:
            # --- 恢復/確保處理空結果的代碼塊 --- 
            weekday_names = ["一", "二", "三", "四", "五", "六", "日"]
            # 使用循環中最後處理的日期，或提供默認值
            last_query_date = query_date if 'query_date' in locals() else get_taiwan_date()
            weekday = weekday_names[last_query_date.weekday()]
            formatted_date = f"{last_query_date.month}/{last_query_date.day} (星期{weekday})"
            logger.info(f"查詢診所班次結果為空，日期: {last_query_date}")
            return None, f"{formatted_date} 沒有診所班次。"
            # --- 結束恢復 ---
        
        # 如果有結果，則生成 Flex (這部分應在 if 塊之外)
        flex_content = generate_trips_flex(all_clinic_trips, is_fixed_trips=False) 
        return flex_content, None
    except Exception as e:
        # ... (錯誤處理) ...
        current_app.logger.error(f"查詢診所班次時發生錯誤: {str(e)}")
        return None, "查詢診所班次時發生錯誤，請稍後再試。"

# --- 重命名並修改：查詢診所班次 (Text) ---
def handle_query_clinic_trips(message_text=None):
    """返回文本格式的診所班次查詢結果"""
    try:
        # 第一層縮進
        today = get_taiwan_date()
        query_dates = []
        # ...
        if message_text and len(message_text.split()) > 1:
            # 第二層縮進
            date_str = message_text.split()[1]
            if date_str == "今天":
                # 第三層縮進
                query_dates = [today]
            elif date_str == "一三五":
                # 第三層縮進
                # 計算一三五的日期
                query_dates = []
                for i in range(7):  # 查詢未來一週
                    check_date = today + timedelta(days=i)
                    # 星期一(0)、三(2)、五(4)
                    if check_date.weekday() in [0, 2, 4]:
                        query_dates.append(check_date)
            elif date_str == "二四六":
                # ... (計算 二四六 日期)
                if not query_dates: return "本周剩餘的星期二、四、六已經沒有診所班次了。"
            else: # <<< 與 elif 對齊
                # <<< 以下需要縮進 >>>
                try: 
                    query_dates = [parse_date_input(date_str)]
                except ValueError as e: 
                    return f"日期格式不正確: {str(e)} ..."
        else:
            query_dates = [today]

        # 第一層縮進
        all_clinic_trips = []
        for query_date in query_dates:
            # 第二層縮進
            query = sql_text(f"""
            SELECT 
                t.trip_id, t.date, t.time, 
                t.start_point, t.end_point, 
                fs.direction, 
                t.status, t.driver_id, t.trip_type,
                t.custom_start_point, t.custom_end_point, t.category,
                t.passenger_leave_reason, t.modification_reason
            FROM trips t
            LEFT JOIN fixed_schedules fs ON t.fixed_trip_id = fs.id 
            WHERE 
                t.date = :query_date
                AND t.status != '已完成'
                AND t.category = '診所' 
            ORDER BY t.time
            """)
            # --- 添加賦值 --- 
            trips = db.session.execute(query, {"query_date": query_date}).fetchall()
            all_clinic_trips.extend(trips)

        # 第一層縮進
        if not all_clinic_trips:
            # 第二層縮進
            # ...
            return "..." # 無班次消息

        # 第一層縮進
        reply_text = "..."
        for trip_row in all_clinic_trips:
            # 第二層縮進
            # ... (格式化) ...
            pass # 確保循環體不為空
        # --- 將 return 取消縮進，與 for 對齊 ---
        return reply_text

    except Exception as e:
        # 第一層縮進
        logger.error(...)
        return "..." # 錯誤消息

# --- 新增：東洋/臨時 班次日期選擇 --- 
def request_toyo_temp_trip_date_selection():
    """生成用於查詢東洋/臨時班次的日期選擇 Quick Reply (今天第一, 週日最後)"""
    try:
        today = get_taiwan_date()
        quick_reply_items = []
        weekday_names = ["日", "一", "二", "三", "四", "五", "六"]
        days_since_sunday = today.isoweekday() % 7 
        week_start_sunday = today - timedelta(days=days_since_sunday)
        today_button = None
        sunday_button = None
        other_day_buttons = []
        for i in range(7):
            current_day = week_start_sunday + timedelta(days=i)
            date_str_iso = current_day.strftime("%Y-%m-%d")
            weekday_index = (current_day.weekday() + 1) % 7 
            weekday = weekday_names[weekday_index]
            label = f"{current_day.month}/{current_day.day}({weekday})"
            button_item = QuickReplyItem(
                action=MessageAction(
                    label=label,
                    text=f"查詢班次 {date_str_iso}" # <-- 注意命令文本不同
                )
            )
            if current_day == today:
                button_item.action.label = f"今天 {label}"
                today_button = button_item
            elif weekday_index == 0: # 星期日
                sunday_button = button_item
            else:
                other_day_buttons.append(button_item)
        
        # 組合按鈕順序
        final_items = []
        if today_button:
            final_items.append(today_button)
        final_items.extend(other_day_buttons)
        if sunday_button:
            final_items.append(sunday_button)
            
        quick_reply = QuickReply(items=final_items)
        reply_msg = TextMessage(
            text="請選擇要查詢東洋/臨時班次的日期 (本週)：", 
            quick_reply=quick_reply
        )
        return reply_msg, None
    except Exception as e:
        # <<< 確保以下兩行有縮進 >>>
        logger.error(f"生成東洋/臨時班次日期選擇時出錯: {e}", exc_info=True)
        return None, f"生成日期選擇失敗: {str(e)}"
