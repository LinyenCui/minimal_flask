from datetime import date, timedelta
from sqlalchemy import text as sql_text
from flask import current_app
import traceback

from modules.models.base import db
from modules.utils.week_utils import (
    parse_week_parameter, 
    calculate_target_week, 
    is_week_in_past,
    get_available_weeks
)

def handle_import_fixed_trips_week(message_text):
    """處理匯入固定班次的命令 - 支援週次選擇和覆蓋選項"""
    try:
        # 解析命令參數
        parts = message_text.strip().split()
        
        if len(parts) == 1:
            # 只有「匯入固定班次」，顯示可用選項
            return show_available_weeks()
        
        week_param = parts[1].strip()
        
        # 檢查是否有覆蓋選項
        force_overwrite = False
        if len(parts) >= 3:
            overwrite_param = parts[2].strip()
            if overwrite_param == '覆蓋':
                force_overwrite = True
            else:
                return f"❌ 無效的選項: {overwrite_param}\n\n{show_available_weeks()}"
        
        # 解析週次參數
        try:
            week_offset, week_name = parse_week_parameter(week_param)
        except ValueError as e:
            return f"❌ {str(e)}\n\n{show_available_weeks()}"
        
        # 計算目標週次
        today = date.today()
        week_start, dates, week_desc = calculate_target_week(today, week_offset)
        
        # 防止匯入過去時間態
        if is_week_in_past(dates, today):
            return f"❌ 不允許匯入過去時間態：{week_name} ({week_desc})\n\n{show_available_weeks()}"
        
        # 執行匯入
        return import_week_trips(week_start, dates, week_name, week_desc, force_overwrite)
        
    except Exception as e:
        current_app.logger.error(f"處理匯入固定班次命令失敗: {str(e)}")
        traceback.print_exc()
        return f"處理匯入固定班次命令失敗: {str(e)}"

def show_available_weeks():
    """顯示可用的週次選項"""
    available_weeks = get_available_weeks()
    
    result = "📅 可用的匯入週次選項：\n\n"
    
    for offset, name, desc in available_weeks[:2]:  # 只顯示本週和下週
        result += f"• 匯入固定班次 {name} ({desc})\n"
    
    result += "\n📝 覆蓋選項：\n"
    result += "• 匯入固定班次 [週次] 覆蓋\n"
    
    result += "\n💡 輸入格式：匯入固定班次 [週次] [覆蓋]\n"
    result += "例如：匯入固定班次 下週\n"
    result += "例如：匯入固定班次 本週 覆蓋"
    
    return result

def import_week_trips(week_start, dates, week_name, week_desc, force_overwrite=False):
    """執行週次固定班次匯入"""
    try:
        current_app.logger.info(f"開始匯入{week_name}固定班次: {week_desc}")
        
        # 檢查是否已經匯入過
        check_query = f"""
        SELECT COUNT(*) FROM trips 
        WHERE date >= '{dates[0]}' AND date <= '{dates[6]}' AND fixed_trip_id IS NOT NULL
        """
        
        existing_count = db.session.execute(sql_text(check_query)).fetchone()[0]
        
        if existing_count > 0 and not force_overwrite:
            # 提供覆蓋選項的提示
            return f"⚠️ {week_name} ({week_desc}) 的固定班次已經匯入過了（共 {existing_count} 筆）。\n\n如需覆蓋，請使用：\n🔄 匯入固定班次 {week_name} 覆蓋\n\n⚠️ 注意：如選覆蓋資料，原先對班次的修改會失效"
        
        # 如果是覆蓋模式，先清除該週次的固定班次
        if force_overwrite and existing_count > 0:
            delete_query = f"""
            DELETE FROM trips 
            WHERE date >= '{dates[0]}' AND date <= '{dates[6]}' AND fixed_trip_id IS NOT NULL
            """
            delete_result = db.session.execute(sql_text(delete_query))
            deleted_count = delete_result.rowcount
            current_app.logger.info(f"覆蓋模式：已刪除 {deleted_count} 筆原有固定班次")
        
        # 週次選擇邏輯：
        # - 本週：在現有基礎上追加（不清空）
        # - 下週：可以清空（因為是未來規劃）
        week_offset = (week_start - date.today()).days // 7
        
        if week_offset == 0:
            # 本週：追加模式（不清空現有班次）
            current_app.logger.info("本週匯入模式：追加到現有班次")
        else:
            # 未來週次：規劃模式（可以清空重新規劃）
            current_app.logger.info(f"未來週次匯入模式：{week_name}")
            
            # 如果不是覆蓋模式，在匯入新班次之前，先將所有未完成的班次移到已完成班次表
            if not force_overwrite:
                from modules.services.scheduler_service import update_completed_trips
                update_completed_trips()
                
                # 清空班次總覽表（只在匯入未來週次時）
                delete_query = "DELETE FROM trips"
                db.session.execute(sql_text(delete_query))
                current_app.logger.info("已清空現有班次，準備匯入新週次")
        
        # 匯入每一天的固定班次
        total_inserted = 0
        status_counts = {'正常': 0, '請假': 0}
        
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
                AND (status IS NULL OR status != '停用')
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
                
                # 檢查是否已存在相同的班次（避免重複匯入）
                # 只有在本週追加模式且不是覆蓋模式時才需要檢查重複
                if week_offset == 0 and not force_overwrite:
                    duplicate_check = """
                    SELECT COUNT(*) FROM trips 
                    WHERE fixed_trip_id = :fixed_trip_id AND date = :date
                    """
                    
                    duplicate_count = db.session.execute(
                        sql_text(duplicate_check), 
                        {"fixed_trip_id": fixed_trip_id, "date": import_date}
                    ).fetchone()[0]
                    
                    if duplicate_count > 0:
                        current_app.logger.info(f"跳過重複班次: {fixed_trip_id} on {import_date}")
                        continue
                
                # 處理班次狀態和請假信息
                fixed_status = trip[12] if len(trip) > 12 and trip[12] else '準備'
                fixed_note = trip[13] if len(trip) > 13 and trip[13] else None
                
                # 根據固定班次狀態設定請假相關欄位
                if fixed_status == '請假' and fixed_note:
                    passenger_leave_reason = fixed_note
                    import_extra_fare = trip[7] if trip[7] is not None else 0
                    status_counts['請假'] += 1
                else:
                    passenger_leave_reason = None
                    import_extra_fare = trip[7] if trip[7] is not None else 0
                    status_counts['正常'] += 1
                
                insert_query = """
                INSERT INTO trips 
                (fixed_trip_id, date, time, start_point, via_point, end_point, 
                 meter_fare, extra_fare, category, driver_id, status, passenger_leave_reason, 
                 unique_code, week_number, trip_type) 
                VALUES 
                (:fixed_trip_id, :date, :time, :start_point, :via_point, :end_point, 
                 :meter_fare, :extra_fare, :category, :driver_id, '準備', :passenger_leave_reason, 
                 :unique_code, :week_number, 'fixed')
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
        
        db.session.commit()
        current_app.logger.info(f"成功匯入{total_inserted}筆固定班次")
        
        # 生成匯入結果報告
        result = f"✅ 成功匯入 {week_name} ({week_desc}) {total_inserted} 筆固定班次"
        
        # 如果是覆蓋模式，添加覆蓋信息
        if force_overwrite and existing_count > 0:
            result = f"🔄 已覆蓋 {existing_count} 筆原有班次\n\n" + result
        
        # 添加狀態統計
        if status_counts['正常'] > 0 or status_counts['請假'] > 0:
            status_details = []
            if status_counts['正常'] > 0:
                status_details.append(f"正常: {status_counts['正常']}筆")
            if status_counts['請假'] > 0:
                status_details.append(f"請假: {status_counts['請假']}筆")
            
            result += f"\n\n📊 狀態統計: {', '.join(status_details)}"
        
        # 添加操作說明
        if week_offset == 0:
            result += f"\n\n💡 已追加到現有班次中，如需查看請使用「東洋班次」指令"
        else:
            result += f"\n\n💡 已清空原有班次並匯入{week_name}，現在可以開始{week_name}的派班作業"
        
        return result
        
    except Exception as e:
        # 發生錯誤時回滾事務
        db.session.rollback()
        current_app.logger.error(f"匯入{week_name}固定班次失敗: {str(e)}")
        traceback.print_exc()
        return f"匯入{week_name}固定班次失敗: {str(e)}" 