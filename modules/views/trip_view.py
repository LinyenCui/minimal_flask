# 班次視圖層 - 負責顯示邏輯

from linebot.v3.messaging import (
    FlexMessage, TextMessage, 
    MessageAction, PostbackAction
)
# 由於v3版本沒有直接的QuickReply和QuickReplyButton，需要自行構建相關結構
# 舊版本導入
# from linebot.models import (
#     FlexSendMessage, TextSendMessage, QuickReply, QuickReplyButton, 
#     MessageAction, PostbackAction, BubbleContainer, BoxComponent,
#     TextComponent, ButtonComponent, SeparatorComponent
# )
from datetime import datetime

def format_trips_flex(trips, date):
    """生成班次列表的Flex Message"""
    # 格式化日期顯示
    date_obj = datetime.strptime(date, '%Y-%m-%d')
    weekday_map = {0: '一', 1: '二', 2: '三', 3: '四', 4: '五', 5: '六', 6: '日'}
    weekday = weekday_map[date_obj.weekday()]
    formatted_date = f"{date_obj.month}/{date_obj.day} (星期{weekday})"
    
    # 準備班次內容
    trip_contents = []
    for trip in trips:
        # 獲取時間
        time_str = trip['time'].strftime('%H:%M') if hasattr(trip['time'], 'strftime') else trip['time']
        
        # 決定狀態顏色
        status = trip['status'] if trip['status'] else '準備'
        status_color = {
            '準備': '#00AA00',  # 綠色
            '完成': '#888888',  # 灰色
            '取消': '#AA0000',  # 紅色
            '衝突': '#FF6600',  # 橙色
            '請假': '#0000AA',  # 藍色
            '待派': '#AA00AA'   # 紫色
        }.get(status, '#888888')
        
        # 構建路線文本
        route_text = trip['start_name']
        if trip['via_name']:
            route_text += f" → {trip['via_name']}"
        route_text += f" → {trip['end_name']}"
        
        # 構建司機信息
        driver_text = f"🚕{trip['driver_id']}" if trip['driver_id'] else "未指派"
        
        # 創建班次行
        trip_content = {
            "type": "box",
            "layout": "horizontal",
            "contents": [
                {
                    "type": "text",
                    "text": time_str,
                    "size": "sm",
                    "flex": 2,
                    "weight": "bold"
                },
                {
                    "type": "text",
                    "text": route_text,
                    "size": "sm",
                    "flex": 5,
                    "wrap": True
                },
                {
                    "type": "text",
                    "text": status,
                    "size": "xs",
                    "color": status_color,
                    "flex": 2,
                    "align": "end"
                },
                {
                    "type": "text",
                    "text": driver_text,
                    "size": "xs",
                    "flex": 2,
                    "align": "end"
                }
            ],
            "action": {
                "type": "message",
                "text": f"!班次 #{trip['trip_id']}"
            },
            "margin": "md",
            "spacing": "sm"
        }
        
        trip_contents.append(trip_content)
        # 添加分隔線
        if trip != trips[-1]:
            trip_contents.append({"type": "separator", "margin": "sm"})
    
    # 沒有班次的處理
    if not trip_contents:
        trip_contents = [{
            "type": "text",
            "text": f"沒有找到 {formatted_date} 的班次",
            "wrap": True,
            "size": "md",
            "align": "center"
        }]
    
    # 構建完整Flex消息
    contents = {
        "type": "bubble",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": f"{formatted_date} 班次列表",
                    "weight": "bold",
                    "size": "xl",
                    "color": "#ffffff"
                }
            ],
            "backgroundColor": "#27ACB2",
            "paddingBottom": "6px"
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": trip_contents,
            "spacing": "md"
        },
        "footer": {
            "type": "box",
            "layout": "horizontal",
            "contents": [
                {
                    "type": "button",
                    "action": {
                        "type": "message",
                        "label": "查詢其他日期",
                        "text": "!東洋班次"
                    },
                    "style": "primary",
                    "color": "#27ACB2"
                }
            ]
        }
    }
    
    return FlexMessage(
        alt_text=f"{formatted_date} 班次列表",
        contents=contents
    )

# 🗑️ 已移除 format_trip_details_flex 函數 - 舊版班次詳情系統
# 新系統位於 modules/flex_designs/trip_details_flex.py，使用 Quick Reply 按鈕
# 避免與現有系統衝突 