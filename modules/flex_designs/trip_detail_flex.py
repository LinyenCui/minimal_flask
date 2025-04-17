def get_trip_details_flex(trip_id, trip_data):
    """
    生成班次詳情的 Flex Message
    
    參數:
        trip_id: 班次ID
        trip_data: 班次數據字典，包含以下鍵:
            - date: 日期
            - time: 時間
            - start_point: 起點
            - via_point: 途經點
            - end_point: 終點
            - status: 狀態
            - driver_id: 司機ID
            - plate_number: 車牌號碼
            - category: 類別
            - base_fare: 基本車資
    
    返回:
        包含 Flex Message 和 Quick Reply 的字典
    """
    # 格式化日期
    trip_date = trip_data.get('date')
    weekday_names = ["一", "二", "三", "四", "五", "六", "日"]
    weekday = weekday_names[trip_date.weekday()]
    formatted_date = f"{trip_date.month}/{trip_date.day} (星期{weekday})"
    
    # 格式化時間
    trip_time = trip_data.get('time')
    formatted_time = trip_time.strftime('%H:%M') if trip_time else '未設置'
    
    # 狀態顏色
    status_color = {
        "準備": "#6CD8A0",  # 綠色
        "完成": "#1DB446",  # 深綠色
        "取消": "#888888",  # 灰色
        "衝突": "#FF9153",  # 橙色
        "請假": "#A0A0FF",  # 藍色
        "待派": "#FF6B6E"   # 紅色
    }.get(trip_data.get('status', ''), "#111111")
    
    # 構建 Flex Message (調整樣式)
    flex_message = {
        "type": "bubble",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": f"班次 {trip_id} 詳情", # 稍微簡化標題
                    "weight": "bold",
                    "size": "lg", # 減小字號
                    "color": "#FFFFFF", # 白色文字
                    "align": "center"
                }
            ],
            "backgroundColor": "#27AE60", # 換個主色調 (例如綠色)
            "paddingTop": "md", # 增加一點內邊距
            "paddingBottom": "md"
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm", # 減小 Body 內元素間距
            "contents": [
                {
                    "type": "box",
                    "layout": "baseline", # 嘗試 baseline 對齊
                    "spacing": "sm", # 增加標籤和值之間的間距
                    "contents": [
                        {
                            "type": "text",
                            "text": "日期",
                            "size": "xs", # 減小字號
                            "color": "#AAAAAA", # 灰色標籤
                            "flex": 2,
                            "wrap": False # 避免標籤換行
                        },
                        {
                            "type": "text",
                            "text": formatted_date,
                            "size": "sm", # 值字號稍大
                            "color": "#111111",
                            "flex": 5,
                            "wrap": True # 值可以換行
                        }
                    ]
                },
                # --- 對所有字段應用類似的 baseline 和字號調整 ---
                {
                    "type": "box",
                    "layout": "baseline", 
                    "spacing": "sm",
                    "contents": [
                        {
                            "type": "text",
                            "text": "時間",
                            "size": "xs", 
                            "color": "#AAAAAA",
                            "flex": 2,
                            "wrap": False
                        },
                        {
                            "type": "text",
                            "text": formatted_time,
                            "size": "sm",
                            "color": "#111111",
                            "flex": 5,
                            "wrap": True 
                        }
                    ],
                   # "margin": "sm" # 移除舊的 margin，使用 spacing
                },
                {
                    "type": "box",
                    "layout": "baseline",
                    "spacing": "sm",
                    "contents": [
                        {
                            "type": "text",
                            "text": "起點",
                            "size": "xs", 
                            "color": "#AAAAAA",
                            "flex": 2,
                            "wrap": False
                        },
                        {
                            "type": "text",
                            "text": trip_data.get('display_start_point') or trip_data.get('start_point') or '未指定',
                            "size": "sm",
                            "color": "#111111",
                            "flex": 5,
                            "wrap": True 
                        }
                    ],
                   # "margin": "sm"
                }
            ]
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm", # 給 footer 內部元素加間距
            "contents": [
                {
                    "type": "button",
                    "action": {
                        "type": "postback",
                        "label": "修改狀態",
                        "data": f"action=update_status&trip_id={trip_id}",
                        "displayText": f"修改狀態 {trip_id}"
                    },
                    "style": "primary",
                    "color": "#2ECC71", # 匹配 Header 顏色
                    "height": "sm" # 讓按鈕矮一點
                }
            ]
        }
    }
    
    # --- 添加其他字段到 Body (使用新的 baseline 布局) ---
    # 途經點
    if trip_data.get('display_via_point') or trip_data.get('via_point'):
        flex_message["body"]["contents"].append({
            "type": "box",
            "layout": "baseline",
            "spacing": "sm",
            "contents": [
                {
                    "type": "text", "text": "途經", "size": "xs", "color": "#AAAAAA", "flex": 2, "wrap": False
                },
                {
                    "type": "text", "text": trip_data.get('display_via_point') or trip_data.get('via_point'), "size": "sm", "color": "#111111", "flex": 5, "wrap": True
                }
            ],
           # "margin": "sm"
        })
    
    # 終點
    flex_message["body"]["contents"].append({
        "type": "box",
        "layout": "baseline",
        "spacing": "sm",
        "contents": [
             {
                 "type": "text", "text": "終點", "size": "xs", "color": "#AAAAAA", "flex": 2, "wrap": False
             },
             {
                 "type": "text", "text": trip_data.get('display_end_point') or trip_data.get('end_point') or '未指定', "size": "sm", "color": "#111111", "flex": 5, "wrap": True
             }
         ],
        # "margin": "sm"
     })
     
    # 狀態
    flex_message["body"]["contents"].append({
         "type": "box",
         "layout": "baseline",
         "spacing": "sm",
         "contents": [
             {
                 "type": "text", "text": "狀態", "size": "xs", "color": "#AAAAAA", "flex": 2, "wrap": False
             },
             {
                 "type": "text", "text": trip_data.get('status') or '未指定', "size": "sm", "color": status_color, "weight": "bold", "flex": 5, "wrap": True
             }
         ],
        # "margin": "sm"
     })
     
    # 司機信息
    if trip_data.get('driver_id'):
         flex_message["body"]["contents"].append({ # 司機
             "type": "box",
             "layout": "baseline",
             "spacing": "sm",
             "contents": [
                 {
                     "type": "text", "text": "司機", "size": "xs", "color": "#AAAAAA", "flex": 2, "wrap": False
                 },
                 {
                     "type": "text", "text": f"🚕{trip_data.get('driver_id')}", "size": "sm", "color": "#111111", "flex": 5, "wrap": True
                 }
             ],
            # "margin": "sm"
         })
         if trip_data.get('plate_number'): # 車牌
             flex_message["body"]["contents"].append({
                 "type": "box",
                 "layout": "baseline",
                 "spacing": "sm",
                 "contents": [
                     {
                         "type": "text", "text": "車牌", "size": "xs", "color": "#AAAAAA", "flex": 2, "wrap": False
                     },
                     {
                         "type": "text", "text": trip_data.get('plate_number'), "size": "sm", "color": "#111111", "flex": 5, "wrap": True
                     }
                 ],
                # "margin": "sm"
             })
    else: # 未指派司機
         flex_message["body"]["contents"].append({
             "type": "box",
             "layout": "baseline",
             "spacing": "sm",
             "contents": [
                 {
                     "type": "text", "text": "司機", "size": "xs", "color": "#AAAAAA", "flex": 2, "wrap": False
                 },
                 {
                     "type": "text", "text": "未指派", "size": "sm", "color": "#888888", "flex": 5, "wrap": True
                 }
             ],
            # "margin": "sm"
         })
         
    # 類別
    if trip_data.get('category'):
         flex_message["body"]["contents"].append({
             "type": "box",
             "layout": "baseline",
             "spacing": "sm",
             "contents": [
                 {
                     "type": "text", "text": "類別", "size": "xs", "color": "#AAAAAA", "flex": 2, "wrap": False
                 },
                 {
                     "type": "text", "text": trip_data.get('category'), "size": "sm", "color": "#111111", "flex": 5, "wrap": True
                 }
             ],
            # "margin": "sm"
         })
         
    # 車資
    if trip_data.get('base_fare'):
         flex_message["body"]["contents"].append({
             "type": "box",
             "layout": "baseline",
             "spacing": "sm",
             "contents": [
                 {
                     "type": "text", "text": "基本車資", "size": "xs", "color": "#AAAAAA", "flex": 2, "wrap": False
                 },
                 {
                     "type": "text", "text": f"{trip_data.get('base_fare')} 元", "size": "sm", "color": "#111111", "flex": 5, "wrap": True
                 }
             ],
            # "margin": "sm"
         })
         
    # 創建修改狀態的 Quick Reply
    quick_reply = {
        "items": []
    }
    
    # 根據當前狀態提供適當的操作選項
    current_status = trip_data.get('status', '')
    
    if current_status != "取消":
        quick_reply["items"].append({
            "type": "action",
            "action": {
                "type": "postback",
                "label": "取消",
                "data": f"action=update_status&trip_id={trip_id}&status=取消",
                "displayText": f"修改狀態 {trip_id} 取消"
            }
        })
    
    if current_status != "衝突":
        quick_reply["items"].append({
            "type": "action",
            "action": {
                "type": "postback",
                "label": "衝突",
                "data": f"action=update_status&trip_id={trip_id}&status=衝突",
                "displayText": f"修改狀態 {trip_id} 衝突"
            }
        })
    
    if current_status != "請假":
        quick_reply["items"].append({
            "type": "action",
            "action": {
                "type": "postback",
                "label": "請假",
                "data": f"action=update_status&trip_id={trip_id}&status=請假",
                "displayText": f"修改狀態 {trip_id} 請假"
            }
        })
    
    if current_status != "準備":
        quick_reply["items"].append({
            "type": "action",
            "action": {
                "type": "postback",
                "label": "改回準備",
                "data": f"action=update_status&trip_id={trip_id}&status=準備",
                "displayText": f"修改狀態 {trip_id} 準備"
            }
        })
    
    # 如果底部按鈕是 postback 而不是 message
    flex_message["footer"]["contents"][0]["action"] = {
        "type": "postback",
        "label": "修改狀態",
        "data": f"action=update_status&trip_id={trip_id}",
        "displayText": f"修改狀態 {trip_id}"
    }
    
    # 返回包含 Flex Message 和 Quick Reply 的字典
    return {
        "flex_message": flex_message,
        "quick_reply": quick_reply
    }
