"""
為司機指派功能設計的Flex Message模板
"""
from sqlalchemy import text as sql_text
from modules.models.base import db

def get_driver_assign_flex(trip_id, trip_info=None):
    """生成司機指派選擇界面"""
    
    # 班次基本信息
    trip_header = f"指派司機：班次 #{trip_id}"
    if trip_info:
        date_str = trip_info.get("date", "未知")
        time_str = trip_info.get("time", "未知")
        start_point = trip_info.get("start_point", "未知")
        end_point = trip_info.get("end_point", "未知")
        trip_detail = f"{date_str} {time_str} | {start_point} → {end_point}"
    else:
        trip_detail = "請選擇要指派的司機"
    
    # 創建 Flex Message 結構
    bubble = {
        "type": "bubble",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": trip_header,
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
            "contents": [
                {
                    "type": "text",
                    "text": trip_detail,
                    "size": "sm",
                    "color": "#555555",
                    "wrap": True,
                    "margin": "md"
                },
                {
                    "type": "separator",
                    "margin": "lg"
                },
                {
                    "type": "text",
                    "text": "選擇司機",
                    "weight": "bold",
                    "margin": "lg"
                }
            ],
            "spacing": "md"
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "button",
                    "action": {
                        "type": "message",
                        "label": "取消",
                        "text": f"取消指派 {trip_id}"
                    },
                    "style": "secondary",
                    "color": "#999999"
                }
            ]
        }
    }
    
    # 查詢所有司機
    try:
        query = """
        SELECT id, name, plate_number 
        FROM drivers 
        ORDER BY name
        """
        
        drivers = db.session.execute(sql_text(query)).fetchall()
        
        # 添加司機按鈕
        for driver in drivers:
            driver_id = driver[0]
            driver_name = driver[1]
            driver_plate = driver[2] or ""
            
            # 創建司機按鈕
            driver_button = {
                "type": "button",
                "action": {
                    "type": "message",
                    "label": f"{driver_name} ({driver_plate})",
                    "text": f"指派司機 {trip_id} {driver_id}"
                },
                "style": "primary",
                "color": "#1e88e5",
                "margin": "sm"
            }
            
            # 添加到body
            bubble["body"]["contents"].append(driver_button)
        
        # 如果沒有司機，顯示提示
        if not drivers:
            bubble["body"]["contents"].append({
                "type": "text",
                "text": "目前沒有可用的司機",
                "size": "sm",
                "color": "#ff0000",
                "margin": "md",
                "align": "center"
            })
            
    except Exception as e:
        # 添加錯誤信息
        bubble["body"]["contents"].append({
            "type": "text",
            "text": f"載入司機列表時出錯: {str(e)}",
            "size": "sm",
            "color": "#ff0000",
            "margin": "md",
            "wrap": True
        })
    
    return bubble

def get_driver_assign_confirm_flex(trip_id, driver_id, driver_info=None, trip_info=None):
    """生成司機指派確認界面"""
    
    # 獲取司機信息
    driver_name = driver_info.get("name", "未知") if driver_info else f"ID: {driver_id}"
    driver_plate = driver_info.get("plate_number", "") if driver_info else ""
    
    # 獲取班次信息
    if trip_info:
        date_str = trip_info.get("date", "未知")
        time_str = trip_info.get("time", "未知")
        start_point = trip_info.get("start_point", "未知")
        end_point = trip_info.get("end_point", "未知")
        trip_detail = f"{date_str} {time_str}\n{start_point} → {end_point}"
    else:
        trip_detail = f"班次 #{trip_id}"
    
    # 創建 Flex Message 結構
    bubble = {
        "type": "bubble",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "確認指派司機",
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
            "contents": [
                {
                    "type": "text",
                    "text": "請確認是否指派以下司機",
                    "size": "sm",
                    "color": "#555555",
                    "margin": "md"
                },
                {
                    "type": "separator",
                    "margin": "lg"
                },
                {
                    "type": "box",
                    "layout": "vertical",
                    "contents": [
                        {
                            "type": "text",
                            "text": f"班次: #{trip_id}",
                            "weight": "bold",
                            "size": "md"
                        },
                        {
                            "type": "text",
                            "text": trip_detail,
                            "size": "sm",
                            "margin": "sm",
                            "wrap": True
                        }
                    ],
                    "margin": "lg"
                },
                {
                    "type": "box",
                    "layout": "vertical",
                    "contents": [
                        {
                            "type": "text",
                            "text": "指派給:",
                            "weight": "bold",
                            "size": "md"
                        },
                        {
                            "type": "text",
                            "text": f"{driver_name} ({driver_plate})",
                            "size": "sm",
                            "margin": "sm"
                        }
                    ],
                    "margin": "lg"
                }
            ],
            "spacing": "md"
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "box",
                    "layout": "horizontal",
                    "contents": [
                        {
                            "type": "button",
                            "action": {
                                "type": "message",
                                "label": "確認指派",
                                "text": f"確認指派 {trip_id} {driver_id}"
                            },
                            "style": "primary",
                            "color": "#4CAF50"
                        },
                        {
                            "type": "button",
                            "action": {
                                "type": "message",
                                "label": "取消",
                                "text": f"取消指派 {trip_id}"
                            },
                            "style": "secondary",
                            "color": "#999999"
                        }
                    ],
                    "spacing": "sm"
                }
            ]
        }
    }
    
    return bubble 