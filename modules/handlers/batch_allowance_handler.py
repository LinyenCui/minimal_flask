"""
LINE Bot 批量加成處理模塊
提供問答式批量加成功能
"""

import logging
import re
from datetime import datetime, timedelta
from sqlalchemy import text
from modules.models.base import db
from modules.utils.taiwan_time import get_taiwan_time
from modules.utils.modification_utils import append_modification_reason

logger = logging.getLogger(__name__)

# 批量加成狀態管理
batch_allowance_states = {}

def parse_date_input(date_str):
    """解析日期輸入，支持單日期和日期範圍"""
    date_str = date_str.strip()
    
    # 日期範圍格式：7/7-7/10 或 7/7到7/10
    range_patterns = [
        r'^(\d{1,2})/(\d{1,2})\s*[-到]\s*(\d{1,2})/(\d{1,2})$',
        r'^(\d{1,2})/(\d{1,2})\s*-\s*(\d{1,2})/(\d{1,2})$'
    ]
    
    for pattern in range_patterns:
        match = re.match(pattern, date_str)
        if match:
            start_month, start_day, end_month, end_day = match.groups()
            current_year = get_taiwan_time().year
            
            try:
                start_date = f"{current_year}-{int(start_month):02d}-{int(start_day):02d}"
                end_date = f"{current_year}-{int(end_month):02d}-{int(end_day):02d}"
                
                # 驗證日期有效性
                datetime.strptime(start_date, "%Y-%m-%d")
                datetime.strptime(end_date, "%Y-%m-%d")
                
                return start_date, end_date
            except ValueError:
                return None, None
    
    # 單日期格式：7/7
    single_pattern = r'^(\d{1,2})/(\d{1,2})$'
    match = re.match(single_pattern, date_str)
    if match:
        month, day = match.groups()
        current_year = get_taiwan_time().year
        
        try:
            single_date = f"{current_year}-{int(month):02d}-{int(day):02d}"
            datetime.strptime(single_date, "%Y-%m-%d")
            return single_date, single_date
        except ValueError:
            return None, None
    
    return None, None

# get_next_modification_number 函數已移至 modules.utils.modification_utils

def query_trips_for_allowance(start_date, end_date, category=None):
    """查詢符合條件的已完成班次"""
    try:
        # 基本查詢條件
        where_conditions = ["date >= :start_date", "date <= :end_date"]
        params = {"start_date": start_date, "end_date": end_date}
        
        # 如果指定了類別，加入條件
        if category and category != "全部":
            where_conditions.append("category = :category")
            params["category"] = category
        
        where_clause = " AND ".join(where_conditions)
        
        query_sql = f"""
        SELECT 
            id, date, start_point, end_point, category, 
            meter_fare, extra_fare, 
            COALESCE(meter_fare, 0) + COALESCE(extra_fare, 0) as current_total,
            driver_id, modification_reason
        FROM completed_trips 
        WHERE {where_clause}
        ORDER BY date, id
        """
        
        results = db.session.execute(text(query_sql), params).fetchall()
        
        return results
        
    except Exception as e:
        logger.error(f"查詢班次時出錯: {e}")
        return []

def format_trips_preview(trips, max_display=10):
    """格式化班次預覽"""
    if not trips:
        return "❌ 沒有找到符合條件的班次"
    
    lines = [f"🔍 找到 {len(trips)} 筆符合條件的班次："]
    lines.append("-" * 40)
    
    # 顯示前幾筆
    display_count = min(len(trips), max_display)
    
    for i, trip in enumerate(trips[:display_count]):
        id, date, start_point, end_point, category = trip[:5]
        meter_fare, extra_fare, current_total = trip[5:8]
        driver_id = trip[8]
        
        current_extra = extra_fare if extra_fare is not None else 0
        lines.append(f"#{id} {date} {start_point}→{end_point} ({category})")
        lines.append(f"   司機:{driver_id} | 加成:{current_extra} | 總計:{current_total}")
    
    if len(trips) > max_display:
        lines.append(f"... 及其他 {len(trips) - max_display} 筆班次")
    
    lines.append("-" * 40)
    total_amount = sum(trip[7] for trip in trips)  # current_total
    lines.append(f"💰 總計金額: {total_amount} 元")
    
    return "\n".join(lines)

def execute_batch_allowance(trips, amount, reason):
    """執行批量加成"""
    try:
        updated_count = 0
        
        # 逐個處理每個班次以確保編號正確
        for trip in trips:
            trip_id = trip[0]
            current_reason = trip[9] if len(trip) > 9 else None  # modification_reason
            
            # 使用統一的 modification_reason 管理工具
            new_modification_reason = append_modification_reason(
                current_reason, 
                reason, 
                "completed_trips"
            )
            
            # 更新單個班次
            update_sql = """
            UPDATE completed_trips 
            SET 
                extra_fare = COALESCE(extra_fare, 0) + :amount,
                modification_reason = :new_reason
            WHERE id = :trip_id
            """
            
            result = db.session.execute(text(update_sql), {
                "amount": amount,
                "new_reason": new_modification_reason,
                "trip_id": trip_id
            })
            
            if result.rowcount > 0:
                updated_count += 1
        
        # 提交事務
        db.session.commit()
        
        return updated_count, None
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"執行批量加成時出錯: {e}")
        return 0, str(e)

def handle_batch_allowance_start(user_id):
    """開始批量加成流程"""
    logger.info(f"用戶 {user_id} 開始批量加成流程")
    
    # 初始化狀態
    batch_allowance_states[user_id] = {
        "state": "waiting_date",
        "start_date": None,
        "end_date": None,
        "category": None,
        "amount": None,
        "reason": None,
        "trips": []
    }
    
    help_text = """💰 批量加成功能

請輸入要加成的日期：

📅 單日期格式：7/7
📅 日期範圍：7/7-7/10 或 7/7到7/10

例如：
• 7/7 （單日）
• 1/20-1/30 （春節假期）
• 7/7-7/9 （颱風假期）

回覆「取消」可退出操作"""
    
    return {"type": "text", "text": help_text}

def handle_batch_allowance_message(user_id, message_text):
    """處理批量加成流程中的消息"""
    if user_id not in batch_allowance_states:
        logger.info(f"用戶 {user_id} 不在批量加成流程中")
        return None
    
    # 處理取消指令
    if message_text.lower() in ["取消", "cancel", "退出", "exit"]:
        logger.info(f"用戶 {user_id} 取消批量加成流程")
        del batch_allowance_states[user_id]
        return {"type": "text", "text": "已取消批量加成操作"}
    
    current_state = batch_allowance_states[user_id]["state"]
    
    if current_state == "waiting_date":
        return handle_date_input(user_id, message_text)
    elif current_state == "waiting_category":
        return handle_category_input(user_id, message_text)
    elif current_state == "waiting_amount":
        return handle_amount_input(user_id, message_text)
    elif current_state == "waiting_reason":
        return handle_reason_input(user_id, message_text)
    elif current_state == "waiting_confirm":
        return handle_confirm_input(user_id, message_text)
    
    return {"type": "text", "text": "未知操作，請回覆相應的選項或「取消」"}

def handle_date_input(user_id, message_text):
    """處理日期輸入"""
    start_date, end_date = parse_date_input(message_text)
    
    if not start_date or not end_date:
        return {"type": "text", "text": "❌ 日期格式不正確\n\n請使用以下格式：\n• 單日：7/7\n• 範圍：7/7-7/10"}
    
    # 保存日期並進入下一步
    batch_allowance_states[user_id]["start_date"] = start_date
    batch_allowance_states[user_id]["end_date"] = end_date
    batch_allowance_states[user_id]["state"] = "waiting_category"
    
    date_range = f"{start_date}" if start_date == end_date else f"{start_date} 到 {end_date}"
    
    category_text = f"""✅ 日期範圍：{date_range}

請選擇要加成的班次類別：

🏥 診所
🚗 東洋  
🎯 全部

回覆類別名稱，或「取消」退出"""
    
    return {"type": "text", "text": category_text}

def handle_category_input(user_id, message_text):
    """處理類別輸入"""
    category = message_text.strip()
    
    if category not in ["診所", "東洋", "全部"]:
        return {"type": "text", "text": "❌ 請選擇正確的類別：診所、東洋、全部"}
    
    # 保存類別並查詢班次
    batch_allowance_states[user_id]["category"] = category
    
    start_date = batch_allowance_states[user_id]["start_date"]
    end_date = batch_allowance_states[user_id]["end_date"]
    
    # 查詢符合條件的班次
    trips = query_trips_for_allowance(start_date, end_date, category)
    
    if not trips:
        del batch_allowance_states[user_id]
        return {"type": "text", "text": f"❌ 沒有找到符合條件的班次\n\n查詢條件：\n• 日期：{start_date} 到 {end_date}\n• 類別：{category}"}
    
    # 保存查詢結果並進入下一步
    batch_allowance_states[user_id]["trips"] = trips
    batch_allowance_states[user_id]["state"] = "waiting_amount"
    
    preview = format_trips_preview(trips)
    
    amount_text = f"""✅ 類別：{category}

{preview}

請輸入加成金額（例如：50）："""
    
    return {"type": "text", "text": amount_text}

def handle_amount_input(user_id, message_text):
    """處理金額輸入"""
    try:
        amount = int(message_text.strip())
        if amount <= 0:
            return {"type": "text", "text": "❌ 金額必須大於 0"}
        
        # 保存金額並進入下一步
        batch_allowance_states[user_id]["amount"] = amount
        batch_allowance_states[user_id]["state"] = "waiting_reason"
        
        reason_text = f"""✅ 加成金額：{amount} 元

請輸入加成原因（例如：春節假期加成、颱風假加成）："""
        
        return {"type": "text", "text": reason_text}
        
    except ValueError:
        return {"type": "text", "text": "❌ 請輸入有效的數字金額"}

def handle_reason_input(user_id, message_text):
    """處理原因輸入"""
    reason = message_text.strip()
    
    if not reason:
        return {"type": "text", "text": "❌ 請輸入加成原因"}
    
    # 保存原因並進入確認步驟
    batch_allowance_states[user_id]["reason"] = reason
    batch_allowance_states[user_id]["state"] = "waiting_confirm"
    
    # 生成確認信息
    state = batch_allowance_states[user_id]
    trips = state["trips"]
    amount = state["amount"]
    total_allowance = len(trips) * amount
    
    start_date = state["start_date"]
    end_date = state["end_date"]
    date_range = f"{start_date}" if start_date == end_date else f"{start_date} 到 {end_date}"
    
    confirm_text = f"""📋 批量加成確認

📅 日期範圍：{date_range}
🏷️ 班次類別：{state["category"]}
💰 加成金額：{amount} 元/筆
📝 加成原因：{reason}

📊 影響班次：{len(trips)} 筆
💵 總加成金額：{total_allowance} 元

⚠️ 確認執行批量加成？
回覆「確認」執行，或「取消」退出"""
    
    return {"type": "text", "text": confirm_text}

def handle_confirm_input(user_id, message_text):
    """處理確認輸入"""
    if message_text.lower() in ["確認", "confirm", "yes", "y"]:
        # 執行批量加成
        state = batch_allowance_states[user_id]
        trips = state["trips"]
        amount = state["amount"]
        reason = state["reason"]
        
        logger.info(f"用戶 {user_id} 確認執行批量加成")
        
        updated_count, error = execute_batch_allowance(trips, amount, reason)
        
        # 清除狀態
        del batch_allowance_states[user_id]
        
        if error:
            return {"type": "text", "text": f"❌ 批量加成執行失敗：{error}"}
        
        total_allowance = updated_count * amount
        
        result_text = f"""✅ 批量加成執行完成！

📊 更新班次數：{updated_count} 筆
💰 總加成金額：{total_allowance} 元
📝 加成原因：{reason}

所有班次的 extra_fare 已增加 {amount} 元
並在 modification_reason 中添加了編號記錄"""
        
        return {"type": "text", "text": result_text}
    
    else:
        return {"type": "text", "text": "請回覆「確認」來執行批量加成，或「取消」退出"} 