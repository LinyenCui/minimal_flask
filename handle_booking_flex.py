"""
處理預約功能的Flex Message版本
"""

from datetime import datetime, date, timedelta, time
from flask import current_app
from sqlalchemy.sql import text
import traceback
from linebot.v3.messaging import FlexMessage, TextMessage, FlexContainer
import logging
import re

# 導入Flex Message模板
try:
    from booking_flex_design import (
        get_booking_start_flex,
        get_booking_time_flex,
        get_booking_location_flex,
        get_booking_confirm_flex,
        get_booking_success_flex
    )
    print("成功導入booking_flex_design模組")
except ImportError as e:
    print(f"無法導入booking_flex_design模組: {e}")
    traceback.print_exc()

# 用於存儲用戶預約狀態的字典
booking_states = {}

# 建立日誌記錄器
logger = logging.getLogger(__name__)

def handle_booking_start(user_id, category="診所"):
    """初始化預約流程"""
    try:
        print(f"初始化預約流程，用戶ID: {user_id}, 類別: {category}")
        
        # 初始化預約狀態
        booking_states[user_id] = {
            "state": "waiting_for_date",
            "category": category
        }
        
        print(f"已設置用戶 {user_id} 的預約狀態: {booking_states[user_id]}")
        print(f"嘗試導入的 Flex 模塊是否存在: {globals().get('get_booking_start_flex', 'Not found')}")
        print(f"本地定義的 get_booking_start_flex 是: {get_booking_start_flex}")
        
        # 返回日期選擇界面
        try:
            print("使用Flex Message模板生成日期選擇界面")
            try:
                flex_content = get_booking_start_flex()
                print(f"Flex內容類型: {type(flex_content)}")
                
                if not isinstance(flex_content, dict):
                    print(f"警告: Flex內容不是字典類型，而是 {type(flex_content)}")
                    raise ValueError("Flex內容格式無效")
                
                container = FlexContainer.from_dict(flex_content)
                print("成功創建FlexContainer")
                
                flex_message = FlexMessage(
                    alt_text="請選擇預約日期",
                    contents=container
                )
                print("成功創建FlexMessage")
                
                return flex_message
            except Exception as flex_error:
                print(f"創建Flex消息時出錯: {flex_error}")
                traceback.print_exc()
                # 使用簡單的文本消息作為備用方案
                print("回退到文本消息")
                return TextMessage(text="請輸入預約日期 (YYYY-MM-DD 格式)，或輸入「今天」、「明天」、「後天」。")
        except Exception as e:
            print(f"創建日期選擇界面時出錯: {e}")
            traceback.print_exc()
            # 使用簡單的文本消息作為備用方案
            return TextMessage(text="請輸入預約日期 (YYYY-MM-DD 格式)，或輸入「今天」、「明天」、「後天」。")
    except Exception as e:
        # 出錯時清除用戶狀態
        if user_id in booking_states:
            del booking_states[user_id]
            print(f"已清除用戶 {user_id} 的預約狀態")
        print(f"初始化預約流程時出錯: {e}")
        traceback.print_exc()
        return TextMessage(text="預約系統暫時無法使用，請稍後重試")

def handle_booking_message(user_id, message_text, booking_states):
    """處理預約流程中的消息"""
    try:
        print(f"處理預約消息: 用戶ID={user_id}, 消息='{message_text}'")
        
        # 檢查取消命令 - 優先處理取消命令，無論用戶是否在預約流程中
        if message_text.lower() in ["取消", "取消預約", "cancel", "退出", "exit", "!取消", "!取消預約", "!cancel", "!退出", "!exit"]:
            print(f"收到取消預約命令: {message_text}")
            # 清除預約狀態
            if user_id in booking_states:
                print(f"清除用戶 {user_id} 的預約狀態")
                del booking_states[user_id]
            
            return TextMessage(text="已取消當前預約流程。")
        
        # 去除可能的前綴
        original_message = message_text
        if message_text.startswith("!") or message_text.startswith("#") or message_text.startswith("/"):
            message_text = message_text[1:].strip()
            print(f"去除前綴後的消息: {message_text}")
        
        # 檢查用戶是否在預約流程中
        if user_id not in booking_states:
            # 檢查是否是預約命令
            if message_text.strip() == "預約":
                print(f"用戶 {user_id} 發送了預約命令，初始化新的預約狀態")
                # 使用handle_booking_start函數初始化預約流程
                return handle_booking_start(user_id, "診所")
            elif message_text.strip() == "東洋預約":
                print(f"用戶 {user_id} 發送了東洋預約命令，初始化新的預約狀態")
                # 使用handle_booking_start函數初始化預約流程
                return handle_booking_start(user_id, "東洋")
            else:
                print(f"用戶 {user_id} 不在預約流程中，且消息不是預約命令: {message_text}")
                return None
        
        # 根據當前狀態處理消息
        current_state = booking_states[user_id]["state"]
        print(f"用戶 {user_id} 當前狀態: {current_state}, 消息: {message_text}")
        
        try:
            if current_state == "waiting_for_date":
                print(f"處理日期輸入: {message_text}")
                return handle_date_input(user_id, message_text, booking_states)
            elif current_state == "waiting_for_time":
                print(f"處理時間輸入: {message_text}")
                return handle_time_input(user_id, message_text, booking_states)
            elif current_state == "waiting_for_location":
                print(f"處理地點輸入: {message_text}")
                return handle_location_input(user_id, message_text, booking_states)
            elif current_state == "waiting_for_via_point":
                print(f"處理經過點輸入: {message_text}")
                return handle_via_point_input(user_id, message_text, booking_states)
            elif current_state == "waiting_for_end_point":
                print(f"處理終點輸入: {message_text}")
                return handle_end_point_input(user_id, message_text, booking_states)
            elif current_state == "waiting_for_confirm":
                print(f"處理確認輸入: {message_text}")
                return handle_confirm_input(user_id, message_text, booking_states)
            else:
                # 未知狀態，重置預約流程
                print(f"未知狀態: {current_state}，重置預約流程")
                booking_states[user_id] = {
                    "state": "waiting_for_date",
                    "category": "診所"
                }
                return TextMessage(text="預約流程出錯，已重置。\n請輸入預約日期:\n- YYYY-MM-DD (例如: 2025-03-15)\n- MM/DD (例如: 3/15)\n- 今天、明天、後天")
        except Exception as state_error:
            # 處理特定狀態下的錯誤
            print(f"處理狀態 '{current_state}' 時出錯: {state_error}")
            traceback.print_exc()
            # 清除預約狀態，避免卡在錯誤狀態
            if user_id in booking_states:
                del booking_states[user_id]
                print(f"已清除用戶 {user_id} 的預約狀態")
            return TextMessage(text=f"處理預約時出錯: {str(state_error)}\n請重新開始預約流程。")
    except Exception as e:
        # 出錯時清除用戶狀態
        if user_id in booking_states:
            del booking_states[user_id]
            print(f"已清除用戶 {user_id} 的預約狀態")
        print(f"處理預約消息時出錯: {e}")
        traceback.print_exc()
        return TextMessage(text=f"處理預約時出錯: {str(e)}\n請重新開始預約流程。")

def handle_date_input(user_id, message_text, booking_states):
    """處理日期輸入"""
    try:
        print(f"處理日期輸入: {message_text}")
        
        # 去除可能的前綴
        if message_text.startswith("!") or message_text.startswith("#") or message_text.startswith("/"):
            message_text = message_text[1:].strip()
            print(f"去除前綴後的日期輸入: {message_text}")
        
        # 解析日期
        selected_date = None
        
        # 檢查是否是特殊日期關鍵字
        if message_text.lower() in ["今天", "today"]:
            selected_date = datetime.now().date()
        elif message_text.lower() in ["明天", "tomorrow"]:
            selected_date = datetime.now().date() + timedelta(days=1)
        elif message_text.lower() in ["後天", "day after tomorrow"]:
            selected_date = datetime.now().date() + timedelta(days=2)
        else:
            # 嘗試解析日期格式
            try:
                # 嘗試解析YYYY-MM-DD格式
                selected_date = datetime.strptime(message_text, "%Y-%m-%d").date()
            except ValueError:
                try:
                    # 嘗試解析MM/DD格式
                    current_year = datetime.now().year
                    date_parts = message_text.split("/")
                    if len(date_parts) == 2:
                        month = int(date_parts[0])
                        day = int(date_parts[1])
                        selected_date = date(current_year, month, day)
                except (ValueError, IndexError):
                    # 無法解析日期
                    return TextMessage(text="無法識別日期格式，請使用以下格式之一:\n- YYYY-MM-DD (例如: 2025-03-15)\n- MM/DD (例如: 3/15)\n- 今天、明天、後天")
        
        if selected_date:
            # 验证日期是否在过去
            current_date = datetime.now().date()
            if selected_date < current_date:
                return TextMessage(text="不能預約過去的日期，請選擇今天或之後的日期。")
                
            # 更新預約狀態
            booking_states[user_id]["date"] = selected_date
            booking_states[user_id]["state"] = "waiting_for_time"
            
            print(f"已設置預約日期: {selected_date}")
            
            # 返回時間選擇界面
            try:
                print("使用Flex Message模板生成時間選擇界面")
                try:
                    flex_content = get_booking_time_flex(booking_states[user_id]["date"])
                    print(f"生成的Flex內容類型: {type(flex_content)}")
                    
                    if not isinstance(flex_content, dict):
                        print(f"警告: Flex內容不是字典類型，而是 {type(flex_content)}")
                        raise ValueError("Flex內容格式無效")
                    
                    container = FlexContainer.from_dict(flex_content)
                    print("成功創建FlexContainer")
                    
                    flex_message = FlexMessage(
                        alt_text="請選擇預約時間",
                        contents=container
                    )
                    print("成功創建FlexMessage")
                    
                    return flex_message
                except Exception as flex_error:
                    print(f"創建Flex消息時出錯: {flex_error}")
                    traceback.print_exc()
                    # 使用簡單的文本消息作為備用方案
                    print("回退到文本消息")
                    weekday = ["一", "二", "三", "四", "五", "六", "日"][selected_date.weekday()]
                    date_display = f"{selected_date.month}/{selected_date.day} (週{weekday})"
                    return TextMessage(text=f"已選擇日期: {date_display}\n\n請輸入預約時間 (格式: HH:MM 或 HHMM)\n\n常用時間:\n上午: 08:00, 08:30, 09:00, 09:30, 10:00, 10:30, 11:00, 11:30\n下午: 13:00, 13:30, 14:00, 14:30, 15:00, 15:30, 16:00, 16:30")
            except Exception as e:
                print(f"創建時間選擇界面時出錯: {e}")
                traceback.print_exc()
                # 使用簡單的文本消息作為備用方案
                weekday = ["一", "二", "三", "四", "五", "六", "日"][selected_date.weekday()]
                date_display = f"{selected_date.month}/{selected_date.day} (週{weekday})"
                return TextMessage(text=f"已選擇日期: {date_display}\n\n請輸入預約時間 (格式: HH:MM 或 HHMM)\n\n常用時間:\n上午: 08:00, 08:30, 09:00, 09:30, 10:00, 10:30, 11:00, 11:30\n下午: 13:00, 13:30, 14:00, 14:30, 15:00, 15:30, 16:00, 16:30")
    except Exception as e:
        # 出錯時清除用戶狀態
        if user_id in booking_states:
            del booking_states[user_id]
        print(f"處理日期輸入時出錯: {e}")
        traceback.print_exc()
        return TextMessage(text=f"處理日期時出錯: {str(e)}\n請重新開始預約流程。")

def handle_time_input(user_id, message_text, booking_states):
    """處理預約時間輸入"""
    try:
        print(f"處理時間輸入: {message_text}")
        
        # 去除可能的前綴
        if message_text.startswith("!") or message_text.startswith("#") or message_text.startswith("/"):
            message_text = message_text[1:].strip()
            print(f"去除前綴後的時間輸入: {message_text}")
            
        # 解析時間格式
        time_pattern = r'^([01]?[0-9]|2[0-3]):?([0-5][0-9])$'
        match = re.match(time_pattern, message_text)
        
        if not match:
            return TextMessage(text="時間格式不正確，請使用24小時制格式 (HH:MM 或 HHMM)，例如 14:30 或 1430")
        
        # 整理時間格式
        hour = int(match.group(1))
        minute = int(match.group(2))
        selected_time = f"{hour:02d}:{minute:02d}"
        
        # 檢查時間是否已過
        now = datetime.now()
        selected_datetime = None
        
        if user_id in booking_states and "date" in booking_states[user_id]:
            date_obj = booking_states[user_id]["date"]
            if isinstance(date_obj, str):
                date_obj = datetime.strptime(date_obj, "%Y-%m-%d").date()
            
            selected_datetime = datetime.combine(date_obj, time(hour, minute))
            
            if date_obj == now.date() and selected_datetime < now:
                return TextMessage(text=f"不能預約過去的時間。現在是 {now.strftime('%H:%M')}，請選擇之後的時間。")
        
        # 更新預約狀態
        booking_states[user_id]["time"] = selected_time
        booking_states[user_id]["state"] = "waiting_for_location"
        
        print(f"已設置預約時間: {selected_time}")
        
        # 返回上車地點選擇界面
        try:
            selected_date = booking_states[user_id]["date"]
            if isinstance(selected_date, date):
                selected_date = selected_date.strftime("%Y-%m-%d")
            
            flex_content = get_booking_location_flex(selected_date, selected_time)
            print(f"Flex內容類型: {type(flex_content)}")
            
            if not isinstance(flex_content, dict):
                print(f"警告: Flex內容不是字典類型，而是 {type(flex_content)}")
                raise ValueError("Flex內容格式無效")
            
            container = FlexContainer.from_dict(flex_content)
            print("成功創建FlexContainer")
            
            flex_message = FlexMessage(
                alt_text="請輸入上車地點",
                contents=container
            )
            print("成功創建FlexMessage")
            
            return flex_message
        except Exception as flex_error:
            print(f"創建Flex消息時出錯: {flex_error}")
            traceback.print_exc()
            # 使用簡單的文本消息作為備用方案
            print("回退到文本消息")
            return TextMessage(text="請輸入上車地點:")
    except Exception as e:
        # 出錯時清除用戶狀態
        if user_id in booking_states:
            del booking_states[user_id]
            print(f"已清除用戶 {user_id} 的預約狀態")
        print(f"處理時間輸入時出錯: {e}")
        traceback.print_exc()
        return TextMessage(text=f"處理時間時出錯: {str(e)}\n請重新開始預約流程。")

def handle_location_input(user_id, message_text, booking_states):
    """處理上車地點輸入"""
    try:
        print(f"處理上車地點輸入: {message_text}")
        
        # 去除可能的前綴
        if message_text.startswith("!") or message_text.startswith("#") or message_text.startswith("/"):
            message_text = message_text[1:].strip()
            print(f"去除前綴後的地點輸入: {message_text}")
        
        # 更新預約狀態
        booking_states[user_id]["start_point"] = message_text
        booking_states[user_id]["state"] = "waiting_for_via_point"
        
        # 返回文字訊息，詢問經過點
        via_point_text = f"已設置上車地點: {message_text}\n\n請輸入經過點 (若無需經過點，請輸入「無」或「-」)"
        print(f"返回經過點提示: {via_point_text}")
        return TextMessage(text=via_point_text)
    except Exception as e:
        # 出錯時清除用戶狀態
        if user_id in booking_states:
            del booking_states[user_id]
            print(f"已清除用戶 {user_id} 的預約狀態")
        print(f"處理上車地點輸入時出錯: {e}")
        traceback.print_exc()
        return TextMessage(text="處理上車地點時出錯，請重新開始預約流程。")

def handle_via_point_input(user_id, message_text, booking_states):
    """處理經過點輸入"""
    try:
        print(f"處理經過點輸入: {message_text}")
        
        # 去除可能的前綴
        if message_text.startswith("!") or message_text.startswith("#") or message_text.startswith("/"):
            message_text = message_text[1:].strip()
            print(f"去除前綴後的經過點輸入: {message_text}")
            
        # 處理無經過點的情況
        if message_text.lower() in ["無", "-", "none", "n/a", "na"]:
            message_text = "無"
        
        # 更新預約狀態
        booking_states[user_id]["via_point"] = message_text
        booking_states[user_id]["state"] = "waiting_for_end_point"
        
        # 返回文字訊息，詢問終點
        end_point_text = f"已設置經過點: {message_text}\n\n請輸入終點地點:"
        print(f"返回終點提示: {end_point_text}")
        return TextMessage(text=end_point_text)
    except Exception as e:
        # 出錯時清除用戶狀態
        if user_id in booking_states:
            del booking_states[user_id]
            print(f"已清除用戶 {user_id} 的預約狀態")
        print(f"處理經過點輸入時出錯: {e}")
        traceback.print_exc()
        return TextMessage(text="處理經過點時出錯，請重新開始預約流程。")

def handle_end_point_input(user_id, message_text, booking_states):
    """處理終點輸入"""
    try:
        print(f"處理終點輸入: {message_text}")
        
        # 去除可能的前綴
        if message_text.startswith("!") or message_text.startswith("#") or message_text.startswith("/"):
            message_text = message_text[1:].strip()
            print(f"去除前綴後的終點輸入: {message_text}")
            
        # 更新預約狀態
        booking_states[user_id]["end_point"] = message_text
        booking_states[user_id]["state"] = "waiting_for_confirm"
        
        # 準備預約數據
        booking_data = {
            "date": booking_states[user_id]["date"],
            "time": booking_states[user_id]["time"],
            "start_point": booking_states[user_id]["start_point"],
            "via_point": booking_states[user_id].get("via_point", "無"),
            "end_point": message_text,
            "category": booking_states[user_id].get("category", "診所")
        }
        
        print(f"預約數據: {booking_data}")
        
        # 返回確認界面
        try:
            print("使用Flex Message模板生成確認界面")
            try:
                flex_content = get_booking_confirm_flex(booking_data)
                print(f"生成的Flex內容類型: {type(flex_content)}")
                
                if not isinstance(flex_content, dict):
                    print(f"警告: Flex內容不是字典類型，而是 {type(flex_content)}")
                    raise ValueError("Flex內容格式無效")
                
                container = FlexContainer.from_dict(flex_content)
                print("成功創建FlexContainer")
                
                flex_message = FlexMessage(
                    alt_text="確認預約資訊",
                    contents=container
                )
                print("成功創建FlexMessage")
                
                return flex_message
            except Exception as flex_error:
                print(f"創建Flex消息時出錯: {flex_error}")
                traceback.print_exc()
                # 使用簡單的文本消息作為備用方案
                print("回退到文本消息")
                date_obj = datetime.strptime(booking_data["date"], "%Y-%m-%d").date()
                weekday = ["一", "二", "三", "四", "五", "六", "日"][date_obj.weekday()]
                date_display = f"{date_obj.month}/{date_obj.day} (週{weekday})"
                
                confirm_text = (
                    "請確認您的預約信息:\n\n"
                    f"日期: {date_display}\n"
                    f"時間: {booking_data['time']}\n"
                    f"上車地點: {booking_data['start_point']}\n"
                    f"經過點: {booking_data['via_point']}\n"
                    f"終點: {booking_data['end_point']}\n"
                    f"類別: {booking_data['category']}\n\n"
                    "回覆「確認」完成預約，或「取消」放棄預約。"
                )
                
                return TextMessage(text=confirm_text)
        except Exception as e:
            print(f"創建確認界面時出錯: {e}")
            traceback.print_exc()
            # 使用簡單的文本消息作為備用方案
            date_obj = datetime.strptime(booking_data["date"], "%Y-%m-%d").date()
            weekday = ["一", "二", "三", "四", "五", "六", "日"][date_obj.weekday()]
            date_display = f"{date_obj.month}/{date_obj.day} (週{weekday})"
            
            confirm_text = (
                "請確認您的預約信息:\n\n"
                f"日期: {date_display}\n"
                f"時間: {booking_data['time']}\n"
                f"上車地點: {booking_data['start_point']}\n"
                f"經過點: {booking_data['via_point']}\n"
                f"終點: {booking_data['end_point']}\n"
                f"類別: {booking_data['category']}\n\n"
                "回覆「確認」完成預約，或「取消」放棄預約。"
            )
            
            return TextMessage(text=confirm_text)
    except Exception as e:
        # 出錯時清除用戶狀態
        if user_id in booking_states:
            del booking_states[user_id]
        print(f"處理終點輸入時出錯: {e}")
        traceback.print_exc()
        return TextMessage(text="處理終點地點時出錯，請重新開始預約流程。")

def handle_confirm_input(user_id, message_text, booking_states):
    """處理確認輸入"""
    try:
        print(f"處理確認輸入: {message_text}")
        
        # 去除可能的前綴
        if message_text.startswith("!") or message_text.startswith("#") or message_text.startswith("/"):
            message_text = message_text[1:].strip()
            print(f"去除前綴後的確認輸入: {message_text}")
        
        # 檢查是否確認預約
        if message_text.lower() in ["確認預約", "確認", "yes", "y", "ok"]:
            print("用戶確認預約")
            # 獲取預約數據
            booking_data = {
                "date": booking_states[user_id]["date"],
                "time": booking_states[user_id]["time"],
                "start_point": booking_states[user_id]["start_point"],
                "via_point": booking_states[user_id]["via_point"],
                "end_point": booking_states[user_id]["end_point"],
                "category": booking_states[user_id]["category"]
            }
            
            # 將預約數據保存到數據庫
            try:
                # 獲取數據庫連接
                from app import get_db_connection
                conn = get_db_connection()
                
                # 格式化日期和時間
                if isinstance(booking_data["date"], date):
                    date_str = booking_data["date"].strftime("%Y-%m-%d")
                else:
                    date_str = booking_data["date"]
                
                # 插入預約記錄
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO trips (date, time, start_point, via_point, end_point, status, category, trip_type)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING trip_id
                    """,
                    (
                        date_str,
                        booking_data["time"],
                        booking_data["start_point"],
                        booking_data["via_point"],
                        booking_data["end_point"],
                        "待派",
                        booking_data["category"],
                        "temp"
                    )
                )
                
                # 獲取新插入記錄的ID
                trip_id = cursor.fetchone()[0]
                conn.commit()
                cursor.close()
                conn.close()
                
                print(f"成功保存預約，ID: {trip_id}")
                
                # 清除預約狀態
                del booking_states[user_id]
                print(f"已清除用戶 {user_id} 的預約狀態")
                
                # 返回成功消息
                try:
                    print("使用Flex Message模板生成成功界面")
                    try:
                        flex_content = get_booking_success_flex(booking_data, trip_id)
                        print(f"Flex內容類型: {type(flex_content)}")
                        
                        if not isinstance(flex_content, dict):
                            print(f"警告: Flex內容不是字典類型，而是 {type(flex_content)}")
                            raise ValueError("Flex內容格式無效")
                        
                        container = FlexContainer.from_dict(flex_content)
                        print("成功創建FlexContainer")
                        
                        flex_message = FlexMessage(
                            alt_text="預約成功",
                            contents=container
                        )
                        print("成功創建FlexMessage")
                        
                        return flex_message
                    except Exception as flex_error:
                        print(f"創建Flex消息時出錯: {flex_error}")
                        traceback.print_exc()
                        # 使用簡單的文本消息作為備用方案
                        print("回退到文本消息")
                        return TextMessage(text=f"預約成功！您的班次ID是: {trip_id}\n\n日期: {date_str}\n時間: {booking_data['time']}\n上車地點: {booking_data['start_point']}\n經過點: {booking_data['via_point']}\n終點: {booking_data['end_point']}\n\n我們會盡快確認您的預約。")
                except Exception as e:
                    print(f"創建成功消息時出錯: {e}")
                    traceback.print_exc()
                    # 使用簡單的文本消息作為備用方案
                    return TextMessage(text=f"預約成功！您的班次ID是: {trip_id}\n\n我們會盡快確認您的預約。")
            except Exception as db_error:
                print(f"保存預約到數據庫時出錯: {db_error}")
                traceback.print_exc()
                return TextMessage(text=f"保存預約時出錯: {str(db_error)}\n請稍後重試。")
        # 檢查是否取消預約
        elif message_text.lower() in ["取消預約", "取消", "no", "n", "cancel"]:
            print("用戶取消預約")
            # 清除預約狀態
            del booking_states[user_id]
            print(f"已清除用戶 {user_id} 的預約狀態")
            
            # 返回取消消息
            return TextMessage(text="已取消預約。")
        else:
            # 未知命令
            return TextMessage(text="請回覆「確認預約」或「取消預約」。")
    except Exception as e:
        # 出錯時清除用戶狀態
        if user_id in booking_states:
            del booking_states[user_id]
            print(f"已清除用戶 {user_id} 的預約狀態")
        print(f"處理確認輸入時出錯: {e}")
        traceback.print_exc()
        return TextMessage(text=f"處理確認時出錯: {str(e)}\n請重新開始預約流程。")

def handle_booking_help():
    """提供預約相關幫助信息"""
    
    help_text = (
        "📝 預約相關指令：\n\n"
        "• 預約 - 開始診所預約流程\n"
        "• 東洋預約 - 開始東洋預約流程\n"
        "• 取消預約 (或 !取消預約) - 取消進行中的預約流程\n\n"
        "📋 預約流程：\n"
        "1. 選擇日期 (YYYY-MM-DD 或 今天/明天/後天)\n"
        "2. 選擇時間 (HH:MM)\n"
        "3. 輸入起點位置\n"
        "4. 輸入經過點 (可選)\n"
        "5. 輸入終點位置\n"
        "6. 確認預約\n\n"
        "⚠️ 注意事項：\n"
        "• 不能預約過去的日期和時間\n"
        "• 在群聊中使用時，請加上前綴 ! 或 # 或 /\n"
        "• 預約保存後會獲得唯一的班次ID\n"
        "• 班次狀態初始為「待派」"
    )
    
    return TextMessage(text=help_text)

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
