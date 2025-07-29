# modules/routes/webhook.py
from flask import Blueprint, request, abort, current_app
from linebot.v3.exceptions import InvalidSignatureError
import traceback
import logging

from modules.utils.line_bot import get_parser, reply_text
from modules.services.postback_service import handle_postback
from modules.handlers.message_handler import should_process_message

# 創建藍圖
webhook_bp = Blueprint('webhook', __name__)

# 設定日誌
logger = logging.getLogger(__name__)

@webhook_bp.route("/callback", methods=['POST'])
def callback():
    """LINE Webhook 回調處理"""
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    current_app.logger.info("Request body: " + body)
    
    try:
        parser = get_parser()
        events = parser.parse(body, signature)
        
        for event in events:
            # 處理 Postback 事件（按鈕點擊）
            if event.type == "postback":
                handle_postback(event)
                continue
                
            # 處理文本消息
            if event.type == "message" and event.message.type == "text":
                message_text = event.message.text
                source_type = event.source.type
                
                # 檢查是否應該處理這條消息（群組需要前綴）
                should_process, processed_text = should_process_message(message_text, source_type)
                
                if not should_process:
                    continue  # 不處理這條消息
                
                # 更新消息文本（去除前綴）
                event.message.text = processed_text
                
                # 處理消息
                handle_text_message(event)
                
    except InvalidSignatureError:
        logger.error("無效的簽名")
        abort(400)
    except Exception as e:
        logger.error(f"處理webhook時出錯: {e}")
        traceback.print_exc()
        abort(500)
        
    return 'OK'

def handle_text_message(event):
    """處理文本消息"""
    from modules.handlers.text_message_handler import process_text_message
    process_text_message(event)
