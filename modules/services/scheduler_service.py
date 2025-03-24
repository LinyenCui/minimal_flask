from datetime import datetime, timedelta
from sqlalchemy import text
from flask import current_app
import traceback

from modules.models.base import db

def schedule_all_trip_updates(app):
    """安排所有未來班次的自動更新任務"""
    with app.app_context():
        try:
            # 獲取當前日期和時間
            now = datetime.now()
            
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
                    "current_date": now.date(),
                    "current_time": now.time()
                }
            ).fetchall()
            
            # 為每個未來班次安排更新任務
            for trip in future_trips:
                trip_id = trip[0]
                trip_date = trip[1]
                trip_time = trip[2]
                
                # 計算執行時間（班次時間後5分鐘）
                execution_time = datetime.combine(trip_date, trip_time) + timedelta(minutes=5)
                
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
                    run_date=execution_time
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
            now = datetime.now()
            
            # 查詢班次信息
            query = """
            SELECT 
                t.trip_id, 
                t.date, 
                t.time, 
                t.start_point, 
                t.via_point,
                t.end_point, 
                t.meter_fare,
                t.extra_fare,
                t.category,
                t.driver_id,
                t.status,
                t.unique_code,
                t.fixed_trip_id
            FROM 
                trips t
            WHERE 
                t.trip_id = :trip_id
            """
            
            trip = db.session.execute(text(query), {"trip_id": trip_id}).fetchone()
            
            if not trip:
                current_app.logger.error(f"找不到班次 #{trip_id}")
                return
            
            # 如果班次狀態不是"準備"，跳過
            if trip[10] != '準備':
                current_app.logger.info(f"班次 #{trip_id} 狀態不是「準備」，跳過更新")
                return
            
            unique_code = trip[11]
            
            # 如果沒有唯一識別碼，生成一個
            if not unique_code:
                if trip[12]:  # fixed_trip_id
                    # 計算一年中的第幾天和第幾周
                    day_of_year = trip[1].timetuple().tm_yday
                    _, week_number, _ = trip[1].isocalendar()
                    unique_code = f"{trip[12]}_{day_of_year}_{week_number}"
                else:
                    unique_code = f"T_{trip_id}"
                    # 對於非固定班次，也需要計算週數
                    _, week_number, _ = trip[1].isocalendar()
                
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
            
            # 插入到completed_trips表
            insert_query = """
            INSERT INTO completed_trips 
            (date, start_point, via_point, end_point, meter_fare, extra_fare, category, driver_id, unique_code) 
            VALUES 
            (:date, :start_point, :via_point, :end_point, :meter_fare, :extra_fare, :category, :driver_id, :unique_code)
            """
            
            db.session.execute(
                text(insert_query), 
                {
                    "date": trip[1],
                    "start_point": trip[3],
                    "via_point": trip[4],
                    "end_point": trip[5],
                    "meter_fare": trip[6],
                    "extra_fare": trip[7],
                    "category": trip[8],
                    "driver_id": trip[9],
                    "unique_code": unique_code
                }
            )
            
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
        now = datetime.now()
        current_app.logger.info(f"開始執行更新已完成班次任務...")
        
        # 獲取當前日期和時間
        current_date = now.date()
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
        
        completed_trips = db.session.execute(
            text(query), 
            {
                "current_date": current_date,
                "current_time": current_time
            }
        ).fetchall()
        
        current_app.logger.info(f"找到 {len(completed_trips)} 個需要更新的班次")
        
        if not completed_trips:
            current_app.logger.info(f"沒有需要更新的已完成班次")
            return "沒有需要更新的已完成班次。"
        
        # 更新每個班次
        updated_count = 0
        error_count = 0
        skipped_count = 0
        
        for trip in completed_trips:
            trip_id = trip[0]
            current_app.logger.info(f"處理班次 #{trip_id}")
            
            try:
                # 查詢班次信息
                query = """
                SELECT 
                    t.trip_id, 
                    t.date, 
                    t.time, 
                    t.start_point, 
                    t.via_point,
                    t.end_point, 
                    t.meter_fare,
                    t.extra_fare,
                    t.category,
                    t.driver_id,
                    t.status,
                    t.unique_code,
                    t.fixed_trip_id
                FROM 
                    trips t
                WHERE 
                    t.trip_id = :trip_id
                """
                
                trip_info = db.session.execute(text(query), {"trip_id": trip_id}).fetchone()
                
                if not trip_info:
                    current_app.logger.error(f"找不到班次 #{trip_id}，可能已被刪除")
                    error_count += 1
                    continue
                
                # 如果班次狀態不是"準備"，跳過
                if trip_info[10] != '準備':
                    current_app.logger.info(f"班次 #{trip_id} 狀態為「{trip_info[10]}」，不是「準備」，跳過更新")
                    skipped_count += 1
                    continue
                
                unique_code = trip_info[11]
                current_app.logger.info(f"班次 #{trip_id} 的唯一識別碼: {unique_code}")
                
                # 如果沒有唯一識別碼，生成一個
                if not unique_code:
                    try:
                        date_obj = trip_info[1]
                        fixed_trip_id = trip_info[12]
                        
                        if not date_obj:
                            current_app.logger.error(f"班次 #{trip_id} 沒有日期信息，無法生成唯一識別碼")
                            error_count += 1
                            continue
                        
                        # 計算一年中的第幾天和第幾周
                        day_of_year = date_obj.timetuple().tm_yday
                        _, week_number, _ = date_obj.isocalendar()
                        current_app.logger.info(f"班次 #{trip_id} 日期: {date_obj}, 一年中的第 {day_of_year} 天, 第 {week_number} 周")
                        
                        if fixed_trip_id:
                            unique_code = f"{fixed_trip_id}_{day_of_year}_{week_number}"
                            current_app.logger.info(f"班次 #{trip_id} 是固定班次 (ID: {fixed_trip_id})，生成唯一識別碼: {unique_code}")
                        else:
                            unique_code = f"T_{trip_id}"
                            current_app.logger.info(f"班次 #{trip_id} 是臨時班次，生成唯一識別碼: {unique_code}")
                        
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
                    except Exception as e:
                        current_app.logger.error(f"生成或更新班次 #{trip_id} 的唯一識別碼時出錯: {e}")
                        traceback.print_exc()
                        error_count += 1
                        continue
                
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
                    current_app.logger.info(f"班次 #{trip_id} (唯一識別碼: {unique_code}) 已經在已完成班次表中，跳過更新")
                    skipped_count += 1
                    continue
                
                # 插入到completed_trips表
                insert_query = """
                INSERT INTO completed_trips 
                (date, start_point, via_point, end_point, meter_fare, extra_fare, category, driver_id, unique_code) 
                VALUES 
                (:date, :start_point, :via_point, :end_point, :meter_fare, :extra_fare, :category, :driver_id, :unique_code)
                """
                
                db.session.execute(
                    text(insert_query), 
                    {
                        "date": trip_info[1],
                        "start_point": trip_info[3],
                        "via_point": trip_info[4],
                        "end_point": trip_info[5],
                        "meter_fare": trip_info[6],
                        "extra_fare": trip_info[7],
                        "category": trip_info[8],
                        "driver_id": trip_info[9],
                        "unique_code": unique_code
                    }
                )
                
                # 更新trips表中的狀態為"已完成"
                update_query = "UPDATE trips SET status = '已完成' WHERE trip_id = :trip_id"
                db.session.execute(text(update_query), {"trip_id": trip_id})
                
                updated_count += 1
                current_app.logger.info(f"成功將班次 #{trip_id} 的狀態更新為「已完成」")
                
            except Exception as e:
                current_app.logger.error(f"更新班次 #{trip_id} 時出錯: {e}")
                traceback.print_exc()
                error_count += 1
                continue
        
        # 提交事務
        db.session.commit()
        
        current_app.logger.info(f"更新已完成班次任務結束。成功: {updated_count}, 跳過: {skipped_count}, 錯誤: {error_count}")
        return f"✅ 成功更新 {updated_count} 筆已完成班次。跳過: {skipped_count}, 錯誤: {error_count}"
        
    except Exception as e:
        # 發生錯誤時回滾事務
        db.session.rollback()
        current_app.logger.error(f"更新已完成班次任務失敗: {e}")
        traceback.print_exc()
        return f"更新已完成班次失敗: {str(e)}"

def initialize_unique_codes():
    """初始化所有沒有唯一識別碼的班次"""
    try:
        now = datetime.now()
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
        
        # 為每個班次生成並更新唯一識別碼
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
                    unique_code = f"T_{trip_id}"
                
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
        
        # 為每個已完成班次生成並更新唯一識別碼
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
        # 發生錯誤時回滾事務
        db.session.rollback()
        current_app.logger.error(f"初始化班次唯一識別碼任務失敗: {e}")
        traceback.print_exc()
        return f"初始化唯一識別碼失敗: {str(e)}" 