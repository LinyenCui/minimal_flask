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
            t.meter_fare as base_fare,
            t.trip_type,
            t.custom_start_point,
            t.custom_via_point,
            t.custom_end_point
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
                'base_fare': trip['base_fare'],
                'trip_type': trip['trip_type'],
                'custom_start_point': trip['custom_start_point'],
                'custom_via_point': trip['custom_via_point'],
                'custom_end_point': trip['custom_end_point']
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
                'base_fare': trip[11],
                'trip_type': trip[12] if len(trip) > 12 else None,
                'custom_start_point': trip[13] if len(trip) > 13 else None,
                'custom_via_point': trip[14] if len(trip) > 14 else None,
                'custom_end_point': trip[15] if len(trip) > 15 else None
            }
        
        # 如果是臨時班次，優先使用自定義地點欄位
        if trip_data.get('trip_type') == 'temp':
            if trip_data.get('custom_start_point'):
                trip_data['display_start_point'] = trip_data['custom_start_point']
            else:
                trip_data['display_start_point'] = trip_data['start_point']
                
            if trip_data.get('custom_via_point'):
                trip_data['display_via_point'] = trip_data['custom_via_point']
            else:
                trip_data['display_via_point'] = trip_data['via_point']
                
            if trip_data.get('custom_end_point'):
                trip_data['display_end_point'] = trip_data['custom_end_point']
            else:
                trip_data['display_end_point'] = trip_data['end_point']
        else:
            # 固定班次使用標準欄位
            trip_data['display_start_point'] = trip_data['start_point']
            trip_data['display_via_point'] = trip_data['via_point']
            trip_data['display_end_point'] = trip_data['end_point']
        
        # 使用Flex設計函數生成Flex Message
        result = get_trip_details_flex(trip_id, trip_data)
        
        return result, None
        
    except Exception as e:
        current_app.logger.error(f"處理班次詳情Flex Message時出錯: {e}")
        traceback.print_exc()
        return None, f"查詢班次詳情錯誤: {str(e)}"
