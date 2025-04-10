"""
處理預約功能的模組
"""
from datetime import datetime, date, timedelta, time
from sqlalchemy.sql import text
import traceback
import logging
import re

from modules.utils.line_bot import (
    create_text_message, create_flex_message, reply_text, reply_flex
)
from modules.utils.helpers import booking_states
from modules.flex_designs.booking_flex import (
    get_booking_start_flex, get_booking_time_flex,
    get_booking_location_flex, get_booking_confirm_flex,
    get_booking_success_flex
)
from modules.models.base import db
from modules.utils.taiwan_time import get_taiwan_time, get_taiwan_date

# 建立日誌記錄器
logger = logging.getLogger(__name__)

def handle_booking_start(user_id, category="診所"):
    """初始化預約流程"""
    try:
        logger.info(f"初始化預約流程，用戶ID: {user_id}, 類別: {category}")
        
        # 初始化預約狀態
        booking_states[user_id] = {
            "state": "waiting_for_date",
            "category": category
        }
        
        logger.info(f"已設置用戶 {user_id} 的預約狀態: {booking_states[user_id]}")
        
        # 返回日期選擇界面
        try:
            flex_content = get_booking_start_flex()
            if flex_content:
                return create_flex_message("請選擇預約日期", flex_content)
            else:
                # 使用簡單的文本消息作為備用方案
                logger.warning("Flex內容為空，回退到文本消息")
                return create_text_message("請輸入預約日期 (YYYY-MM-DD 格式)，或輸入「今天」、「明天」、「後天」。")
        except Exception as e:
            logger.error(f"創建日期選擇界面時出錯: {e}")
            traceback.print_exc()
            # 使用簡單的文本消息作為備用方案
            return create_text_message("請輸入預約日期 (YYYY-MM-DD 格式)，或輸入「今天」、「明天」、「後天」。")
    except Exception as e:
        # 出錯時清除用戶狀態
        if user_id in booking_states:
            del booking_states[user_id]
            logger.info(f"已清除用戶 {user_id} 的預約狀態")
        logger.error(f"初始化預約流程時出錯: {e}")
        traceback.print_exc()
        return create_text_message("預約系統暫時無法使用，請稍後重試")

def handle_booking_message(user_id, message_text, booking_states_dict=None):
    """處理預約流程中的消息"""
    # 使用傳入的狀態字典，或使用全局狀態字典
    states = booking_states_dict if booking_states_dict is not None else booking_states
    
    try:
        logger.info(f"處理預約消息: 用戶ID={user_id}, 消息='{message_text}'")
        
        # 檢查取消命令 - 優先處理取消命令，無論用戶是否在預約流程中
        if message_text.lower() in ["取消", "取消預約", "cancel", "退出", "exit", "!取消", "!取消預約", "!cancel", "!退出", "!exit"]:
            logger.info(f"收到取消預約命令: {message_text}")
            # 清除預約狀態
            if user_id in states:
                logger.info(f"清除用戶 {user_id} 的預約狀態")
                del states[user_id]
            
            return create_text_message("已取消預約流程")
        
        # 檢查用戶是否在預約流程中
        if user_id not in states:
            logger.info(f"用戶 {user_id} 不在預約流程中")
            # 如果用戶不在預約流程中，直接返回
            return None
        
        # 獲取用戶當前狀態
        current_state = states[user_id]["state"]
        logger.info(f"用戶 {user_id} 當前狀態: {current_state}")
        
        # 根據用戶狀態處理輸入
        if current_state == "waiting_for_date":
            return handle_date_input(user_id, message_text, states)
        
        elif current_state == "waiting_for_time":
            return handle_time_input(user_id, message_text, states)
        
        elif current_state == "waiting_for_location":
            return handle_location_input(user_id, message_text, states)
        
        elif current_state == "waiting_for_via_point":
            return handle_via_point_input(user_id, message_text, states)
        
        elif current_state == "waiting_for_end_point":
            return handle_end_point_input(user_id, message_text, states)
        
        elif current_state == "waiting_for_confirm":
            return handle_confirm_input(user_id, message_text, states)
        
        else:
            logger.warning(f"未知的用戶狀態: {current_state}")
            # 狀態無效，清除並重新開始
            del states[user_id]
            return create_text_message("對不起，預約流程出現錯誤。請重新開始預約。")
    
    except Exception as e:
        logger.error(f"處理預約消息時出錯: {e}")
        traceback.print_exc()
        # 出錯時清除用戶狀態
        if user_id in states:
            del states[user_id]
        return create_text_message("預約處理過程中出現錯誤，請重新開始預約。")

def handle_date_input(user_id, message_text, states):
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
                selected_date = datetime.strptime(message_text, "%Y-%m-%d").date()
            except ValueError:
                return create_text_message("日期格式無效。請使用YYYY-MM-DD格式（如2025-03-20），或輸入「今天」、「明天」、「後天」。")
        
        # 檢查日期是否有效（不能是過去的日期）
        if selected_date < today:
            return create_text_message("無法預約過去的日期。請選擇今天或未來的日期。")
        
        # 更新用戶狀態
        states[user_id]["date"] = selected_date.strftime("%Y-%m-%d")
        states[user_id]["state"] = "waiting_for_time"
        
        logger.info(f"用戶 {user_id} 選擇了日期: {selected_date}, 狀態更新為: {states[user_id]}")
        
        # 返回時間選擇界面
        try:
            flex_content = get_booking_time_flex(selected_date)
            if flex_content:
                return create_flex_message("請選擇預約時間", flex_content)
            else:
                # 使用簡單的文本消息作為備用方案
                return create_text_message("請輸入預約時間 (HH:MM 格式)，例如 09:00、14:30 等。")
        except Exception as e:
            logger.error(f"創建時間選擇界面時出錯: {e}")
            # 使用簡單的文本消息作為備用方案
            return create_text_message("請輸入預約時間 (HH:MM 格式)，例如 09:00、14:30 等。")
    
    except Exception as e:
        logger.error(f"處理日期輸入時出錯: {e}")
        # 重置狀態
        states[user_id]["state"] = "waiting_for_date"
        return create_text_message("處理日期時出錯。請重新輸入預約日期。")

def handle_time_input(user_id, message_text, states):
    """處理用戶輸入的時間"""
    try:
        # 檢查時間格式是否有效 (HH:MM)
        time_pattern = r"^([01]?[0-9]|2[0-3]):([0-5][0-9])$"
        if not re.match(time_pattern, message_text):
            return create_text_message("時間格式無效。請使用HH:MM格式（如09:00或14:30）。")
        
        # 解析時間
        try:
            time_obj = datetime.strptime(message_text, "%H:%M").time()
        except ValueError:
            return create_text_message("無法解析時間。請使用HH:MM格式（如09:00或14:30）。")
        
        # 檢查時間是否是過去的時間
        selected_date = states[user_id]["date"]
        date_obj = datetime.strptime(selected_date, "%Y-%m-%d").date()
        now = get_taiwan_time()
        
        if date_obj == now.date() and time_obj < now.time():
            return create_text_message("無法預約過去的時間。請選擇未來的時間。")
        
        # 更新用戶狀態
        states[user_id]["time"] = message_text
        states[user_id]["state"] = "waiting_for_location"
        
        logger.info(f"用戶 {user_id} 選擇了時間: {message_text}, 狀態更新為: {states[user_id]}")
        
        # 返回位置選擇界面
        try:
            flex_content = get_booking_location_flex()
            if flex_content:
                return create_flex_message("請選擇起點位置", flex_content)
            else:
                # 使用簡單的文本消息作為備用方案
                return create_text_message("請輸入預約起點位置（完整地址）。")
        except Exception as e:
            logger.error(f"創建位置選擇界面時出錯: {e}")
            # 使用簡單的文本消息作為備用方案
            return create_text_message("請輸入預約起點位置（完整地址）。")
    
    except Exception as e:
        logger.error(f"處理時間輸入時出錯: {e}")
        # 重置狀態
        states[user_id]["state"] = "waiting_for_time"
        return create_text_message("處理時間時出錯。請重新輸入預約時間。")

def handle_location_input(user_id, message_text, states):
    """處理用戶輸入的起點位置"""
    try:
        # 直接使用用戶輸入的位置
        states[user_id]["start_location"] = message_text
        states[user_id]["state"] = "waiting_for_via_point"
        
        logger.info(f"用戶 {user_id} 選擇了起點位置: {message_text}, 狀態更新為: {states[user_id]}")
        
        # 詢問經由點（可選）
        return create_text_message("請輸入經由點位置（如果有的話）。如果沒有，請輸入「無」或「沒有」。")
    
    except Exception as e:
        logger.error(f"處理位置輸入時出錯: {e}")
        # 重置狀態
        states[user_id]["state"] = "waiting_for_location"
        return create_text_message("處理位置時出錯。請重新輸入起點位置。")

def handle_via_point_input(user_id, message_text, states):
    """處理用戶輸入的經由點位置"""
    try:
        # 檢查是否跳過經由點
        skip_via_point = message_text.lower() in ["無", "沒有", "no", "skip", "跳過"]
        
        if not skip_via_point:
            states[user_id]["via_point"] = message_text
        
        states[user_id]["state"] = "waiting_for_end_point"
        
        logger.info(f"用戶 {user_id} 選擇了經由點: {message_text if not skip_via_point else '(跳過)'}, 狀態更新為: {states[user_id]}")
        
        # 詢問終點
        return create_text_message("請輸入終點位置（完整地址）。")
    
    except Exception as e:
        logger.error(f"處理經由點輸入時出錯: {e}")
        # 重置狀態
        states[user_id]["state"] = "waiting_for_via_point"
        return create_text_message("處理經由點時出錯。請重新輸入經由點位置，或輸入「無」跳過。")

def handle_end_point_input(user_id, message_text, states):
    """處理用戶輸入的終點位置"""
    try:
        # 直接使用用戶輸入的位置
        states[user_id]["end_location"] = message_text
        states[user_id]["state"] = "waiting_for_confirm"
        
        logger.info(f"用戶 {user_id} 選擇了終點位置: {message_text}, 狀態更新為: {states[user_id]}")
        
        # 生成預約確認界面
        try:
            flex_content = get_booking_confirm_flex(states[user_id])
            if flex_content:
                return create_flex_message("確認預約資訊", flex_content)
            else:
                # 使用簡單的文本消息作為備用方案
                # 格式化預約信息
                booking_info = format_booking_info(states[user_id])
                return create_text_message(f"請確認您的預約信息：\n\n{booking_info}\n\n請回覆「確認」完成預約，或「取消」取消預約。")
        except Exception as e:
            logger.error(f"創建確認界面時出錯: {e}")
            # 使用簡單的文本消息作為備用方案
            # 格式化預約信息
            booking_info = format_booking_info(states[user_id])
            return create_text_message(f"請確認您的預約信息：\n\n{booking_info}\n\n請回覆「確認」完成預約，或「取消」取消預約。")
    
    except Exception as e:
        logger.error(f"處理終點位置輸入時出錯: {e}")
        # 重置狀態
        states[user_id]["state"] = "waiting_for_end_point"
        return create_text_message("處理終點位置時出錯。請重新輸入終點位置。")

def handle_confirm_input(user_id, message_text, states):
    """處理用戶確認預約"""
    try:
        # 檢查是否確認預約
        if message_text.lower() not in ["確認", "confirm", "yes", "是", "確定", "ok"]:
            # 用戶沒有確認，取消預約
            del states[user_id]
            return create_text_message("預約已取消。")
        
        # 用戶確認，保存預約到數據庫
        booking_data = states[user_id]
        
        try:
            # 從中文日期格式轉換為數據庫格式
            booking_date = datetime.strptime(booking_data["date"], "%Y-%m-%d").date()
            booking_time = datetime.strptime(booking_data["time"], "%H:%M").time()
            
            # 保存數據到數據庫
            query = """
            INSERT INTO bookings 
            (user_id, booking_date, booking_time, start_location, via_point, end_location, status, category, created_at)
            VALUES 
            (:user_id, :booking_date, :booking_time, :start_location, :via_point, :end_location, 'pending', :category, NOW())
            RETURNING booking_id
            """
            
            result = db.session.execute(text(query), {
                "user_id": user_id,
                "booking_date": booking_date,
                "booking_time": booking_time,
                "start_location": booking_data["start_location"],
                "via_point": booking_data.get("via_point", ""),
                "end_location": booking_data["end_location"],
                "category": booking_data.get("category", "診所")
            })
            
            # 獲取生成的預約ID
            booking_id = result.fetchone()[0]
            
            # 提交事務
            db.session.commit()
            
            logger.info(f"用戶 {user_id} 的預約已保存，預約ID: {booking_id}")
            
            # 更新預約狀態
            booking_data["booking_id"] = booking_id
            
            # 清除用戶狀態
            del states[user_id]
            
            # 返回預約成功界面
            try:
                flex_content = get_booking_success_flex(booking_data)
                if flex_content:
                    return create_flex_message("預約成功", flex_content)
                else:
                    # 使用簡單的文本消息作為備用方案
                    return create_text_message(f"您的預約已成功送出！\n\n預約編號：{booking_id}\n日期：{booking_data['date']}\n時間：{booking_data['time']}\n謝謝您的使用！")
            except Exception as e:
                logger.error(f"創建成功界面時出錯: {e}")
                # 使用簡單的文本消息作為備用方案
                return create_text_message(f"您的預約已成功送出！\n\n預約編號：{booking_id}\n日期：{booking_data['date']}\n時間：{booking_data['time']}\n謝謝您的使用！")
        
        except Exception as db_error:
            logger.error(f"保存預約到數據庫時出錯: {db_error}")
            # 回滾事務
            db.session.rollback()
            return create_text_message("保存預約時出錯，請稍後重試。")
    
    except Exception as e:
        logger.error(f"處理確認輸入時出錯: {e}")
        # 清除用戶狀態
        if user_id in states:
            del states[user_id]
        return create_text_message("處理預約確認時出錯。請重新開始預約流程。")

def format_booking_info(booking_data):
    """格式化預約信息為文本"""
    # 格式化日期
    date_str = booking_data.get("date", "")
    display_date = date_str
    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
        display_date = date_obj.strftime("%Y/%m/%d")
    except ValueError:
        pass
    
    # 創建信息字符串
    info = f"日期：{display_date}\n時間：{booking_data.get('time', '')}\n"
    info += f"起點：{booking_data.get('start_location', '')}\n"
    
    if "via_point" in booking_data and booking_data["via_point"]:
        info += f"經由：{booking_data['via_point']}\n"
    
    info += f"終點：{booking_data.get('end_location', '')}"
    
    return info

def handle_booking_help():
    """提供預約幫助信息"""
    help_text = (
        "預約使用說明：\n\n"
        "1. 輸入「預約」開始預約流程\n"
        "2. 選擇或輸入預約日期（格式：YYYY-MM-DD）\n"
        "3. 選擇或輸入預約時間（格式：HH:MM）\n"
        "4. 輸入起點位置（完整地址）\n"
        "5. 輸入經由點（如有）或輸入「無」跳過\n"
        "6. 輸入終點位置（完整地址）\n"
        "7. 確認預約信息\n\n"
        "任何時候輸入「取消」即可取消預約流程"
    )
    return create_text_message(help_text) 