from datetime import datetime, timedelta, timezone
from sqlalchemy import text, Row
from sqlalchemy.engine import ResultProxy
from flask import current_app
import traceback
from modules.utils.taiwan_time import get_taiwan_time, get_taiwan_date
from modules.utils.helpers import row_to_dict

from modules.models.base import db

def schedule_all_trip_updates(app):
    """安排所有未來班次的自動更新任務"""
    with app.app_context():
        try:
            # 獲取當前日期和時間
            now = get_taiwan_time()
            taiwan_tz = timezone(timedelta(hours=8))
            
            # 查詢所有狀態為"準備"且時間在未來的班次
            query = """
            SELECT 
                t.trip_id, 
                t.date, 
                t.time
            FROM 
                trips t
            WHERE 
                t.status = '準備'
                AND (t.date > :current_date OR (t.date = :current_date AND t.time > :current_time))
            ORDER BY
                t.date, t.time
            """
            
            future_trips = db.session.execute(
                text(query), 
                {
                    "current_date": get_taiwan_date(),
                    "current_time": now.time()
                }
            ).fetchall()
            
            # 為每個未來班次安排更新任務
            for trip in future_trips:
                trip_id = trip[0]
                trip_date = trip[1]
                trip_time = trip[2]
                
                # 計算執行時間（班次時間後5分鐘）
                # 使用timezone添加时区信息
                execution_datetime = datetime.combine(trip_date, trip_time)
                execution_time = execution_datetime.replace(tzinfo=taiwan_tz) + timedelta(minutes=5)
                
                # 如果執行時間已經過去，跳過
                if execution_time < now:
                    continue
                
                # 創建任務ID
                job_id = f"update_trip_{trip_id}"
                
                # 檢查任務是否已經存在
                existing_job = current_app.scheduler.get_job(job_id)
                if existing_job:
                    continue
                
                # 安排任務
                current_app.scheduler.add_job(
                    id=job_id,
                    func=update_single_trip,
                    args=[current_app._get_current_object(), trip_id],
                    trigger='date',
                    run_date=execution_time,
                    timezone='Asia/Taipei'
                )
                
                current_app.logger.info(f"已安排班次 #{trip_id} 的自動更新任務，執行時間：{execution_time}")
            
        except Exception as e:
            error_msg = f"安排班次更新任務失敗: {str(e)}"
            current_app.logger.error(error_msg)
            traceback.print_exc()

def update_single_trip(app, trip_id):
    """更新單個班次的狀態為已完成"""
    with app.app_context():
        try:
            # 獲取當前日期和時間
            now = get_taiwan_time()
            
            # 查詢班次詳細信息，確保包含 trip_type, custom_start_point, custom_end_point, custom_via_point
            query = """
            SELECT 
                t.trip_id, t.date, t.time, 
                t.start_point, t.via_point, t.end_point, 
                t.meter_fare, t.extra_fare, t.category, t.driver_id,
                t.status, t.unique_code, t.fixed_trip_id,
                t.trip_type, t.custom_start_point, t.custom_end_point, t.custom_via_point
            FROM 
                trips t
            WHERE 
                t.trip_id = :trip_id
            """
            result: ResultProxy = db.session.execute(text(query), {"trip_id": trip_id})
            trip_info_row: Row = result.fetchone()
            
            if not trip_info_row:
                current_app.logger.error(f"找不到班次 #{trip_id}")
                return
            
            trip_info = dict(trip_info_row._mapping) # Convert Row to dict
            
            if not trip_info or trip_info.get('status') != '準備':
                current_app.logger.error(f"找不到班次 #{trip_id}")
                return
            
            # 如果班次狀態不是"準備"，跳過
            if trip_info.get('status') != '準備':
                current_app.logger.info(f"班次 #{trip_id} 狀態不是「準備」，跳過更新")
                return
            
            unique_code = trip_info.get('unique_code')
            
            # 如果沒有唯一識別碼，生成一個
            if not unique_code:
                if trip_info.get('fixed_trip_id'):  # fixed_trip_id
                    # 計算一年中的第幾天和第幾周
                    day_of_year = trip_info.get('date').timetuple().tm_yday
                    _, week_number, _ = trip_info.get('date').isocalendar()
                    unique_code = f"{trip_info.get('fixed_trip_id')}_{day_of_year}_{week_number}"
                else:
                    # 臨時班次：加入日期信息避免 trip_id 重複問題
                    date_str = trip_info.get('date').strftime('%Y%m%d')
                    unique_code = f"T_{trip_id}_{date_str}"
                    # 對於非固定班次，也需要計算週數
                    _, week_number, _ = trip_info.get('date').isocalendar()
                
                # 更新班次的唯一識別碼和週數
                update_query = """
                UPDATE trips 
                SET unique_code = :unique_code, week_number = :week_number
                WHERE trip_id = :trip_id
                """
                
                db.session.execute(
                    text(update_query), 
                    {
                        "unique_code": unique_code,
                        "week_number": week_number,
                        "trip_id": trip_id
                    }
                )
            
            # 檢查是否已經在completed_trips表中
            check_query = """
            SELECT COUNT(*) FROM completed_trips 
            WHERE unique_code = :unique_code
            """
            
            existing_count = db.session.execute(
                text(check_query), 
                {"unique_code": unique_code}
            ).fetchone()[0]
            
            if existing_count > 0:
                current_app.logger.info(f"班次 #{trip_id} 已經在已完成班次表中，跳過更新")
                return
            
            # --- 修改插入 completed_trips 的邏輯 ---
            # 移除 custom_start_point, custom_end_point 列
            insert_query = """
            INSERT INTO completed_trips
            (date, start_point, via_point, end_point,
             meter_fare, extra_fare, category, driver_id,
             unique_code, trip_type, passenger_name,
             passenger_leave_reason, modification_reason)
            VALUES
            (:date, :start_point, :via_point, :end_point,
             :meter_fare, :extra_fare, :category, :driver_id,
             :unique_code, :trip_type, :passenger_name,
             :passenger_leave_reason, :modification_reason)
            """

            params = {
                "date": trip_info.get('date'),
                # "via_point": trip_info.get('via_point'), # via_point needs conditional logic too
                "meter_fare": trip_info.get('meter_fare'),
                "extra_fare": trip_info.get('extra_fare'),
                "category": trip_info.get('category'),
                "driver_id": trip_info.get('driver_id'),
                "unique_code": unique_code,
                "trip_type": trip_info.get('trip_type'),
                "passenger_name": trip_info.get('passenger_name'),
                "passenger_leave_reason": trip_info.get('passenger_leave_reason'),
                "modification_reason": trip_info.get('modification_reason')
            }

            # 根據 trip_type 設置地點
            trip_type = trip_info.get('trip_type')
            if trip_type == 'fixed': # 如果是固定班次
                params["start_point"] = trip_info.get('start_point') # Assume this is the text representation needed
                params["end_point"] = trip_info.get('end_point')     # Assume this is the text representation needed
                params["via_point"] = trip_info.get('via_point')     # Assume this is the text representation needed
                current_app.logger.info(f"固定班次 #{trip_id}，將標準地點寫入 completed_trips 的標準欄位")
            elif trip_type == 'temp': # 如果是臨時班次
                params["start_point"] = trip_info.get('custom_start_point') # Use custom start_point from trips
                params["end_point"] = trip_info.get('custom_end_point')   # Use custom end_point from trips
                # Assuming trips table has custom_via_point. If not, this will be None.
                params["via_point"] = trip_info.get('custom_via_point') # Use custom via_point from trips
                current_app.logger.info(f"臨時班次 #{trip_id}，將自定義地點寫入 completed_trips 的標準欄位")
            else: # 其他未知類型，都設為 NULL
                params["start_point"] = None
                params["end_point"] = None
                params["via_point"] = None
                current_app.logger.warning(f"班次 #{trip_id} 類型未知 ({trip_type})，地點設置為 NULL")

            # 添加日誌記錄要插入的參數 (遮蔽敏感信息，如果有的話)
            current_app.logger.info(f"準備插入 completed_trips (single): {params}")

            try:
                db.session.execute(text(insert_query), params)
                current_app.logger.info(f"已將班次 #{trip_id} 插入到已完成班次表中")
            except Exception as e:
                current_app.logger.error(f"將班次 #{trip_id} 插入到已完成班次表中時出錯: {e}")
                raise
            
            # 更新trips表中的狀態為"已完成"
            update_query = "UPDATE trips SET status = '已完成' WHERE trip_id = :trip_id"
            db.session.execute(text(update_query), {"trip_id": trip_id})
            
            # 提交事務
            db.session.commit()
            
            current_app.logger.info(f"成功更新班次 #{trip_id} 為已完成")
            
        except Exception as e:
            # 發生錯誤時回滾事務
            db.session.rollback()
            error_msg = f"更新班次 #{trip_id} 失敗: {str(e)}"
            current_app.logger.error(error_msg)
            traceback.print_exc()

def update_completed_trips():
    """
    自動更新已完成的班次：
    1. 查找所有狀態為"準備"且時間已過的班次
    2. 將它們標記為"已完成"
    3. 將它們複製到已完成班次資料表
    """
    try:
        now = get_taiwan_time()
        current_app.logger.info(f"開始執行更新已完成班次任務...")
        
        current_date = get_taiwan_date()
        current_time = now.time()
        current_app.logger.info(f"當前日期: {current_date}, 當前時間: {current_time}")
        
        # 查詢所有狀態為"準備"且時間已過的班次
        query = """
        SELECT 
            t.trip_id
        FROM 
            trips t
        WHERE 
            t.status = '準備'
            AND (t.date < :current_date OR (t.date = :current_date AND t.time < :current_time))
        """
        
        try:
            completed_trips = db.session.execute(
                text(query), 
                {
                    "current_date": current_date,
                    "current_time": current_time
                }
            ).fetchall()
            current_app.logger.info(f"找到 {len(completed_trips)} 個需要更新的班次")
        except Exception as e:
            current_app.logger.error(f"查詢需要更新的班次時出錯: {e}")
            db.session.rollback()
            raise
        
        if not completed_trips:
            current_app.logger.info("沒有需要更新的已完成班次")
            return "沒有需要更新的已完成班次。"
        
        # 更新每個班次
        updated_count = 0
        error_count = 0
        skipped_count = 0
        
        for trip_row in completed_trips: # Rename variable
            trip_id = trip_row[0]
            current_app.logger.info(f"開始處理班次 #{trip_id}")
            
            try:
                # 查詢班次詳細信息
                query = text("""
                SELECT 
                    t.trip_id, t.date, t.time, 
                    t.start_point, t.via_point, t.end_point, 
                    t.meter_fare, t.extra_fare, t.category, t.driver_id,
                    t.status, t.unique_code, t.fixed_trip_id,
                    t.trip_type, t.custom_start_point, t.custom_end_point, t.custom_via_point, t.passenger_name,
                    t.passenger_leave_reason, t.modification_reason
                FROM trips t WHERE t.trip_id = :trip_id FOR UPDATE
                """)
                result: ResultProxy = db.session.execute(query, {"trip_id": trip_id})
                trip_info_row: Row = result.fetchone() 
                trip_info = dict(trip_info_row._mapping) # Convert Row to dict
                
                if not trip_info:
                    current_app.logger.warning(f"找不到班次 #{trip_id}，可能已被刪除")
                    error_count += 1
                    continue
                
                if trip_info.get('status') != '準備':
                    current_app.logger.info(f"班次 #{trip_id} 狀態為「{trip_info.get('status')}」，不是「準備」，跳過更新")
                    skipped_count += 1
                    continue
                    
                unique_code = trip_info.get('unique_code')
                
                if not unique_code:
                    if trip_info.get('fixed_trip_id'):  # fixed_trip_id
                        # 計算一年中的第幾天和第幾周
                        day_of_year = trip_info.get('date').timetuple().tm_yday
                        _, week_number, _ = trip_info.get('date').isocalendar()
                        unique_code = f"{trip_info.get('fixed_trip_id')}_{day_of_year}_{week_number}"
                    else:
                        # 臨時班次：加入日期信息避免 trip_id 重複問題
                        date_str = trip_info.get('date').strftime('%Y%m%d')
                        unique_code = f"T_{trip_id}_{date_str}"
                        # 對於非固定班次，也需要計算週數
                        _, week_number, _ = trip_info.get('date').isocalendar()
                    
                    # 更新班次的唯一識別碼和週數
                    update_query = """
                    UPDATE trips 
                    SET unique_code = :unique_code, week_number = :week_number
                    WHERE trip_id = :trip_id
                    """
                    
                    try:
                        db.session.execute(
                            text(update_query), 
                            {
                                "unique_code": unique_code,
                                "week_number": week_number,
                                "trip_id": trip_id
                            }
                        )
                        current_app.logger.info(f"已更新班次 #{trip_id} 的唯一識別碼為 {unique_code}")
                    except Exception as e:
                        current_app.logger.error(f"更新班次 #{trip_id} 的唯一識別碼時出錯: {e}")
                        raise
                
                # 檢查是否已經在completed_trips表中
                check_query = """
                SELECT COUNT(*) FROM completed_trips 
                WHERE unique_code = :unique_code
                """
                
                try:
                    existing_count = db.session.execute(
                        text(check_query), 
                        {"unique_code": unique_code}
                    ).fetchone()[0]
                except Exception as e:
                    current_app.logger.error(f"檢查班次 #{trip_id} 是否已在已完成班次表中時出錯: {e}")
                    raise
                
                if existing_count > 0:
                    current_app.logger.info(f"班次 #{trip_id} 已經在已完成班次表中，跳過更新")
                    skipped_count += 1
                    continue
                
                # --- 修改插入 completed_trips 的邏輯 ---
                # 移除 custom_start_point, custom_end_point 列
                insert_query = """
                INSERT INTO completed_trips
                (date, start_point, via_point, end_point,
                 meter_fare, extra_fare, category, driver_id,
                 unique_code, trip_type, passenger_name,
                 passenger_leave_reason, modification_reason)
                VALUES
                (:date, :start_point, :via_point, :end_point,
                 :meter_fare, :extra_fare, :category, :driver_id,
                 :unique_code, :trip_type, :passenger_name,
                 :passenger_leave_reason, :modification_reason)
                """

                params = {
                    "date": trip_info.get('date'),
                    # "via_point": trip_info.get('via_point'), # via_point needs conditional logic too
                    "meter_fare": trip_info.get('meter_fare'),
                    "extra_fare": trip_info.get('extra_fare'),
                    "category": trip_info.get('category'),
                    "driver_id": trip_info.get('driver_id'),
                    "unique_code": unique_code,
                    "trip_type": trip_info.get('trip_type'),
                    "passenger_name": trip_info.get('passenger_name'),
                    "passenger_leave_reason": trip_info.get('passenger_leave_reason'),
                    "modification_reason": trip_info.get('modification_reason')
                }

                # 根據 trip_type 設置地點
                trip_type = trip_info.get('trip_type')
                if trip_type == 'fixed': # 如果是固定班次
                    params["start_point"] = trip_info.get('start_point') # Assume this is the text representation needed
                    params["end_point"] = trip_info.get('end_point')     # Assume this is the text representation needed
                    params["via_point"] = trip_info.get('via_point')     # Assume this is the text representation needed
                    current_app.logger.info(f"固定班次 #{trip_id}，將標準地點寫入 completed_trips 的標準欄位")
                elif trip_type == 'temp': # 如果是臨時班次
                    params["start_point"] = trip_info.get('custom_start_point') # Use custom start_point from trips
                    params["end_point"] = trip_info.get('custom_end_point')   # Use custom end_point from trips
                    # Assuming trips table has custom_via_point. If not, this will be None.
                    params["via_point"] = trip_info.get('custom_via_point') # Use custom via_point from trips
                    current_app.logger.info(f"臨時班次 #{trip_id}，將自定義地點寫入 completed_trips 的標準欄位")
                else: # 其他未知類型，都設為 NULL
                    params["start_point"] = None
                    params["end_point"] = None
                    params["via_point"] = None
                    current_app.logger.warning(f"班次 #{trip_id} 類型未知 ({trip_type})，地點設置為 NULL")

                # 添加日誌記錄要插入的參數 (遮蔽敏感信息，如果有的話)
                current_app.logger.info(f"準備插入 completed_trips: {params}")

                try:
                    db.session.execute(text(insert_query), params)
                    current_app.logger.info(f"已將班次 #{trip_id} 插入到已完成班次表中")
                except Exception as e:
                    current_app.logger.error(f"將班次 #{trip_id} 插入到已完成班次表中時出錯: {e}")
                    raise
                
                # 更新trips表中的狀態為"已完成"
                update_trips_query = text("UPDATE trips SET status = '已完成' WHERE trip_id = :trip_id")
                db.session.execute(update_trips_query, {"trip_id": trip_id})
                current_app.logger.info(f"已將班次 #{trip_id} 的狀態更新為「已完成」")
                    
                updated_count += 1
                    
            except Exception as e:
                current_app.logger.error(f"處理班次 #{trip_id} 時出錯: {e}")
                traceback.print_exc()
                error_count += 1
                db.session.rollback()
                continue
        
        # 提交事務
        try:
            db.session.commit()
            current_app.logger.info("成功提交所有更新")
        except Exception as e:
            current_app.logger.error(f"提交事務時出錯: {e}")
            db.session.rollback()
            raise
        
        result_message = f"更新已完成班次任務結束。成功: {updated_count}, 跳過: {skipped_count}, 錯誤: {error_count}"
        current_app.logger.info(result_message)
        return f"✅ {result_message}"
            
    except Exception as e:
        error_msg = f"更新已完成班次任務失敗: {e}"
        try:
            db.session.rollback()
            current_app.logger.info("Rolled back session due to outer exception in update_completed_trips")
        except Exception as rb_ex:
            current_app.logger.error(f"Rollback failed in outer exception handler: {rb_ex}")
        try:
            current_app.logger.error(error_msg)
        except RuntimeError:
             print(f"ERROR (outside context): {error_msg}") # fallback
        traceback.print_exc()
        return error_msg

def initialize_unique_codes():
    """初始化所有沒有唯一識別碼的班次"""
    try:
        now = get_taiwan_time()
        current_app.logger.info(f"開始初始化班次唯一識別碼...")
        
        # 查詢所有沒有唯一識別碼的班次
        query = """
        SELECT 
            trip_id, 
            date, 
            fixed_trip_id
        FROM 
            trips
        WHERE 
            unique_code IS NULL
        """
        
        trips = db.session.execute(text(query)).fetchall()
        current_app.logger.info(f"找到 {len(trips)} 個沒有唯一識別碼的班次")
        
        updated_trips_count = 0
        for trip in trips:
            try:
                trip_id = trip[0]
                date_obj = trip[1]
                fixed_trip_id = trip[2]
                
                if not date_obj:
                    current_app.logger.error(f"班次 #{trip_id} 沒有日期信息，無法生成唯一識別碼")
                    continue
                
                # 計算一年中的第幾天和第幾周
                day_of_year = date_obj.timetuple().tm_yday
                _, week_number, _ = date_obj.isocalendar()
                
                # 生成唯一識別碼
                if fixed_trip_id:
                    unique_code = f"{fixed_trip_id}_{day_of_year}_{week_number}"
                else:
                    # 臨時班次：加入日期信息避免 trip_id 重複問題
                    date_str = date_obj.strftime('%Y%m%d')
                    unique_code = f"T_{trip_id}_{date_str}"
                
                # 更新班次的唯一識別碼和週數
                update_query = """
                UPDATE trips 
                SET unique_code = :unique_code, week_number = :week_number
                WHERE trip_id = :trip_id
                """
                
                db.session.execute(
                    text(update_query), 
                    {
                        "unique_code": unique_code,
                        "week_number": week_number,
                        "trip_id": trip_id
                    }
                )
                updated_trips_count += 1
                
            except Exception as e:
                current_app.logger.error(f"更新班次 #{trip_id} 的唯一識別碼時出錯: {e}")
                traceback.print_exc()
        
        # 查詢所有沒有唯一識別碼的已完成班次
        completed_query = """
        SELECT 
            id, 
            date
        FROM 
            completed_trips
        WHERE 
            unique_code IS NULL
        """
        
        completed_trips = db.session.execute(text(completed_query)).fetchall()
        current_app.logger.info(f"找到 {len(completed_trips)} 個沒有唯一識別碼的已完成班次")
        
        updated_completed_count = 0
        for trip in completed_trips:
            try:
                trip_id = trip[0]
                
                # 生成唯一識別碼（臨時班次）
                unique_code = f"C_{trip_id}"
                
                # 更新已完成班次的唯一識別碼
                update_query = """
                UPDATE completed_trips 
                SET unique_code = :unique_code 
                WHERE id = :id
                """
                
                db.session.execute(
                    text(update_query), 
                    {
                        "unique_code": unique_code,
                        "id": trip_id
                    }
                )
                updated_completed_count += 1
                
            except Exception as e:
                current_app.logger.error(f"更新已完成班次 #{trip_id} 的唯一識別碼時出錯: {e}")
                traceback.print_exc()
        
        # 提交事務
        db.session.commit()
        
        current_app.logger.info(f"初始化班次唯一識別碼任務結束。成功更新班次: {updated_trips_count}, 已完成班次: {updated_completed_count}")
        return f"✅ 成功初始化 {updated_trips_count} 筆班次和 {updated_completed_count} 筆已完成班次的唯一識別碼。"
            
    except Exception as e:
        db.session.rollback()
        error_msg = f"初始化班次唯一識別碼任務失敗: {e}"
        try:
            current_app.logger.error(error_msg)
        except RuntimeError:
             print(f"ERROR (outside context): {error_msg}") # fallback
        traceback.print_exc()
        return f"初始化唯一識別碼失敗: {str(e)}"

# 創建初始化排程任務的函數
def init_scheduler(app):
    """初始化排程任務"""

    # 包裝函數：為 update_completed_trips 提供上下文
    def update_completed_wrapper():
        with app.app_context():
            update_completed_trips()

    # 包裝函數：為 initialize_unique_codes 提供上下文
    def initialize_codes_wrapper():
        with app.app_context():
            initialize_unique_codes()

    # schedule_all_trip_updates 任務定義 (這個函數內部已有上下文處理)
    app.scheduler.add_job(
        id='schedule_daily_updates',
        func=schedule_all_trip_updates,
        args=[app],
        trigger='cron',
        hour=0, minute=0, timezone='Asia/Taipei',
        replace_existing=True
    )

    # hourly_update_completed 任務定義 (使用包裝函數)
    app.scheduler.add_job(
        id='hourly_update_completed',
        func=update_completed_wrapper, # <--- 使用包裝函數
        trigger='cron',
        hour='*', minute=0, timezone='Asia/Taipei',
        replace_existing=True
    )

    # hourly_update_unique_codes 任務定義 (使用包裝函數)
    app.scheduler.add_job(
        id='hourly_update_unique_codes',
        func=initialize_codes_wrapper, # <--- 使用包裝函數
        trigger='cron',
        hour='*', minute=30, timezone='Asia/Taipei',
        replace_existing=True
    ) 