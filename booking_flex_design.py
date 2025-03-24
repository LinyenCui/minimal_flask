"""
預約功能的 Flex Message 設計
"""

from datetime import datetime, date, timedelta

def get_booking_start_flex():
    """生成預約開始的 Flex Message（日期選擇界面）"""
    # 獲取當前日期
    now = datetime.now()
    
    # 計算未來7天的日期
    dates = []
    for i in range(7):
        date_obj = now.date() + timedelta(days=i)
        weekday = ["一", "二", "三", "四", "五", "六", "日"][date_obj.weekday()]
        
        # 格式化顯示用的日期
        if i == 0:
            display_text = f"今天 ({date_obj.month}/{date_obj.day})"
        elif i == 1:
            display_text = f"明天 ({date_obj.month}/{date_obj.day})"
        elif i == 2:
            display_text = f"後天 ({date_obj.month}/{date_obj.day})"
        else:
            display_text = f"{date_obj.month}/{date_obj.day} (週{weekday})"
        
        # 格式化數據用的日期
        date_value = date_obj.strftime("%Y-%m-%d")
        
        dates.append({
            "display": display_text,
            "value": date_value
        })
    
    # 創建 Flex Message 結構
    bubble = {
        "type": "bubble",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "預約服務",
                    "weight": "bold",
                    "size": "xl",
                    "color": "#ffffff"
                }
            ],
            "backgroundColor": "#27ACB2",
            "paddingAll": "12px"
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "請選擇預約日期",
                    "weight": "bold",
                    "size": "md",
                    "margin": "md"
                },
                {
                    "type": "box",
                    "layout": "vertical",
                    "contents": [],
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
                        "label": "取消預約",
                        "data": "action=cancel_booking",
                        "displayText": "取消預約"
                    },
                    "style": "secondary",
                    "color": "#999999"
                }
            ]
        }
    }
    
    # 添加日期按鈕
    date_buttons = []
    for date_info in dates:
        date_buttons.append({
            "type": "button",
            "action": {
                "type": "postback",
                "label": date_info["display"],
                "data": f"action=select_date&date={date_info['value']}",
                "displayText": date_info["value"]
            },
            "style": "primary",
            "color": "#27ACB2",
            "margin": "sm",
            "height": "sm"
        })
    
    # 將日期按鈕添加到主體內容中
    bubble["body"]["contents"][1]["contents"] = date_buttons
    
    return bubble

def get_booking_time_flex(selected_date=None):
    """生成預約時間的 Flex Message（時間選擇界面）"""
    # 處理日期格式
    if isinstance(selected_date, date):
        date_obj = selected_date
        date_str = selected_date.strftime("%Y-%m-%d")
    elif isinstance(selected_date, str):
        date_obj = datetime.strptime(selected_date, "%Y-%m-%d").date()
        date_str = selected_date
    else:
        date_obj = datetime.now().date()
        date_str = date_obj.strftime("%Y-%m-%d")
    
    # 獲取星期幾
    weekday = ["一", "二", "三", "四", "五", "六", "日"][date_obj.weekday()]
    date_display = f"{date_obj.month}/{date_obj.day} (週{weekday})"
    
    # 創建時間按鈕列表
    am_times = ["08:00", "08:30", "09:00", "09:30", "10:00", "10:30", "11:00", "11:30"]
    pm_times = ["13:00", "13:30", "14:00", "14:30", "15:00", "15:30", "16:00", "16:30"]
    
    # 創建上午時間按鈕
    am_time_buttons = []
    for time_slot in am_times:
        am_time_buttons.append({
            "type": "button",
            "action": {
                "type": "postback",
                "label": time_slot,
                "data": f"action=select_time&time={time_slot}",
                "displayText": time_slot
            },
            "style": "primary",
            "color": "#4169E1", # 藍色
            "margin": "sm",
            "height": "sm"
        })
    
    # 創建下午時間按鈕
    pm_time_buttons = []
    for time_slot in pm_times:
        pm_time_buttons.append({
            "type": "button",
            "action": {
                "type": "postback",
                "label": time_slot,
                "data": f"action=select_time&time={time_slot}",
                "displayText": time_slot
            },
            "style": "primary",
            "color": "#4169E1", # 藍色
            "margin": "sm",
            "height": "sm"
        })
    
    # 組織按鈕為兩列
    am_button_pairs = []
    for i in range(0, len(am_time_buttons), 2):
        if i + 1 < len(am_time_buttons):
            am_button_pairs.append([am_time_buttons[i], am_time_buttons[i+1]])
        else:
            am_button_pairs.append([am_time_buttons[i]])
    
    pm_button_pairs = []
    for i in range(0, len(pm_time_buttons), 2):
        if i + 1 < len(pm_time_buttons):
            pm_button_pairs.append([pm_time_buttons[i], pm_time_buttons[i+1]])
        else:
            pm_button_pairs.append([pm_time_buttons[i]])
    
    # 創建 Flex Message 結構
    bubble = {
        "type": "bubble",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "選擇預約時間",
                    "weight": "bold",
                    "color": "#ffffff",
                    "size": "lg"
                },
                {
                    "type": "text",
                    "text": date_display,
                    "color": "#ffffff",
                    "size": "sm"
                }
            ],
            "backgroundColor": "#2E8B57", # 深綠色背景
            "paddingAll": "12px"
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "上午",
                    "weight": "bold",
                    "color": "#1f76de",
                    "size": "md"
                },
                {
                    "type": "box",
                    "layout": "vertical",
                    "contents": []
                },
                {
                    "type": "text",
                    "text": "下午",
                    "weight": "bold",
                    "color": "#1f76de",
                    "size": "md",
                    "margin": "md"
                },
                {
                    "type": "box",
                    "layout": "vertical",
                    "contents": []
                },
                {
                    "type": "text",
                    "text": "你也可以手動輸入時間",
                    "color": "#888888",
                    "size": "xs",
                    "align": "center",
                    "margin": "md"
                }
            ],
            "paddingAll": "12px"
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "button",
                    "action": {
                        "type": "postback",
                        "label": "返回預約日期",
                        "data": "action=booking",
                        "displayText": "返回預約日期"
                    },
                    "style": "secondary",
                    "margin": "sm"
                },
                {
                    "type": "button",
                    "action": {
                        "type": "postback",
                        "label": "取消預約",
                        "data": "action=cancel_booking",
                        "displayText": "取消預約"
                    },
                    "style": "secondary",
                    "color": "#999999",
                    "margin": "sm"
                }
            ]
        }
    }
    
    # 為每個時間對創建一個行
    am_rows = []
    for button_pair in am_button_pairs:
        if len(button_pair) == 2:
            row = {
                "type": "box",
                "layout": "horizontal",
                "contents": [
                    button_pair[0],
                    button_pair[1]
                ],
                "margin": "md"
            }
        else:
            row = {
                "type": "box",
                "layout": "horizontal",
                "contents": [
                    button_pair[0],
                    {
                        "type": "filler"
                    }
                ],
                "margin": "md"
            }
        am_rows.append(row)
    
    pm_rows = []
    for button_pair in pm_button_pairs:
        if len(button_pair) == 2:
            row = {
                "type": "box",
                "layout": "horizontal",
                "contents": [
                    button_pair[0],
                    button_pair[1]
                ],
                "margin": "md"
            }
        else:
            row = {
                "type": "box",
                "layout": "horizontal",
                "contents": [
                    button_pair[0],
                    {
                        "type": "filler"
                    }
                ],
                "margin": "md"
            }
        pm_rows.append(row)
    
    # 將行添加到上午和下午部分
    bubble["body"]["contents"][1]["contents"] = am_rows
    bubble["body"]["contents"][3]["contents"] = pm_rows
    
    return bubble

def get_booking_location_flex(selected_date, selected_time):
    """生成上車地點選擇的 Flex Message"""
    # 處理日期格式
    if isinstance(selected_date, date):
        date_obj = selected_date
        date_str = selected_date.strftime("%Y-%m-%d")
    elif isinstance(selected_date, str):
        date_obj = datetime.strptime(selected_date, "%Y-%m-%d").date()
        date_str = selected_date
    else:
        date_obj = datetime.now().date()
        date_str = date_obj.strftime("%Y-%m-%d")
    
    # 獲取星期幾
    weekday = ["一", "二", "三", "四", "五", "六", "日"][date_obj.weekday()]
    date_display = f"{date_obj.month}/{date_obj.day} (週{weekday})"
    
    # 創建 Flex Message 結構
    bubble = {
        "type": "bubble",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "輸入上車地點",
                    "weight": "bold",
                    "color": "#ffffff",
                    "size": "xl"
                }
            ],
            "backgroundColor": "#FF7F50", # 珊瑚紅
            "paddingAll": "12px"
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "已選擇的時間",
                    "weight": "bold",
                    "size": "md"
                },
                {
                    "type": "box",
                    "layout": "horizontal",
                    "contents": [
                        {
                            "type": "text",
                            "text": date_display,
                            "size": "sm",
                            "color": "#555555",
                            "flex": 0
                        },
                        {
                            "type": "text",
                            "text": selected_time,
                            "size": "sm",
                            "color": "#555555",
                            "align": "end"
                        }
                    ],
                    "margin": "md"
                },
                {
                    "type": "separator",
                    "margin": "lg"
                },
                {
                    "type": "text",
                    "text": "請輸入上車地點",
                    "weight": "bold",
                    "margin": "lg"
                },
                {
                    "type": "text",
                    "text": "例如：家裡、公司、台北車站等",
                    "size": "sm",
                    "color": "#555555",
                    "margin": "sm"
                }
            ],
            "paddingAll": "12px"
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "button",
                    "action": {
                        "type": "postback",
                        "label": "返回時間選擇",
                        "data": f"action=select_date&date={date_str}",
                        "displayText": "返回時間選擇"
                    },
                    "style": "secondary",
                    "margin": "sm"
                },
                {
                    "type": "button",
                    "action": {
                        "type": "postback",
                        "label": "取消預約",
                        "data": "action=cancel_booking",
                        "displayText": "取消預約"
                    },
                    "style": "secondary",
                    "color": "#999999",
                    "margin": "sm"
                }
            ]
        }
    }
    
    return bubble

def get_booking_confirm_flex(booking_data):
    """生成預約確認的 Flex Message"""
    # 處理日期格式
    if isinstance(booking_data["date"], date):
        date_obj = booking_data["date"]
        date_str = booking_data["date"].strftime("%Y-%m-%d")
    elif isinstance(booking_data["date"], str):
        date_obj = datetime.strptime(booking_data["date"], "%Y-%m-%d").date()
        date_str = booking_data["date"]
    else:
        raise ValueError("日期格式無效")
    
    # 獲取星期幾
    weekday = ["一", "二", "三", "四", "五", "六", "日"][date_obj.weekday()]
    date_display = f"{date_obj.month}/{date_obj.day} (週{weekday})"
    
    # 創建 Flex Message 結構
    bubble = {
        "type": "bubble",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "確認預約資訊",
                    "weight": "bold",
                    "color": "#ffffff",
                    "size": "xl"
                }
            ],
            "backgroundColor": "#6A5ACD", # 石板藍
            "paddingAll": "12px"
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
                            "text": "日期:",
                            "size": "md",
                            "color": "#555555",
                            "flex": 0,
                            "weight": "bold",
                            "margin": "sm"
                        },
                        {
                            "type": "text",
                            "text": date_display,
                            "size": "md",
                            "color": "#555555",
                            "align": "end",
                            "margin": "sm"
                        }
                    ]
                },
                {
                    "type": "box",
                    "layout": "horizontal",
                    "contents": [
                        {
                            "type": "text",
                            "text": "時間:",
                            "size": "md",
                            "color": "#555555",
                            "flex": 0,
                            "weight": "bold",
                            "margin": "sm"
                        },
                        {
                            "type": "text",
                            "text": booking_data["time"],
                            "size": "md",
                            "color": "#555555",
                            "align": "end",
                            "margin": "sm"
                        }
                    ]
                },
                {
                    "type": "box",
                    "layout": "horizontal",
                    "contents": [
                        {
                            "type": "text",
                            "text": "上車地點:",
                            "size": "md",
                            "color": "#555555",
                            "flex": 0,
                            "weight": "bold",
                            "margin": "sm"
                        },
                        {
                            "type": "text",
                            "text": booking_data["start_point"],
                            "size": "md",
                            "color": "#555555",
                            "align": "end",
                            "margin": "sm"
                        }
                    ]
                },
                {
                    "type": "box",
                    "layout": "horizontal",
                    "contents": [
                        {
                            "type": "text",
                            "text": "經過點:",
                            "size": "md",
                            "color": "#555555",
                            "flex": 0,
                            "weight": "bold",
                            "margin": "sm"
                        },
                        {
                            "type": "text",
                            "text": booking_data["via_point"],
                            "size": "md",
                            "color": "#555555",
                            "align": "end",
                            "margin": "sm"
                        }
                    ]
                },
                {
                    "type": "box",
                    "layout": "horizontal",
                    "contents": [
                        {
                            "type": "text",
                            "text": "終點:",
                            "size": "md",
                            "color": "#555555",
                            "flex": 0,
                            "weight": "bold",
                            "margin": "sm"
                        },
                        {
                            "type": "text",
                            "text": booking_data["end_point"],
                            "size": "md",
                            "color": "#555555",
                            "align": "end",
                            "margin": "sm"
                        }
                    ]
                },
                {
                    "type": "box",
                    "layout": "horizontal",
                    "contents": [
                        {
                            "type": "text",
                            "text": "類別:",
                            "size": "md",
                            "color": "#555555",
                            "flex": 0,
                            "weight": "bold",
                            "margin": "sm"
                        },
                        {
                            "type": "text",
                            "text": booking_data["category"],
                            "size": "md",
                            "color": "#555555",
                            "align": "end",
                            "margin": "sm"
                        }
                    ]
                },
                {
                    "type": "separator",
                    "margin": "lg"
                },
                {
                    "type": "text",
                    "text": "請確認以上預約資訊",
                    "size": "sm",
                    "color": "#FF0000",
                    "align": "center",
                    "margin": "lg"
                }
            ],
            "paddingAll": "12px"
        },
        "footer": {
            "type": "box",
            "layout": "horizontal",
            "contents": [
                {
                    "type": "button",
                    "action": {
                        "type": "postback",
                        "label": "確認預約",
                        "data": "action=confirm_booking",
                        "displayText": "確認預約"
                    },
                    "style": "primary",
                    "color": "#4CAF50",
                    "margin": "sm"
                },
                {
                    "type": "button",
                    "action": {
                        "type": "postback",
                        "label": "取消預約",
                        "data": "action=cancel_booking",
                        "displayText": "取消預約"
                    },
                    "style": "secondary",
                    "color": "#999999",
                    "margin": "sm"
                }
            ]
        }
    }
    
    return bubble

def get_booking_success_flex(booking_data, trip_id):
    """生成預約成功的 Flex Message"""
    # 處理日期格式
    if isinstance(booking_data["date"], date):
        date_obj = booking_data["date"]
        date_str = booking_data["date"].strftime("%Y-%m-%d")
    elif isinstance(booking_data["date"], str):
        date_obj = datetime.strptime(booking_data["date"], "%Y-%m-%d").date()
        date_str = booking_data["date"]
    else:
        raise ValueError("日期格式無效")
    
    # 獲取星期幾
    weekday = ["一", "二", "三", "四", "五", "六", "日"][date_obj.weekday()]
    date_display = f"{date_obj.month}/{date_obj.day} (週{weekday})"
    
    # 創建 Flex Message 結構
    bubble = {
        "type": "bubble",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "預約成功",
                    "weight": "bold",
                    "color": "#ffffff",
                    "size": "xl"
                }
            ],
            "backgroundColor": "#4CAF50", # 綠色
            "paddingAll": "12px"
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": f"班次 ID: {trip_id}",
                    "weight": "bold",
                    "size": "lg",
                    "color": "#1DB446",
                    "align": "center"
                },
                {
                    "type": "separator",
                    "margin": "lg"
                },
                {
                    "type": "box",
                    "layout": "horizontal",
                    "contents": [
                        {
                            "type": "text",
                            "text": "日期:",
                            "size": "md",
                            "color": "#555555",
                            "flex": 0,
                            "weight": "bold",
                            "margin": "sm"
                        },
                        {
                            "type": "text",
                            "text": date_display,
                            "size": "md",
                            "color": "#555555",
                            "align": "end",
                            "margin": "sm"
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
                            "text": "時間:",
                            "size": "md",
                            "color": "#555555",
                            "flex": 0,
                            "weight": "bold",
                            "margin": "sm"
                        },
                        {
                            "type": "text",
                            "text": booking_data["time"],
                            "size": "md",
                            "color": "#555555",
                            "align": "end",
                            "margin": "sm"
                        }
                    ]
                },
                {
                    "type": "box",
                    "layout": "horizontal",
                    "contents": [
                        {
                            "type": "text",
                            "text": "上車地點:",
                            "size": "md",
                            "color": "#555555",
                            "flex": 0,
                            "weight": "bold",
                            "margin": "sm"
                        },
                        {
                            "type": "text",
                            "text": booking_data["start_point"],
                            "size": "md",
                            "color": "#555555",
                            "align": "end",
                            "margin": "sm"
                        }
                    ]
                },
                {
                    "type": "box",
                    "layout": "horizontal",
                    "contents": [
                        {
                            "type": "text",
                            "text": "經過點:",
                            "size": "md",
                            "color": "#555555",
                            "flex": 0,
                            "weight": "bold",
                            "margin": "sm"
                        },
                        {
                            "type": "text",
                            "text": booking_data["via_point"],
                            "size": "md",
                            "color": "#555555",
                            "align": "end",
                            "margin": "sm"
                        }
                    ]
                },
                {
                    "type": "box",
                    "layout": "horizontal",
                    "contents": [
                        {
                            "type": "text",
                            "text": "終點:",
                            "size": "md",
                            "color": "#555555",
                            "flex": 0,
                            "weight": "bold",
                            "margin": "sm"
                        },
                        {
                            "type": "text",
                            "text": booking_data["end_point"],
                            "size": "md",
                            "color": "#555555",
                            "align": "end",
                            "margin": "sm"
                        }
                    ]
                },
                {
                    "type": "box",
                    "layout": "horizontal",
                    "contents": [
                        {
                            "type": "text",
                            "text": "狀態:",
                            "size": "md",
                            "color": "#555555",
                            "flex": 0,
                            "weight": "bold",
                            "margin": "sm"
                        },
                        {
                            "type": "text",
                            "text": "待派",
                            "size": "md",
                            "color": "#FF9800",
                            "align": "end",
                            "margin": "sm"
                        }
                    ]
                },
                {
                    "type": "separator",
                    "margin": "lg"
                },
                {
                    "type": "text",
                    "text": "我們會盡快確認您的預約",
                    "size": "sm",
                    "color": "#555555",
                    "align": "center",
                    "margin": "lg"
                }
            ],
            "paddingAll": "12px"
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "button",
                    "action": {
                        "type": "postback",
                        "label": "查詢班次",
                        "data": "action=query_trips",
                        "displayText": "查詢班次"
                    },
                    "style": "primary",
                    "margin": "sm"
                }
            ]
        },
        "styles": {
            "header": {
                "backgroundColor": "#4CAF50"
            }
        }
    }
    
    return bubble

# 測試用例
if __name__ == "__main__":
    # 測試預約開始界面
    start_bubble = get_booking_start_flex()
    print("預約開始界面生成成功")
    
    # 測試時間選擇界面
    time_bubble = get_booking_time_flex("2025-03-15")
    print("時間選擇界面生成成功")
    
    # 測試地點選擇界面
    location_bubble = get_booking_location_flex("2025-03-15", "09:30")
    print("地點選擇界面生成成功")
    
    # 測試預約確認界面
    booking_data = {
        "date": "2025-03-15",
        "time": "09:30",
        "start_point": "怡平路",
        "via_point": "無",
        "end_point": "診所",
        "category": "診所"
    }
    confirm_bubble = get_booking_confirm_flex(booking_data)
    print("預約確認界面生成成功")
    
    # 測試預約成功界面
    success_bubble = get_booking_success_flex(booking_data, 123)
    print("預約成功界面生成成功") 