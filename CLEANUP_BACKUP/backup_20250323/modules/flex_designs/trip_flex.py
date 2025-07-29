# modules/flex_designs/trip_flex.py
def get_trip_details_flex(trip_id, trip_data):
    """生成班次詳情的Flex Message"""
    # 格式化日期
    trip_date = trip_data.get('date')
    weekday_names = ["一", "二", "三", "四", "五", "六", "日"]
    weekday = weekday_names[trip_date.weekday()]
    formatted_date = f"{trip_date.month}/{trip_date.day} (星期{weekday})"
    
    # 格式化時間
    trip_time = trip_data.get('time')
    formatted_time = trip_time.strftime('%H:%M') if trip_time else '未設置'
    
    # 構建Flex Message
    flex_message = {
        "type": "bubble",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": f"班次 #{trip_id} 詳細信息",
                    "weight": "bold",
                    "size": "xl",
                    "color": "#1DB446"
                }
            ],
            "backgroundColor": "#F2F2F2"
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "box",
                    "layout": "horizontal",
                    "contents": [
                        {
                            "type": "text",
                            "text": "日期",
                            "size": "sm",
                            "color": "#555555",
                            "flex": 2
                        },
                        {
                            "type": "text",
                            "text": formatted_date,
                            "size": "sm",
                            "color": "#111111",
                            "flex": 5
                        }
                    ]
                },
                {
                    "type": "box",
                    "layout": "horizontal",
                    "contents": [
                        {
                            "type": "text",
                            "text": "時間",
                            "size": "sm",
                            "color": "#555555",
                            "flex": 2
                        },
                        {
                            "type": "text",
                            "text": formatted_time,
                            "size": "sm",
                            "color": "#111111",
                            "flex": 5
                        }
                    ],
                    "margin": "md"
                },
                {
                    "type": "box",
                    "layout": "horizontal",
                    "contents": [
                        {
                            "type": "text",
                            "text": "起點",
                            "size": "sm",
                            "color": "#555555",
                            "flex": 2
                        },
                        {
                            "type": "text",
                            "text": trip_data.get('start_point') or '未指定',
                            "size": "sm",
                            "color": "#111111",
                            "flex": 5
                        }
                    ],
                    "margin": "md"
                }
            ]
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "button",
                    "action": {
                        "type": "postback",
                        "label": "修改狀態",
                        "data": f"action=change_status&trip_id={trip_id}",
                        "displayText": f"修改狀態 {trip_id}"
                    },
                    "style": "primary",
                    "color": "#1DB446"
                }
            ]
        }
    }
    
    return flex_message
