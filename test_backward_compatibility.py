#!/usr/bin/env python3
"""
測試向後兼容性：驗證沒有乘客資訊的現有班次能否正常完成轉移
"""

import os
import sys
from datetime import datetime, date, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from modules.models.base import db
from sqlalchemy import text
from flask import Flask

def test_backward_compatibility():
    """測試向後兼容性：沒有乘客資訊的班次"""
    
    # 設置測試環境
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:postgres@localhost:5432/dispatch_db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)
    
    with app.app_context():
        try:
            print("🧪 開始向後兼容性測試...")
            
            # 1. 創建一個沒有乘客資訊的測試班次
            print("📝 創建測試班次（無乘客資訊）...")
            insert_test_trip = """
            INSERT INTO trips (date, time, start_point, end_point, category, status, trip_type, 
                              custom_start_point, custom_end_point, meter_fare, passenger_name)
            VALUES (:date, :time, '臨時地點', '臨時地點', '東洋', '準備', 'temp', 
                    :custom_start_point, :custom_end_point, :meter_fare, :passenger_name)
            RETURNING trip_id
            """
            
            result = db.session.execute(text(insert_test_trip), {
                "date": date.today(),
                "time": time(10, 30),  # 過去時間，會被自動完成
                "custom_start_point": "測試起點",
                "custom_end_point": "測試終點", 
                "meter_fare": 250,
                "passenger_name": None  # 重點：NULL 值
            })
            
            test_trip_id = result.fetchone()[0]
            print(f"✅ 創建測試班次 ID: {test_trip_id}（passenger_name = NULL）")
            
            # 2. 創建另一個沒有錶價的測試班次
            print("📝 創建測試班次（無錶價）...")
            result2 = db.session.execute(text(insert_test_trip), {
                "date": date.today(),
                "time": time(11, 30),  # 過去時間
                "custom_start_point": "測試起點2",
                "custom_end_point": "測試終點2", 
                "meter_fare": None,  # 重點：NULL 值
                "passenger_name": None  # 重點：NULL 值
            })
            
            test_trip_id2 = result2.fetchone()[0]
            print(f"✅ 創建測試班次 ID: {test_trip_id2}（meter_fare = NULL, passenger_name = NULL）")
            
            # 3. 模擬完成轉移過程
            print("🔄 模擬班次完成轉移...")
            
            # 查詢班次信息（模擬 scheduler_service.py 的邏輯）
            query_trip = """
            SELECT 
                t.trip_id, t.date, t.time, 
                t.start_point, t.via_point, t.end_point, 
                t.meter_fare, t.extra_fare, t.category, t.driver_id,
                t.status, t.unique_code, t.fixed_trip_id,
                t.trip_type, t.custom_start_point, t.custom_end_point, t.passenger_name
            FROM trips t WHERE t.trip_id = :trip_id
            """
            
            for trip_id in [test_trip_id, test_trip_id2]:
                trip_info_result = db.session.execute(text(query_trip), {"trip_id": trip_id})
                trip_info = dict(trip_info_result.fetchone()._mapping)
                
                print(f"📊 班次 {trip_id} 資訊:")
                print(f"   - meter_fare: {trip_info.get('meter_fare')}")
                print(f"   - passenger_name: {trip_info.get('passenger_name')}")
                
                # 生成唯一識別碼
                unique_code = f"T_{trip_id}"
                
                # 模擬插入到 completed_trips（這是關鍵測試）
                insert_completed = """
                INSERT INTO completed_trips
                (date, start_point, via_point, end_point,
                 meter_fare, extra_fare, category, driver_id,
                 unique_code, trip_type, passenger_name)
                VALUES
                (:date, :start_point, :via_point, :end_point,
                 :meter_fare, :extra_fare, :category, :driver_id,
                 :unique_code, :trip_type, :passenger_name)
                """
                
                params = {
                    "date": trip_info.get('date'),
                    "start_point": trip_info.get('custom_start_point'),
                    "via_point": trip_info.get('via_point'),
                    "end_point": trip_info.get('custom_end_point'),
                    "meter_fare": trip_info.get('meter_fare'),  # 可能為 NULL
                    "extra_fare": trip_info.get('extra_fare'),
                    "category": trip_info.get('category'),
                    "driver_id": trip_info.get('driver_id'),
                    "unique_code": unique_code,
                    "trip_type": trip_info.get('trip_type'),
                    "passenger_name": trip_info.get('passenger_name')  # 可能為 NULL
                }
                
                print(f"📤 準備插入 completed_trips，參數: {params}")
                
                try:
                    db.session.execute(text(insert_completed), params)
                    print(f"✅ 班次 {trip_id} 成功轉移到 completed_trips")
                except Exception as e:
                    print(f"❌ 班次 {trip_id} 轉移失敗: {e}")
                    raise
            
            # 4. 驗證結果
            print("🔍 驗證 completed_trips 中的記錄...")
            check_completed = """
            SELECT id, meter_fare, passenger_name 
            FROM completed_trips 
            WHERE unique_code LIKE 'T_%'
            ORDER BY id DESC LIMIT 2
            """
            
            completed_results = db.session.execute(text(check_completed)).fetchall()
            
            for result in completed_results:
                print(f"📋 Completed Trip:")
                print(f"   - id: {result[0] if len(result) > 0 else 'N/A'}")
                print(f"   - meter_fare: {result[1] if len(result) > 1 else 'N/A'}")
                print(f"   - passenger_name: {result[2] if len(result) > 2 else 'N/A'}")
            
            # 提交測試
            db.session.commit()
            print("\n🎉 向後兼容性測試通過！")
            print("✅ NULL 值的 meter_fare 和 passenger_name 都能正確處理")
            
            # 清理測試數據
            print("🧹 清理測試數據...")
            db.session.execute(text("DELETE FROM completed_trips WHERE unique_code LIKE 'T_%'"))
            db.session.execute(text("DELETE FROM trips WHERE trip_id IN (:id1, :id2)"), 
                             {"id1": test_trip_id, "id2": test_trip_id2})
            db.session.commit()
            print("✅ 測試數據清理完成")
            
        except Exception as e:
            print(f"❌ 測試失敗: {e}")
            db.session.rollback()
            import traceback
            traceback.print_exc()
            return False
        
        return True

if __name__ == "__main__":
    success = test_backward_compatibility()
    if success:
        print("\n🚀 所有測試通過！向後兼容性確認無問題。")
    else:
        print("\n💥 測試失敗！需要修復向後兼容性問題。")
        sys.exit(1) 