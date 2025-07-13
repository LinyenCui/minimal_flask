#!/usr/bin/env python3
"""
測試基於執行時間的30分鐘修改限制功能的腳本
"""

import os
import sys
from datetime import datetime, timedelta, date, time
from dotenv import load_dotenv

# 加載環境變數
load_dotenv('.env.dev' if os.environ.get('FLASK_ENV') == 'development' else '.env')

# 添加專案根目錄到Python路徑
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules import create_app
from modules.models.base import db
from modules.models.trip import Trip
from modules.flex_designs.trip_details_flex import get_trip_details_flex
import json
import pytz

def test_execution_time_restriction():
    """測試基於執行時間的30分鐘修改限制功能"""
    app = create_app()
    
    with app.app_context():
        try:
            print("🧪 開始測試基於執行時間的30分鐘修改限制功能...")
            
            # 獲取台灣時區
            taiwan_tz = pytz.timezone('Asia/Taipei')
            current_time = datetime.now(taiwan_tz)
            
            print(f"🕐 當前台灣時間: {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
            
            # 測試場景1：創建一個1小時後執行的班次（應該可以修改）
            print("\n📋 測試場景1：1小時後執行的班次（應該可以修改）")
            
            future_time = current_time + timedelta(hours=1)
            test_trip_1 = Trip(
                date=future_time.date(),
                time=future_time.time(),
                start_point='測試起點A',
                end_point='測試終點A',
                status='準備',
                category='測試'
            )
            
            db.session.add(test_trip_1)
            db.session.commit()
            
            print(f"📊 測試班次1 ID: {test_trip_1.trip_id}")
            print(f"📅 執行時間: {test_trip_1.date} {test_trip_1.time}")
            print(f"✅ 可修改狀態: {test_trip_1.can_modify_status()}")
            print(f"⏰ 距離限制期: {test_trip_1.minutes_until_restriction()} 分鐘")
            
            if test_trip_1.can_modify_status():
                print("✅ 正確：1小時後的班次可以修改狀態")
            else:
                print("❌ 錯誤：1小時後的班次應該可以修改狀態")
            
            # 測試場景2：創建一個20分鐘後執行的班次（應該不能修改）
            print("\n📋 測試場景2：20分鐘後執行的班次（應該不能修改）")
            
            near_future_time = current_time + timedelta(minutes=20)
            test_trip_2 = Trip(
                date=near_future_time.date(),
                time=near_future_time.time(),
                start_point='測試起點B',
                end_point='測試終點B',
                status='準備',
                category='測試'
            )
            
            db.session.add(test_trip_2)
            db.session.commit()
            
            print(f"📊 測試班次2 ID: {test_trip_2.trip_id}")
            print(f"📅 執行時間: {test_trip_2.date} {test_trip_2.time}")
            print(f"✅ 可修改狀態: {test_trip_2.can_modify_status()}")
            print(f"⏰ 距離限制期: {test_trip_2.minutes_until_restriction()} 分鐘")
            print(f"💬 限制訊息: {test_trip_2.get_restriction_message()}")
            
            if not test_trip_2.can_modify_status():
                print("✅ 正確：20分鐘後的班次不能修改狀態")
            else:
                print("❌ 錯誤：20分鐘後的班次應該不能修改狀態")
            
            # 測試場景3：創建一個已過期的班次（應該不能修改）
            print("\n📋 測試場景3：已過期的班次（應該不能修改）")
            
            past_time = current_time - timedelta(minutes=10)
            test_trip_3 = Trip(
                date=past_time.date(),
                time=past_time.time(),
                start_point='測試起點C',
                end_point='測試終點C',
                status='準備',
                category='測試'
            )
            
            db.session.add(test_trip_3)
            db.session.commit()
            
            print(f"📊 測試班次3 ID: {test_trip_3.trip_id}")
            print(f"📅 執行時間: {test_trip_3.date} {test_trip_3.time}")
            print(f"✅ 可修改狀態: {test_trip_3.can_modify_status()}")
            print(f"💬 限制訊息: {test_trip_3.get_restriction_message()}")
            
            if not test_trip_3.can_modify_status():
                print("✅ 正確：已過期的班次不能修改狀態")
            else:
                print("❌ 錯誤：已過期的班次應該不能修改狀態")
            
            # 測試Flex Message生成
            print("\n🎨 測試Flex Message生成...")
            
            for i, trip in enumerate([test_trip_1, test_trip_2, test_trip_3], 1):
                trip_data = {
                    'date': trip.date,
                    'time': trip.time,
                    'start_point': trip.start_point,
                    'via_point': trip.via_point,
                    'end_point': trip.end_point,
                    'status': trip.status,
                    'driver_id': trip.driver_id,
                    'category': trip.category,
                    'base_fare': trip.meter_fare,
                    'display_start_point': trip.start_point,
                    'display_via_point': trip.via_point,
                    'display_end_point': trip.end_point
                }
                
                result = get_trip_details_flex(trip.trip_id, trip_data)
                
                print(f"📱 班次{i} Flex Message: {'成功' if result['flex_message'] else '失敗'}")
                print(f"🔘 班次{i} Quick Reply按鈕數量: {len(result['quick_reply']['items']) if result['quick_reply'] else 0}")
            
            # 清理測試數據
            print("\n🧹 清理測試數據...")
            db.session.delete(test_trip_1)
            db.session.delete(test_trip_2)
            db.session.delete(test_trip_3)
            db.session.commit()
            print("✅ 測試數據已清理")
            
            print("\n🎉 基於執行時間的30分鐘修改限制功能測試完成！")
            
        except Exception as e:
            print(f"❌ 測試失敗：{e}")
            import traceback
            traceback.print_exc()
            db.session.rollback()
        finally:
            db.session.close()

if __name__ == "__main__":
    test_execution_time_restriction() 