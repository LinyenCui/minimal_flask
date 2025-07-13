#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
補充固定班次到 Render 線上資料庫
用於在已經匯入固定班次後，補充遺漏的單筆班次到 trips 表
"""

import sys
import os
from datetime import date, timedelta
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import traceback

# 添加項目根目錄到路徑
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def get_render_database_url():
    """獲取 Render 資料庫連接 URL"""
    # 方法1：從環境變數讀取（如果您有設定）
    render_url = os.environ.get('RENDER_DATABASE_URL')
    if render_url:
        return render_url
    
    # 方法2：從個別環境變數組合
    host = os.environ.get('RENDER_DB_HOST')
    user = os.environ.get('RENDER_DB_USER')
    password = os.environ.get('RENDER_DB_PASSWORD')
    database = os.environ.get('RENDER_DB_NAME')
    
    if all([host, user, password, database]):
        return f"postgresql://{user}:{password}@{host}:5432/{database}"
    
    # 方法3：手動輸入（交互式）
    print("請輸入 Render 資料庫連接資訊：")
    print("（可以在 Render Dashboard > Database > Connect 找到）")
    print()
    
    # 提示用戶輸入
    host = input("Host (例如: dpg-xxx-a.oregon-postgres.render.com): ").strip()
    user = input("User (例如: dispatch_system_db_user): ").strip()
    password = input("Password: ").strip()
    database = input("Database (例如: dispatch_system_db): ").strip()
    
    if not all([host, user, password, database]):
        print("❌ 資訊不完整，無法連接")
        return None
    
    return f"postgresql://{user}:{password}@{host}:5432/{database}"

def add_single_fixed_trip_render(fixed_schedule_id, database_url, target_dates=None):
    """
    補充單筆固定班次到指定日期的 trips 表 (Render 版本)
    
    Args:
        fixed_schedule_id (int): 固定班次表的 ID
        database_url (str): Render 資料庫連接 URL
        target_dates (list): 目標日期列表，如果為 None 則自動計算本週對應的日期
    
    Returns:
        tuple: (success_count, error_messages)
    """
    try:
        engine = create_engine(database_url, echo=False)
        Session = sessionmaker(bind=engine)
        session = Session()
    except Exception as e:
        return 0, [f"連接 Render 資料庫失敗: {str(e)}"]
    
    try:
        # 1. 查詢固定班次資料
        fixed_query = """
        SELECT 
            id, route_number, departure_time, start_point, via_point, end_point,
            base_fare, surcharge, total_fare, category, driver_id, direction,
            status, note
        FROM fixed_schedules 
        WHERE id = :fixed_id
        """
        
        fixed_result = session.execute(text(fixed_query), {"fixed_id": fixed_schedule_id}).fetchone()
        
        if not fixed_result:
            return 0, [f"找不到固定班次 ID: {fixed_schedule_id}"]
        
        # 解包固定班次資料
        (schedule_id, route_number, departure_time, start_point, via_point, end_point,
         base_fare, surcharge, total_fare, category, driver_id, direction,
         fixed_status, fixed_note) = fixed_result
        
        print(f"✅ 找到固定班次: ID={schedule_id}, route_number={route_number}, time={departure_time}")
        print(f"   路線: {start_point} → {end_point}, 類別: {category}, 司機: {driver_id}")
        
        # 2. 如果沒有指定目標日期，自動計算本週對應的日期
        if target_dates is None:
            target_dates = []
            today = date.today()
            
            # 計算本周的開始日期（星期日）
            days_since_sunday = today.weekday() + 1 if today.weekday() < 6 else 0
            week_start = today - timedelta(days=days_since_sunday)
            
            # 根據 route_number 包含的數字確定對應的星期
            for weekday_num in range(1, 8):  # 1-7 表示星期一到星期日
                if str(weekday_num) in route_number:
                    # 計算對應星期的日期（星期日=0, 星期一=1, ...）
                    if weekday_num == 7:  # 星期日
                        target_date = week_start
                    else:  # 星期一到星期六
                        target_date = week_start + timedelta(days=weekday_num)
                    
                    target_dates.append(target_date)
                    weekday_names = ["日", "一", "二", "三", "四", "五", "六"]
                    print(f"   route_number {route_number} 包含 {weekday_num}，對應星期{weekday_names[weekday_num % 7]}：{target_date}")
        
        if not target_dates:
            return 0, [f"route_number {route_number} 沒有對應的星期日期"]
        
        # 3. 為每個目標日期補充班次
        success_count = 0
        error_messages = []
        
        for target_date in target_dates:
            try:
                # 檢查是否已存在相同班次
                check_query = """
                SELECT trip_id FROM trips 
                WHERE fixed_trip_id = :fixed_id 
                AND date = :target_date
                """
                
                existing = session.execute(text(check_query), {
                    "fixed_id": schedule_id,
                    "target_date": target_date
                }).fetchone()
                
                if existing:
                    print(f"   {target_date} 已存在班次 #{existing[0]}，跳過")
                    continue
                
                # 計算週數和唯一識別碼
                day_of_year = target_date.timetuple().tm_yday
                _, week_number, _ = target_date.isocalendar()
                unique_code = f"{schedule_id}_{day_of_year}_{week_number}"
                
                # 根據固定班次狀態設定請假相關欄位
                if fixed_status == '請假' and fixed_note:
                    passenger_leave_reason = fixed_note
                    import_extra_fare = surcharge if surcharge is not None else 0
                else:
                    passenger_leave_reason = None
                    import_extra_fare = surcharge if surcharge is not None else 0
                
                # 插入新班次
                insert_query = """
                INSERT INTO trips 
                (fixed_trip_id, date, time, start_point, via_point, end_point, 
                 meter_fare, extra_fare, category, driver_id, status, 
                 passenger_leave_reason, unique_code, week_number, trip_type) 
                VALUES 
                (:fixed_trip_id, :date, :time, :start_point, :via_point, :end_point, 
                 :meter_fare, :extra_fare, :category, :driver_id, '準備', 
                 :passenger_leave_reason, :unique_code, :week_number, 'fixed')
                """
                
                session.execute(text(insert_query), {
                    "fixed_trip_id": schedule_id,
                    "date": target_date,
                    "time": departure_time,
                    "start_point": start_point,
                    "via_point": via_point,
                    "end_point": end_point,
                    "meter_fare": base_fare,
                    "extra_fare": import_extra_fare,
                    "category": category,
                    "driver_id": driver_id,
                    "passenger_leave_reason": passenger_leave_reason,
                    "unique_code": unique_code,
                    "week_number": week_number
                })
                
                success_count += 1
                weekday_names = ["一", "二", "三", "四", "五", "六", "日"]
                weekday = weekday_names[target_date.weekday()]
                print(f"   ✅ 成功補充到 {target_date} (星期{weekday})")
                
            except Exception as e:
                error_msg = f"補充 {target_date} 失敗: {str(e)}"
                error_messages.append(error_msg)
                print(f"   ❌ {error_msg}")
        
        # 提交事務
        session.commit()
        return success_count, error_messages
        
    except Exception as e:
        session.rollback()
        error_msg = f"補充固定班次時出錯: {str(e)}"
        print(f"❌ {error_msg}")
        print(traceback.format_exc())
        return 0, [error_msg]
    
    finally:
        session.close()

def main():
    """主函數：補充 ID=54 的固定班次到 Render"""
    print("🚌 開始補充固定班次 ID=54 到 Render 線上資料庫...")
    print("=" * 70)
    
    # 獲取 Render 資料庫連接 URL
    database_url = get_render_database_url()
    if not database_url:
        print("❌ 無法獲取 Render 資料庫連接資訊")
        return
    
    print("🔗 正在連接到 Render 資料庫...")
    
    # 補充 ID=54 的固定班次
    success_count, error_messages = add_single_fixed_trip_render(54, database_url)
    
    print("=" * 70)
    print(f"📊 補充結果總結：")
    print(f"   成功補充: {success_count} 筆")
    print(f"   錯誤數量: {len(error_messages)}")
    
    if error_messages:
        print("\n❌ 錯誤詳情：")
        for error in error_messages:
            print(f"   - {error}")
    
    if success_count > 0:
        print(f"\n🎉 成功補充 {success_count} 筆班次到 Render！")
        print("現在 LINE Bot 的「查詢班次 二四六」應該可以看到補充的班次。")
    else:
        print("\n⚠️  沒有補充任何班次。")

if __name__ == "__main__":
    main() 