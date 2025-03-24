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
                        "text": "!查詢班次"
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

def format_trip_details_flex(trip):
    """生成班次詳情的Flex Message"""
    # 格式化日期
    date_obj = datetime.strptime(trip['date'], '%Y-%m-%d') if isinstance(trip['date'], str) else trip['date']
    weekday_map = {0: '一', 1: '二', 2: '三', 3: '四', 4: '五', 5: '六', 6: '日'}
    weekday = weekday_map[date_obj.weekday()]
    formatted_date = f"{date_obj.month}/{date_obj.day} (星期{weekday})"
    
    # 格式化時間
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
    
    # 構建內容項
    detail_items = [
        {"label": "日期", "value": formatted_date},
        {"label": "時間", "value": time_str},
        {"label": "起點", "value": trip['start_name']},
    ]
    
    if trip['via_name']:
        detail_items.append({"label": "途經", "value": trip['via_name']})
    
    detail_items.extend([
        {"label": "終點", "value": trip['end_name']},
        {"label": "狀態", "value": status, "color": status_color},
    ])
    
    if trip['driver_id']:
        detail_items.append({"label": "司機", "value": f"🚕{trip['driver_id']}"})
        if trip['plate_number']:
            detail_items.append({"label": "車牌", "value": trip['plate_number']})
    
    if trip['meter_fare']:
        detail_items.append({"label": "基本車資", "value": f"{trip['meter_fare']} 元"})
    if trip['extra_fare']:
        detail_items.append({"label": "額外費用", "value": f"{trip['extra_fare']} 元"})
    if trip['actual_fare']:
        detail_items.append({"label": "總車資", "value": f"{trip['actual_fare']} 元"})
    
    # 創建詳情內容
    contents_body = []
    for item in detail_items:
        contents_body.append({
            "type": "box",
            "layout": "horizontal",
            "contents": [
                {
                    "type": "text",
                    "text": item["label"],
                    "size": "sm",
                    "color": "#555555",
                    "flex": 2
                },
                {
                    "type": "text",
                    "text": item["value"],
                    "size": "sm",
                    "color": item.get("color", "#111111"),
                    "flex": 4,
                    "wrap": True
                }
            ],
            "spacing": "md"
        })
    
    # 添加狀態修改提示
    contents_body.append({
        "type": "separator",
        "margin": "xxl"
    })
    contents_body.append({
        "type": "text",
        "text": "修改狀態",
        "weight": "bold",
        "margin": "md"
    })
    
    # 添加狀態按鈕
    status_buttons = []
    for status_name, color in [
        ("取消", "#AA0000"), 
        ("衝突", "#FF6600"), 
        ("請假", "#0000AA")
    ]:
        status_buttons.append({
            "type": "button",
            "action": {
                "type": "message",
                "label": status_name,
                "text": f"!修改狀態 {trip['trip_id']} {status_name}"
            },
            "color": color,
            "style": "primary",
            "height": "sm",
            "margin": "sm"
        })
    
    contents_body.append({
        "type": "box",
        "layout": "horizontal",
        "contents": status_buttons,
        "margin": "md",
        "spacing": "sm"
    })
    
    # 構建完整Flex消息
    contents = {
        "type": "bubble",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": f"班次 #{trip['trip_id']} 詳情",
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
            "contents": contents_body,
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
                        "label": "返回班次列表",
                        "text": f"!查詢班次 {date_obj.strftime('%Y-%m-%d')}"
                    },
                    "style": "primary",
                    "color": "#27ACB2"
                }
            ]
        }
    }
    
    return FlexMessage(
        alt_text=f"班次 #{trip['trip_id']} 詳情",
        contents=contents
    ) 