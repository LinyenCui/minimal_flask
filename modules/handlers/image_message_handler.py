"""
圖片消息處理模組 - 處理包含預約資訊的圖片
"""
import logging
import requests
from modules.services.ai_service_enhanced import extract_booking_info_from_image
from modules.handlers.temp_booking_handler import temp_booking_states, _update_booking_data, _check_missing_fields, _generate_confirm_response, _generate_followup_prompt, STATE_WAITING_AI_INPUT, STATE_WAITING_AI_FOLLOWUP, STATE_WAITING_CONFIRM
from modules.utils.line_bot import reply_text, get_line_bot_api

logger = logging.getLogger(__name__)

def process_image_message(event):
    """處理圖片消息並進行AI預約資訊提取"""
    user_id = event.source.user_id
    message_id = event.message.id
    
    logger.info(f"Processing image message for user {user_id}, message_id: {message_id}")
    
    # 檢查用戶是否在預約流程中
    if user_id not in temp_booking_states:
        logger.info(f"User {user_id} not in booking state, ignoring image")
        return
    
    current_state = temp_booking_states[user_id]["state"]
    
    # 只在等待AI輸入或AI追問階段處理圖片
    if current_state not in [STATE_WAITING_AI_INPUT, STATE_WAITING_AI_FOLLOWUP]:
        logger.info(f"User {user_id} in state {current_state}, not suitable for image processing")
        reply_text(event.reply_token, "請在文字預約流程中發送圖片，或重新開始「預約叫車」。")
        return
    
    try:
        # 下載圖片
        image_data = download_image_from_line(message_id)
        if not image_data:
            logger.error(f"Failed to download image for message {message_id}")
            reply_text(event.reply_token, "圖片下載失敗，請重新發送或改用文字描述。")
            return
        
        # 使用AI提取圖片中的預約資訊
        logger.info(f"Extracting booking info from image for user {user_id}")
        extracted_info = extract_booking_info_from_image(image_data)
        
        if not extracted_info:
            logger.warning(f"No booking info extracted from image for user {user_id}")
            reply_text(event.reply_token, "無法從圖片中識別預約資訊，請嘗試更清晰的圖片或改用文字描述。")
            return
        
        logger.info(f"Image AI extraction result for user {user_id}: {extracted_info}")
        
        # 處理提取的資訊
        booking_data = temp_booking_states[user_id]["data"].copy()
        
        if current_state == STATE_WAITING_AI_INPUT:
            # 初次圖片處理
            booking_data = _update_booking_data(booking_data, extracted_info)
            missing_fields = _check_missing_fields(booking_data)
            temp_booking_states[user_id]["data"] = booking_data
            
            if not missing_fields:
                logger.info(f"Image extraction complete for user {user_id}, moving to confirmation")
                temp_booking_states[user_id]["state"] = STATE_WAITING_CONFIRM
                response = _generate_confirm_response(booking_data)
            else:
                logger.info(f"Image extraction incomplete for user {user_id}, missing: {missing_fields}")
                temp_booking_states[user_id]["state"] = STATE_WAITING_AI_FOLLOWUP
                response = _generate_followup_prompt(booking_data, missing_fields)
                
        elif current_state == STATE_WAITING_AI_FOLLOWUP:
            # 追問階段的圖片處理
            booking_data = _update_booking_data(booking_data, extracted_info, merge=True)
            missing_fields = _check_missing_fields(booking_data)
            temp_booking_states[user_id]["data"] = booking_data
            
            if not missing_fields:
                logger.info(f"Follow-up image extraction complete for user {user_id}")
                temp_booking_states[user_id]["state"] = STATE_WAITING_CONFIRM
                response = _generate_confirm_response(booking_data)
            else:
                logger.info(f"Follow-up image extraction incomplete for user {user_id}, missing: {missing_fields}")
                response = _generate_followup_prompt(booking_data, missing_fields)
        
        # 發送回應
        if response["type"] == "text":
            reply_text(event.reply_token, response["text"])
        elif response["type"] == "flex":
            from modules.utils.line_bot import reply_flex
            reply_flex(event.reply_token, response["alt_text"], response["contents"])
            
    except Exception as e:
        logger.error(f"Error processing image message for user {user_id}: {e}", exc_info=True)
        reply_text(event.reply_token, "處理圖片時發生錯誤，請重新發送或聯繫技術支援。")

def download_image_from_line(message_id):
    """從LINE下載圖片內容"""
    try:
        line_bot_api = get_line_bot_api()
        
        # 獲取圖片內容
        message_content = line_bot_api.get_message_content(message_id)
        
        # 讀取圖片數據
        image_data = b""
        for chunk in message_content.iter_content():
            image_data += chunk
            
        logger.info(f"Downloaded image {message_id}, size: {len(image_data)} bytes")
        return image_data
        
    except Exception as e:
        logger.error(f"Error downloading image {message_id}: {e}", exc_info=True)
        return None

def get_image_format_from_data(image_data):
    """檢測圖片格式"""
    if image_data.startswith(b'\xff\xd8\xff'):
        return "jpeg"
    elif image_data.startswith(b'\x89PNG\r\n\x1a\n'):
        return "png"
    elif image_data.startswith(b'GIF87a') or image_data.startswith(b'GIF89a'):
        return "gif"
    elif image_data.startswith(b'RIFF') and b'WEBP' in image_data[:12]:
        return "webp"
    else:
        return "jpeg"  # Default to JPEG