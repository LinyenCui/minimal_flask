# modules/handlers/trip_handler.py
from datetime import date, datetime, timedelta
from flask import current_app
from sqlalchemy import text as sql_text
import traceback
import logging
import pytz

from modules.models.base import db
from modules.models.trip import Trip, FixedSchedule
from modules.models.driver import Driver
from modules.models.customer import Customer
from modules.utils.helpers import parse_date_input
from modules.utils.line_bot import reply_text, reply_flex  # 添加必要的LINE Bot工具函数
from modules.utils.taiwan_time import get_taiwan_time

logger = logging.getLogger(__name__)

# 處理查詢班次命令
def handle_query_trips(message_text=None):
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
                t.driver_id
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
        
        # 按日期分組顯示
        current_date = None
        
        for trip in all_trips:
            trip_id = trip[0]
            trip_date = trip[1]
            time_val = trip[2].strftime("%H:%M") if trip[2] else "--:--"
            direction = trip[5]  # "來" 或 "回"
            
            # 根據方向決定顯示起點還是終點
            if direction == "來":
                location = trip[3] or "未指定"  # 起點
            else:  # "回"
                location = trip[4] or "未指定"  # 終點
            
            status = trip[6] or "未指定"
            driver_id = trip[7] or "未指派"
            
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
            
            # 使用黃色小車表情符號代替"司機#"
            reply_text += f"{status_emoji} #{trip_id} {time_val} {location}{direction} - 🚕{driver_id}\n"
        
        reply_text += "\n輸入「班次詳情 [ID]」查看特定班次的詳細信息。"
        
        return reply_text
        
    except Exception as e:
        logger.error(f"查詢班次錯誤: {str(e)}")
        traceback.print_exc()
        return f"查詢班次錯誤: {str(e)}"

# 處理班次詳情命令
def handle_trip_details(trip_id):
    try:
        # 查詢班次
        trip = db.session.query(
            Trip, Customer, Driver
        ).join(
            Customer, Trip.start_point == Customer.short_name
        ).outerjoin(
            Driver, Trip.driver_id == Driver.id
        ).filter(
            Trip.trip_id == trip_id
        ).first()
        
        if not trip:
            return f"找不到ID為 {trip_id} 的班次"
        
        trip, customer, driver = trip
        
        # 格式化結果
        result = f"📋 班次 #{trip_id} 詳細信息：\n\n"
        
        # 格式化日期和時間
        trip_date = trip.date.strftime("%Y-%m-%d") if trip.date else "未設置"
        trip_time = trip.time.strftime("%H:%M") if trip.time else "未設置"
        
        # 檢查是否為臨時預約
        is_temp_booking = trip.trip_type == 'temp'
        
        # 根據班次類型選擇顯示的起點
        if is_temp_booking and trip.custom_start_point:
            start_display = trip.custom_start_point
        else:
            start_display = f"{customer.short_name} ({customer.name})"
        
        result += (f"📅 日期: {trip_date}\n"
                  f"⏰ 時間: {trip_time}\n"
                  f"📍 起點: {start_display}\n")
        
        # 如果有經由點
        if trip.via_point or (is_temp_booking and trip.custom_via_point):
            if is_temp_booking and trip.custom_via_point:
                result += f"🚩 經由: {trip.custom_via_point}\n"
            else:
                via_customer = db.session.query(Customer).filter(Customer.short_name == trip.via_point).first()
                if via_customer:
                    result += f"🚩 經由: {via_customer.short_name} ({via_customer.name})\n"
                else:
                    result += f"🚩 經由: {trip.via_point}\n"
        
        # 終點
        if is_temp_booking and trip.custom_end_point:
            result += f"🏁 終點: {trip.custom_end_point}\n"
        else:
            end_customer = db.session.query(Customer).filter(Customer.short_name == trip.end_point).first()
            if end_customer:
                result += f"🏁 終點: {end_customer.short_name} ({end_customer.name})\n"
            else:
                result += f"🏁 終點: {trip.end_point}\n"
        
        # 價格信息
        result += (f"💰 表價: {trip.meter_fare or 0}\n"
                  f"💸 加成: {trip.extra_fare or 0}\n"
                  f"💲 實收: {trip.actual_fare or (trip.meter_fare or 0) + (trip.extra_fare or 0)}\n")
        
        # 類別與狀態
        result += (f"📊 類別: {trip.category}\n"
                  f"🚦 狀態: {trip.status}\n")
        
        # 司機信息
        if driver:
            result += (f"👨‍✈️ 司機: {driver.name}\n"
                      f"🚕 車號: {driver.plate_number}\n")
        else:
            result += "🚫 未指派司機\n"
        
        # 如果是固定班次，顯示固定班次ID
        if trip.fixed_trip_id:
            result += f"🔄 固定班次ID: {trip.fixed_trip_id}\n"
        
        # 顯示唯一碼
        if trip.unique_code:
            result += f"🔑 唯一碼: {trip.unique_code}\n"
        
        return result
    except Exception as e:
        current_app.logger.error(f"處理班次詳情命令時出錯: {e}")
        traceback.print_exc()
        return f"查詢班次詳情失敗: {str(e)}"

# 處理修改狀態命令
def handle_change_status(message_text):
    try:
        # 解析參數
        parts = message_text.split()
        if len(parts) < 3:
            return "修改狀態命令格式不正確。正確格式：修改狀態 [班次ID] [新狀態]"
        
        trip_id = int(parts[1])
        new_status = parts[2]
        
        # 檢查狀態是否有效
        user_modifiable_statuses = ['準備', '待派', '取消', '衝突', '請假']
        if new_status not in user_modifiable_statuses:
            return f"無效的狀態: {new_status}。用戶可修改的狀態: {', '.join(user_modifiable_statuses)}\n註：「完成」狀態由系統自動更新。"
        
        # 檢查班次是否存在
        trip = db.session.query(Trip).filter(Trip.trip_id == trip_id).first()
        
        if not trip:
            return f"找不到ID為 {trip_id} 的班次"
        
        # 檢查班次時間是否已過
        current_time = get_taiwan_time()
        
        # 確保比較的日期時間對象類型相同（解決offset-naive和offset-aware比較問題）
        from datetime import datetime
        
        # 將班次日期時間轉換為aware datetime（帶時區信息）
        trip_datetime = datetime.combine(trip.date, trip.time)
        
        # 如果trip_datetime沒有時區信息，添加台灣時區
        if trip_datetime.tzinfo is None:
            taiwan_tz = pytz.timezone('Asia/Taipei')
            trip_datetime = taiwan_tz.localize(trip_datetime)
        
        # 確保current_time也有時區信息
        if current_time.tzinfo is None:
            current_time = taiwan_tz.localize(current_time)
        
        # 如果班次時間已過，不允許修改狀態
        if trip_datetime < current_time:
            return f"⚠️ 無法修改已過時間的班次狀態。班次 {trip_id} 的時間 ({trip.date.strftime('%Y-%m-%d')} {trip.time.strftime('%H:%M')}) 已過。"
        
        # 更新狀態
        trip.status = new_status
        db.session.commit()
        
        return f"✅ 已成功將班次 {trip_id} 的狀態更改為 '{new_status}'。"
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"處理修改狀態命令時出錯: {e}")
        traceback.print_exc()
        return f"修改狀態失敗: {str(e)}"

def handle_record_fare(message_text):
    """處理記錄已完成班次車資的命令 (加成可選，默認為0)"""
    try:
        parts = message_text.split()
        if len(parts) < 3 or len(parts) > 4:
            return "命令格式不正確。正確格式：記錄車資 [ID] [錶價] [加成(可選)]"
            
        completed_trip_id = None
        meter_fare = None
        extra_fare = 0
        
        # 解析參數並進行類型檢查
        try:
            completed_trip_id = int(parts[1])
        except ValueError:
            return "錯誤：班次 ID 必須是數字。"
            
        try:
            meter_fare = int(parts[2])
        except ValueError:
             return "錯誤：錶價必須是數字。"
             
        if len(parts) == 4:
            try:
                extra_fare = int(parts[3]) # 允許負數
            except ValueError:
                 return "錯誤：加成必須是數字。"

        # 查找 completed_trips 記錄
        # 注意：這裡不能使用 FOR UPDATE，因為 completed_trips 是歷史記錄
        query = sql_text("SELECT id FROM completed_trips WHERE id = :id")
        trip = db.session.execute(query, {"id": completed_trip_id}).fetchone()
        
        if not trip:
            return f"錯誤：找不到已完成班次記錄 ID: {completed_trip_id}"
            
        # 更新車資
        update_query = sql_text("""
        UPDATE completed_trips 
        SET meter_fare = :meter_fare, extra_fare = :extra_fare
        WHERE id = :id
        """)
        
        db.session.execute(update_query, {
            "meter_fare": meter_fare,
            "extra_fare": extra_fare,
            "id": completed_trip_id
        })
        
        db.session.commit()
        logger.info(f"成功記錄車資 - ID: {completed_trip_id}, 錶價: {meter_fare}, 加成: {extra_fare}")
        return f"✅ 成功記錄班次 {completed_trip_id} 車資：錶價={meter_fare}, 加成={extra_fare}"

    except Exception as e:
        db.session.rollback() # 確保回滾
        logger.error(f"記錄車資時出錯: {e}")
        traceback.print_exc()
        return f"記錄車資失敗: {str(e)}"

def handle_modify_category(message_text):
    """處理修改已完成班次類別的命令"""
    try:
        parts = message_text.split()
        if len(parts) != 3:
            return "命令格式不正確。正確格式：修改類別 [ID] [新類別]"
            
        completed_trip_id = None
        new_category = None
        valid_categories = ["診所", "東洋", "臨時"] # 根據您的實際情況調整
        
        try:
            completed_trip_id = int(parts[1])
        except ValueError:
            return "錯誤：班次 ID 必須是數字。"
            
        new_category = parts[2]
        if new_category not in valid_categories:
            return f"錯誤：無效的類別 '{new_category}'。請選擇：{', '.join(valid_categories)}"

        # 查找 completed_trips 記錄
        query = sql_text("SELECT id, category FROM completed_trips WHERE id = :id")
        trip = db.session.execute(query, {"id": completed_trip_id}).fetchone()
        
        if not trip:
            return f"錯誤：找不到已完成班次記錄 ID: {completed_trip_id}"
            
        old_category = trip[1]
        if old_category == new_category:
             return f"班次 {completed_trip_id} 的類別已經是 '{new_category}'，無需修改。"
            
        # 更新類別
        update_query = sql_text("""
        UPDATE completed_trips 
        SET category = :category
        WHERE id = :id
        """)
        
        db.session.execute(update_query, {
            "category": new_category,
            "id": completed_trip_id
        })
        
        db.session.commit()
        logger.info(f"成功修改類別 - ID: {completed_trip_id}, 從 {old_category} 改為 {new_category}")
        return f"✅ 成功將班次 {completed_trip_id} 的類別從 '{old_category}' 修改為 '{new_category}'。"

    except Exception as e:
        db.session.rollback() # 確保回滾
        logger.error(f"修改類別時出錯: {e}")
        traceback.print_exc()
        return f"修改類別失敗: {str(e)}"
