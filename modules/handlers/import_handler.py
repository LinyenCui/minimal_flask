from datetime import date, timedelta
from sqlalchemy import text as sql_text
from flask import current_app
import traceback

from modules.models.base import db

def handle_import_fixed_trips_week(message_text):
    """處理匯入固定班次(一整周)的命令"""
    try:
        # 獲取當前日期
        today = date.today()
        
        # 計算本周的開始日期（星期日）
        days_since_sunday = today.weekday() + 1 if today.weekday() < 6 else 0
        week_start = today - timedelta(days=days_since_sunday)
        
        # 計算本周的日期範圍（星期日到星期六）
        dates = [week_start + timedelta(days=i) for i in range(7)]
        
        # 檢查是否已經匯入過
        check_query = f"""
        SELECT COUNT(*) FROM trips 
        WHERE date >= '{dates[0]}' AND date <= '{dates[6]}' AND fixed_trip_id IS NOT NULL
        """
        
        existing_count = db.session.execute(sql_text(check_query)).fetchone()[0]
        
        if existing_count > 0:
            # 格式化日期範圍
            date_range = f"{dates[0].month}/{dates[0].day}-{dates[6].month}/{dates[6].day}"
            return f"本周 ({date_range}) 的固定班次已經匯入過了。如需重新匯入，請先刪除該日期範圍的班次。"
        
        # 在匯入新班次之前，先將所有未完成的班次移到已完成班次表
        # 這確保了不會丟失任何班次信息
        from modules.services.scheduler_service import update_completed_trips
        update_completed_trips()
        
        # 清空班次總覽表
        delete_query = "DELETE FROM trips"
        db.session.execute(sql_text(delete_query))
        
        # 匯入每一天的固定班次
        total_inserted = 0
        status_counts = {'正常': 0, '請假': 0}  # 統計各狀態數量（修正：基於實際顯示效果）
        for import_date in dates:
            # 獲取星期幾（1-7，其中1是星期一）
            weekday = import_date.isoweekday()
            
            # 查詢符合當天星期的固定班次（包含狀態和說明）
            query = f"""
            SELECT 
                id, 
                route_number, 
                departure_time, 
                start_point, 
                via_point, 
                end_point, 
                base_fare, 
                surcharge, 
                total_fare, 
                category, 
                driver_id,
                direction,
                status,
                note
            FROM 
                fixed_schedules
            WHERE 
                route_number LIKE '%{weekday}%'
            """
            
            fixed_trips = db.session.execute(sql_text(query)).fetchall()
            
            # 匯入固定班次到班次總覽表
            for trip in fixed_trips:
                fixed_trip_id = trip[0]
                
                # 計算一年中的第幾天和第幾周
                day_of_year = import_date.timetuple().tm_yday
                _, week_number, _ = import_date.isocalendar()
                
                # 生成唯一識別碼
                unique_code = f"{fixed_trip_id}_{day_of_year}_{week_number}"
                
                # 🔧 修正：統一邏輯 - 所有匯入的班次 status 都設為「準備」
                fixed_status = trip[12] if len(trip) > 12 and trip[12] else '準備'
                fixed_note = trip[13] if len(trip) > 13 and trip[13] else None
                
                # 根據固定班次狀態設定請假相關欄位
                if fixed_status == '請假' and fixed_note:
                    # 固定班次是請假狀態，設定請假原因
                    passenger_leave_reason = fixed_note
                    # 使用固定班次的加成（可能是負值）
                    import_extra_fare = trip[7] if trip[7] is not None else 0
                else:
                    # 固定班次是正常狀態
                    passenger_leave_reason = None
                    import_extra_fare = trip[7] if trip[7] is not None else 0
                
                insert_query = """
                INSERT INTO trips 
                (fixed_trip_id, date, time, start_point, via_point, end_point, 
                 meter_fare, extra_fare, category, driver_id, status, passenger_leave_reason, unique_code, week_number, trip_type) 
                VALUES 
                (:fixed_trip_id, :date, :time, :start_point, :via_point, :end_point, 
                 :meter_fare, :extra_fare, :category, :driver_id, '準備', :passenger_leave_reason, :unique_code, :week_number, 'fixed')
                """
                
                db.session.execute(
                    sql_text(insert_query), 
                    {
                        "fixed_trip_id": fixed_trip_id,
                        "date": import_date,
                        "time": trip[2],
                        "start_point": trip[3],
                        "via_point": trip[4],
                        "end_point": trip[5],
                        "meter_fare": trip[6],
                        "extra_fare": import_extra_fare,
                        "category": trip[9],
                        "driver_id": trip[10],
                        "passenger_leave_reason": passenger_leave_reason,
                        "unique_code": unique_code,
                        "week_number": week_number
                    }
                )
                total_inserted += 1
                
                # 🔧 修正：基於實際顯示效果統計
                if fixed_status == '請假' and fixed_note:
                    status_counts['請假'] += 1
                else:
                    status_counts['正常'] += 1
        
        db.session.commit()
        
        # 格式化日期範圍
        date_range = f"{dates[0].month}/{dates[0].day}-{dates[6].month}/{dates[6].day}"
        
        # 生成詳細統計報告
        status_report = []
        for status, count in status_counts.items():
            if count > 0:
                status_report.append(f"{status}: {count}筆")
        
        status_detail = " (" + ", ".join(status_report) + ")" if status_report else ""
        
        return f"✅ 成功匯入 {total_inserted} 筆固定班次到本周 ({date_range}){status_detail}。"
        
    except Exception as e:
        # 發生錯誤時回滾事務
        db.session.rollback()
        current_app.logger.error(f"匯入固定班次失敗: {str(e)}")
        traceback.print_exc()
        return f"匯入固定班次失敗: {str(e)}" 