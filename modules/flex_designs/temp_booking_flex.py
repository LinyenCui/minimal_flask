"""
為臨時預約功能設計的Flex Message模板，結合Quick Reply
"""
from datetime import datetime, date, timedelta

def get_temp_booking_start_flex(current_date=None):
    """生成臨時預約開始的日期選擇頁面，使用Flex Message + Quick Reply組合"""
    if current_date is None:
        current_date = date.today()
    
    # 計算未來7天的日期
    dates = []
    for i in range(7):
        date_obj = current_date + timedelta(days=i)
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
    
    # 創建 Flex Message 結構（保留表頭和取消按鈕）
    bubble = {
        "type": "bubble",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "臨時預約",
                    "weight": "bold",
                    "size": "xl",
                    "color": "#ffffff"
                }
            ],
            "backgroundColor": "#FF6B6E",
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
                    "align": "center",
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
                        "type": "message",
                        "label": "取消預約",
                        "text": "取消預約"
                    },
                    "style": "secondary",
                    "color": "#999999"
                }
            ]
        }
    }
    
    # 創建 Quick Reply 項目 (使用字典格式，而不是QuickReplyItem對象)
    quick_reply_items = []
    for date_info in dates:
        quick_reply_items.append({
            "type": "action",
            "action": {
                "type": "message",
                "label": date_info["display"],
                "text": date_info["value"]
            }
        })
    
    # 組合Quick Reply (使用字典格式，而不是QuickReply對象)
    quick_reply = {
        "items": quick_reply_items
    }
    
    return bubble, quick_reply

def get_temp_booking_time_flex(selected_date=None):
    """生成臨時預約時間選擇頁面，使用Flex Message + Quick Reply組合"""
    if selected_date is None:
        selected_date = date.today()
    
    # 格式化顯示日期
    weekday = ["一", "二", "三", "四", "五", "六", "日"][selected_date.weekday()]
    display_date = f"{selected_date.month}/{selected_date.day} (週{weekday})"
    
    # 創建指定的常用時間段 - 根據需求使用特定時間
    specific_times = ["09:17", "10:32", "14:30", "15:30", "17:00", "17:30"]
    
    # 創建 Flex Message 結構（簡化設計，只保留表頭和必要信息）
    bubble = {
        "type": "bubble",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": f"選擇時間: {display_date}",
                    "weight": "bold",
                    "size": "lg",
                    "color": "#ffffff"
                }
            ],
            "backgroundColor": "#FF6B6E",
            "paddingAll": "12px"
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "請選擇預約時間",
                    "weight": "bold",
                    "size": "md",
                    "align": "center"
                },
                {
                    "type": "text",
                    "text": "您也可以直接輸入時間（如: 14:30）",
                    "size": "xs",
                    "color": "#AAAAAA",
                    "margin": "lg",
                    "align": "center"
                }
            ],
            "spacing": "md",
            "paddingAll": "12px"
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "button",
                    "action": {
                        "type": "message",
                        "label": "重新開始預約",
                        "text": "臨時預約"
                    },
                    "style": "primary",
                    "height": "sm",
                    "color": "#4DAACD"
                },
                {
                    "type": "button",
                    "action": {
                        "type": "message",
                        "label": "取消預約",
                        "text": "取消預約"
                    },
                    "style": "secondary",
                    "color": "#999999",
                    "margin": "sm",
                    "height": "sm"
                }
            ]
        }
    }
    
    # 創建 Quick Reply 項目
    quick_reply_items = []
    
    # 使用特定時間選項
    for time in specific_times:
        quick_reply_items.append({
            "type": "action",
            "action": {
                "type": "message",
                "label": time,
                "text": time
            }
        })
    
    # 組合Quick Reply (使用字典格式)
    quick_reply = {
        "items": quick_reply_items
    }
    
    return bubble, quick_reply

def get_temp_booking_location_flex():
    """生成臨時預約起點選擇頁面，使用Flex Message + Quick Reply組合"""
    # 創建 Flex Message 結構
    bubble = {
        "type": "bubble",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "選擇起點位置",
                    "weight": "bold",
                    "size": "lg",
                    "color": "#ffffff"
                }
            ],
            "backgroundColor": "#FF6B6E",
            "paddingAll": "12px"
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "請選擇或輸入起點位置",
                    "weight": "bold",
                    "size": "md",
                    "align": "center"
                },
                {
                    "type": "text",
                    "text": "您也可以直接輸入地址或地標名稱",
                    "size": "xs",
                    "color": "#AAAAAA",
                    "margin": "lg",
                    "align": "center"
                }
            ],
            "spacing": "md",
            "paddingAll": "12px"
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "button",
                    "action": {
                        "type": "message",
                        "label": "取消預約",
                        "text": "取消預約"
                    },
                    "style": "secondary",
                    "color": "#999999"
                }
            ]
        }
    }
    
    # 常用地點選項 - 根據customers表的short_name
    common_locations = ["東洋前門", "東洋後門", "高鐵站", "HANNSTAR", "群創D3哨"]
    
    # 創建 Quick Reply 項目
    quick_reply_items = []
    
    for location in common_locations:
        quick_reply_items.append({
            "type": "action",
            "action": {
                "type": "message",
                "label": location,
                "text": location
            }
        })
    
    # 組合Quick Reply
    quick_reply = {
        "items": quick_reply_items
    }
    
    return bubble, quick_reply

def get_temp_booking_destination_flex():
    """生成臨時預約目的地選擇頁面，使用Flex Message + Quick Reply組合"""
    # 創建 Flex Message 結構
    bubble = {
        "type": "bubble",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "選擇目的地位置",
                    "weight": "bold",
                    "size": "lg",
                    "color": "#ffffff"
                }
            ],
            "backgroundColor": "#FF6B6E",
            "paddingAll": "12px"
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "請選擇或輸入目的地位置",
                    "weight": "bold",
                    "size": "md",
                    "align": "center"
                },
                {
                    "type": "text",
                    "text": "您也可以直接輸入地址或地標名稱",
                    "size": "xs",
                    "color": "#AAAAAA",
                    "margin": "lg",
                    "align": "center"
                }
            ],
            "spacing": "md",
            "paddingAll": "12px"
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "button",
                    "action": {
                        "type": "message",
                        "label": "取消預約",
                        "text": "取消預約"
                    },
                    "style": "secondary",
                    "color": "#999999"
                }
            ]
        }
    }
    
    # 常用地點選項 - 將「無(略過)」放在第一位
    common_locations = ["無(略過)", "東洋前門", "東洋後門", "高鐵站", "HANNSTAR", "群創D3哨"]
    
    # 創建 Quick Reply 項目
    quick_reply_items = []
    
    for location in common_locations:
        quick_reply_items.append({
            "type": "action",
            "action": {
                "type": "message",
                "label": location,
                "text": location
            }
        })
    
    # 組合Quick Reply
    quick_reply = {
        "items": quick_reply_items
    }
    
    return bubble, quick_reply

def get_temp_booking_confirm_flex(date_str, time_str, start_point, end_point=None, category="臨時"):
    """生成臨時預約確認頁面，使用Flex Message + Quick Reply組合"""
    bubble = {
        "type": "bubble",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "預約確認",
                    "weight": "bold",
                    "size": "xl",
                    "color": "#ffffff"
                }
            ],
            "backgroundColor": "#FF6B6E",
            "paddingAll": "12px"
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "請確認您的臨時預約信息",
                    "weight": "bold",
                    "size": "md",
                    "align": "center"
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
                                    "text": date_str,
                                    "size": "sm",
                                    "color": "#111111",
                                    "flex": 4
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
                                    "text": "時間",
                                    "size": "sm",
                                    "color": "#555555",
                                    "flex": 2
                                },
                                {
                                    "type": "text",
                                    "text": time_str,
                                    "size": "sm",
                                    "color": "#111111",
                                    "flex": 4
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
                                    "text": start_point,
                                    "size": "sm",
                                    "color": "#111111",
                                    "flex": 4,
                                    "wrap": True
                                }
                            ],
                            "margin": "md"
                        }
                    ],
                    "paddingAll": "10px",
                    "backgroundColor": "#F5F5F5",
                    "cornerRadius": "5px",
                    "margin": "md"
                }
            ],
            "spacing": "md",
            "paddingBottom": "10px"
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "button",
                    "action": {
                        "type": "message",
                        "label": "取消預約",
                        "text": "取消預約"
                    },
                    "style": "secondary",
                    "color": "#999999"
                }
            ]
        }
    }
    
    # 如果有目的地，添加到內容中
    if end_point and end_point != "無(略過)":
        bubble["body"]["contents"][2]["contents"].append({
            "type": "box",
            "layout": "horizontal",
            "contents": [
                {
                    "type": "text",
                    "text": "目的地",
                    "size": "sm",
                    "color": "#555555",
                    "flex": 2
                },
                {
                    "type": "text",
                    "text": end_point,
                    "size": "sm",
                    "color": "#111111",
                    "flex": 4,
                    "wrap": True
                }
            ],
            "margin": "md"
        })
    
    # 添加類別
    bubble["body"]["contents"][2]["contents"].append({
        "type": "box",
        "layout": "horizontal",
        "contents": [
            {
                "type": "text",
                "text": "類別",
                "size": "sm",
                "color": "#555555",
                "flex": 2
            },
            {
                "type": "text",
                "text": category,
                "size": "sm",
                "color": "#111111",
                "flex": 4
            }
        ],
        "margin": "md"
    })
    
    # 創建確認的Quick Reply選項
    quick_reply_items = [
        {
            "type": "action",
            "action": {
                "type": "message",
                "label": "確認預約",
                "text": "確認"
            }
        }
    ]
    
    quick_reply = {
        "items": quick_reply_items
    }
    
    return bubble, quick_reply 