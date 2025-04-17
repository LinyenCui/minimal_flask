# modules/services/trip_query_service.py
from datetime import date, timedelta
from sqlalchemy import text as sql_text
from flask import current_app
import traceback
import re

from modules.models.base import db
from modules.utils.helpers import parse_date_input
from modules.flex_designs.trip_query_flex import generate_trips_flex
from modules.utils.taiwan_time import get_taiwan_date
from modules.utils.line_bot import QuickReply, QuickReplyItem, MessageAction, TextMessage

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
                t.trip_id, 
                t.date,
                t.time, 
                t.start_point, 
                t.end_point, 
                COALESCE(fs.direction, '來') as direction,
                t.status,
                t.driver_id,
                t.trip_type,
                t.custom_start_point,
                t.custom_end_point
            FROM 
                trips t
            LEFT JOIN
                fixed_schedules fs ON t.fixed_trip_id = fs.id
            WHERE 
                t.date = '{query_date}'
                AND t.status != '已完成'
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
                t.trip_id, 
                t.date,
                t.time, 
                t.start_point, 
                t.end_point, 
                COALESCE(fs.direction, '來') as direction,
                t.status,
                t.driver_id,
                t.trip_type,
                t.custom_start_point,
                t.custom_end_point
            FROM 
                trips t
            LEFT JOIN
                fixed_schedules fs ON t.fixed_trip_id = fs.id
            WHERE 
                t.date = '{query_date}'
                AND t.status != '已完成'
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
            
            # 根據狀態添加不同的表情符號
            status_emoji = {
                "準備": "🟢",
                "完成": "✅",
                "取消": "❌",
                "衝突": "⚠️",
                "請假": "🔵",
                "待派": "🟠"
            }.get(status, "⚪")
            
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
            
            # 根據方向決定顯示的地點
            if direction == "來":
                location = start_point
            else:
                location = end_point
            
            # 根據狀態添加不同的表情符號
            status_emoji = {
                "準備": "🟢",
                "完成": "✅",
                "取消": "❌",
                "衝突": "⚠️",
                "請假": "🔵",
                "待派": "🟠"
            }.get(status, "⚪")
            
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
