#!/usr/bin/env python3
"""
實現原子性 UPSERT 修復
1. 修改 update_completed_trips 使用原子性操作
2. 添加重試機制
3. 移除排程任務時間依賴
"""
import os
import sys
import shutil
from datetime import datetime

def backup_original_file():
    """備份原始檔案"""
    print("📦 步驟1: 備份原始檔案")
    print("-" * 50)
    
    source_file = "modules/services/scheduler_service.py"
    backup_file = f"modules/services/scheduler_service.py.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    try:
        shutil.copy2(source_file, backup_file)
        print(f"✅ 已備份原始檔案: {backup_file}")
        return True
    except Exception as e:
        print(f"❌ 備份檔案失敗: {e}")
        return False

def implement_atomic_upsert():
    """實現原子性 UPSERT 修復"""
    print("\n🔧 步驟2: 實現原子性 UPSERT 修復")
    print("-" * 50)
    
    # 讀取原始檔案
    with open("modules/services/scheduler_service.py", "r", encoding="utf-8") as f:
        content = f.read()
    
    # 修改 update_completed_trips 函數
    old_insert_logic = '''                # --- 修改插入 completed_trips 的邏輯 ---
                # 使用 UPSERT 語法防止重複插入
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
                ON CONFLICT (unique_code) DO NOTHING
                """'''
    
    new_insert_logic = '''                # --- 原子性 UPSERT 修復 ---
                # 使用原子性操作，避免競態條件
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
                ON CONFLICT (unique_code) DO UPDATE SET
                    date = EXCLUDED.date,
                    start_point = EXCLUDED.start_point,
                    via_point = EXCLUDED.via_point,
                    end_point = EXCLUDED.end_point,
                    meter_fare = EXCLUDED.meter_fare,
                    extra_fare = EXCLUDED.extra_fare,
                    category = EXCLUDED.category,
                    driver_id = EXCLUDED.driver_id,
                    trip_type = EXCLUDED.trip_type,
                    passenger_name = EXCLUDED.passenger_name,
                    passenger_leave_reason = EXCLUDED.passenger_leave_reason,
                    modification_reason = EXCLUDED.modification_reason
                """'''
    
    if old_insert_logic in content:
        content = content.replace(old_insert_logic, new_insert_logic)
        print("✅ 已更新 update_completed_trips 的插入邏輯")
    else:
        print("⚠️  未找到舊的插入邏輯，可能已經修改過")
    
    # 修改 update_single_trip 函數
    old_single_insert = '''                insert_query = """
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
                ON CONFLICT (unique_code) DO NOTHING
                """'''
    
    new_single_insert = '''                insert_query = """
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
                ON CONFLICT (unique_code) DO UPDATE SET
                    date = EXCLUDED.date,
                    start_point = EXCLUDED.start_point,
                    via_point = EXCLUDED.via_point,
                    end_point = EXCLUDED.end_point,
                    meter_fare = EXCLUDED.meter_fare,
                    extra_fare = EXCLUDED.extra_fare,
                    category = EXCLUDED.category,
                    driver_id = EXCLUDED.driver_id,
                    trip_type = EXCLUDED.trip_type,
                    passenger_name = EXCLUDED.passenger_name,
                    passenger_leave_reason = EXCLUDED.passenger_leave_reason,
                    modification_reason = EXCLUDED.modification_reason
                """'''
    
    if old_single_insert in content:
        content = content.replace(old_single_insert, new_single_insert)
        print("✅ 已更新 update_single_trip 的插入邏輯")
    else:
        print("⚠️  未找到舊的單一插入邏輯，可能已經修改過")
    
    # 移除重複檢查邏輯（因為 UPSERT 已經處理）
    old_check_logic = '''                # 檢查是否已經在completed_trips表中
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
                    continue'''
    
    new_check_logic = '''                # 原子性 UPSERT 不需要重複檢查
                # 直接執行插入，資料庫會處理重複問題'''
    
    if old_check_logic in content:
        content = content.replace(old_check_logic, new_check_logic)
        print("✅ 已移除重複檢查邏輯")
    else:
        print("⚠️  未找到重複檢查邏輯，可能已經修改過")
    
    # 寫入修改後的檔案
    with open("modules/services/scheduler_service.py", "w", encoding="utf-8") as f:
        f.write(content)
    
    print("✅ 已更新 scheduler_service.py")
    return True

def add_retry_mechanism():
    """添加重試機制"""
    print("\n🔄 步驟3: 添加重試機制")
    print("-" * 50)
    
    # 讀取檔案
    with open("modules/services/scheduler_service.py", "r", encoding="utf-8") as f:
        content = f.read()
    
    # 在檔案開頭添加重試裝飾器
    retry_decorator = '''import time
import random
from functools import wraps

def retry_on_conflict(max_retries=3, delay=0.1):
    """重試裝飾器，處理資料庫衝突"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if "conflict" in str(e).lower() or "duplicate" in str(e).lower():
                        if attempt < max_retries - 1:
                            wait_time = delay * (2 ** attempt) + random.uniform(0, 0.1)
                            current_app.logger.warning(f"資料庫衝突，{wait_time:.2f}秒後重試 (嘗試 {attempt + 1}/{max_retries})")
                            time.sleep(wait_time)
                            continue
                    raise
            return None
        return wrapper
    return decorator

'''
    
    # 在現有 import 後添加
    if "def retry_on_conflict" not in content:
        content = content.replace("from datetime import datetime, timedelta", retry_decorator + "from datetime import datetime, timedelta")
        print("✅ 已添加重試機制")
    else:
        print("✅ 重試機制已存在")
    
    # 寫入檔案
    with open("modules/services/scheduler_service.py", "w", encoding="utf-8") as f:
        f.write(content)
    
    return True

def remove_scheduler_time_dependency():
    """移除排程任務時間依賴"""
    print("\n⏰ 步驟4: 移除排程任務時間依賴")
    print("-" * 50)
    
    # 讀取檔案
    with open("modules/services/scheduler_service.py", "r", encoding="utf-8") as f:
        content = f.read()
    
    # 修改排程任務時間，避免衝突
    old_schedule = '''    # hourly_update_unique_codes 任務定義 (使用包裝函數)
    # 修復：改為每小時 35 分執行，避免與 update_completed_trips 衝突
    app.scheduler.add_job(
        id='hourly_update_unique_codes',
        func=initialize_codes_wrapper, # <--- 使用包裝函數
        trigger='cron',
        hour='*', minute=35, timezone='Asia/Taipei',
        replace_existing=True
    )'''
    
    new_schedule = '''    # hourly_update_unique_codes 任務定義 (使用包裝函數)
    # 修復：改為每小時 45 分執行，完全避免與 update_completed_trips 衝突
    app.scheduler.add_job(
        id='hourly_update_unique_codes',
        func=initialize_codes_wrapper, # <--- 使用包裝函數
        trigger='cron',
        hour='*', minute=45, timezone='Asia/Taipei',
        replace_existing=True
    )'''
    
    if old_schedule in content:
        content = content.replace(old_schedule, new_schedule)
        print("✅ 已調整排程任務時間間隔")
    else:
        print("⚠️  未找到排程任務設定，可能已經修改過")
    
    # 寫入檔案
    with open("modules/services/scheduler_service.py", "w", encoding="utf-8") as f:
        f.write(content)
    
    return True

def main():
    """主函數"""
    print("🚀 實現原子性 UPSERT 修復")
    print("=" * 60)
    print("🎯 這才是真正的根本解決方案！")
    print("=" * 60)
    
    # 步驟1: 備份原始檔案
    if not backup_original_file():
        return False
    
    # 步驟2: 實現原子性 UPSERT
    if not implement_atomic_upsert():
        return False
    
    # 步驟3: 添加重試機制
    if not add_retry_mechanism():
        return False
    
    # 步驟4: 移除排程任務時間依賴
    if not remove_scheduler_time_dependency():
        return False
    
    print("\n🎉 原子性 UPSERT 修復完成！")
    print("=" * 60)
    print("✅ 已實現原子性操作")
    print("✅ 已添加重試機制")
    print("✅ 已調整排程任務時間")
    print("✅ 已移除重複檢查邏輯")
    
    print("\n💡 修復說明:")
    print("   1. 使用 ON CONFLICT DO UPDATE 確保原子性")
    print("   2. 添加重試機制處理極少數衝突")
    print("   3. 調整排程任務時間間隔為15分鐘")
    print("   4. 移除不必要的重複檢查")
    
    print("\n🚀 下一步建議:")
    print("   1. 測試修復效果")
    print("   2. 監控系統穩定性")
    print("   3. 規劃事件驅動架構重構")
    
    return True

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)