from models import db
from sqlalchemy import text as sql_text
from datetime import datetime
from flask import current_app
import traceback

# 處理指派司機命令
def handle_assign_driver(message_text):
    try:
        # 解析參數
        parts = message_text.split()
        if len(parts) < 3:
            return "指派命令格式不正確。正確格式：指派 [班次ID] [司機ID]"
        
        trip_id = parts[1]
        driver_id = parts[2]
        
        # 使用應用上下文和DB_ENGINE進行數據庫操作
        with current_app.app_context():
            engine = current_app.config['DB_ENGINE']
            with engine.connect() as conn:
                # 開始事務
                trans = conn.begin()
                try:
                    # 檢查班次和司機
                    trip_query = """
                    SELECT status, date, fixed_trip_id, unique_code 
                    FROM trips 
                    WHERE trip_id = :trip_id
                    """
                    trip = conn.execute(sql_text(trip_query), {"trip_id": trip_id}).fetchone()
                    
                    if not trip:
                        return f"找不到班次 {trip_id}"
                    
                    if trip[0] != "待派":
                        return f"班次 {trip_id} 狀態不是待派，無法指派"
                    
                    driver_query = "SELECT id FROM drivers WHERE id = :driver_id"
                    driver = conn.execute(sql_text(driver_query), {"driver_id": driver_id}).fetchone()
                    
                    if not driver:
                        return f"找不到司機 {driver_id}"
                    
                    # 檢查是否有唯一識別碼，如果沒有則生成
                    unique_code = trip[3]
                    update_unique_code = False
                    
                    if not unique_code:
                        # 獲取班次日期和固定班次ID
                        date_obj = trip[1]
                        fixed_trip_id = trip[2]
                        
                        # 計算一年中的第幾天和第幾周
                        day_of_year = date_obj.timetuple().tm_yday
                        _, week_number, _ = date_obj.isocalendar()
                        
                        # 生成唯一識別碼
                        if fixed_trip_id:
                            unique_code = f"{fixed_trip_id}_{day_of_year}_{week_number}"
                        else:
                            unique_code = f"T_{trip_id}"
                        
                        update_unique_code = True
                    
                    # 指派司機，狀態變為「準備」，如果需要則更新唯一識別碼
                    if update_unique_code:
                        update_query = """
                        UPDATE trips 
                        SET driver_id = :driver_id, status = '準備', unique_code = :unique_code, week_number = :week_number
                        WHERE trip_id = :trip_id
                        """
                        
                        conn.execute(
                            sql_text(update_query), 
                            {
                                "driver_id": driver_id,
                                "trip_id": trip_id,
                                "unique_code": unique_code,
                                "week_number": week_number
                            }
                        )
                    else:
                        update_query = """
                        UPDATE trips 
                        SET driver_id = :driver_id, status = '準備' 
                        WHERE trip_id = :trip_id
                        """
                        
                        conn.execute(
                            sql_text(update_query), 
                            {
                                "driver_id": driver_id,
                                "trip_id": trip_id
                            }
                        )
                    
                    # 提交事務
                    trans.commit()
                    
                    return f"✅ 已指派司機 {driver_id} 給班次 {trip_id}"
                except Exception as e:
                    # 發生錯誤時回滾事務
                    trans.rollback()
                    print(f"指派司機時出錯: {e}")
                    print(traceback.format_exc())
                    return f"指派失敗: {str(e)}"
    except Exception as e:
        print(f"處理指派命令時出錯: {e}")
        print(traceback.format_exc())
        return f"指派失敗: {str(e)}"

# 處理查詢司機班次命令
def handle_query_driver_trips(message_text):
    try:
        # 簡化版本，不查詢數據庫
        parts = message_text.split()
        if len(parts) < 3:
            return "查車命令格式不正確。正確格式：查車 [司機ID] [日期]"
        
        driver_id = parts[1]
        date_str = parts[2]
        
        return f"這是查詢司機班次功能的測試回覆。您嘗試查詢司機 {driver_id} 在 {date_str} 的班次。實際功能尚未完全實現。"
    except Exception as e:
        return f"查車失敗: {str(e)}" 