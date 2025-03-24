import os
from flask import Flask, request, abort
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
    FlexMessage,
    FlexContainer
)

app = Flask(__name__)

# 獲取環境變量
channel_access_token = os.environ.get('LINE_CHANNEL_TOKEN')
channel_secret = os.environ.get('LINE_CHANNEL_SECRET')

# 檢查環境變量
if not channel_access_token or not channel_secret:
    raise ValueError("LINE_CHANNEL_TOKEN 或 LINE_CHANNEL_SECRET 環境變量未設置")

# 配置 LINE Bot API
configuration = Configuration(access_token=channel_access_token)

# 嘗試導入 WebhookParser
try:
    from linebot.v3.webhook import WebhookParser
    parser = WebhookParser(channel_secret)
    print("成功導入 WebhookParser")
except ImportError:
    try:
        from linebot.v3.webhooks import WebhookParser
        parser = WebhookParser(channel_secret)
        print("從 webhooks 導入 WebhookParser")
    except ImportError:
        from linebot import WebhookParser
        parser = WebhookParser(channel_secret)
        print("使用舊版本 WebhookParser")

@app.route("/")
def hello():
    return "Hello, World!"

@app.route("/callback", methods=['POST'])
def callback():
    # 獲取 X-Line-Signature 請求頭
    signature = request.headers['X-Line-Signature']

    # 獲取請求體
    body = request.get_data(as_text=True)
    
    try:
        # 解析 webhook 請求體
        events = parser.parse(body, signature)
        
        # 處理事件
        for event in events:
            if isinstance(event, MessageEvent) and isinstance(event.message, TextMessageContent):
                handle_text_message(event)
        
        return 'OK'
    except InvalidSignatureError:
        abort(400)
    except Exception as e:
        print(f"發生錯誤: {str(e)}")
        abort(500)

def handle_text_message(event):
    """處理文本消息"""
    message_text = event.message.text
    reply_token = event.reply_token
    
    # 幫助 - 使用 Flex Message
    if message_text == "幫助":
        # 使用 JSON 字符串創建 Flex Message
        help_bubble_json = """
        {
            "type": "bubble",
            "header": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": "可用命令列表",
                        "weight": "bold",
                        "size": "xl",
                        "color": "#ffffff"
                    }
                ],
                "backgroundColor": "#4682B4"
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": "這是一個測試 Flex Message",
                        "size": "md",
                        "color": "#000000",
                        "wrap": true
                    }
                ],
                "spacing": "sm",
                "paddingAll": "13px"
            }
        }
        """
        
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            
            # 創建 Flex Message
            flex_message = FlexMessage(
                alt_text="幫助信息",
                contents=FlexContainer.from_json(help_bubble_json)
            )
            
            # 創建回覆消息請求
            reply_message_request = ReplyMessageRequest(
                reply_token=reply_token,
                messages=[flex_message]
            )
            
            # 發送回覆
            line_bot_api.reply_message(reply_message_request)
    else:
        # 默認回覆
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            
            reply_message_request = ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text=f"您發送了: {message_text}\n\n請輸入「幫助」查看可用命令。")]
            )
            
            line_bot_api.reply_message(reply_message_request)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=3000, debug=True) 