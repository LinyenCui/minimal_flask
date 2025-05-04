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
# Old step-by-step states (keep for potential future use or fallback)
STATE_WAITING_DATE = "waiting_for_date" 
STATE_WAITING_TIME = "waiting_for_time"
STATE_WAITING_LOCATION = "waiting_for_location"
STATE_WAITING_DESTINATION = "waiting_for_destination"

temp_booking_states = {}
logger = logging.getLogger(__name__)

def handle_temp_booking_start(user_id, category="東洋"):
    """初始化 AI 叫車流程"""
    try:
        logger.info(f"初始化 AI 叫車流程，用戶ID: {user_id}, 類別: {category}")
        temp_booking_states[user_id] = {
            "state": STATE_WAITING_AI_INPUT,
            "data": {
                "category": category,
                "date": None, "time": None, "start_point": None,
                "end_point": None, "via_point": None 
            }
        }
        logger.info(f"已設置用戶 {user_id} 的 AI 叫車狀態: {temp_booking_states[user_id]}")
        prompt_text = "請儘可能以簡短易懂的文字提供日期、時間、出發地，也能提供目的地是最好(非必需)，更詳細的經過地或哪裡的班次亦可(預設東洋)。"
        quick_reply = QuickReply(items=[
             QuickReplyItem(action=MessageAction(label="取消", text="取消"))
        ])
        return {"type": "text", "text": prompt_text, "quick_reply": quick_reply.to_dict()}
    except Exception as e:
        if user_id in temp_booking_states: del temp_booking_states[user_id]
        logger.error(f"初始化 AI 叫車流程時出錯: {e}", exc_info=True)
        return {"type": "text", "text": "AI 叫車系統暫時無法使用，請稍後重試"}


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
        # --- State: Waiting for initial AI input --- 
        if current_state == STATE_WAITING_AI_INPUT:
            extracted_info = extract_booking_info_with_gemini(message_text)
            if not extracted_info: 
                logger.warning("AI 未能提取任何有效信息 (initial)。")
                return {"type": "text", "text": "抱歉，無法理解您的預約需求，請嘗試換句話說或更詳細地描述。"}
                
            logger.info(f"AI 初始解析結果: {extracted_info}")
            booking_data = _update_booking_data(booking_data, extracted_info) # Update using helper
            missing_fields = _check_missing_fields(booking_data)
            
            temp_booking_states[user_id]["data"] = booking_data # Save updated data

            if not missing_fields:
                 logger.info("AI 初始提取信息完整，進入確認步驟")
                 temp_booking_states[user_id]["state"] = STATE_WAITING_CONFIRM
                 return _generate_confirm_response(booking_data)
            else:
                 logger.info(f"AI 初始提取信息不完整，缺少: {missing_fields}")
                 temp_booking_states[user_id]["state"] = STATE_WAITING_AI_FOLLOWUP
                 return _generate_followup_prompt(booking_data, missing_fields)

        # --- State: Waiting for AI followup --- 
        elif current_state == STATE_WAITING_AI_FOLLOWUP:
            extracted_info_followup = extract_booking_info_with_gemini(message_text)
            if not extracted_info_followup:
                 logger.warning("AI 未能提取任何有效信息 (followup)。")
                 missing_fields = _check_missing_fields(booking_data) # Check based on existing data
                 feedback_text = f"抱歉，還是不太明白。還需要請您提供：{'、'.join(missing_fields)}。" if missing_fields else "抱歉，還是不太明白，請嘗試重新說明。"
                 return {"type": "text", "text": feedback_text}
                 
            logger.info(f"AI 追問解析結果: {extracted_info_followup}")
            booking_data = _update_booking_data(booking_data, extracted_info_followup, merge=True) # Merge results
            missing_fields = _check_missing_fields(booking_data)
            
            temp_booking_states[user_id]["data"] = booking_data # Save updated data

            if not missing_fields:
                 logger.info("AI 追問後信息齊全，進入確認步驟")
                 temp_booking_states[user_id]["state"] = STATE_WAITING_CONFIRM
                 return _generate_confirm_response(booking_data)
            else:
                 logger.info(f"AI 追問後仍缺少: {missing_fields}")
                 # Stay in followup state
                 return _generate_followup_prompt(booking_data, missing_fields)
                 
        # --- State: Waiting for confirmation --- 
        elif current_state == STATE_WAITING_CONFIRM:
            # Reuse the existing confirm handler, assuming it's correct
            return handle_confirm_input(user_id, message_text)
            
        # --- Handle unexpected old states --- 
        elif current_state in [STATE_WAITING_DATE, STATE_WAITING_TIME, STATE_WAITING_LOCATION, STATE_WAITING_DESTINATION]:
             logger.warning(f"Reached unexpected state '{current_state}' during AI flow. Resetting.")
             if user_id in temp_booking_states: del temp_booking_states[user_id]
             return {"type": "text", "text": "預約流程狀態錯誤，請重新使用「AI叫車」開始。"}
            
        else:
            logger.warning(f"未知的用戶狀態: {current_state}")
            if user_id in temp_booking_states: del temp_booking_states[user_id]
            return {"type": "text", "text": "對不起，預約流程出現錯誤。請重新開始。"}

    except Exception as e:
        logger.error(f"處理 AI 叫車消息時頂層出錯: {e}", exc_info=True)
        if user_id in temp_booking_states: del temp_booking_states[user_id]
        return {"type": "text", "text": "預約處理過程中出現錯誤，請重新開始。"}

# --- Helper function to update booking data --- 
def _update_booking_data(current_data, extracted_info, merge=False):
    """Updates booking data with extracted info. If merge=True, only fills missing fields."""
    logger.debug(f"Updating booking data. Merge={merge}. Current={current_data}, Extracted={extracted_info}")
    updated_data = current_data.copy()
    
    # Date
    if (not merge or not updated_data.get("date")) and extracted_info.get("date"):
        try: 
            parsed_date = parse_date_input(extracted_info["date"])
            if parsed_date >= get_taiwan_date(): updated_data["date"] = parsed_date
        except ValueError: pass
        
    # Time (Requires valid date)
    if updated_data.get("date") and (not merge or not updated_data.get("time")) and extracted_info.get("time"):
        try: 
            parsed_time = parse_time_input(extracted_info["time"])
            now = get_taiwan_time()
            if not (updated_data["date"] == now.date() and parsed_time < now.time()): 
                updated_data["time"] = parsed_time
        except ValueError: pass
        
    # Start Point
    if (not merge or not updated_data.get("start_point")) and extracted_info.get("start_point"):
        updated_data["start_point"] = extracted_info["start_point"]
        
    # Optional Fields (Merge or Overwrite based on `merge` flag)
    if (not merge or not updated_data.get("end_point")) and extracted_info.get("end_point"):
        updated_data["end_point"] = extracted_info["end_point"]
    if (not merge or not updated_data.get("via_point")) and extracted_info.get("via_point"):
        updated_data["via_point"] = extracted_info["via_point"]
    # Category: Always overwrite if provided by AI?
    if extracted_info.get("category"): 
        updated_data["category"] = extracted_info["category"]
        
    logger.debug(f"Updated booking data: {updated_data}")
    return updated_data

# --- Helper function to check missing fields --- 
def _check_missing_fields(booking_data):
    """Checks for required fields and returns a list of missing ones."""
    missing = []
    if not booking_data.get("date"): missing.append("日期")
    if not booking_data.get("time"): missing.append("時間")
    if not booking_data.get("start_point"): missing.append("起點")
    return missing

# --- Helper function to generate confirmation response --- 
def _generate_confirm_response(booking_data):
    """Generates the Flex Message dictionary for confirmation."""
    try:
        formatted_date = booking_data["date"].strftime("%Y-%m-%d")
        formatted_time = booking_data["time"].strftime("%H:%M")
        flex_content, quick_reply = get_temp_booking_confirm_flex(
            formatted_date, formatted_time,
            booking_data["start_point"],
            booking_data.get("end_point"), 
            booking_data.get("category", "東洋"), 
            booking_data.get("via_point") 
        )
        return {"type": "flex", "alt_text": "請確認預約信息", "contents": flex_content, "quick_reply": quick_reply}
    except Exception as e:
        logger.error(f"生成確認 Flex 時出錯: {e}", exc_info=True)
        # Fallback to simple text confirmation request
        confirm_text = (
             "我們已處理您的請求，但生成確認界面出錯。\n"
             "請確認以下信息是否正確：\n"
             f"日期: {booking_data.get('date')}, 時間: {booking_data.get('time')}, "
             f"起點: {booking_data.get('start_point')}"
             # Add optional fields if they exist
             f"{', 目的地: ' + booking_data['end_point'] if booking_data.get('end_point') else ''}"
             f"{', 途經: ' + booking_data['via_point'] if booking_data.get('via_point') else ''}"
             f"{', 類別: ' + booking_data['category'] if booking_data.get('category') else ''}\n\n"
             "回覆「確認」或「取消」。"
        )
        return {"type": "text", "text": confirm_text}

# --- Helper function to generate followup prompt --- 
def _generate_followup_prompt(booking_data, missing_fields):
    """Generates the text message prompt for missing information."""
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
        
        try:
            insert_query = """
            INSERT INTO trips (date, time, start_point, end_point, category, status, trip_type, custom_start_point, custom_end_point, custom_via_point)
            VALUES (:date, :time, '臨時地點', '臨時地點', :category, '待派', 'temp', :custom_start_point, :custom_end_point, :custom_via_point)
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
                "custom_via_point": via_point_db
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
            if booking_data.get("end_point") and booking_data.get("end_point") != "無(略過)": success_message += f"目的地：{booking_data['end_point']}\n"
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
# def handle_date_input(...)
# def handle_time_input(...)
# ...

def handle_temp_booking_help():
    # ... (Existing help logic can remain for now) ...
    pass

def handle_temp_booking_start(user_id, category="東洋"):
    """初始化 AI 叫車流程"""
    try:
        logger.info(f"初始化 AI 叫車流程，用戶ID: {user_id}, 類別: {category}")
        temp_booking_states[user_id] = {
            "state": "waiting_for_ai_input", # Start with waiting for NL input
            "data": {
                "category": category,
                # Initialize other fields to None or leave empty initially
                "date": None,
                "time": None,
                "start_point": None,
                "end_point": None,
                "via_point": None 
            }
        }
        logger.info(f"已設置用戶 {user_id} 的 AI 叫車狀態: {temp_booking_states[user_id]}")
        
        # Use the prompt from the logs
        prompt_text = "請儘可能以簡短易懂的文字提供日期、時間、出發地，也能提供目的地是最好(非必需)，更詳細的經過地或哪裡的班次亦可(預設東洋)。"
        
        # Add a cancel button for easier exit
        quick_reply = QuickReply(items=[
             QuickReplyItem(action=MessageAction(label="取消", text="取消"))
             # Optionally add a button to force step-by-step later if needed
        ])
        
        return {
            "type": "text",
            "text": prompt_text,
            "quick_reply": quick_reply.to_dict()
        }
    except Exception as e:
        # 出錯時清除用戶狀態
        if user_id in temp_booking_states:
            del temp_booking_states[user_id]
            logger.info(f"已清除用戶 {user_id} 的預約狀態")
        logger.error(f"初始化 AI 叫車流程時出錯: {e}")
        traceback.print_exc()
        return {
            "type": "text",
            "text": "AI 叫車系統暫時無法使用，請稍後重試"
        }

def handle_temp_booking_message(user_id, message_text):
    """處理 AI 叫車流程中的消息"""
    try:
        logger.info(f"處理 AI 叫車消息: 用戶ID={user_id}, 消息='{message_text}'")
        
        if message_text.lower() in ["取消", "取消預約", "cancel", "退出", "exit"]:
            if user_id in temp_booking_states: del temp_booking_states[user_id]
            return {"type": "text", "text": "已取消預約流程"}

        if user_id not in temp_booking_states: return None 

        current_state = temp_booking_states[user_id]["state"]
        logger.info(f"用戶 {user_id} 當前狀態: {current_state}")
        booking_data = temp_booking_states[user_id]["data"].copy() 

        if current_state == "waiting_for_ai_input":
            logger.info(f"嘗試使用 AI 解析初始輸入: {message_text}")
            extracted_info = extract_booking_info_with_gemini(message_text)

            if extracted_info:
                logger.info(f"AI 解析結果: {extracted_info}")
                missing_fields = []
                # --- Process and validate extracted info --- 
                # Date
                extracted_date_str = extracted_info.get("date")
                if extracted_date_str:
                    try:
                        parsed_date = parse_date_input(extracted_date_str)
                        if parsed_date >= get_taiwan_date(): booking_data["date"] = parsed_date
                    except ValueError: pass # Ignore invalid date format from AI
                if not booking_data.get("date"): missing_fields.append("日期")
                
                # Time (only process if date is valid)
                extracted_time_str = extracted_info.get("time")
                if booking_data.get("date") and extracted_time_str:
                    try:
                        parsed_time = parse_time_input(extracted_time_str)
                        now = get_taiwan_time()
                        if not (booking_data["date"] == now.date() and parsed_time < now.time()): booking_data["time"] = parsed_time
                    except ValueError: pass # Ignore invalid time format
                if not booking_data.get("time"): missing_fields.append("時間")
                
                # Start Point
                if extracted_info.get("start_point"): booking_data["start_point"] = extracted_info.get("start_point")
                if not booking_data.get("start_point"): missing_fields.append("起點")
                
                # Optional Fields
                if extracted_info.get("end_point"): booking_data["end_point"] = extracted_info.get("end_point")
                if extracted_info.get("via_point"): booking_data["via_point"] = extracted_info.get("via_point")
                if extracted_info.get("category"): booking_data["category"] = extracted_info.get("category")
                
                temp_booking_states[user_id]["data"] = booking_data 
                logger.info(f"AI初步處理後數據: {booking_data}")
                
                # --- Decide next step --- 
                if not missing_fields:
                    logger.info("AI 提取信息完整，進入確認步驟")
                    temp_booking_states[user_id]["state"] = "waiting_for_confirm"
                    # Generate confirm flex...
                    try:
                         formatted_date = booking_data["date"].strftime("%Y-%m-%d")
                         formatted_time = booking_data["time"].strftime("%H:%M")
                         flex_content, quick_reply = get_temp_booking_confirm_flex(
                              formatted_date, formatted_time,
                              booking_data["start_point"],
                              booking_data.get("end_point"), 
                              booking_data.get("category", "東洋"), # Use default if missing in data
                              booking_data.get("via_point") 
                         )
                         return {"type": "flex", "alt_text": "請確認預約信息", "contents": flex_content, "quick_reply": quick_reply}
                    except Exception as confirm_e: 
                        logger.error(f"AI流程中創建確認界面時出錯: {confirm_e}")
                        return {"type": "text", "text": "信息已處理，但生成確認界面出錯。請輸入「確認」或「取消」。"}
                else:
                    logger.info(f"AI 提取信息不完整，缺少: {missing_fields}")
                    temp_booking_states[user_id]["state"] = "waiting_for_ai_followup"
                    # --- Rebuild feedback text logic carefully --- 
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
                    # --- End feedback text logic --- 
                    return {"type": "text", "text": feedback_text}
            else:
                 logger.warning("AI 未能提取任何有效信息。")
                 return {"type": "text", "text": "抱歉，無法理解您的預約需求，請嘗試換句話說或更詳細地描述。"}
        
        elif current_state == "waiting_for_ai_followup":
             logger.info(f"處理 AI 追問狀態，用戶補充輸入: {message_text}")
             extracted_info_followup = extract_booking_info_with_gemini(message_text)
             
             if extracted_info_followup:
                  logger.info(f"AI 追問解析結果: {extracted_info_followup}")
                  # --- Merge followup info (only fill if None/missing in existing booking_data) ---
                  if not booking_data.get("date") and extracted_info_followup.get("date"):
                      try: 
                           parsed_date = parse_date_input(extracted_info_followup["date"])
                           if parsed_date >= get_taiwan_date(): booking_data["date"] = parsed_date
                      except ValueError: pass
                  if not booking_data.get("time") and booking_data.get("date") and extracted_info_followup.get("time"):
                       try: 
                           parsed_time = parse_time_input(extracted_info_followup["time"])
                           now = get_taiwan_time()
                           if not (booking_data["date"] == now.date() and parsed_time < now.time()): 
                               booking_data["time"] = parsed_time
                       except ValueError: pass
                  if not booking_data.get("start_point") and extracted_info_followup.get("start_point"):
                       booking_data["start_point"] = extracted_info_followup["start_point"]
                  # Merge optional fields 
                  if not booking_data.get("end_point") and extracted_info_followup.get("end_point"): 
                       booking_data["end_point"] = extracted_info_followup["end_point"]
                  if not booking_data.get("via_point") and extracted_info_followup.get("via_point"): 
                       booking_data["via_point"] = extracted_info_followup["via_point"]
                  if booking_data.get("category") == "東洋" and extracted_info_followup.get("category"): 
                       booking_data["category"] = extracted_info_followup["category"]
                  
                  temp_booking_states[user_id]["data"] = booking_data
                  logger.info(f"合併追問信息後數據: {booking_data}")
                  
                  # --- Check completion again --- 
                  missing_fields = []
                  if not booking_data.get("date"): missing_fields.append("日期")
                  if not booking_data.get("time"): missing_fields.append("時間")
                  if not booking_data.get("start_point"): missing_fields.append("起點")

                  if not missing_fields:
                       logger.info("AI 追問後信息齊全，進入確認步驟")
                       temp_booking_states[user_id]["state"] = "waiting_for_confirm"
                       try:
                           formatted_date = booking_data["date"].strftime("%Y-%m-%d")
                           formatted_time = booking_data["time"].strftime("%H:%M")
                           flex_content, quick_reply = get_temp_booking_confirm_flex(
                                formatted_date, formatted_time,
                                booking_data["start_point"],
                                booking_data.get("end_point"), 
                                booking_data.get("category", "東洋"),
                                booking_data.get("via_point") 
                           )
                           return {"type": "flex", "alt_text": "請確認預約信息", "contents": flex_content, "quick_reply": quick_reply}
                       except Exception as confirm_e: 
                            logger.error(f"AI追問流程中創建確認界面時出錯: {confirm_e}")
                            return {"type": "text", "text": "信息已處理，但生成確認界面出錯。請輸入「確認」或「取消」。"}
                  else:
                       logger.info(f"AI 追問後仍缺少: {missing_fields}")
                       # --- Rebuild feedback text logic carefully --- 
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
                       # --- End feedback text logic --- 
                       return {"type": "text", "text": feedback_text} 
             else:
                  logger.warning("AI 未能解析補充信息。")
                  # Re-prompt based on currently known missing fields
                  missing_fields = []
                  if not booking_data.get("date"): missing_fields.append("日期")
                  if not booking_data.get("time"): missing_fields.append("時間")
                  if not booking_data.get("start_point"): missing_fields.append("起點")
                  if missing_fields: # Only prompt if something is actually missing
                       feedback_text = f"抱歉，還是不太明白。還需要請您提供：{'、'.join(missing_fields)}。"
                  else: # Should not happen if state is followup, but as a fallback
                       feedback_text = "抱歉，無法處理您的輸入，請嘗試重新說明。"
                       temp_booking_states[user_id]["state"] = "waiting_for_ai_input" # Reset state?
                  return {"type": "text", "text": feedback_text}
                  
        elif current_state == "waiting_for_confirm":
            return handle_confirm_input(user_id, message_text)
            
        # --- Fallback for Old Step-by-Step States (Log warning) ---
        elif current_state in ["waiting_for_date", "waiting_for_time", "waiting_for_location", "waiting_for_destination"]:
             logger.warning(f"Reached unexpected state '{current_state}' during AI flow. Resetting.")
             if user_id in temp_booking_states: del temp_booking_states[user_id]
             return {"type": "text", "text": "預約流程狀態錯誤，請重新使用「AI叫車」開始。"}
            
        else:
            # ... (handle unknown state) ...
            logger.warning(f"未知的用戶狀態: {current_state}")
            if user_id in temp_booking_states: del temp_booking_states[user_id]
            return {"type": "text", "text": "對不起，預約流程出現錯誤。請重新開始。"}

    except Exception as e:
        logger.error(f"處理 AI 叫車消息時出錯: {e}")
        traceback.print_exc()
        if user_id in temp_booking_states: del temp_booking_states[user_id]
        return {"type": "text", "text": "預約處理過程中出現錯誤，請重新開始。"}

def handle_temp_booking_help():
    """提供臨時預約幫助信息"""
    help_text = (
        "📱 臨時預約使用說明：\n\n"
        "1. 輸入「臨時預約」開始預約流程\n"
        "2. 選擇或輸入預約日期\n"
        "3. 選擇或輸入預約時間（09:17, 10:32, 14:30, 15:30, 17:00, 17:30）\n"
        "4. 選擇或輸入起點位置\n"
        "5. 選擇或輸入目的地位置（可選擇「無(略過)」跳過）\n"
        "6. 確認預約信息\n\n"
        "臨時預約適用於非固定行程的單次接送服務。\n"
        "任何時候輸入「取消」即可取消預約流程。"
    )
    
    return {
        "type": "text",
        "text": help_text
    } 