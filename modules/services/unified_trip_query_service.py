
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
