"""
LINE Bot 配置和工具模組
"""
import os
import logging
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
    FlexMessage,
    FlexContainer,
    PostbackAction,
    MessageAction
)
from linebot.v3.exceptions import InvalidSignatureError
from modules.config import LINE_CHANNEL_TOKEN, LINE_CHANNEL_SECRET
from flask import current_app
from linebot.v3 import WebhookParser
from linebot.v3.webhooks import MessageEvent, TextMessageContent

# 設置日誌
logger = logging.getLogger(__name__)

# 配置 LINE Bot API
configuration = Configuration(access_token=LINE_CHANNEL_TOKEN)
api_client = ApiClient(configuration)
messaging_api = MessagingApi(api_client)

# 嘗試導入 WebhookParser
try:
    parser = WebhookParser(LINE_CHANNEL_SECRET)
    logger.info("成功導入 WebhookParser")
except ImportError:
    try:
        parser = WebhookParser(LINE_CHANNEL_SECRET)
        logger.info("從 webhooks 導入 WebhookParser")
    except ImportError:
        parser = WebhookParser(LINE_CHANNEL_SECRET)
        logger.info("使用舊版本 WebhookParser")

def reply_message(reply_token, messages):
    """回覆訊息的通用方法"""
    if not isinstance(messages, list):
        messages = [messages]
    
    try:
        messaging_api = get_line_bot_api()
        messaging_api.reply_message(ReplyMessageRequest(
            reply_token=reply_token,
            messages=messages
        ))
        return True
    except Exception as e:
        import traceback
        traceback.print_exc()
        current_app.logger.error(f"回覆訊息時出錯: {e}")
        return False

def create_text_message(text):
    """創建文字訊息"""
    return TextMessage(text=text)

def create_flex_message(alt_text, contents):
    """創建Flex訊息"""
    try:
        if isinstance(contents, dict):
            container = FlexContainer.from_dict(contents)
        else:
            container = contents
        
        return FlexMessage(
            alt_text=alt_text,
            contents=container
        )
    except Exception as e:
        logger.error(f"創建Flex訊息時出錯: {e}")
        # 返回一個文字訊息作為備用
        return TextMessage(text=alt_text)

def create_postback_action(label, data, display_text=None):
    """創建Postback操作"""
    return PostbackAction(
        label=label,
        data=data,
        display_text=display_text
    )

def create_message_action(label, text):
    """創建Message操作"""
    return MessageAction(
        label=label,
        text=text
    )

# 初始化Line Bot相關物件
def get_parser():
    """獲取LINE Webhook解析器"""
    channel_secret = current_app.config.get('LINE_CHANNEL_SECRET')
    return WebhookParser(channel_secret)

def get_line_bot_api():
    """獲取LINE Messaging API客戶端"""
    channel_token = current_app.config.get('LINE_CHANNEL_TOKEN')
    
    # 正確的初始化方式
    configuration = Configuration(access_token=channel_token)
    api_client = ApiClient(configuration)
    return MessagingApi(api_client)

# 發送回覆訊息
def reply_text(reply_token, text):
    """發送文字回覆"""
    try:
        messaging_api = get_line_bot_api()
        messaging_api.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text=text)]
            )
        )
        return True
    except Exception as e:
        import traceback
        traceback.print_exc()
        current_app.logger.error(f"發送回覆訊息時出錯: {e}")
        return False

# 發送Flex Message
def reply_flex(reply_token, alt_text, flex_content):
    """發送Flex Message回覆"""
    try:
        messaging_api = get_line_bot_api()
        flex_message = FlexMessage(
            alt_text=alt_text,
            contents=FlexContainer.from_dict(flex_content)
        )
        messaging_api.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[flex_message]
            )
        )
        return True
    except Exception as e:
        import traceback
        traceback.print_exc()
        current_app.logger.error(f"發送Flex Message時出錯: {e}")
        return False 