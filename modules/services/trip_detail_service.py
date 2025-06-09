from flask import current_app
from sqlalchemy import text
import traceback
import inspect
import logging
import json
# import sys # No longer needed for sys.modules manipulation

logger = logging.getLogger(__name__)

from modules.models.base import db
from modules.flex_designs.trip_details_flex import get_trip_details_flex # Standard import
from linebot.v3.messaging import FlexMessage, FlexContainer, QuickReply as LineQuickReply

def handle_trip_details_flex(trip_id):
    """以Flex Message格式返回班次詳情"""
    try:
        func_file_path = inspect.getfile(get_trip_details_flex)
        logger.info(f"<<<<< get_trip_details_flex is imported from: {func_file_path} >>>>>")
    except Exception as e_inspect:
        logger.error(f"<<<<< Error inspecting get_trip_details_flex: {e_inspect} >>>>>")

    try:
        # Removed forced sys.modules deletion and re-import from here
        
        # ... (查詢和 trip_data 準備邏輯保持不變) ...
        query = """ 
        SELECT 
            t.trip_id, t.date, t.time, t.start_point, t.via_point,
            t.end_point, t.status, d.id as driver_id, d.plate_number,
            t.category, t.fixed_trip_id, t.meter_fare as base_fare,
            t.extra_fare, t.modification_reason, t.passenger_leave_reason, t.trip_type, t.custom_start_point, t.custom_via_point,
            t.custom_end_point
        FROM trips t
        LEFT JOIN drivers d ON t.driver_id = d.id
        WHERE t.trip_id = :trip_id
        """
        trip = db.session.execute(text(query), {"trip_id": trip_id}).fetchone()
        if not trip:
            return None, f"找不到ID為 {trip_id} 的班次。"
        
        try:
            trip_data = dict(trip._mapping) 
        except AttributeError: 
            trip_data = dict(zip(trip.keys(), trip))
        
        # Populate display_ fields for consistency
        if trip_data.get('trip_type') == 'temp':
            trip_data['display_start_point'] = trip_data.get('custom_start_point') or trip_data.get('start_point')
            trip_data['display_via_point'] = trip_data.get('custom_via_point') or trip_data.get('via_point')
            trip_data['display_end_point'] = trip_data.get('custom_end_point') or trip_data.get('end_point')
        else:
            trip_data['display_start_point'] = trip_data.get('start_point')
            trip_data['display_via_point'] = trip_data.get('via_point')
            trip_data['display_end_point'] = trip_data.get('end_point')
                
        result_dict = get_trip_details_flex(trip_id, trip_data)
        
        if result_dict and "flex_message" in result_dict and isinstance(result_dict["flex_message"], dict):
            flex_message_payload = result_dict["flex_message"]
            quick_reply_payload = result_dict.get("quick_reply")

            logger.info(f"+++++ PREPARING TO SEND FLEX MESSAGE FOR TRIP {trip_id} (Final Check) +++++")
            try:
                logger.info("Raw flex_message_payload from get_trip_details_flex (Final Check):")
                logger.info(json.dumps(flex_message_payload, indent=2, ensure_ascii=False))
                if quick_reply_payload:
                    logger.info("Raw quick_reply_payload from get_trip_details_flex (Final Check):")
                    logger.info(json.dumps(quick_reply_payload, indent=2, ensure_ascii=False))
            except Exception as e_json_dump:
                logger.error(f"Error during JSON dump for logging: {e_json_dump}")
            logger.info(f"++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
            
            return result_dict, None 
        else:
            logger.error(f"get_trip_details_flex (from import) did not return expected dict structure for trip {trip_id}. Received: {result_dict}")
            return None, f"無法生成班次 {trip_id} 的詳細資訊 (Final Check)。"
            
    except Exception as e:
        current_app.logger.error(f"處理班次詳情Flex Message時出錯: {e}")
        traceback.print_exc()
        return None, f"查詢班次詳情錯誤: {str(e)}"
