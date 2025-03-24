"""
預約功能的 Flex Message 設計
"""
from datetime import datetime, date, timedelta, time
from linebot.v3.messaging import PostbackAction
import logging

# 設置日誌
logger = logging.getLogger(__name__)

def get_booking_start_flex():
    """獲取預約開始 Flex Message"""
    try:
        # 計算未來7天的日期
        today = date.today()
        date_buttons = []
        
        # 添加預定義的日期選項（今天、明天、後天）
        quick_dates = [
            {"label": "今天", "date": today},
            {"label": "明天", "date": today + timedelta(days=1)},
            {"label": "後天", "date": today + timedelta(days=2)}
        ]
        
        for quick_date in quick_dates:
            date_str = quick_date["date"].strftime("%Y-%m-%d")
            display_date = quick_date["date"].strftime("%m/%d")
            
            date_buttons.append({
                "type": "button",
                "style": "primary",
                "action": {
                    "type": "postback",
                    "label": f"{quick_date['label']} ({display_date})",
                    "data": f"action=select_date&date={date_str}",
                    "displayText": f"預約 {quick_date['label']} ({display_date})"
                }
            })
        
        # 添加未來4天的日期選項
        for i in range(3, 7):
            future_date = today + timedelta(days=i)
            date_str = future_date.strftime("%Y-%m-%d")
            display_date = future_date.strftime("%m/%d")
            weekday = ["一", "二", "三", "四", "五", "六", "日"][future_date.weekday()]
            
            date_buttons.append({
                "type": "button",
                "style": "secondary",
                "action": {
                    "type": "postback",
                    "label": f"{display_date} (週{weekday})",
                    "data": f"action=select_date&date={date_str}",
                    "displayText": f"預約 {display_date} (週{weekday})"
                }
            })
        
        # 創建 Flex Message
        flex_content = {
            "type": "bubble",
            "header": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": "選擇預約日期",
                        "weight": "bold",
                        "size": "xl",
                        "color": "#1E3A8A"
                    }
                ],
                "backgroundColor": "#E0E7FF"
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": date_buttons,
                "spacing": "sm"
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "button",
                        "style": "link",
                        "action": {
                            "type": "postback",
                            "label": "取消預約",
                            "data": "action=cancel_booking",
                            "displayText": "取消預約"
                        },
                        "color": "#9CA3AF"
                    }
                ]
            }
        }
        
        return flex_content
    except Exception as e:
        logger.error(f"創建預約開始 Flex Message 時出錯: {e}")
        return None

def get_booking_time_flex(selected_date):
    """獲取預約時間 Flex Message"""
    try:
        # 格式化日期為顯示格式
        display_date = ""
        if isinstance(selected_date, str):
            try:
                date_obj = datetime.strptime(selected_date, "%Y-%m-%d").date()
                display_date = date_obj.strftime("%Y/%m/%d")
            except ValueError:
                display_date = selected_date
        elif isinstance(selected_date, date):
            display_date = selected_date.strftime("%Y/%m/%d")
        else:
            display_date = str(selected_date)
        
        # 創建時間按鈕
        time_buttons = []
        time_ranges = [
            "09:00", "10:00", "11:00", "12:00",
            "13:00", "14:00", "15:00", "16:00",
            "17:00", "18:00", "19:00", "20:00"
        ]
        
        for time_str in time_ranges:
            time_buttons.append({
                "type": "button",
                "style": "secondary",
                "action": {
                    "type": "postback",
                    "label": time_str,
                    "data": f"action=select_time&time={time_str}",
                    "displayText": f"選擇時間 {time_str}"
                },
                "margin": "sm"
            })
        
        # 將按鈕分成3列，每列4個
        button_rows = [
            {
                "type": "box",
                "layout": "horizontal",
                "contents": time_buttons[i:i+4],
                "spacing": "sm",
                "margin": "md"
            } for i in range(0, len(time_buttons), 4)
        ]
        
        # 創建 Flex Message
        flex_content = {
            "type": "bubble",
            "header": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": "選擇預約時間",
                        "weight": "bold",
                        "size": "xl",
                        "color": "#1E3A8A"
                    }
                ],
                "backgroundColor": "#E0E7FF"
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": f"日期: {display_date}",
                        "weight": "bold",
                        "margin": "md"
                    },
                    *button_rows
                ]
            },
            "footer": {
                "type": "box",
                "layout": "horizontal",
                "contents": [
                    {
                        "type": "button",
                        "style": "link",
                        "action": {
                            "type": "postback",
                            "label": "返回選擇日期",
                            "data": "action=back_to_date",
                            "displayText": "返回選擇日期"
                        },
                        "flex": 1
                    },
                    {
                        "type": "button",
                        "style": "link",
                        "action": {
                            "type": "postback",
                            "label": "取消預約",
                            "data": "action=cancel_booking",
                            "displayText": "取消預約"
                        },
                        "flex": 1,
                        "color": "#9CA3AF"
                    }
                ]
            }
        }
        
        return flex_content
    except Exception as e:
        logger.error(f"創建預約時間 Flex Message 時出錯: {e}")
        return None

def get_booking_location_flex():
    """獲取預約地點 Flex Message"""
    try:
        # 常用地點列表
        locations = [
            "台北", "新北", "桃園", "新竹", "台中", 
            "彰化", "嘉義", "台南", "高雄", "屏東"
        ]
        
        location_buttons = []
        for location in locations:
            location_buttons.append({
                "type": "button",
                "style": "secondary",
                "action": {
                    "type": "postback",
                    "label": location,
                    "data": f"action=select_location&location={location}",
                    "displayText": f"選擇地點: {location}"
                },
                "margin": "sm"
            })
        
        # 將按鈕分成2列，每列5個
        button_rows = [
            {
                "type": "box",
                "layout": "horizontal",
                "contents": location_buttons[i:i+5],
                "spacing": "sm",
                "margin": "md"
            } for i in range(0, len(location_buttons), 5)
        ]
        
        # 創建 Flex Message
        flex_content = {
            "type": "bubble",
            "header": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": "選擇起點位置",
                        "weight": "bold",
                        "size": "xl",
                        "color": "#1E3A8A"
                    }
                ],
                "backgroundColor": "#E0E7FF"
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": "請選擇起點位置，或直接輸入地址",
                        "wrap": True,
                        "margin": "md"
                    },
                    *button_rows,
                    {
                        "type": "text",
                        "text": "或直接輸入詳細地址",
                        "margin": "xl",
                        "size": "sm",
                        "color": "#6B7280"
                    }
                ]
            },
            "footer": {
                "type": "box",
                "layout": "horizontal",
                "contents": [
                    {
                        "type": "button",
                        "style": "link",
                        "action": {
                            "type": "postback",
                            "label": "返回選擇時間",
                            "data": "action=back_to_time",
                            "displayText": "返回選擇時間"
                        },
                        "flex": 1
                    },
                    {
                        "type": "button",
                        "style": "link",
                        "action": {
                            "type": "postback",
                            "label": "取消預約",
                            "data": "action=cancel_booking",
                            "displayText": "取消預約"
                        },
                        "flex": 1,
                        "color": "#9CA3AF"
                    }
                ]
            }
        }
        
        return flex_content
    except Exception as e:
        logger.error(f"創建預約地點 Flex Message 時出錯: {e}")
        return None

def get_booking_confirm_flex(booking_data):
    """獲取預約確認 Flex Message"""
    try:
        # 格式化預約日期和時間
        date_str = booking_data.get("date", "")
        time_str = booking_data.get("time", "")
        start_location = booking_data.get("start_location", "")
        via_point = booking_data.get("via_point", "")
        end_location = booking_data.get("end_location", "")
        
        # 整理日期顯示
        display_date = ""
        if date_str:
            try:
                date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
                display_date = date_obj.strftime("%Y/%m/%d")
            except ValueError:
                display_date = date_str
        
        # 創建確認內容
        contents = [
            {
                "type": "box",
                "layout": "horizontal",
                "contents": [
                    {
                        "type": "text",
                        "text": "日期",
                        "flex": 1,
                        "color": "#6B7280"
                    },
                    {
                        "type": "text",
                        "text": display_date,
                        "flex": 2
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
                        "flex": 1,
                        "color": "#6B7280"
                    },
                    {
                        "type": "text",
                        "text": time_str,
                        "flex": 2
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
                        "flex": 1,
                        "color": "#6B7280"
                    },
                    {
                        "type": "text",
                        "text": start_location,
                        "flex": 2,
                        "wrap": True
                    }
                ],
                "margin": "md"
            }
        ]
        
        # 如果有經由點，添加該項目
        if via_point:
            contents.append({
                "type": "box",
                "layout": "horizontal",
                "contents": [
                    {
                        "type": "text",
                        "text": "經由",
                        "flex": 1,
                        "color": "#6B7280"
                    },
                    {
                        "type": "text",
                        "text": via_point,
                        "flex": 2,
                        "wrap": True
                    }
                ],
                "margin": "md"
            })
        
        # 添加終點信息
        contents.append({
            "type": "box",
            "layout": "horizontal",
            "contents": [
                {
                    "type": "text",
                    "text": "終點",
                    "flex": 1,
                    "color": "#6B7280"
                },
                {
                    "type": "text",
                    "text": end_location,
                    "flex": 2,
                    "wrap": True
                }
            ],
            "margin": "md"
        })
        
        # 創建 Flex Message
        flex_content = {
            "type": "bubble",
            "header": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": "確認預約資訊",
                        "weight": "bold",
                        "size": "xl",
                        "color": "#1E3A8A"
                    }
                ],
                "backgroundColor": "#E0E7FF"
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": contents
            },
            "footer": {
                "type": "box",
                "layout": "horizontal",
                "contents": [
                    {
                        "type": "button",
                        "style": "primary",
                        "action": {
                            "type": "postback",
                            "label": "確認預約",
                            "data": "action=confirm_booking",
                            "displayText": "確認預約"
                        },
                        "flex": 2
                    },
                    {
                        "type": "button",
                        "style": "secondary",
                        "action": {
                            "type": "postback",
                            "label": "取消",
                            "data": "action=cancel_booking",
                            "displayText": "取消預約"
                        },
                        "flex": 1,
                        "margin": "sm"
                    }
                ]
            }
        }
        
        return flex_content
    except Exception as e:
        logger.error(f"創建預約確認 Flex Message 時出錯: {e}")
        return None

def get_booking_success_flex(booking_data):
    """獲取預約成功 Flex Message"""
    try:
        # 格式化預約日期和時間
        date_str = booking_data.get("date", "")
        time_str = booking_data.get("time", "")
        start_location = booking_data.get("start_location", "")
        via_point = booking_data.get("via_point", "")
        end_location = booking_data.get("end_location", "")
        booking_id = booking_data.get("booking_id", "")
        
        # 整理日期顯示
        display_date = ""
        if date_str:
            try:
                date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
                display_date = date_obj.strftime("%Y/%m/%d")
            except ValueError:
                display_date = date_str
        
        # 創建確認內容
        contents = [
            {
                "type": "text",
                "text": "您的預約已成功送出",
                "weight": "bold",
                "size": "lg",
                "margin": "md",
                "color": "#10B981"
            },
            {
                "type": "box",
                "layout": "horizontal",
                "contents": [
                    {
                        "type": "text",
                        "text": "預約編號",
                        "flex": 1,
                        "color": "#6B7280"
                    },
                    {
                        "type": "text",
                        "text": str(booking_id),
                        "flex": 2,
                        "weight": "bold"
                    }
                ],
                "margin": "lg"
            },
            {
                "type": "box",
                "layout": "horizontal",
                "contents": [
                    {
                        "type": "text",
                        "text": "日期",
                        "flex": 1,
                        "color": "#6B7280"
                    },
                    {
                        "type": "text",
                        "text": display_date,
                        "flex": 2
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
                        "flex": 1,
                        "color": "#6B7280"
                    },
                    {
                        "type": "text",
                        "text": time_str,
                        "flex": 2
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
                        "flex": 1,
                        "color": "#6B7280"
                    },
                    {
                        "type": "text",
                        "text": start_location,
                        "flex": 2,
                        "wrap": True
                    }
                ],
                "margin": "md"
            }
        ]
        
        # 如果有經由點，添加該項目
        if via_point:
            contents.append({
                "type": "box",
                "layout": "horizontal",
                "contents": [
                    {
                        "type": "text",
                        "text": "經由",
                        "flex": 1,
                        "color": "#6B7280"
                    },
                    {
                        "type": "text",
                        "text": via_point,
                        "flex": 2,
                        "wrap": True
                    }
                ],
                "margin": "md"
            })
        
        # 添加終點信息
        contents.append({
            "type": "box",
            "layout": "horizontal",
            "contents": [
                {
                    "type": "text",
                    "text": "終點",
                    "flex": 1,
                    "color": "#6B7280"
                },
                {
                    "type": "text",
                    "text": end_location,
                    "flex": 2,
                    "wrap": True
                }
            ],
            "margin": "md"
        })
        
        # 創建 Flex Message
        flex_content = {
            "type": "bubble",
            "header": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": "預約成功",
                        "weight": "bold",
                        "size": "xl",
                        "color": "#1E3A8A"
                    }
                ],
                "backgroundColor": "#E0E7FF"
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": contents
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "button",
                        "style": "primary",
                        "action": {
                            "type": "postback",
                            "label": "開始新的預約",
                            "data": "action=new_booking",
                            "displayText": "開始新的預約"
                        }
                    },
                    {
                        "type": "button",
                        "style": "link",
                        "action": {
                            "type": "postback",
                            "label": "返回主選單",
                            "data": "action=main_menu",
                            "displayText": "返回主選單"
                        },
                        "margin": "sm"
                    }
                ]
            }
        }
        
        return flex_content
    except Exception as e:
        logger.error(f"創建預約成功 Flex Message 時出錯: {e}")
        return None