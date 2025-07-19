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
from modules.utils.line_bot import reply_text, reply_flex, get_user_display_name  # 添加必要的LINE Bot工具函数
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
                t.driver_id,
                t.trip_type
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
            trip_type_val = trip[8]
            
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
            reply_text += f"{status_emoji} #{trip[0]} {time_val} {location}{direction} - 🚕{driver_id}\n"
        
        reply_text += "\n輸入「班次詳情 [ID]」查看特定班次的詳細信息。"
        
        return reply_text
        
    except Exception as e:
        logger.error(f"查詢班次錯誤: {str(e)}")
        traceback.print_exc()
        return f"查詢班次錯誤: {str(e)}"

# 處理班次詳情命令
def handle_trip_details(trip_id):
    try:
        logger.info(f"處理班次詳情查詢 (文本版): trip_id={trip_id}") # 更新日誌
        
        # 查詢班次詳情 - 確保包含 trip_type
        query = """
        SELECT 
            t.trip_id, 
            t.date,
            t.time,
            t.start_point, -- 使用原始 short_name
            t.via_point,   -- 使用原始 short_name
            t.end_point,   -- 使用原始 short_name
            t.status,
            t.custom_start_point, # 新增
            t.custom_via_point,   # 新增
            t.custom_end_point,   # 新增
            t.trip_type,          # <--- 確保選取 trip_type
            t.category,
            t.meter_fare,
            t.extra_fare,
            t.actual_fare,
            t.driver_id,          -- 直接獲取 driver_id
            d.name as driver_name, -- 獲取司機名字
            d.plate_number,       -- 獲取車牌
            t.fixed_trip_id,
            t.unique_code
        FROM 
            trips t
        LEFT JOIN 
            drivers d ON t.driver_id = d.id
        WHERE 
            t.trip_id = :trip_id
        """
        
        # 使用 fetchone() 因為我們期望只有一條記錄
        trip_row = db.session.execute(sql_text(query), {"trip_id": trip_id}).fetchone()
        
        if not trip_row:
            # 🚨 新增：智能錯誤提示 - 三時間態引導
            logger.info(f"🔍 生產線上找不到班次 #{trip_id}，提供智能引導")
            
            # 檢查是否在已完成班次中存在相似ID
            completed_query = """
            SELECT COUNT(*) as count 
            FROM completed_trips 
            WHERE id <= :trip_id + 50 AND id >= :trip_id - 50
            """
            completed_count = db.session.execute(sql_text(completed_query), {"trip_id": trip_id}).fetchone()[0]
            
            error_message = f"❌ 在生產線上找不到班次 #{trip_id}\n\n"
            error_message += "💡 可能的原因：\n"
            error_message += "1. 班次已完成並移至成品倉庫\n"
            error_message += "2. 班次ID輸入錯誤\n"
            error_message += "3. 班次已被取消或刪除\n\n"
            
            error_message += "🔍 建議操作：\n"
            
            if completed_count > 0:
                error_message += f"• 查已完成 昨天 → 查看最近完成的班次\n"
                error_message += f"• 查看 {trip_id} → 如果是已完成班次ID\n"
            
            error_message += "• 東洋班次 今天 → 查看今天進行中班次\n"
            error_message += "• 診所班次 今天 → 查看今天診所班次\n"
            error_message += "• 查詢班次 狀態=準備 → 查看準備中班次\n\n"
            
            error_message += "📚 命令說明：\n"
            error_message += "• 班次詳情 [ID] → 查看生產線上的班次 (trips表)\n"
            error_message += "• 查看 [ID] → 查看已完成班次 (completed_trips表)\n"
            
            return error_message
        
        # 將 RowProxy 轉換為字典以便於訪問
        trip = dict(trip_row._mapping if hasattr(trip_row, '_mapping') else trip_row) 

        result_text = f"📋 班次 #{trip.get('trip_id')} 詳細信息：\n\n"
        trip_date_obj = trip.get('date')
        formatted_date = trip_date_obj.strftime("%Y-%m-%d") if trip_date_obj else "未設置"
        weekday_names = ["一", "二", "三", "四", "五", "六", "日"]
        weekday = weekday_names[trip_date_obj.weekday()] if trip_date_obj else ""
        result_text += f"📅 日期: {formatted_date} (星期{weekday})\n"
        
        trip_time_obj = trip.get('time')
        formatted_time = trip_time_obj.strftime("%H:%M") if trip_time_obj else "未設置"
        result_text += f"⏰ 時間: {formatted_time}\n"

        is_temp_booking = trip.get('trip_type') == 'temp'
        start_display = trip.get('custom_start_point') if is_temp_booking and trip.get('custom_start_point') else trip.get('start_point')
        via_display = trip.get('custom_via_point') if is_temp_booking and trip.get('custom_via_point') else trip.get('via_point')
        end_display = trip.get('custom_end_point') if is_temp_booking and trip.get('custom_end_point') else trip.get('end_point')

        result_text += f"📍 起點: {start_display or '未指定'}\n"
        if via_display:
            result_text += f"🚩 經由: {via_display}\n"
        result_text += f"🏁 終點: {end_display or '未指定'}\n"
        
        result_text += f"🚦 狀態: {trip.get('status') or '未指定'}\n"
        result_text += f"🚕 司機: {trip.get('driver_name') or '未指派'}\n"
        if trip.get('plate_number'):
            result_text += f"牌照: {trip.get('plate_number')}\n"
        result_text += f"📊 類別: {trip.get('category') or '未分類'}\n"
        if trip.get('meter_fare') is not None:
            result_text += f"💰 表價: {trip.get('meter_fare')} 元\n"
        if trip.get('extra_fare') is not None:
            result_text += f"💸 加成: {trip.get('extra_fare')} 元\n"
        if trip.get('actual_fare') is not None:
            result_text += f"💲 實收: {trip.get('actual_fare')} 元\n"
        else: # 如果 actual_fare 為空，嘗試計算
            meter = trip.get('meter_fare', 0) or 0
            extra = trip.get('extra_fare', 0) or 0
            result_text += f"💲 實收: {meter + extra} 元\n"

        if trip.get('fixed_trip_id'):
            result_text += f"🔄 固定班次ID: {trip.get('fixed_trip_id')}\n"
        if trip.get('unique_code'):
            result_text += f"🔑 唯一碼: {trip.get('unique_code')}\n"
        
        return result_text
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

def handle_record_fare(message_text, user_id=None):
    """處理記錄已完成班次車資的命令 - 增強版：支持修改原因追蹤"""
    try:
        parts = message_text.split()
        
        logger.info(f"🔧 handle_record_fare 收到命令: '{message_text}'")
        
        if len(parts) < 3:
            return "命令格式不正確。正確格式：記錄車資 [ID] [錶價] [加成] [修改原因]"
            
        completed_trip_id = None
        meter_fare = None
        extra_fare = 0
        reason = None
        
        # 解析參數並進行類型檢查
        try:
            completed_trip_id = int(parts[1])
        except ValueError:
            return "錯誤：班次 ID 必須是數字。"
            
        try:
            meter_fare = int(parts[2])
        except ValueError:
             return "錯誤：錶價必須是數字。"
             
        if len(parts) >= 4:
            try:
                extra_fare = int(parts[3]) # 允許負數
            except ValueError:
                # 如果第3個參數不是數字，可能是原因
                extra_fare = 0
                reason = ' '.join(parts[3:])
        
        if len(parts) >= 5:
            # 如果有5個或更多參數，第4個開始是原因
            reason = ' '.join(parts[4:])



        # 查找現有記錄並獲取當前值
        query = sql_text("SELECT id, meter_fare, extra_fare FROM completed_trips WHERE id = :id")
        current_trip = db.session.execute(query, {"id": completed_trip_id}).fetchone()
        
        if not current_trip:
            return f"錯誤：找不到已完成班次記錄 ID: {completed_trip_id}"
        
        current_meter = current_trip[1] or 0
        current_extra = current_trip[2] or 0
        
        logger.info(f"🔧 比較數據: 數據庫({current_meter}+{current_extra}) vs 新值({meter_fare}+{extra_fare}), 原因: '{reason}'")
        
        # 🔥 簡化邏輯：按照用戶初衷，只在車資變更時要求原因
        meter_changed = current_meter != meter_fare
        extra_changed = current_extra != extra_fare
        has_changes = meter_changed or extra_changed
        
        # 如果有變更但沒有提供原因，要求說明
        if has_changes and not reason:
            change_summary = []
            if meter_changed:
                change_summary.append(f"錶價: {current_meter} → {meter_fare} ({meter_fare - current_meter:+d})")
            if extra_changed:
                change_summary.append(f"加成: {current_extra} → {extra_fare} ({extra_fare - current_extra:+d})")
            
            return f"""⚠️ 檢測到車資變更，需要說明原因：

📊 當前記錄：
• {chr(10).join(change_summary)}

💡 請使用完整格式：
記錄車資 {completed_trip_id} {meter_fare} {extra_fare} [修改原因]

範例：記錄車資 {completed_trip_id} {meter_fare} {extra_fare} 客戶要求調整價格"""

        # 獲取現有的 modification_reason 以便追加
        current_reason_query = sql_text("SELECT modification_reason FROM completed_trips WHERE id = :id")
        current_reason_result = db.session.execute(current_reason_query, {"id": completed_trip_id}).fetchone()
        current_reason = current_reason_result[0] if current_reason_result else None
        
        # 使用統一的 modification_reason 管理工具
        from modules.utils.modification_utils import build_modification_update_dict
        from modules.utils.taiwan_time import get_taiwan_time
        
        logger.info(f"🔧 準備執行數據庫更新: trip_id={completed_trip_id}, meter={meter_fare}, extra={extra_fare}")
        
        # 獲取用戶顯示名稱
        user_display_name = get_user_display_name(user_id) if user_id else "系統用戶"
        
        # 構建修改信息字典
        modification_updates = build_modification_update_dict(
            current_reason, 
            reason or '車資調整', 
            user_display_name, 
            "completed_trips"
        )
        
        update_query = sql_text("""
        UPDATE completed_trips 
        SET meter_fare = :meter_fare, 
            extra_fare = :extra_fare,
            modified_by = :modified_by,
            modification_reason = :modification_reason,
            modification_time = :modification_time
        WHERE id = :id
        """)
        
        db.session.execute(update_query, {
            "meter_fare": meter_fare,
            "extra_fare": extra_fare,
            "modified_by": modification_updates["modified_by"],
            "modification_reason": modification_updates["modification_reason"],
            "modification_time": modification_updates["modification_time"],
            "id": completed_trip_id
        })
        
        db.session.commit()
        logger.info(f"🔧 數據庫更新完成！")
        
        # 格式化變更信息
        change_info = []
        if meter_changed:
            change_info.append(f"錶價: {current_meter} → {meter_fare}")
        if extra_changed:
            change_info.append(f"加成: {current_extra} → {extra_fare}")
        
        logger.info(f"成功記錄車資 - ID: {completed_trip_id}, 錶價: {meter_fare}, 加成: {extra_fare}, 修改者: {user_id}")
        
        result = f"✅ 成功記錄班次 {completed_trip_id} 車資：錶價={meter_fare}, 加成={extra_fare}"
        if change_info:
            result += f"\n📝 變更記錄：\n• {chr(10).join(change_info)}"
        if reason:
            result += f"\n• 原因: {reason}"
        
        return result

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
        logger.error(f"修改類別錯誤: {str(e)}")
        traceback.print_exc()
        return f"修改類別錯誤: {str(e)}"

# 處理查看已完成班次命令
def handle_completed_trip_details(completed_trip_id):
    """查看已完成班次詳細信息"""
    logger.info(f"處理查看已完成班次查詢: completed_trip_id={completed_trip_id}")
    
    # 查詢已完成班次詳情
    try:
        query = """
        SELECT 
            ct.id,
            ct.date,
            ct.start_point,
            ct.via_point,
            ct.end_point,
            ct.category,
            ct.meter_fare,
            ct.extra_fare,
            ct.driver_id,
            ct.remarks,
            ct.created_at,
            ct.unique_code,
            d.name as driver_name,
            d.plate_number,
            ct.passenger_leave_reason,
            ct.modification_reason
        FROM 
            completed_trips ct
        LEFT JOIN 
            drivers d ON ct.driver_id = d.id
        WHERE 
            ct.id = :completed_trip_id
        """
        
        trip_row = db.session.execute(sql_text(query), {"completed_trip_id": completed_trip_id}).fetchone()
        
        if not trip_row:
            return f"找不到已完成班次 #{completed_trip_id}"
        
        # 轉換為字典
        trip = dict(trip_row._mapping if hasattr(trip_row, '_mapping') else trip_row)
        
        # 格式化結果 - 簡潔版UI
        result_text = f"✅ 已完成班次 #{trip.get('id')}\n\n"
        
        # 基本信息
        trip_date_obj = trip.get('date')
        if trip_date_obj:
            weekday_names = ["一", "二", "三", "四", "五", "六", "日"]
            weekday = weekday_names[trip_date_obj.weekday()]
            formatted_date = f"{trip_date_obj.month}/{trip_date_obj.day} (星期{weekday})"
            result_text += f"📅 {formatted_date}\n"
        
        # 路線信息
        start = trip.get('start_point') or "未指定"
        end = trip.get('end_point') or "未指定"
        via = trip.get('via_point')
        
        if via:
            result_text += f"🚩 {start} → {via} → {end}\n"
        else:
            result_text += f"🚩 {start} → {end}\n"
        
        # 類別和司機
        category = trip.get('category') or "未分類"
        driver_name = trip.get('driver_name')
        driver_id = trip.get('driver_id')
        
        result_text += f"📊 {category} | "
        if driver_name:
            result_text += f"🚕{driver_name}({driver_id})\n"
        elif driver_id:
            result_text += f"🚕司機#{driver_id}\n"
        else:
            result_text += "🚕未指派\n"
        
        # 車資信息
        meter_fare = trip.get('meter_fare')
        extra_fare = trip.get('extra_fare')
        
        if meter_fare is not None or extra_fare is not None:
            meter = meter_fare or 0
            extra = extra_fare or 0
            total = meter + extra
            
            if extra >= 0:
                fare_display = f"{meter}+{extra}"
            else:
                fare_display = f"{meter}{extra}"
            
            result_text += f"💰 {fare_display} = {total}元\n"
        else:
            result_text += f"💰 未記錄車資\n"
        
        # 備註
        remarks = trip.get('remarks')
        if remarks:
            result_text += f"📝 {remarks}\n"
        
        # 🔥 新增：顯示請假原因（如果有）
        passenger_leave_reason = trip.get('passenger_leave_reason')
        if passenger_leave_reason:
            result_text += f"🔵 請假原因: {passenger_leave_reason}\n"
        
        # 🔥 新增：顯示修改原因（如果有且不是請假相關）
        modification_reason = trip.get('modification_reason')
        if modification_reason and not passenger_leave_reason:  # 避免重複顯示請假原因
            result_text += f"🟠 修改原因: {modification_reason}\n"
        
        # 記錄時間
        created_at = trip.get('created_at')
        if created_at:
            result_text += f"\n⏰ 記錄於: {created_at.strftime('%m/%d %H:%M')}"
        
        return result_text
        
    except Exception as e:
        logger.error(f"查看已完成班次錯誤: {str(e)}")
        traceback.print_exc()
        return f"查看已完成班次錯誤: {str(e)}"
