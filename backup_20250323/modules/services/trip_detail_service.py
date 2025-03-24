from flask import current_app
from sqlalchemy import text
import traceback

from modules.models.base import db
from modules.flex_designs.trip_detail_flex import get_trip_details_flex

def handle_trip_details_flex(trip_id):
    """以Flex Message格式返回班次詳情"""
    try:
        # 查詢特定班次的詳細信息
        query = """
        SELECT 
            t.trip_id, 
            t.date, 
            t.time, 
            t.start_point, 
            t.via_point,
            t.end_point, 
            t.status,
            d.id as driver_id,
            d.plate_number,
            t.category,
            t.fixed_trip_id,
            t.meter_fare as base_fare
        FROM 
            trips t
        LEFT JOIN 
            drivers d ON t.driver_id = d.id
        WHERE 
            t.trip_id = :trip_id
        """
        
        trip = db.session.execute(text(query), {"trip_id": trip_id}).fetchone()
        
        if not trip:
            return None, f"找不到ID為 {trip_id} 的班次。"
        
        # 準備數據字典 - 使用索引或命名元組訪問
        try:
            # 嘗試使用字典方式訪問
            trip_data = {
                'date': trip['date'],
                'time': trip['time'],
                'start_point': trip['start_point'],
                'via_point': trip['via_point'],
                'end_point': trip['end_point'],
                'status': trip['status'],
                'driver_id': trip['driver_id'],
                'plate_number': trip['plate_number'],
                'category': trip['category'],
                'base_fare': trip['base_fare']
            }
        except (TypeError, KeyError):
            # 如果失敗，嘗試使用索引訪問
            trip_data = {
                'date': trip[1],
                'time': trip[2],
                'start_point': trip[3],
                'via_point': trip[4],
                'end_point': trip[5],
                'status': trip[6],
                'driver_id': trip[7],
                'plate_number': trip[8],
                'category': trip[9],
                'base_fare': trip[11]
            }
        
        # 使用Flex設計函數生成Flex Message
        result = get_trip_details_flex(trip_id, trip_data)
        
        return result, None
        
    except Exception as e:
        current_app.logger.error(f"處理班次詳情Flex Message時出錯: {e}")
        traceback.print_exc()
        return None, f"查詢班次詳情錯誤: {str(e)}"
