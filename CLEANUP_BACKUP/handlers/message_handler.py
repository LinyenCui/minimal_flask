from flask import request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, ReplyMessageRequest, TextMessage
from config import LINE_CHANNEL_TOKEN, LINE_CHANNEL_SECRET
from models import db
from sqlalchemy import text as sql_text
from datetime import date
from handlers.booking_handler import handle_booking_conversation
from models.customer import Customer
from models.driver import Driver
from models.fixed_schedule import FixedSchedule
from models.trip import Trip
from models.completed_trip import CompletedTrip
from modules.services.ai_service import extract_booking_info_with_gemini
import logging

# 配置 LINE Bot API
configuration = Configuration(access_token=LINE_CHANNEL_TOKEN)
api_client = ApiClient(configuration)
messaging_api = MessagingApi(api_client)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# 用戶狀態字典，用於跟踪對話狀態
user_states = {}

def setup_line_bot(app):
    """設置 LINE Bot 的路由和處理器"""
    
    # 設置日誌
    logger = logging.getLogger('line_bot')
    logger.setLevel(logging.DEBUG)
    
    @app.route("/callback", methods=['POST'])
    def callback():
        # 獲取 X-Line-Signature 請求頭
        signature = request.headers['X-Line-Signature']
        
        # 獲取請求體
        body = request.get_data(as_text=True)
        logger.info("Request body: " + body)
        
        # 處理 webhook 請求
        try:
            handler.handle(body, signature)
        except InvalidSignatureError:
            abort(400)
        except Exception as e:
            logger.error(f"發生錯誤: {e}")
            abort(500)

        return 'OK'
    
    @handler.add(MessageEvent, message=TextMessageContent)
    def handle_text_message(event):
        """處理文本消息"""
        message_text = event.message.text
        reply_token = event.reply_token
        user_id = event.source.user_id
        
        # 添加調試日誌
        logger.info(f"收到消息: {message_text} 來自用戶: {user_id}")
        
        # 檢查用戶是否在預約流程中
        if user_id in user_states and user_states[user_id]['state'] == 'booking':
            logger.info(f"用戶 {user_id} 在預約流程中，步驟: {user_states[user_id]['step']}")
            handle_booking_conversation(event, user_id, message_text, user_states, messaging_api)
            return
        
        # 根據不同的命令執行不同的操作
        reply_text = ""
        
        # 測試數據庫連接
        if message_text == "測試數據庫":
            logger.info("執行測試數據庫命令")
            try:
                # 執行簡單查詢
                result = db.session.execute(sql_text("SELECT 1")).fetchone()
                if result:
                    reply_text = "✅ 數據庫連接成功！"
                else:
                    reply_text = "❌ 數據庫連接失敗：無法執行查詢"
            except Exception as e:
                reply_text = f"❌ 數據庫連接錯誤: {str(e)}"
        
        # 查看數據庫表結構
        elif message_text == "數據庫表":
            logger.info("執行數據庫表命令")
            try:
                # 獲取所有表名
                tables = db.session.execute(sql_text("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")).fetchall()
                
                if not tables:
                    reply_text = "數據庫中沒有表。"
                else:
                    reply_text = "數據庫表列表：\n\n"
                    for table in tables:
                        table_name = table[0]
                        reply_text += f"- {table_name}\n"
            except Exception as e:
                reply_text = f"獲取數據庫表結構錯誤: {str(e)}"
        
        # 查詢今天的班次
        elif message_text == "查詢班次":
            logger.info("執行查詢班次命令")
            try:
                # 獲取今天的日期
                today = date.today()
                
                # 根據您的資料表結構修改查詢
                query = f"""
                SELECT 
                    t.trip_id, 
                    t.date, 
                    t.time, 
                    t.start_point, 
                    t.via_point,
                    t.end_point, 
                    t.status,
                    d.name as driver_name
                FROM 
                    trips t
                LEFT JOIN 
                    drivers d ON t.driver_id = d.id
                WHERE 
                    t.date = '{today}'
                ORDER BY 
                    t.time
                """
                
                trips = db.session.execute(sql_text(query)).fetchall()
                
                if not trips:
                    reply_text = f"今天 ({today}) 沒有安排班次。"
                else:
                    # 格式化班次信息
                    reply_text = f"今天 ({today}) 班次信息：\n\n"
                    for trip in trips:
                        trip_id = trip[0]
                        trip_date = trip[1]
                        departure_time = trip[2].strftime("%H:%M") if trip[2] else "未設置"
                        start_point = trip[3] or "未指定"
                        via_point = trip[4] or ""
                        end_point = trip[5] or "未指定"
                        status = trip[6] or "未指定"
                        driver_name = trip[7] or "未指派"
                        
                        reply_text += f"班次ID: {trip_id}\n"
                        reply_text += f"日期: {trip_date}\n"
                        reply_text += f"時間: {departure_time}\n"
                        reply_text += f"起點: {start_point}\n"
                        if via_point:
                            reply_text += f"途經: {via_point}\n"
                        reply_text += f"終點: {end_point}\n"
                        reply_text += f"狀態: {status}\n"
                        reply_text += f"司機: {driver_name}\n"
                        reply_text += "-------------------\n"
            except Exception as e:
                reply_text = f"查詢班次錯誤: {str(e)}"
        
        # 查詢待派班次
        elif message_text == "待派班次":
            logger.info("執行待派班次命令")
            try:
                # 查詢所有待派班次
                query = """
                SELECT 
                    t.trip_id, 
                    t.date,
                    t.time, 
                    t.start_point, 
                    t.via_point,
                    t.end_point
                FROM 
                    trips t
                WHERE 
                    t.status = '待派'
                ORDER BY 
                    t.date, t.time
                """
                
                pending_trips = db.session.execute(sql_text(query)).fetchall()
                
                if not pending_trips:
                    reply_text = "目前沒有待派的班次。"
                else:
                    # 查詢所有司機
                    drivers_query = "SELECT id, name FROM drivers ORDER BY id"
                    drivers = db.session.execute(sql_text(drivers_query)).fetchall()
                    
                    # 格式化待派班次信息
                    reply_text = "📋 待派班次列表：\n\n"
                    for trip in pending_trips:
                        trip_id = trip[0]
                        trip_date = trip[1]
                        departure_time = trip[2].strftime("%H:%M") if trip[2] else "未設置"
                        start_point = trip[3] or "未指定"
                        via_point = trip[4] or ""
                        end_point = trip[5] or "未指定"
                        
                        reply_text += f"班次ID: {trip_id}\n"
                        reply_text += f"日期: {trip_date}\n"
                        reply_text += f"時間: {departure_time}\n"
                        reply_text += f"起點: {start_point}\n"
                        if via_point:
                            reply_text += f"途經: {via_point}\n"
                        reply_text += f"終點: {end_point}\n"
                        reply_text += "-------------------\n"
                    
                    # 添加可用司機列表
                    reply_text += "\n🚗 可用司機列表：\n\n"
                    for driver in drivers:
                        driver_id = driver[0]
                        driver_name = driver[1]
                        reply_text += f"司機ID: {driver_id}, 姓名: {driver_name}\n"
                    
                    reply_text += "\n使用 '指派 [班次ID] [司機ID]' 來指派司機。"
            except Exception as e:
                reply_text = f"查詢待派班次錯誤: {str(e)}"
        
        # 指派司機
        elif message_text.startswith("指派"):
            logger.info("執行指派司機命令")
            try:
                # 解析指派參數
                parts = message_text.split()
                if len(parts) < 3:
                    reply_text = "指派命令格式不正確。正確格式：指派 [班次ID] [司機ID]"
                else:
                    trip_id = int(parts[1])
                    driver_id = int(parts[2])
                    
                    # 檢查班次是否存在且狀態為"待派"
                    trip_query = "SELECT trip_id, status FROM trips WHERE trip_id = :trip_id"
                    trip = db.session.execute(sql_text(trip_query), {"trip_id": trip_id}).fetchone()
                    
                    if not trip:
                        raise ValueError(f"找不到ID為 {trip_id} 的班次")
                    
                    if trip[1] != '待派':
                        raise ValueError(f"班次 {trip_id} 的狀態不是'待派'，無法指派司機")
                    
                    # 檢查司機是否存在
                    driver_query = "SELECT id, name FROM drivers WHERE id = :driver_id"
                    driver = db.session.execute(sql_text(driver_query), {"driver_id": driver_id}).fetchone()
                    
                    if not driver:
                        raise ValueError(f"找不到ID為 {driver_id} 的司機")
                    
                    # 更新班次，指派司機
                    update_query = """
                    UPDATE trips 
                    SET driver_id = :driver_id, status = '準備' 
                    WHERE trip_id = :trip_id
                    """
                    
                    db.session.execute(
                        sql_text(update_query), 
                        {
                            "driver_id": driver_id,
                            "trip_id": trip_id
                        }
                    )
                    db.session.commit()
                    
                    # 發送確認消息
                    confirm_text = f"✅ 已成功將班次 {trip_id} 指派給司機 {driver[1]}（ID: {driver_id}）。班次狀態已更新為'準備'。"
                    reply_text = confirm_text
            except ValueError as e:
                reply_text = f"指派失敗: {str(e)}"
            except Exception as e:
                reply_text = f"指派失敗: {str(e)}"
        
        # 開始預約流程
        elif message_text == "預約":
            logger.info("執行預約命令")
            # 初始化預約狀態
            user_states[user_id] = {
                'state': 'booking',
                'step': 'date',
                'data': {
                    'category': '東洋'  # 預設類別為"東洋"
                }
            }
            
            reply_text = "請輸入預約日期（格式：YYYY-MM-DD）："
        
        else:
            # 嘗試使用 AI 理解用戶意圖
            logger.info(f"未知指令 '{message_text}'，嘗試交由 AI 處理")
            try:
                extracted_info = extract_booking_info_with_gemini(message_text)
                if extracted_info:
                    # 如果 AI 成功提取信息，格式化並回覆
                    logger.info(f"AI 提取到預約資訊: {extracted_info}")
                    reply_text = "好的，我幫您看看。請問您是要預約：\n\n"
                    details = []
                    if extracted_info.get('customer_name'):
                        details.append(f"乘客: {extracted_info['customer_name']}")
                    if extracted_info.get('date'):
                        details.append(f"日期: {extracted_info['date']}")
                    if extracted_info.get('time'):
                        details.append(f"時間: {extracted_info['time']}")
                    if extracted_info.get('start_point'):
                        details.append(f"起點: {extracted_info['start_point']}")
                    if extracted_info.get('end_point'):
                        details.append(f"終點: {extracted_info['end_point']}")
                    
                    if details:
                        reply_text += "\n".join(details)
                        reply_text += "\n\n如果資訊正確，請直接開始預約流程。"
                    else:
                        # 雖然有回傳但內容為空
                        reply_text = "抱歉，我好像沒能完全理解您的意思。您可以試著說「預約」來開始，或參考以下指令。"
                        reply_text += (
                            "\n\n可用命令：\n"
                            "- 測試數據庫\n"
                            "- 數據庫表\n"
                            "- 查詢班次\n"
                            "- 待派班次\n"
                            "- 指派 [班次ID] [司機ID]\n"
                            "- 預約"
                        )

                else:
                    # 如果 AI 無法提取信息，回覆通用幫助訊息
                    logger.info("AI 未能提取有效資訊，回覆通用幫助訊息")
                    reply_text = (
                        f"您好，我不確定如何處理「{message_text}」。\n\n"
                        "您可以試試以下指令：\n"
                        "- 測試數據庫\n"
                        "- 數據庫表\n"
                        "- 查詢班次\n"
                        "- 待派班次\n"
                        "- 指派 [班次ID] [司機ID]\n"
                        "- 預約"
                    )
            except Exception as e:
                logger.error(f"調用 AI 服務時發生錯誤: {e}")
                reply_text = "抱歉，AI 服務暫時無法使用，請稍後再試。"
        
        logger.info(f"準備回覆: {reply_text[:50]}...")
        
        # 創建回覆消息請求
        reply_message_request = ReplyMessageRequest(
            reply_token=reply_token,
            messages=[TextMessage(text=reply_text)]
        )
        
        # 發送回覆
        messaging_api.reply_message(reply_message_request) 