"""
處理臨時預約功能的模組，用於處理客戶臨時需求的班次預約
"""
from datetime import datetime, date, timedelta
from flask import current_app
from sqlalchemy import text as sql_text
import logging
import traceback
import re

from modules.models.base import db
from modules.utils.taiwan_time import get_taiwan_time, get_taiwan_date
from modules.utils.helpers import parse_date_input
from modules.flex_designs.temp_booking_flex import (
    get_temp_booking_start_flex, 
    get_temp_booking_time_flex, 
    get_temp_booking_location_flex,
    get_temp_booking_destination_flex,
    get_temp_booking_confirm_flex
)

# 用於存儲臨時預約過程中的用戶狀態
temp_booking_states = {}

# 設置日誌
logger = logging.getLogger(__name__)

def handle_temp_booking_start(user_id, category="臨時"):
    """初始化臨時預約流程"""
    try:
        logger.info(f"初始化臨時預約流程，用戶ID: {user_id}, 類別: {category}")
        
        # 初始化預約狀態
        temp_booking_states[user_id] = {
            "state": "waiting_for_date",
            "data": {
                "category": category
            }
        }
        
        logger.info(f"已設置用戶 {user_id} 的臨時預約狀態: {temp_booking_states[user_id]}")
        
        # 返回日期選擇界面
        try:
            # 使用當前台灣時間作為參考
            current_date = get_taiwan_date()
            flex_content, quick_reply = get_temp_booking_start_flex(current_date)
            
            # 創建包含Flex內容和Quick Reply的回覆
            return {
                "type": "flex",
                "alt_text": "請選擇預約日期",
                "contents": flex_content,
                "quick_reply": quick_reply  # 添加QuickReply
            }
        except Exception as e:
            logger.error(f"創建日期選擇界面時出錯: {e}")
            traceback.print_exc()
            # 使用簡單的文本消息作為備用方案
            return {
                "type": "text",
                "text": "請輸入預約日期 (YYYY-MM-DD 格式)，或輸入「今天」、「明天」、「後天」。"
            }
    except Exception as e:
        # 出錯時清除用戶狀態
        if user_id in temp_booking_states:
            del temp_booking_states[user_id]
            logger.info(f"已清除用戶 {user_id} 的預約狀態")
        logger.error(f"初始化臨時預約流程時出錯: {e}")
        traceback.print_exc()
        return {
            "type": "text",
            "text": "臨時預約系統暫時無法使用，請稍後重試"
        }

def handle_temp_booking_message(user_id, message_text):
    """處理臨時預約流程中的消息"""
    try:
        logger.info(f"處理臨時預約消息: 用戶ID={user_id}, 消息='{message_text}'")
        
        # 檢查取消命令 - 優先處理取消命令，無論用戶是否在預約流程中
        if message_text.lower() in ["取消", "取消預約", "cancel", "退出", "exit", "!取消", "!取消預約", "!cancel", "!退出", "!exit"]:
            logger.info(f"收到取消預約命令: {message_text}")
            # 清除預約狀態
            if user_id in temp_booking_states:
                logger.info(f"清除用戶 {user_id} 的預約狀態")
                del temp_booking_states[user_id]
            
            return {
                "type": "text",
                "text": "已取消臨時預約流程"
            }
        
        # 檢查用戶是否在預約流程中
        if user_id not in temp_booking_states:
            logger.info(f"用戶 {user_id} 不在臨時預約流程中")
            # 如果用戶不在預約流程中，直接返回
            return None
        
        # 獲取用戶當前狀態
        current_state = temp_booking_states[user_id]["state"]
        logger.info(f"用戶 {user_id} 當前狀態: {current_state}")
        
        # 根據用戶狀態處理輸入
        if current_state == "waiting_for_date":
            return handle_date_input(user_id, message_text)
        
        elif current_state == "waiting_for_time":
            return handle_time_input(user_id, message_text)
        
        elif current_state == "waiting_for_location":
            return handle_location_input(user_id, message_text)
            
        elif current_state == "waiting_for_destination":
            return handle_destination_input(user_id, message_text)
        
        elif current_state == "waiting_for_confirm":
            return handle_confirm_input(user_id, message_text)
        
        else:
            logger.warning(f"未知的用戶狀態: {current_state}")
            # 狀態無效，清除並重新開始
            del temp_booking_states[user_id]
            return {
                "type": "text",
                "text": "對不起，臨時預約流程出現錯誤。請重新開始預約。"
            }
    
    except Exception as e:
        logger.error(f"處理臨時預約消息時出錯: {e}")
        traceback.print_exc()
        # 出錯時清除用戶狀態
        if user_id in temp_booking_states:
            del temp_booking_states[user_id]
        return {
            "type": "text",
            "text": "臨時預約處理過程中出現錯誤，請重新開始預約。"
        }

def handle_date_input(user_id, message_text):
    """處理用戶輸入的日期"""
    try:
        # 解析日期輸入
        selected_date = None
        today = get_taiwan_date()
        
        # 處理特殊日期輸入
        if message_text == "今天":
            selected_date = today
        elif message_text == "明天":
            selected_date = today + timedelta(days=1)
        elif message_text == "後天":
            selected_date = today + timedelta(days=2)
        else:
            # 嘗試解析標準日期格式
            try:
                selected_date = parse_date_input(message_text)
            except ValueError:
                return {
                    "type": "text",
                    "text": "日期格式無效。請使用YYYY-MM-DD格式（如2025-03-20），或輸入「今天」、「明天」、「後天」。"
                }
        
        # 檢查日期是否有效（不能是過去的日期）
        if selected_date < today:
            return {
                "type": "text",
                "text": "無法預約過去的日期。請選擇今天或未來的日期。"
            }
        
        # 更新用戶狀態
        temp_booking_states[user_id]["data"]["date"] = selected_date
        temp_booking_states[user_id]["state"] = "waiting_for_time"
        
        logger.info(f"用戶 {user_id} 選擇了日期: {selected_date}, 狀態更新為: {temp_booking_states[user_id]}")
        
        # 返回時間選擇界面
        try:
            flex_content, quick_reply = get_temp_booking_time_flex(selected_date)
            
            # 創建包含Flex內容和Quick Reply的回覆
            return {
                "type": "flex",
                "alt_text": "請選擇預約時間",
                "contents": flex_content,
                "quick_reply": quick_reply  # 添加QuickReply
            }
        except Exception as e:
            logger.error(f"創建時間選擇界面時出錯: {e}")
            # 使用簡單的文本消息作為備用方案
            return {
                "type": "text",
                "text": "請輸入預約時間 (HH:MM 格式)，例如 09:17、14:30 等。"
            }
    
    except Exception as e:
        logger.error(f"處理日期輸入時出錯: {e}")
        # 重置狀態
        temp_booking_states[user_id]["state"] = "waiting_for_date"
        return {
            "type": "text",
            "text": "處理日期時出錯。請重新輸入預約日期。"
        }

def handle_time_input(user_id, message_text):
    """處理用戶輸入的時間"""
    try:
        # 檢查時間格式是否有效 (HH:MM)
        time_pattern = r"^([01]?[0-9]|2[0-3]):([0-5][0-9])$"
        if not re.match(time_pattern, message_text):
            # 嘗試轉換其他格式（如HHMM）
            if re.match(r'^\d{3,4}$', message_text):
                if len(message_text) == 3:
                    message_text = message_text[0] + ":" + message_text[1:3]
                else:
                    message_text = message_text[0:2] + ":" + message_text[2:4]
            else:
                return {
                    "type": "text",
                    "text": "時間格式無效。請使用HH:MM格式（如09:17或14:30）或HHMM格式（如0917）。"
                }
        
        # 解析時間
        try:
            time_obj = datetime.strptime(message_text, "%H:%M").time()
        except ValueError:
            return {
                "type": "text",
                "text": "無法解析時間。請使用HH:MM格式（如09:17或14:30）。"
            }
        
        # 檢查時間是否是過去的時間
        selected_date = temp_booking_states[user_id]["data"]["date"]
        now = get_taiwan_time()
        
        if selected_date == now.date() and time_obj < now.time():
            return {
                "type": "text",
                "text": "無法預約過去的時間。請選擇未來的時間。"
            }
        
        # 更新用戶狀態
        temp_booking_states[user_id]["data"]["time"] = time_obj
        temp_booking_states[user_id]["state"] = "waiting_for_location"
        
        logger.info(f"用戶 {user_id} 選擇了時間: {time_obj}, 狀態更新為: {temp_booking_states[user_id]}")
        
        # 返回地點選擇界面
        try:
            flex_content, quick_reply = get_temp_booking_location_flex()
            
            # 創建包含Flex內容和Quick Reply的回覆
            return {
                "type": "flex",
                "alt_text": "請選擇起點位置",
                "contents": flex_content,
                "quick_reply": quick_reply
            }
        except Exception as e:
            logger.error(f"創建地點選擇界面時出錯: {e}")
            # 使用簡單的文本消息作為備用方案
            return {
                "type": "text",
                "text": "請輸入起點位置（完整地址或地標名稱）："
            }
    
    except Exception as e:
        logger.error(f"處理時間輸入時出錯: {e}")
        # 重置狀態
        temp_booking_states[user_id]["state"] = "waiting_for_time"
        return {
            "type": "text",
            "text": "處理時間時出錯。請重新輸入預約時間。"
        }

def handle_location_input(user_id, message_text):
    """處理用戶輸入的起點位置"""
    try:
        # 檢查位置是否有效
        if not message_text.strip():
            return {
                "type": "text",
                "text": "位置不能為空，請輸入起點位置："
            }
        
        # 更新用戶狀態
        temp_booking_states[user_id]["data"]["start_point"] = message_text.strip()
        # 更新狀態為等待目的地輸入
        temp_booking_states[user_id]["state"] = "waiting_for_destination"
        
        logger.info(f"用戶 {user_id} 輸入了起點位置: {message_text.strip()}, 狀態更新為: {temp_booking_states[user_id]}")
        
        # 返回目的地選擇界面
        try:
            flex_content, quick_reply = get_temp_booking_destination_flex()
            
            # 創建包含Flex內容和Quick Reply的回覆
            return {
                "type": "flex",
                "alt_text": "請選擇目的地位置",
                "contents": flex_content,
                "quick_reply": quick_reply
            }
        except Exception as e:
            logger.error(f"創建目的地選擇界面時出錯: {e}")
            # 使用簡單的文本消息作為備用方案
            return {
                "type": "text",
                "text": "請輸入目的地位置（完整地址或地標名稱），或輸入「無(略過)」跳過："
            }
    
    except Exception as e:
        logger.error(f"處理起點位置輸入時出錯: {e}")
        # 重置狀態
        temp_booking_states[user_id]["state"] = "waiting_for_location"
        return {
            "type": "text",
            "text": "處理起點位置時出錯。請重新輸入起點位置。"
        }

def handle_destination_input(user_id, message_text):
    """處理用戶輸入的目的地位置"""
    try:
        # 檢查位置是否有效，但允許"無(略過)"
        if not message_text.strip():
            return {
                "type": "text",
                "text": "位置不能為空，請輸入目的地位置或輸入「無(略過)」跳過："
            }
        
        # 更新用戶狀態
        temp_booking_states[user_id]["data"]["end_point"] = message_text.strip()
        # 更新狀態為等待確認
        temp_booking_states[user_id]["state"] = "waiting_for_confirm"
        
        logger.info(f"用戶 {user_id} 輸入了目的地位置: {message_text.strip()}, 狀態更新為: {temp_booking_states[user_id]}")
        
        # 生成確認信息
        booking_data = temp_booking_states[user_id]["data"]
        selected_date = booking_data["date"]
        time_obj = booking_data["time"]
        
        # 格式化日期和時間
        formatted_date = selected_date.strftime("%Y-%m-%d")
        formatted_time = time_obj.strftime("%H:%M")
        
        # 創建預約確認界面
        try:
            # 根據用戶是否提供了目的地決定參數
            end_point = booking_data.get("end_point", None)
            
            flex_content, quick_reply = get_temp_booking_confirm_flex(
                formatted_date,
                formatted_time,
                booking_data["start_point"],
                end_point,
                booking_data["category"]
            )
            
            # 創建包含Flex內容和Quick Reply的回覆
            return {
                "type": "flex",
                "alt_text": "請確認臨時預約信息",
                "contents": flex_content,
                "quick_reply": quick_reply
            }
        except Exception as e:
            logger.error(f"創建確認界面時出錯: {e}")
            # 使用簡單的文本消息作為備用方案
            confirm_text = (
                "請確認臨時預約信息：\n\n"
                f"日期：{formatted_date}\n"
                f"時間：{formatted_time}\n"
                f"起點：{booking_data['start_point']}\n"
            )
            
            # 如果有提供目的地且不是"無(略過)"，則顯示
            if booking_data.get("end_point") and booking_data.get("end_point") != "無(略過)":
                confirm_text += f"目的地：{booking_data['end_point']}\n"
                
            confirm_text += (
                f"類別：{booking_data['category']}\n\n"
                "確認預約請回覆「確認」，取消請回覆「取消」："
            )
            
            return {
                "type": "text",
                "text": confirm_text
            }
    
    except Exception as e:
        logger.error(f"處理目的地位置輸入時出錯: {e}")
        # 重置狀態
        temp_booking_states[user_id]["state"] = "waiting_for_destination"
        return {
            "type": "text",
            "text": "處理目的地位置時出錯。請重新輸入目的地位置。"
        }

def handle_confirm_input(user_id, message_text):
    """處理用戶確認臨時預約"""
    try:
        # 檢查是否確認預約
        if message_text.lower() not in ["確認", "confirm", "yes", "是", "確定", "ok"]:
            # 用戶沒有確認，取消預約
            del temp_booking_states[user_id]
            return {
                "type": "text",
                "text": "您已取消臨時預約。"
            }
        
        # 用戶確認，保存預約到數據庫
        booking_data = temp_booking_states[user_id]["data"]
        
        try:
            # 修改為使用臨時地點和自定義欄位
            insert_query = """
            INSERT INTO trips 
            (date, time, start_point, end_point, category, status, trip_type, 
             custom_start_point, custom_end_point) 
            VALUES 
            (:date, :time, '臨時地點', '臨時地點', :category, '待派', 'temp',
             :custom_start_point, :custom_end_point)
            RETURNING trip_id
            """
            
            # 确保 end_point 不为空，如果为空则设置为默认值
            end_point = booking_data.get("end_point", "")
            if not end_point or end_point == "無(略過)":
                end_point = "无指定终点"
            
            params = {
                "date": booking_data["date"],
                "time": booking_data["time"],
                "category": booking_data["category"],
                "custom_start_point": booking_data["start_point"],
                "custom_end_point": end_point
            }
            
            result = db.session.execute(sql_text(insert_query), params)
            
            new_trip_id = result.fetchone()[0]
            
            # 生成唯一識別碼
            unique_code = f"T_{new_trip_id}"
            
            # 計算一年中的第幾周
            _, week_number, _ = booking_data["date"].isocalendar()
            
            # 更新班次的唯一識別碼和週數
            update_query = """
            UPDATE trips 
            SET unique_code = :unique_code, week_number = :week_number
            WHERE trip_id = :trip_id
            """
            
            db.session.execute(
                sql_text(update_query), 
                {
                    "unique_code": unique_code,
                    "week_number": week_number,
                    "trip_id": new_trip_id
                }
            )
            
            db.session.commit()
            
            logger.info(f"成功創建臨時班次: ID={new_trip_id}, 日期={booking_data['date']}, 時間={booking_data['time']}")
            
            # 清除用戶狀態
            del temp_booking_states[user_id]
            
            # 生成成功消息
            success_message = (
                "✅ 臨時預約成功！\n\n"
                f"班次ID: {new_trip_id}\n"
                f"日期：{booking_data['date'].strftime('%Y-%m-%d')}\n"
                f"時間：{booking_data['time'].strftime('%H:%M')}\n"
                f"起點：{booking_data['start_point']}\n"
            )
            
            if booking_data.get("end_point") and booking_data.get("end_point") != "無(略過)":
                success_message += f"目的地：{booking_data['end_point']}\n"
            
            success_message += (
                f"類別：{booking_data['category']}\n"
                f"狀態：待派\n\n"
                "我們會盡快為您指派司機。"
            )
            
            return {
                "type": "text",
                "text": success_message
            }
        
        except Exception as db_error:
            logger.error(f"保存臨時預約到數據庫時出錯: {db_error}")
            # 回滾事務
            db.session.rollback()
            return {
                "type": "text",
                "text": f"保存臨時預約時出錯: {str(db_error)}\n請稍後重試。"
            }
    
    except Exception as e:
        logger.error(f"處理確認輸入時出錯: {e}")
        # 清除用戶狀態
        if user_id in temp_booking_states:
            del temp_booking_states[user_id]
        return {
            "type": "text",
            "text": "處理臨時預約確認時出錯。請重新開始預約流程。"
        }

def handle_temp_booking_help():
    """提供臨時預約幫助信息"""
    help_text = (
        "📱 臨時預約使用說明：\n\n"
        "1. 輸入「臨時預約」開始預約流程\n"
        "2. 選擇或輸入預約日期\n"
        "3. 選擇或輸入預約時間（09:17, 10:32, 14:30, 15:30, 17:00, 17:30）\n"
        "4. 選擇或輸入起點位置\n"
        "5. 選擇或輸入目的地位置（可選擇「無(略過)」跳過）\n"
        "6. 確認預約信息\n\n"
        "臨時預約適用於非固定行程的單次接送服務。\n"
        "任何時候輸入「取消」即可取消預約流程。"
    )
    
    return {
        "type": "text",
        "text": help_text
    } 