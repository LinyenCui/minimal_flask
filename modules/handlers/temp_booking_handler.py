"""
處理臨時預約功能的模組，用於處理客戶臨時需求的班次預約
"""
from datetime import datetime, date, timedelta
from flask import current_app
from sqlalchemy import text as sql_text
import logging
import traceback
import re

from modules.models.base import db
from modules.utils.taiwan_time import get_taiwan_time, get_taiwan_date
from modules.utils.helpers import parse_date_input, parse_time_input
from modules.flex_designs.temp_booking_flex import (
    get_temp_booking_start_flex, 
    get_temp_booking_time_flex, 
    get_temp_booking_location_flex,
    get_temp_booking_destination_flex,
    get_temp_booking_confirm_flex
)
from modules.services.ai_service import extract_booking_info_with_gemini
from linebot.v3.messaging import TextMessage, QuickReply, QuickReplyItem, MessageAction

# State definitions for clarity
STATE_WAITING_AI_INPUT = "waiting_for_ai_input"
STATE_WAITING_AI_FOLLOWUP = "waiting_for_ai_followup"
STATE_WAITING_CONFIRM = "waiting_for_confirm"
# Old step-by-step states (REMOVED)
# STATE_WAITING_DATE = "waiting_for_date" 
# STATE_WAITING_TIME = "waiting_for_time"
# STATE_WAITING_LOCATION = "waiting_for_location"
# STATE_WAITING_DESTINATION = "waiting_for_destination"

temp_booking_states = {}
logger = logging.getLogger(__name__)

def handle_temp_booking_start(user_id, category="東洋"):
    """初始化 預約叫車 (AI) 流程"""
    logger.info(f"[AI Flow Start] Initializing for User ID: {user_id}, Category: {category}")
    temp_booking_states[user_id] = {
        "state": STATE_WAITING_AI_INPUT,  # Use the consistent state name
        "data": { 
            "category": category, "date": None, "time": None, "start_point": None,
            "end_point": None, "via_point": None, "meter_fare": None, "passenger_name": None
        }
    }
    logger.info(f"[AI Flow Start] State for User ID {user_id} set to: {temp_booking_states[user_id]}")
    
    # Corrected prompt text for AI flow
    prompt_text = "請以簡短易懂的文字提供日期、時間、出發地(必需)，也能提供目的地是最好(非必需)"
    
    # Corrected Quick Reply for AI flow (Only Cancel)
    quick_reply = QuickReply(items=[
         QuickReplyItem(action=MessageAction(label="取消", text="取消"))
    ])
    
    logger.info(f"[AI Flow Start] Returning prompt: '{prompt_text}' with QuickReply: {quick_reply.to_dict()}")
    return {"type": "text", "text": prompt_text, "quick_reply": quick_reply.to_dict()}


def handle_temp_booking_message(user_id, message_text):
    """處理 AI 叫車流程中的消息"""
    if user_id not in temp_booking_states: 
        logger.info(f"用戶 {user_id} 不在叫車流程中，忽略消息。")
        return None 
        
    # --- Always handle cancel first --- 
    if message_text.lower() in ["取消", "取消預約", "cancel", "退出", "exit"]:
        logger.info(f"用戶 {user_id} 取消預約流程。")
        del temp_booking_states[user_id]
        return {"type": "text", "text": "已取消預約流程"}

    current_state = temp_booking_states[user_id]["state"]
    booking_data = temp_booking_states[user_id]["data"].copy() 
    logger.info(f"處理 AI 叫車消息: User={user_id}, State={current_state}, Msg='{message_text}'")

    try:
        # --- Ensure AI Flow States are checked correctly --- 
        if current_state == STATE_WAITING_AI_INPUT: # This MUST match the state set in handle_temp_booking_start
            response = _handle_ai_input(user_id, message_text)
        elif current_state == STATE_WAITING_AI_FOLLOWUP:
            response = _handle_ai_followup(user_id, message_text)
        elif current_state == STATE_WAITING_CONFIRM: 
             response = handle_confirm_input(user_id, message_text)
        else:
            # This case should ideally not be reached if all AI states are handled above.
            logger.warning(f"未知的預約狀態 (AI 流程): {current_state}, Resetting.")
            if user_id in temp_booking_states: del temp_booking_states[user_id]
            response = {"type": "text", "text": "預約流程出現未預期錯誤，請重新開始「預約叫車」。"}

    except Exception as e:
        logger.error(f"處理 AI 叫車消息時頂層出錯: {e}", exc_info=True)
        if user_id in temp_booking_states: del temp_booking_states[user_id]
        response = {"type": "text", "text": "預約處理過程中出現錯誤，請重新開始。"}

    return response

# --- ADD BACK: AI Helper Functions (from commit 4f4f04a) ---
def _handle_ai_input(user_id, message_text): 
    logger.info(f"[_handle_ai_input] User={user_id} Msg='{message_text}'")
    booking_data = temp_booking_states[user_id]["data"].copy()
    extracted_info = extract_booking_info_with_gemini(message_text)
    if not extracted_info: 
        logger.warning("AI 未能提取任何有效信息 (initial)。")
        return {"type": "text", "text": "抱歉，無法理解您的預約需求，請嘗試換句話說或更詳細地描述。"}
    logger.info(f"AI 初始解析結果: {extracted_info}")
    booking_data = _update_booking_data(booking_data, extracted_info) 
    missing_fields = _check_missing_fields(booking_data)
    temp_booking_states[user_id]["data"] = booking_data 
    if not missing_fields:
         logger.info("AI 初始提取信息完整，進入確認步驟")
         temp_booking_states[user_id]["state"] = STATE_WAITING_CONFIRM
         return _generate_confirm_response(booking_data)
    else:
         logger.info(f"AI 初始提取信息不完整，缺少: {missing_fields}")
         temp_booking_states[user_id]["state"] = STATE_WAITING_AI_FOLLOWUP
         return _generate_followup_prompt(booking_data, missing_fields)

def _handle_ai_followup(user_id, message_text):
    logger.info(f"[_handle_ai_followup] User={user_id} Msg='{message_text}'")
    booking_data = temp_booking_states[user_id]["data"].copy()
    extracted_info_followup = extract_booking_info_with_gemini(message_text)
    if not extracted_info_followup:
         logger.warning("AI 未能提取任何有效信息 (followup)。")
         missing_fields = _check_missing_fields(booking_data) 
         feedback_text = f"抱歉，還是不太明白。還需要請您提供：{'、'.join(missing_fields)}。" if missing_fields else "抱歉，還是不太明白，請嘗試重新說明。"
         return {"type": "text", "text": feedback_text}
    logger.info(f"AI 追問解析結果: {extracted_info_followup}")
    booking_data = _update_booking_data(booking_data, extracted_info_followup, merge=True) 
    missing_fields = _check_missing_fields(booking_data)
    temp_booking_states[user_id]["data"] = booking_data 
    if not missing_fields:
         logger.info("AI 追問後信息齊全，進入確認步驟")
         temp_booking_states[user_id]["state"] = STATE_WAITING_CONFIRM
         return _generate_confirm_response(booking_data)
    else:
         logger.info(f"AI 追問後仍缺少: {missing_fields}")
         return _generate_followup_prompt(booking_data, missing_fields)

def _update_booking_data(current_data, extracted_info, merge=False):
    logger.debug(f"Updating booking data. Merge={merge}. Current={current_data}, Extracted={extracted_info}")
    updated_data = current_data.copy()
    if (not merge or not updated_data.get("date")) and extracted_info.get("date"):
        try: 
            parsed_date = parse_date_input(extracted_info["date"])
            if parsed_date >= get_taiwan_date(): updated_data["date"] = parsed_date
        except ValueError: pass
    if updated_data.get("date") and (not merge or not updated_data.get("time")) and extracted_info.get("time"):
        try: 
            parsed_time = parse_time_input(extracted_info["time"])
            now = get_taiwan_time()
            if not (updated_data["date"] == now.date() and parsed_time < now.time()): updated_data["time"] = parsed_time
        except ValueError: pass
    if (not merge or not updated_data.get("start_point")) and extracted_info.get("start_point"):
        updated_data["start_point"] = extracted_info["start_point"]
    if (not merge or not updated_data.get("end_point")) and extracted_info.get("end_point"):
        updated_data["end_point"] = extracted_info["end_point"]
    if (not merge or not updated_data.get("via_point")) and extracted_info.get("via_point"):
        updated_data["via_point"] = extracted_info["via_point"]
    if extracted_info.get("category"): updated_data["category"] = extracted_info["category"]
    # 🔥 新增：處理錶價
    if (not merge or not updated_data.get("meter_fare")) and extracted_info.get("meter_fare"):
        try:
            meter_fare = int(extracted_info["meter_fare"])
            if meter_fare > 0: updated_data["meter_fare"] = meter_fare
        except (ValueError, TypeError): pass
    # 🔥 新增：處理乘客姓名
    if (not merge or not updated_data.get("passenger_name")) and extracted_info.get("passenger_name"):
        updated_data["passenger_name"] = extracted_info["passenger_name"]
    logger.debug(f"Updated booking data: {updated_data}")
    return updated_data

def _check_missing_fields(booking_data):
    missing = []
    if not booking_data.get("date"): missing.append("日期")
    if not booking_data.get("time"): missing.append("時間")
    if not booking_data.get("start_point"): missing.append("起點")
    return missing

def _generate_confirm_response(booking_data):
    try:
        if not all([booking_data.get("date"), booking_data.get("time"), booking_data.get("start_point") ]):
            logger.error(f"生成確認 Flex 時缺少必要數據: {booking_data}")
            return {"type":"text", "text": "抱歉，預約信息不完整，無法生成確認。請重新開始。"}
        formatted_date = booking_data["date"].strftime("%Y-%m-%d")
        formatted_time = booking_data["time"].strftime("%H:%M")
        flex_content, quick_reply = get_temp_booking_confirm_flex(
            formatted_date, formatted_time,
            booking_data["start_point"],
            booking_data.get("end_point"), 
            booking_data.get("category", "東洋"), 
            booking_data.get("via_point"),
            booking_data.get("meter_fare"),      # 🔥 新增：錶價
            booking_data.get("passenger_name")   # 🔥 新增：乘客姓名
        )
        return {"type": "flex", "alt_text": "請確認預約信息", "contents": flex_content, "quick_reply": quick_reply}
    except Exception as e:
        logger.error(f"生成確認 Flex 時出錯: {e}", exc_info=True)
        # 🔥 增強文本確認界面，包含新欄位
        confirm_text = (
             "我們已處理您的請求，但生成確認界面出錯。\n"
             "請確認以下信息是否正確：\n"
             f"日期: {booking_data.get('date')}, 時間: {booking_data.get('time')}, "
             f"起點: {booking_data.get('start_point')}"
             f"{', 目的地: ' + booking_data['end_point'] if booking_data.get('end_point') else ''}"
             f"{', 途經: ' + booking_data['via_point'] if booking_data.get('via_point') else ''}"
             f"{', 類別: ' + booking_data['category'] if booking_data.get('category') else ''}"
             f"{', 錶價: ' + str(booking_data['meter_fare']) + '元' if booking_data.get('meter_fare') else ''}"
             f"{', 乘客: ' + booking_data['passenger_name'] if booking_data.get('passenger_name') else ''}\n\n"
             "回覆「確認」或「取消」。"
        )
        return {"type": "text", "text": confirm_text}

def _generate_followup_prompt(booking_data, missing_fields):
    feedback_parts = []
    if booking_data.get("date"): feedback_parts.append(f"日期:{booking_data['date'].strftime('%m/%d')}")
    if booking_data.get("time"): feedback_parts.append(f"時間:{booking_data['time'].strftime('%H:%M')}")
    if booking_data.get("start_point"): feedback_parts.append(f"起點:'{booking_data['start_point']}'")
    if booking_data.get("end_point"): feedback_parts.append(f"目的地:'{booking_data['end_point']}'")
    if booking_data.get("via_point"): feedback_parts.append(f"途經:'{booking_data['via_point']}'")
    initial_category = "東洋" 
    if booking_data.get("category") and booking_data.get("category") != initial_category: 
        feedback_parts.append(f"類別:'{booking_data['category']}'")
    feedback_prefix = "好的，我了解到：" + "、".join(feedback_parts) + "。\n" if feedback_parts else "好的，\n"
    feedback_suffix = f"還需要請您提供：{'、'.join(missing_fields)}。"
    feedback_text = feedback_prefix + feedback_suffix
    return {"type": "text", "text": feedback_text}
# --- END ADD BACK --- 

# --- Keep handle_confirm_input as it is likely shared/correct --- 
def handle_confirm_input(user_id, message_text):
    # ... (Existing confirmation logic - SAVE TO DB) ...
    # Ensure this function uses the latest booking_data including via_point
    # The logic to include via_point in the DB insert and success message
    # should already be here from previous edits.
    try:
        if message_text.lower() not in ["確認", "confirm", "yes", "是", "確定", "ok"]:
            if user_id in temp_booking_states: del temp_booking_states[user_id]
            return {"type": "text", "text": "您已取消臨時預約。"}
        
        booking_data = temp_booking_states[user_id]["data"]
        logger.info(f"用戶 {user_id} 確認預約，數據: {booking_data}")
        
        # 🔥 新增：自動處理乘客資料（使用獨立事務）
        if booking_data.get("passenger_name"):
            try:
                passenger_name = booking_data["passenger_name"]
                category = booking_data.get("category", "東洋")
                
                # 🔥 修復：使用short_name進行檢查（因為有UNIQUE約束）
                check_query = "SELECT id FROM customers WHERE name = :name OR short_name = :short_name"
                existing_passenger = db.session.execute(sql_text(check_query), {
                    "name": passenger_name, 
                    "short_name": passenger_name
                }).fetchone()
                
                if existing_passenger:
                    logger.info(f"乘客已存在: {passenger_name} (ID: {existing_passenger[0]})")
                else:
                    # 🔥 修復：使用獨立事務處理乘客插入，避免影響主要預約流程
                    try:
                        # 先提交當前事務以清除任何錯誤狀態
                        db.session.commit()
                        
                        # 使用新的事務處理乘客插入
                        insert_passenger_query = """
                        INSERT INTO customers (name, short_name, category, address) 
                        VALUES (:name, :short_name, :category, :address)
                        ON CONFLICT (short_name) DO NOTHING
                        """
                        db.session.execute(sql_text(insert_passenger_query), {
                            "name": passenger_name,
                            "short_name": passenger_name,
                            "category": category,
                            "address": "預約時未提供地址"
                        })
                        db.session.commit()
                        logger.info(f"成功新增乘客: {passenger_name}, 類別: {category}")
                    except Exception as insert_error:
                        # 回滾乘客插入事務，但不影響主要預約流程
                        logger.warning(f"乘客插入出錯，但繼續預約流程: {insert_error}")
                        db.session.rollback()
                        # 重新開始新的事務為預約做準備
                        db.session.begin()
                    
            except Exception as passenger_error:
                logger.error(f"處理乘客資料時出錯: {passenger_error}")
                db.session.rollback()
                # 重新開始新的事務
                db.session.begin()
        
        try:
            insert_query = """
            INSERT INTO trips (date, time, start_point, end_point, category, status, trip_type, 
                              custom_start_point, custom_end_point, custom_via_point, meter_fare, passenger_name)
            VALUES (:date, :time, '臨時地點', '臨時地點', :category, '待派', 'temp', 
                    :custom_start_point, :custom_end_point, :custom_via_point, :meter_fare, :passenger_name)
            RETURNING trip_id
            """
            end_point_db = booking_data.get("end_point")
            if not end_point_db or end_point_db == "無(略過)": end_point_db = "无指定终点"
            via_point_db = booking_data.get("via_point")
            
            params = {
                "date": booking_data["date"],
                "time": booking_data["time"],
                "category": booking_data.get("category", "東洋"),
                "custom_start_point": booking_data["start_point"],
                "custom_end_point": end_point_db,
                "custom_via_point": via_point_db,
                "meter_fare": booking_data.get("meter_fare"),        # 錶價
                "passenger_name": booking_data.get("passenger_name") # 乘客姓名
            }
            result = db.session.execute(sql_text(insert_query), params)
            new_trip_id = result.fetchone()[0]
            
            # Update unique code and week number
            unique_code = f"T_{new_trip_id}"
            _, week_number, _ = booking_data["date"].isocalendar()
            update_query = "UPDATE trips SET unique_code = :unique_code, week_number = :week_number WHERE trip_id = :trip_id"
            db.session.execute(sql_text(update_query), {"unique_code": unique_code, "week_number": week_number, "trip_id": new_trip_id})
            
            db.session.commit()
            logger.info(f"成功創建臨時班次: ID={new_trip_id}, Data={booking_data}")
            del temp_booking_states[user_id]
            
            # Build success message
            success_message = (
                 "✅ 臨時預約成功！\n\n"
                 f"班次ID: {new_trip_id}\n"
                 f"日期：{booking_data['date'].strftime('%Y-%m-%d')}\n"
                 f"時間：{booking_data['time'].strftime('%H:%M')}\n"
                 f"起點：{booking_data['start_point']}\n"
            )
            if via_point_db: success_message += f"途經：{via_point_db}\n"
            if booking_data.get("end_point") and booking_data.get("end_point") != "無(略過)": 
                success_message += f"目的地：{booking_data['end_point']}\n"
            # 顯示錶價信息
            if booking_data.get("meter_fare"):
                success_message += f"錶價：{booking_data['meter_fare']}元\n"
            # 顯示乘客信息
            if booking_data.get("passenger_name"):
                success_message += f"乘客：{booking_data['passenger_name']}\n"
            success_message += (
                 f"類別：{booking_data['category']}\n"
                 f"狀態：待派\n\n"
                 "我們會盡快為您指派司機。"
            )
            return {"type": "text", "text": success_message}
        
        except Exception as db_error:
             logger.error(f"保存臨時預約到數據庫時出錯: {db_error}", exc_info=True)
             db.session.rollback()
             # Don't clear state on DB error, allow retry?
             # if user_id in temp_booking_states: del temp_booking_states[user_id]
             return {"type": "text", "text": f"保存預約時出錯，請稍後重試或聯繫管理員。"}
    
    except Exception as e:
         logger.error(f"處理確認輸入時出錯: {e}", exc_info=True)
         if user_id in temp_booking_states: del temp_booking_states[user_id]
         return {"type": "text", "text": "處理預約確認時出錯。請重新開始預約流程。"}

# --- Remove or comment out old step-by-step handlers --- 
# (All old step-by-step handler definitions and their comments should be removed if they exist below this line)

def handle_temp_booking_help():
    """提供預約叫車幫助信息"""
    help_text = (
        "📱 預約叫車使用說明：\n\n"
        "1. 輸入「預約叫車」開始。\n"
        "2. 描述您的需求，例如：『明天下午三點半從火車站送到成大醫院，途經文南路』。\n"
        "3. 若信息不全，我會向您確認或請您補充。\n"
        "4. 確認信息無誤後即可完成預約。\n\n"
        "💡 任何時候輸入「取消」即可取消當前叫車流程。"
    )
    return {"type": "text", "text": help_text} 