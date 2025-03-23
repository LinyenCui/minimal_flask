# modules/flex_designs/trip_query_flex.py

def generate_trips_flex(trips_data, date_str=None, is_fixed_trips=False):
    """
    生成班次查詢結果的 Flex Message
    
    參數:
        trips_data: 班次數據列表，每個元素包含班次信息
        date_str: 日期字符串，用於顯示在標題中
        is_fixed_trips: 是否為固定班次查詢
    
    返回:
        Flex Message 字典
    """
    # 創建基本結構
    bubble = {
        "type": "bubble",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": f"班次查詢結果" if not is_fixed_trips else f"固定班次查詢結果",
                    "weight": "bold",
                    "size": "md",
                    "color": "#ffffff"
                }
            ],
            "backgroundColor": "#4682B4",
            "paddingTop": "8px",
            "paddingBottom": "8px",
            "paddingStart": "12px",
            "paddingEnd": "12px"
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [],
            "spacing": "md"
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "輸入「班次詳情 [ID]」查看詳細信息",
                    "size": "xs",
                    "color": "#888888",
                    "wrap": True,
                    "align": "center"
                }
            ]
        }
    }
    
    # 按日期分組處理數據
    current_date = None
    
    for trip in trips_data:
        trip_id = trip[0]
        trip_date = trip[1]
        time_val = trip[2].strftime("%H:%M") if trip[2] else "--:--"
        direction = trip[5]  # "來" 或 "回"
        
        # 根據方向決定顯示起點還是終點
        if direction == "來":
            location = trip[3] or "未指定"  # 起點
        else:  # "回"
            location = trip[4] or "未指定"  # 終點
        
        status = trip[6] or "未指定"
        driver_id = trip[7] or "未指派"
        
        # 如果日期變了，添加日期標題
        if current_date != trip_date:
            current_date = trip_date
            weekday_names = ["一", "二", "三", "四", "五", "六", "日"]
            weekday = weekday_names[current_date.weekday()]
            date_title = f"{current_date.month}/{current_date.day} (星期{weekday})"
            
            # 添加日期分隔線 (如果不是第一個日期)
            if bubble["body"]["contents"]:
                bubble["body"]["contents"].append({
                    "type": "separator",
                    "margin": "md"
                })
            
            # 添加日期標題
            bubble["body"]["contents"].append({
                "type": "text",
                "text": f"【{date_title}】",
                "weight": "bold",
                "size": "md",
                "margin": "md"
            })
        
        # 根據狀態添加不同的表情符號
        status_emoji = {
            "準備": "🟢",
            "完成": "✅",
            "取消": "❌",
            "衝突": "⚠️",
            "請假": "🔵",
            "待派": "🟠"
        }.get(status, "⚪")
        
        # 添加班次信息
        trip_box = {
            "type": "box",
            "layout": "horizontal",
            "contents": [
                {
                    "type": "text",
                    "text": f"{status_emoji} #{trip_id}",
                    "size": "xs",
                    "flex": 3
                },
                {
                    "type": "text",
                    "text": time_val,
                    "size": "xs",
                    "flex": 2
                },
                {
                    "type": "text",
                    "text": f"{location}{direction}",
                    "size": "xs",
                    "flex": 5,
                    "wrap": True
                },
                {
                    "type": "text",
                    "text": f"🚕{driver_id}",
                    "size": "xs",
                    "flex": 2,
                    "align": "end"
                }
            ],
            "margin": "sm",
            "action": {
                "type": "message",
                "text": f"班次詳情 {trip_id}"
            }
        }
        
        bubble["body"]["contents"].append(trip_box)
    
    return bubble
