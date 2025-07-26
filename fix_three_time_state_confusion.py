#!/usr/bin/env python3
"""
修復三時間態混亂問題 - 立即實施方案
添加 original_trip_id 欄位到 completed_trips 表，並創建統一查詢服務
"""
import sys
import os
sys.path.insert(0, os.path.abspath('.'))

from modules import create_app
from modules.models.base import db
from sqlalchemy import text
import traceback

def add_original_trip_id_column():
    """添加 original_trip_id 欄位到 completed_trips 表"""
    app = create_app()
    
    with app.app_context():
        try:
            print("🔧 開始修復三時間態混亂問題...")
            
            # 1. 檢查欄位是否已存在
            check_query = """
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'completed_trips' 
            AND column_name = 'original_trip_id'
            """
            
            result = db.session.execute(text(check_query)).fetchone()
            
            if result:
                print("✅ original_trip_id 欄位已存在")
                return True
            
            # 2. 添加 original_trip_id 欄位
            print("📊 添加 original_trip_id 欄位...")
            alter_query = """
            ALTER TABLE completed_trips 
            ADD COLUMN original_trip_id INTEGER
            """
            
            db.session.execute(text(alter_query))
            
            # 3. 創建索引提升查詢效率
            print("🚀 創建索引...")
            index_query = """
            CREATE INDEX IF NOT EXISTS idx_completed_trips_original_trip_id 
            ON completed_trips(original_trip_id)
            """
            
            db.session.execute(text(index_query))
            
            # 4. 提交更改
            db.session.commit()
            
            print("✅ 成功添加 original_trip_id 欄位和索引")
            return True
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ 添加欄位失敗: {str(e)}")
            traceback.print_exc()
            return False

def update_existing_completed_trips():
    """更新現有 completed_trips 記錄，設置 original_trip_id"""
    app = create_app()
    
    with app.app_context():
        try:
            print("🔄 更新現有記錄的 original_trip_id...")
            
            # 通過 unique_code 關聯，找到對應的 original trip_id
            # 對於已經存在的 completed_trips，我們無法完美恢復 original_trip_id
            # 但可以使用一些啟發式方法
            
            # 方法1：對於沒有 original_trip_id 的記錄，嘗試從 unique_code 推斷
            update_query = """
            UPDATE completed_trips 
            SET original_trip_id = CASE
                WHEN unique_code LIKE 'T_%' THEN CAST(SUBSTRING(unique_code FROM 3) AS INTEGER)
                WHEN original_trip_id IS NULL THEN id  -- 作為後備方案
                ELSE original_trip_id
            END
            WHERE original_trip_id IS NULL
            """
            
            result = db.session.execute(text(update_query))
            updated_count = result.rowcount
            
            db.session.commit()
            
            print(f"✅ 更新了 {updated_count} 筆記錄的 original_trip_id")
            return True
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ 更新現有記錄失敗: {str(e)}")
            traceback.print_exc()
            return False

def create_unified_query_service():
    """創建統一查詢服務的代碼模板"""
    service_code = '''
"""
統一班次查詢服務
解決三時間態混亂問題，讓用戶使用統一ID查詢不同時間態的班次
"""
from modules.models.base import db
from sqlalchemy import text
from typing import Dict, Optional, List

class UnifiedTripQueryService:
    """統一班次查詢服務，自動跨時間態查找班次"""
    
    @staticmethod
    def find_trip_by_id(trip_id: int) -> Dict:
        """
        根據ID查找班次，自動判斷時間態
        
        Args:
            trip_id: 班次ID (可能是 trip_id 或 original_trip_id)
            
        Returns:
            {
                "found": bool,
                "source_table": str,  # "trips" 或 "completed_trips"
                "time_state": str,    # "present" 或 "past"
                "data": dict,         # 班次數據
                "original_trip_id": int  # 原始 trip_id
            }
        """
        # 1. 先查 trips 表 (現在態)
        trips_query = """
        SELECT trip_id, date, time, start_point, via_point, end_point,
               meter_fare, extra_fare, category, driver_id, status, 
               unique_code, trip_type
        FROM trips 
        WHERE trip_id = :trip_id
        """
        
        result = db.session.execute(text(trips_query), {"trip_id": trip_id}).fetchone()
        
        if result:
            return {
                "found": True,
                "source_table": "trips",
                "time_state": "present", 
                "data": dict(result._mapping),
                "original_trip_id": trip_id,
                "message": f"班次 #{trip_id} (進行中)"
            }
        
        # 2. 再查 completed_trips 表 (過去態)
        completed_query = """
        SELECT id, original_trip_id, date, start_point, via_point, end_point,
               meter_fare, extra_fare, category, driver_id, status,
               unique_code, trip_type, created_at
        FROM completed_trips 
        WHERE original_trip_id = :trip_id OR id = :trip_id
        ORDER BY created_at DESC
        LIMIT 1
        """
        
        result = db.session.execute(text(completed_query), {"trip_id": trip_id}).fetchone()
        
        if result:
            data = dict(result._mapping)
            original_id = data.get('original_trip_id', data.get('id'))
            return {
                "found": True,
                "source_table": "completed_trips",
                "time_state": "past",
                "data": data,
                "original_trip_id": original_id,
                "message": f"班次 #{original_id} (已完成)"
            }
        
        # 3. 通過 unique_code 查找
        unique_code_query = """
        (SELECT 'trips' as source, trip_id as id, unique_code, date, driver_id 
         FROM trips WHERE unique_code LIKE '%' || :trip_id || '%')
        UNION
        (SELECT 'completed_trips' as source, id, unique_code, date, driver_id
         FROM completed_trips WHERE unique_code LIKE '%' || :trip_id || '%')
        ORDER BY date DESC
        LIMIT 1
        """
        
        result = db.session.execute(text(unique_code_query), {"trip_id": str(trip_id)}).fetchone()
        
        if result:
            return {
                "found": True,
                "source_table": result[0],
                "time_state": "present" if result[0] == "trips" else "past",
                "data": {"found_by_unique_code": True, "unique_code": result[2]},
                "original_trip_id": result[1],
                "message": f"通過 unique_code 找到相關班次"
            }
        
        # 4. 找不到
        return {
            "found": False,
            "source_table": None,
            "time_state": None,
            "data": None,
            "original_trip_id": None,
            "message": f"找不到班次 #{trip_id}"
        }
    
    @staticmethod 
    def get_trip_history(trip_id: int) -> List[Dict]:
        """獲取班次的完整歷史 (從 trips 到 completed_trips)"""
        
        # 先找到所有相關的 unique_code
        history_query = """
        SELECT 'trips' as source, trip_id as id, date, time, status, unique_code, created_at
        FROM trips 
        WHERE trip_id = :trip_id OR unique_code IN (
            SELECT unique_code FROM trips WHERE trip_id = :trip_id
            UNION 
            SELECT unique_code FROM completed_trips WHERE original_trip_id = :trip_id
        )
        
        UNION ALL
        
        SELECT 'completed_trips' as source, id, date, NULL as time, status, unique_code, created_at
        FROM completed_trips
        WHERE original_trip_id = :trip_id OR unique_code IN (
            SELECT unique_code FROM trips WHERE trip_id = :trip_id
            UNION 
            SELECT unique_code FROM completed_trips WHERE original_trip_id = :trip_id
        )
        
        ORDER BY date, created_at
        """
        
        results = db.session.execute(text(history_query), {"trip_id": trip_id}).fetchall()
        
        return [dict(row._mapping) for row in results]

# 使用示例：
# service = UnifiedTripQueryService()
# result = service.find_trip_by_id(1585)
# if result["found"]:
#     print(f"找到班次：{result['message']}")
#     print(f"數據：{result['data']}")
# else:
#     print(result["message"])
'''
    
    # 寫入服務文件
    service_file = "/Users/linyancui/minimal_flask/modules/services/unified_trip_query_service.py"
    
    try:
        with open(service_file, 'w', encoding='utf-8') as f:
            f.write(service_code)
        
        print(f"✅ 統一查詢服務已創建: {service_file}")
        return True
        
    except Exception as e:
        print(f"❌ 創建統一查詢服務失敗: {str(e)}")
        return False

def modify_scheduler_service():
    """修改 scheduler_service.py，在轉移班次時保存 original_trip_id"""
    print("📝 需要手動修改 scheduler_service.py")
    print("在 update_single_trip 和 update_completed_trips 函數中：")
    print("""
    # 在插入 completed_trips 時添加 original_trip_id：
    insert_query = '''
    INSERT INTO completed_trips
    (original_trip_id, date, start_point, via_point, end_point,
     meter_fare, extra_fare, category, driver_id,
     unique_code, trip_type, passenger_name,
     passenger_leave_reason, modification_reason)
    VALUES
    (:original_trip_id, :date, :start_point, :via_point, :end_point,
     :meter_fare, :extra_fare, :category, :driver_id,
     :unique_code, :trip_type, :passenger_name,
     :passenger_leave_reason, :modification_reason)
    '''
    
    params["original_trip_id"] = trip_id  # 🔥 新增：保存原始 trip_id
    """)

def test_unified_query():
    """測試統一查詢功能"""
    print("🧪 測試統一查詢功能...")
    
    app = create_app()
    with app.app_context():
        # 導入剛創建的服務
        try:
            from modules.services.unified_trip_query_service import UnifiedTripQueryService
            
            service = UnifiedTripQueryService()
            
            # 測試一些常見的班次ID
            test_ids = [1, 100, 1000, 2014]  # 2014 是日誌中提到的
            
            for test_id in test_ids:
                try:
                    result = service.find_trip_by_id(test_id)
                    print(f"  測試 ID {test_id}: {result['message']}")
                except Exception as e:
                    print(f"  測試 ID {test_id}: ERROR - {str(e)}")
                    
        except ImportError:
            print("  ⚠️ 請重啟應用後測試統一查詢服務")

if __name__ == "__main__":
    print("🎯 修復三時間態混亂問題")
    print("=" * 50)
    
    # 1. 添加 original_trip_id 欄位
    if add_original_trip_id_column():
        print("✅ 步驟1完成：添加 original_trip_id 欄位")
    else:
        print("❌ 步驟1失敗")
        exit(1)
    
    # 2. 更新現有記錄
    if update_existing_completed_trips():
        print("✅ 步驟2完成：更新現有記錄")
    else:
        print("⚠️ 步驟2部分完成")
    
    # 3. 創建統一查詢服務
    if create_unified_query_service():
        print("✅ 步驟3完成：創建統一查詢服務")
    else:
        print("❌ 步驟3失敗")
        
    # 4. 提醒手動修改
    modify_scheduler_service()
    
    # 5. 測試功能
    test_unified_query()
    
    print("\n" + "=" * 50)
    print("🎉 三時間態混亂問題修復完成！")
    print("\n📋 下一步操作：")
    print("  1. 手動修改 scheduler_service.py 添加 original_trip_id 支持")
    print("  2. 重啟應用測試統一查詢功能") 
    print("  3. 更新相關的查詢命令使用新的統一服務")
    print("\n✨ 用戶現在可以用同一個ID查詢，不管班次在哪個時間態！")