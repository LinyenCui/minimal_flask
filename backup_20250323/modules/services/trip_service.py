# 班次服務層 - 負責業務邏輯

from datetime import datetime, timedelta
import re
from sqlalchemy import text
from database import engine, Session
from flask import current_app
import traceback

from modules.models.base import db

def get_trips_by_date(date, category=None):
    """根據日期和類別獲取班次列表"""
    query = """
    SELECT 
        t.trip_id, 
        t.time, 
        c_start.name as start_name,
        c_via.name as via_name,
        c_end.name as end_name,
        t.status,
        d.id as driver_id,
        d.plate_number
    FROM 
        trips t
    LEFT JOIN 
        customers c_start ON t.start_point = c_start.short_name
    LEFT JOIN 
        customers c_via ON t.via_point = c_via.short_name
    LEFT JOIN 
        customers c_end ON t.end_point = c_end.short_name
    LEFT JOIN 
        drivers d ON t.driver_id = d.id
    WHERE 
        t.date = :date
    """
    
    if category:
        query += " AND t.category = :category"
    
    query += " ORDER BY t.time"
    
    with engine.connect() as conn:
        if category:
            result = conn.execute(text(query), {"date": date, "category": category})
        else:
            result = conn.execute(text(query), {"date": date})
        trips = [dict(row) for row in result]
    
    return trips

def get_trip_details(trip_id):
    """獲取班次詳細信息"""
    query = """
    SELECT 
        t.trip_id, 
        t.date, 
        t.time, 
        c_start.name as start_name, 
        c_via.name as via_name,
        c_end.name as end_name, 
        t.start_point, 
        t.via_point,
        t.end_point,
        t.status,
        d.id as driver_id,
        d.plate_number,
        t.category,
        t.fixed_trip_id,
        t.meter_fare,
        t.extra_fare,
        t.actual_fare
    FROM 
        trips t
    LEFT JOIN 
        customers c_start ON t.start_point = c_start.short_name
    LEFT JOIN 
        customers c_via ON t.via_point = c_via.short_name
    LEFT JOIN 
        customers c_end ON t.end_point = c_end.short_name
    LEFT JOIN 
        drivers d ON t.driver_id = d.id
    WHERE 
        t.trip_id = :trip_id
    """
    
    with engine.connect() as conn:
        result = conn.execute(text(query), {"trip_id": trip_id})
        trip = dict(result.first()) if result.rowcount > 0 else None
    
    return trip 

def update_completed_trips():
    """
    自動更新已完成的班次：
    1. 查找所有狀態為"準備"且時間已過的班次
    2. 將它們標記為"已完成"
    3. 將它們複製到已完成班次資料表
    """
    try:
        print(f"[{datetime.now()}] 開始執行更新已完成班次任務...")
        
        # 獲取當前日期和時間
        now = datetime.now()
        current_date = now.date()
        current_time = now.time()
        
        print(f"[{now}] 當前日期: {current_date}, 當前時間: {current_time}")
        
        # 使用應用上下文和DB_ENGINE進行數據庫操作
        engine = current_app.config.get('DB_ENGINE')
        if not engine:
            print(f"[{now}] 找不到數據庫引擎配置")
            return "找不到數據庫引擎配置"
            
        with engine.connect() as conn:
            # 開始事務
            trans = conn.begin()
            try:
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
                
                completed_trips = conn.execute(
                    text(query), 
                    {
                        "current_date": current_date,
                        "current_time": current_time
                    }
                ).fetchall()
                
                print(f"[{now}] 找到 {len(completed_trips)} 個需要更新的班次")
                
                if not completed_trips:
                    print(f"[{now}] 沒有需要更新的已完成班次")
                    return "沒有需要更新的已完成班次。"
                
                # 更新每個班次
                updated_count = 0
                error_count = 0
                skipped_count = 0
                
                for trip in completed_trips:
                    trip_id = trip[0]
                    print(f"[{now}] 處理班次 #{trip_id}")
                    
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
                    
                    trip_info = conn.execute(text(query), {"trip_id": trip_id}).fetchone()
                    
                    if not trip_info:
                        print(f"[{now}] 找不到班次 #{trip_id}，可能已被刪除")
                        error_count += 1
                        continue
                    
                    # 如果班次狀態不是"準備"，跳過
                    if trip_info[10] != '準備':
                        print(f"[{now}] 班次 #{trip_id} 狀態為「{trip_info[10]}」，不是「準備」，跳過更新")
                        skipped_count += 1
                        continue
                    
                    unique_code = trip_info[11]
                    print(f"[{now}] 班次 #{trip_id} 的唯一識別碼: {unique_code}")
                    
                    # 如果沒有唯一識別碼，生成一個
                    if not unique_code:
                        print(f"[{now}] 班次 #{trip_id} 沒有唯一識別碼，嘗試生成...")
                        
                        try:
                            date_obj = trip_info[1]
                            fixed_trip_id = trip_info[12]
                            
                            if not date_obj:
                                print(f"[{now}] 班次 #{trip_id} 沒有日期信息，無法生成唯一識別碼")
                                error_count += 1
                                continue
                            
                            # 計算一年中的第幾天和第幾周
                            try:
                                day_of_year = date_obj.timetuple().tm_yday
                                _, week_number, _ = date_obj.isocalendar()
                                print(f"[{now}] 班次 #{trip_id} 日期: {date_obj}, 一年中的第 {day_of_year} 天, 第 {week_number} 周")
                            except Exception as e:
                                print(f"[{now}] 計算班次 #{trip_id} 的日期信息時出錯: {e}")
                                error_count += 1
                                continue
                            
                            if fixed_trip_id:
                                unique_code = f"{fixed_trip_id}_{day_of_year}_{week_number}"
                                print(f"[{now}] 班次 #{trip_id} 是固定班次 (ID: {fixed_trip_id})，生成唯一識別碼: {unique_code}")
                            else:
                                unique_code = f"T_{trip_id}"
                                print(f"[{now}] 班次 #{trip_id} 是臨時班次，生成唯一識別碼: {unique_code}")
                            
                            # 更新班次的唯一識別碼和週數
                            update_query = """
                            UPDATE trips 
                            SET unique_code = :unique_code, week_number = :week_number
                            WHERE trip_id = :trip_id
                            """
                            
                            conn.execute(
                                text(update_query), 
                                {
                                    "unique_code": unique_code,
                                    "week_number": week_number,
                                    "trip_id": trip_id
                                }
                            )
                            print(f"[{now}] 成功更新班次 #{trip_id} 的唯一識別碼為 {unique_code}")
                        except Exception as e:
                            print(f"[{now}] 生成或更新班次 #{trip_id} 的唯一識別碼時出錯: {e}")
                            error_count += 1
                            continue
                    
                    # 檢查是否已經在completed_trips表中
                    try:
                        check_query = """
                        SELECT COUNT(*) as count FROM completed_trips 
                        WHERE unique_code = :unique_code
                        """
                        
                        existing_result = conn.execute(
                            text(check_query), 
                            {"unique_code": unique_code}
                        ).fetchone()
                        
                        existing_count = existing_result.count if existing_result else 0
                        
                        if existing_count > 0:
                            print(f"[{now}] 班次 #{trip_id} (唯一識別碼: {unique_code}) 已經在已完成班次表中，跳過更新")
                            skipped_count += 1
                            continue
                    except Exception as e:
                        print(f"[{now}] 檢查班次 #{trip_id} 是否已在已完成班次表中時出錯: {e}")
                        error_count += 1
                        continue
                    
                    # 插入到completed_trips表
                    try:
                        insert_query = """
                        INSERT INTO completed_trips 
                        (date, start_point, via_point, end_point, meter_fare, extra_fare, category, driver_id, unique_code) 
                        VALUES 
                        (:date, :start_point, :via_point, :end_point, :meter_fare, :extra_fare, :category, :driver_id, :unique_code)
                        """
                        
                        conn.execute(
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
                        print(f"[{now}] 成功將班次 #{trip_id} 插入到已完成班次表中")
                    except Exception as e:
                        print(f"[{now}] 將班次 #{trip_id} 插入到已完成班次表中時出錯: {e}")
                        error_count += 1
                        continue
                    
                    # 更新trips表中的狀態為"已完成"
                    try:
                        update_query = "UPDATE trips SET status = '已完成' WHERE trip_id = :trip_id"
                        conn.execute(text(update_query), {"trip_id": trip_id})
                        print(f"[{now}] 成功將班次 #{trip_id} 的狀態更新為「已完成」")
                        updated_count += 1
                    except Exception as e:
                        print(f"[{now}] 更新班次 #{trip_id} 的狀態時出錯: {e}")
                        error_count += 1
                        continue
                
                # 提交事務
                trans.commit()
                print(f"[{now}] 成功提交所有更新")
                
                print(f"[{now}] 更新已完成班次任務結束。成功: {updated_count}, 跳過: {skipped_count}, 錯誤: {error_count}")
                return f"✅ 成功更新 {updated_count} 筆已完成班次。跳過: {skipped_count}, 錯誤: {error_count}"
                
            except Exception as e:
                # 發生錯誤時回滾事務
                trans.rollback()
                print(f"[{now}] 處理班次更新時出錯，已回滾: {e}")
                print(traceback.format_exc())
                raise
        
    except Exception as e:
        print(f"[{datetime.now()}] 更新已完成班次任務失敗: {e}")
        print(traceback.format_exc())
        error_msg = f"更新已完成班次失敗: {str(e)}"
        return error_msg 