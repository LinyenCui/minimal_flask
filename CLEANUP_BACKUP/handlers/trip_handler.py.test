from models import db
from sqlalchemy import text as sql_text
from datetime import date, datetime
from flask import current_app
import traceback

# 處理查詢班次命令
def handle_query_trips(message_text):
    try:
        # 解析參數
        parts = message_text.split()
        
        # 默認查詢今天的班次
        query_date = date.today()
        
        # 如果提供了日期參數，則使用指定日期
        if len(parts) > 1:
            try:
                # 嘗試解析日期格式 YYYY-MM-DD
                query_date = datetime.strptime(parts[1], "%Y-%m-%d").date()
            except ValueError:
                return "日期格式不正確。請使用格式：YYYY-MM-DD"
        
        # 使用應用上下文和DB_ENGINE進行數據庫操作
        with current_app.app_context():
            engine = current_app.config['DB_ENGINE']
            with engine.connect() as conn:
                try:
                    # 查詢指定日期的班次
                    query = """
                    SELECT t.trip_id, t.date, t.time, t.start_point, t.end_point, 
                           c_start.short_name as pickup_location, c_end.short_name as dropoff_location,
                           c_start.name as customer_name, c_start.address as customer_phone, t.status, t.driver_id, d.name as driver_name
                    FROM trips t
                    LEFT JOIN drivers d ON t.driver_id = d.id
                    LEFT JOIN customers c_start ON t.start_point = c_start.id
                    LEFT JOIN customers c_end ON t.end_point = c_end.id
                    WHERE DATE(t.date) = :query_date
                    ORDER BY t.time
                    """
                    
                    trips = conn.execute(sql_text(query), {"query_date": query_date}).fetchall()
                    
                    if not trips:
                        return f"📅 {query_date} 沒有安排班次。"
                    
                    # 格式化結果
                    result = f"📅 {query_date} 班次列表：\n\n"
                    
                    for trip in trips:
                        pickup_time = f"{trip.date.strftime('%Y-%m-%d')} {trip.time.strftime('%H:%M')}" if hasattr(trip, 'time') and trip.time else "未知時間"
                        driver_info = f"👨‍✈️ {trip.driver_name}" if trip.driver_name else "🚫 未指派司機"
                        
                        result += (f"🔢 班次ID: {trip.trip_id}\n"
                                  f"⏰ 接送時間: {pickup_time}\n"
                                  f"📍 接送地點: {trip.pickup_location}\n"
                                  f"🏁 目的地: {trip.dropoff_location}\n"
                                  f"👤 客戶: {trip.customer_name} ({trip.customer_phone})\n"
                                  f"🚦 狀態: {trip.status}\n"
                                  f"{driver_info}\n\n")
                    
                    return result
                except Exception as e:
                    print(f"查詢班次時出錯: {e}")
                    print(traceback.format_exc())
                    raise
    except Exception as e:
        print(f"處理查詢班次命令時出錯: {e}")
        print(traceback.format_exc())
        return f"查詢班次失敗: {str(e)}"

# 處理待派班次命令
def handle_pending_trips():
    try:
        # 使用應用上下文和DB_ENGINE進行數據庫操作
        with current_app.app_context():
            engine = current_app.config['DB_ENGINE']
            with engine.connect() as conn:
                try:
                    # 查詢待派班次
                    pending_query = """
                    SELECT t.trip_id, t.date, t.time, 
                           c_start.short_name as pickup_location, c_end.short_name as dropoff_location,
                           c_start.name as customer_name, c_start.address as customer_phone
                    FROM trips t
                    LEFT JOIN customers c_start ON t.start_point = c_start.id
                    LEFT JOIN customers c_end ON t.end_point = c_end.id
                    WHERE t.status = '待派' 
                    ORDER BY t.date, t.time
                    """
                    pending_trips = conn.execute(sql_text(pending_query)).fetchall()
                    
                    # 查詢可用司機
                    drivers_query = """
                    SELECT driver_id, name, phone
                    FROM drivers
                    WHERE active = TRUE
                    ORDER BY name
                    """
                    available_drivers = conn.execute(sql_text(drivers_query)).fetchall()
                    
                    if not pending_trips:
                        return "📋 目前沒有待派班次。"
                    
                    # 格式化結果
                    result = "📋 待派班次列表：\n\n"
                    
                    for trip in pending_trips:
                        pickup_time = f"{trip.date.strftime('%Y-%m-%d')} {trip.time.strftime('%H:%M')}" if hasattr(trip, 'date') and hasattr(trip, 'time') else "未知時間"
                        
                        result += (f"🔢 班次ID: {trip.trip_id}\n"
                                  f"⏰ 接送時間: {pickup_time}\n"
                                  f"📍 接送地點: {trip.pickup_location}\n"
                                  f"🏁 目的地: {trip.dropoff_location}\n"
                                  f"👤 客戶: {trip.customer_name} ({trip.customer_phone})\n\n")
                    
                    # 添加可用司機列表
                    if available_drivers:
                        result += "👨‍✈️ 可用司機列表：\n"
                        for driver in available_drivers:
                            result += f"ID: {driver.driver_id}, 姓名: {driver.name}, 電話: {driver.phone}\n"
                    else:
                        result += "⚠️ 目前沒有可用司機。\n"
                    
                    # 添加指派司機的指令說明
                    result += "\n💡 指派司機指令：指派司機 [班次ID] [司機ID]"
                    
                    return result
                except Exception as e:
                    print(f"查詢待派班次時出錯: {e}")
                    print(traceback.format_exc())
                    raise
    except Exception as e:
        print(f"處理待派班次命令時出錯: {e}")
        print(traceback.format_exc())
        return f"查詢待派班次失敗: {str(e)}"

# 處理更改班次狀態命令
def handle_change_status(message_text):
    try:
        # 解析參數
        parts = message_text.split()
        if len(parts) < 3:
            return "更改狀態命令格式不正確。正確格式：更改狀態 [班次ID] [新狀態]"
        
        trip_id = int(parts[1])
        new_status = parts[2]
        
        # 檢查狀態是否有效
        valid_statuses = ['準備', '待派', '取消', '衝突', '完成']
        if new_status not in valid_statuses:
            raise ValueError(f"無效的狀態: {new_status}。有效狀態: {', '.join(valid_statuses)}")
        
        # 使用應用上下文和DB_ENGINE進行數據庫操作
        with current_app.app_context():
            engine = current_app.config['DB_ENGINE']
            with engine.connect() as conn:
                # 開始事務
                trans = conn.begin()
                try:
                    # 檢查班次是否存在
                    trip_query = "SELECT trip_id, status FROM trips WHERE trip_id = :trip_id"
                    trip = conn.execute(sql_text(trip_query), {"trip_id": trip_id}).fetchone()
                    
                    if not trip:
                        raise ValueError(f"找不到ID為 {trip_id} 的班次")
                    
                    # 更新當前班次狀態
                    update_query = """
                    UPDATE trips 
                    SET status = :new_status 
                    WHERE trip_id = :trip_id
                    """
                    conn.execute(
                        sql_text(update_query), 
                        {
                            "new_status": new_status,
                            "trip_id": trip_id
                        }
                    )
                    
                    # 提交事務
                    trans.commit()
                    
                    # 發送確認消息
                    return f"✅ 已成功將班次 {trip_id} 的狀態更改為 '{new_status}'。"
                except Exception as e:
                    # 發生錯誤時回滾事務
                    trans.rollback()
                    print(f"更改狀態時出錯: {e}")
                    print(traceback.format_exc())
                    raise
    except ValueError as e:
        return f"更改狀態失敗: {str(e)}"
    except Exception as e:
        print(f"處理更改狀態命令時出錯: {e}")
        print(traceback.format_exc())
        return f"更改狀態失敗: {str(e)}"

# 處理導入固定班次命令
def handle_import_fixed_trips(message_text):
    try:
        # 解析參數
        parts = message_text.split()
        if len(parts) < 2:
            return "導入固定班次命令格式不正確。正確格式：導入固定班次 [日期]"
        
        try:
            # 嘗試解析日期格式 YYYY-MM-DD
            target_date = datetime.strptime(parts[1], "%Y-%m-%d").date()
        except ValueError:
            return "日期格式不正確。請使用格式：YYYY-MM-DD"
        
        # 獲取星期幾 (0=星期一, 6=星期日)
        weekday = target_date.weekday()
        
        # 使用應用上下文和DB_ENGINE進行數據庫操作
        with current_app.app_context():
            engine = current_app.config['DB_ENGINE']
            with engine.connect() as conn:
                # 開始事務
                trans = conn.begin()
                try:
                    # 查詢指定星期的固定班次
                    fixed_query = """
                    SELECT fs.id as schedule_id, fs.weekday, fs.departure_time as time, 
                           c_start.short_name as pickup_location, c_end.short_name as dropoff_location, 
                           c_start.id as customer_id, c_start.name as customer_name, c_start.address as customer_phone
                    FROM fixed_schedules fs
                    JOIN customers c_start ON fs.start_point = c_start.id
                    JOIN customers c_end ON fs.end_point = c_end.id
                    WHERE fs.weekday = :weekday
                    ORDER BY fs.departure_time
                    """
                    
                    fixed_schedules = conn.execute(sql_text(fixed_query), {"weekday": weekday}).fetchall()
                    
                    if not fixed_schedules:
                        return f"沒有找到星期{weekday+1}的固定班次。"
                    
                    # 檢查是否已經導入
                    check_query = """
                    SELECT COUNT(*) as count
                    FROM trips
                    WHERE DATE(date) = :target_date
                    AND fixed_trip_id IS NOT NULL
                    """
                    
                    existing_count = conn.execute(sql_text(check_query), {"target_date": target_date}).fetchone()
                    
                    if existing_count and existing_count.count > 0:
                        return f"⚠️ {target_date} 的固定班次已經導入。如需重新導入，請先刪除現有班次。"
                    
                    # 導入固定班次
                    imported_count = 0
                    for schedule in fixed_schedules:
                        # 創建完整的日期時間
                        schedule_time = datetime.strptime(schedule.time, "%H:%M").time()
                        pickup_datetime = datetime.combine(target_date, schedule_time)
                        
                        # 插入新班次
                        insert_query = """
                        INSERT INTO trips (
                            date, time, start_point, end_point, 
                            driver_id, status, fixed_trip_id
                        ) VALUES (
                            :date, :time, :start_point, :end_point,
                            NULL, '待派', :fixed_trip_id
                        )
                        """
                        
                        conn.execute(sql_text(insert_query), {
                            "date": pickup_datetime.date(),
                            "time": pickup_datetime.time(),
                            "start_point": schedule.customer_id,
                            "end_point": schedule.customer_id,
                            "fixed_trip_id": schedule.schedule_id
                        })
                        
                        imported_count += 1
                    
                    # 提交事務
                    trans.commit()
                    
                    return f"✅ 成功導入 {target_date} 的 {imported_count} 個固定班次。"
                except Exception as e:
                    # 發生錯誤時回滾事務
                    trans.rollback()
                    print(f"導入固定班次時出錯: {e}")
                    print(traceback.format_exc())
                    raise
    except Exception as e:
        print(f"處理導入固定班次命令時出錯: {e}")
        print(traceback.format_exc())
        return f"導入固定班次失敗: {str(e)}"

# 處理更新班次狀態命令
def handle_update_status():
    try:
        # 獲取當前日期和時間
        now = datetime.now()
        today = now.date()
        current_time = now.time()
        
        # 更新過期的"準備"狀態班次為"完成"
        past_date_query = """
        UPDATE trips 
        SET status = '完成' 
        WHERE status = '準備' AND date < :today
        """
        
        db.session.execute(
            sql_text(past_date_query), 
            {"today": today}
        )
        
        # 更新當天已過時間的"準備"狀態班次為"完成"
        past_time_query = """
        UPDATE trips 
        SET status = '完成' 
        WHERE status = '準備' AND date = :today AND time < :current_time
        """
        
        db.session.execute(
            sql_text(past_time_query), 
            {
                "today": today,
                "current_time": current_time
            }
        )
        
        db.session.commit()
        
        return "✅ 已成功更新班次狀態。過期的班次已標記為'完成'。"
    except Exception as e:
        return f"更新班次狀態失敗: {str(e)}" 