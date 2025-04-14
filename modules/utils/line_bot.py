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
    MessageAction,
    QuickReply,
    QuickReplyItem
)
from linebot.v3.exceptions import InvalidSignatureError
from flask import current_app
from linebot.v3 import WebhookParser
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from dotenv import load_dotenv

# 設置日誌
logger = logging.getLogger(__name__)

def get_parser():
    """獲取LINE Webhook解析器"""
    # 優先從 Flask 配置中獲取
    channel_secret = current_app.config.get('LINE_CHANNEL_SECRET')
    
    # 如果配置中沒有，則嘗試從環境變量獲取
    if not channel_secret:
        # 直接从本地环境变量文件获取
        load_dotenv('.env.dev', override=True)
        channel_secret = os.environ.get('LINE_CHANNEL_SECRET')
        
    if not channel_secret:
        raise ValueError("LINE_CHANNEL_SECRET not found in config or environment variables")
    
    # 修改後的日誌
    logger.info(f"Channel Secret length: {len(channel_secret)}")
    if current_app.config.get('LINE_CHANNEL_SECRET'):
        cs_config = current_app.config.get('LINE_CHANNEL_SECRET')
        logger.info(f"Channel Secret from config: {cs_config[:6]}...{cs_config[-4:]}")
    else:
        logger.info("Channel Secret from config: 未设置")
    
    if os.environ.get('LINE_CHANNEL_SECRET'):
        cs_env = os.environ.get('LINE_CHANNEL_SECRET')
        logger.info(f"Channel Secret from env: {cs_env[:6]}...{cs_env[-4:]}")
    else:
        logger.info("Channel Secret from env: 未设置")
    
    # 去除可能的空白字符
    channel_secret = channel_secret.strip()
    logger.info("Using Channel Secret from configuration")
    return WebhookParser(channel_secret)

def get_line_bot_api():
    """獲取LINE Messaging API客戶端"""
    # 優先從 Flask 配置中獲取
    token = current_app.config.get('LINE_CHANNEL_TOKEN')
    
    # 如果配置中沒有，則嘗試從環境變量獲取
    if not token:
        # 直接从本地环境变量文件获取
        load_dotenv('.env.dev', override=True)
        token = os.environ.get('LINE_CHANNEL_TOKEN')
    
    if not token:
        logger.error("LINE_CHANNEL_TOKEN not found in config or environment variables")
        raise ValueError("LINE_CHANNEL_TOKEN not found in config or environment variables")
        
    logger.info(f"Using Channel Token: {token[:6]}...{token[-4:]}" if token else "未设置")
    
    configuration = Configuration(access_token=token)
    api_client = ApiClient(configuration)
    return MessagingApi(api_client)

def reply_message(reply_token, messages):
    """回覆訊息的通用方法"""
    if not isinstance(messages, list):
        messages = [messages]
    
    try:
        messaging_api = get_line_bot_api()
        
        # 處理消息列表，將字典轉換為對應的對象
        processed_messages = []
        for msg in messages:
            if isinstance(msg, dict):
                # 如果是字典格式，根據type轉換為對應的消息對象
                if msg.get("type") == "text":
                    processed_messages.append(TextMessage(text=msg.get("text", "")))
                elif msg.get("type") == "flex":
                    # 處理Flex Message
                    flex_container = FlexContainer.from_dict(msg.get("contents", {}))
                    flex_msg = FlexMessage(
                        alt_text=msg.get("altText", "Flex Message"),
                        contents=flex_container
                    )
                    
                    # 如果有QuickReply，以正確方式添加
                    if "quickReply" in msg and "items" in msg["quickReply"]:
                        # 創建QuickReply項目
                        quick_reply_items = []
                        
                        logger.info(f"處理QuickReply項目: {msg['quickReply']['items']}")
                        
                        for item in msg["quickReply"]["items"]:
                            if "action" in item and item["action"].get("type") == "message":
                                action_data = item["action"]
                                action = MessageAction(
                                    label=action_data.get("label", ""),
                                    text=action_data.get("text", "")
                                )
                                quick_reply_items.append(
                                    QuickReplyItem(action=action)
                                )
                                logger.info(f"添加QuickReply項目: {action_data.get('label')}, 文本: {action_data.get('text')}")
                        
                        # 創建QuickReply並賦值
                        if quick_reply_items:
                            # 直接手動構建QuickReply屬性
                            qr = QuickReply(items=quick_reply_items)
                            logger.info(f"創建QuickReply對象: {qr}")
                            # 賦值給flex_msg
                            flex_msg.quick_reply = qr
                            logger.info(f"成功設置QuickReply屬性")
                    
                    processed_messages.append(flex_msg)
                    logger.info(f"添加Flex消息到處理列表: {flex_msg}")
                else:
                    # 未知類型，跳過
                    logger.warning(f"未知的消息類型: {msg.get('type')}")
                    continue
            else:
                # 如果已經是消息對象，直接添加
                processed_messages.append(msg)
        
        # 發送處理後的消息
        logger.info(f"準備發送 {len(processed_messages)} 條處理後的消息")
        messaging_api.reply_message(ReplyMessageRequest(
            reply_token=reply_token,
            messages=processed_messages
        ))
        logger.info("消息發送成功")
        
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