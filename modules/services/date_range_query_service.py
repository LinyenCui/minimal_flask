"""
日期範圍查詢服務
支援跨日期範圍查詢trips和completed_trips表
"""

import logging
from datetime import datetime, timedelta
from sqlalchemy import text
from modules.utils.unified_date_parser import UnifiedDateParser
from modules.utils.taiwan_time import get_taiwan_date

# 直接導入db，與其他服務保持一致
from modules.models.base import db

logger = logging.getLogger(__name__)

def parse_date_range(date_range_str):
    """
    解析日期範圍字符串
    支援格式：7/28-7/30, 2025-07-28-2025-07-30, 昨天到今天等
    
    Returns:
        tuple: (start_date, end_date) datetime objects, 或 (None, None) 如果解析失敗
    """
    try:
        # 移除空格
        date_range_str = date_range_str.strip()
        
        # 檢查是否包含範圍分隔符
        separators = ['-', '到', '至', '~', 'to']
        separator_used = None
        
        for sep in separators:
            if sep in date_range_str:
                separator_used = sep
                break
        
        if not separator_used:
            return None, None
        
        # 分割日期範圍
        parts = date_range_str.split(separator_used, 1)
        if len(parts) != 2:
            return None, None
        
        start_str = parts[0].strip()
        end_str = parts[1].strip()
        
        # 解析開始和結束日期
        start_date = UnifiedDateParser.parse(start_str)
        end_date = UnifiedDateParser.parse(end_str)
        
        # 確保開始日期不晚於結束日期
        if start_date > end_date:
            start_date, end_date = end_date, start_date
        
        return start_date, end_date
        
    except Exception as e:
        logger.error(f"解析日期範圍 '{date_range_str}' 失敗: {e}")
        return None, None

def query_completed_trips_range(start_date, end_date, driver_id=None, category=None):
    """
    查詢日期範圍內的已完成班次
    
    Args:
        start_date: 開始日期
        end_date: 結束日期  
        driver_id: 司機ID（可選）
        category: 班次類別（可選）
    
    Returns:
        list: 查詢結果列表
    """
    try:
        # 基本查詢條件
        where_conditions = ["date >= :start_date", "date <= :end_date"]
        params = {
            "start_date": start_date,
            "end_date": end_date
        }
        
        # 添加司機ID條件
        if driver_id:
            where_conditions.append("driver_id = :driver_id")
            params["driver_id"] = driver_id
        
        # 添加類別條件
        if category and category != "全部":
            where_conditions.append("category = :category")
            params["category"] = category
        
        where_clause = " AND ".join(where_conditions)
        
        query_sql = f"""
        SELECT 
            id, date, start_point, end_point, category,
            meter_fare, extra_fare, 
            CASE 
                WHEN meter_fare IS NULL AND extra_fare IS NULL THEN NULL
                WHEN meter_fare IS NULL THEN extra_fare
                WHEN extra_fare IS NULL THEN meter_fare
                ELSE meter_fare + extra_fare
            END as calculated_total,
            COALESCE(meter_fare, 0) + COALESCE(extra_fare, 0) as coalesced_total,
            actual_fare as original_total,
            driver_id, modification_reason, trip_type
        FROM completed_trips 
        WHERE {where_clause}
        ORDER BY date, id
        """
        
        # 調試日誌
        logger.info(f"🔍 執行SQL查詢:")
        logger.info(f"   SQL: {query_sql}")
        logger.info(f"   參數: {params}")
        
        results = db.session.execute(text(query_sql), params).fetchall()
        logger.info(f"🔍 查詢結果數量: {len(results)}")
        
        return results
        
    except Exception as e:
        logger.error(f"查詢已完成班次範圍失敗: {e}")
        import traceback
        logger.error(f"詳細錯誤: {traceback.format_exc()}")
        return []

def query_current_trips_range(start_date, end_date, driver_id=None, category=None):
    """
    查詢日期範圍內的進行中班次(trips表)
    
    Args:
        start_date: 開始日期
        end_date: 結束日期
        driver_id: 司機ID（可選）
        category: 班次類別（可選）
    
    Returns:
        list: 查詢結果列表
    """
    try:
        # 基本查詢條件
        where_conditions = ["date >= :start_date", "date <= :end_date"]
        params = {
            "start_date": start_date,
            "end_date": end_date
        }
        
        # 添加司機ID條件
        if driver_id:
            where_conditions.append("driver_id = :driver_id")
            params["driver_id"] = driver_id
        
        # 添加類別條件
        if category and category != "全部":
            where_conditions.append("category = :category")
            params["category"] = category
        
        where_clause = " AND ".join(where_conditions)
        
        query_sql = f"""
        SELECT 
            trip_id, date, time, start_point, end_point, category,
            driver_id, status, trip_type,
            custom_start_point, custom_end_point, custom_via_point,
            passenger_leave_reason, modification_reason
        FROM trips 
        WHERE {where_clause}
        ORDER BY date, time, trip_id
        """
        
        # 調試日誌
        logger.info(f"🔍 執行現在態SQL查詢:")
        logger.info(f"   SQL: {query_sql}")
        logger.info(f"   參數: {params}")
        
        results = db.session.execute(text(query_sql), params).fetchall()
        logger.info(f"🔍 現在態查詢結果數量: {len(results)}")
        
        return results
        
    except Exception as e:
        logger.error(f"查詢進行中班次範圍失敗: {e}")
        import traceback
        logger.error(f"詳細錯誤: {traceback.format_exc()}")
        return []

def format_completed_trips_range_result(trips, start_date, end_date, driver_id=None, category=None, page_info=None):
    """
    格式化已完成班次範圍查詢結果
    page_info: {'current': 1, 'total_items': 50, 'has_more': True}
    """
    if not trips:
        filter_desc = []
        if driver_id:
            filter_desc.append(f"司機{driver_id}")
        if category:
            filter_desc.append(f"{category}班次")
        
        filter_text = "".join(filter_desc) if filter_desc else ""
        
        return f"""❌ 找不到符合條件的已完成班次

📅 查詢範圍：{start_date.strftime('%Y-%m-%d')} 至 {end_date.strftime('%Y-%m-%d')}
🔍 篩選條件：{filter_text if filter_text else "無"}

💡 建議：
• 確認日期範圍是否正確
• 嘗試擴大查詢範圍
• 檢查司機號碼和類別是否正確"""

    # 統計信息
    total_trips = len(trips)
    
    # 使用最準確的金額計算方式
    # 如果有 page_info 且包含 total_fare，使用傳入的總金額（避免只計算部分筆數）
    if page_info and 'total_fare' in page_info:
        total_fare = page_info['total_fare']
        total_trips = page_info.get('total_items', total_trips)
        problematic_trips = []
    else:
        total_fare = 0
        problematic_trips = []
        
        for trip in trips:
            # 新查詢結構：calculated_total=7, coalesced_total=8, original_total=9
            calculated_total = trip[7]  # 智能計算（NULL處理）
            coalesced_total = trip[8]   # 強制COALESCE處理
            original_total = trip[9]    # 原始數據庫total_fare
            
            # 優先使用original_total，如果為NULL則使用calculated_total
            if original_total is not None:
                trip_amount = original_total
            elif calculated_total is not None:
                trip_amount = calculated_total
            else:
                trip_amount = 0
                problematic_trips.append(trip[0])  # 記錄問題班次ID
                
            total_fare += trip_amount
    
    # 按日期分組
    trips_by_date = {}
    for trip in trips:
        date_str = trip[1]  # date欄位
        if date_str not in trips_by_date:
            trips_by_date[date_str] = []
        trips_by_date[date_str].append(trip)
    
    # 建立回應
    lines = []
    lines.append("🔍 AI智能搜索結果")
    lines.append("")
    
    # 查詢條件摘要
    filter_desc = []
    if driver_id:
        filter_desc.append(f"司機{driver_id}")
    if category:
        filter_desc.append(f"{category}班次")
    
    lines.append(f"📅 查詢範圍：{start_date.strftime('%m/%d')} - {end_date.strftime('%m/%d')}")
    if filter_desc:
        lines.append(f"🔍 篩選條件：{' '.join(filter_desc)}")
    lines.append("")
    
    # 統計摘要
    lines.append(f"📊 找到 {total_trips} 筆班次，總車資 ${total_fare:,.0f}")
    lines.append("-" * 30)
    
    # 按日期列出班次（最多顯示前20筆）
    displayed_count = 0
    max_display = 20
    
    for date_str in sorted(trips_by_date.keys()):
        if displayed_count >= max_display:
            break
            
        date_trips = trips_by_date[date_str]
        lines.append(f"📅 {date_str}")
        
        for trip in date_trips:
            if displayed_count >= max_display:
                break
                
            trip_id, date, start_point, end_point, category = trip[:5]
            meter_fare, extra_fare = trip[5:7]
            calculated_total, coalesced_total, original_total = trip[7:10]
            driver_id_result, modification_reason = trip[10:12]
            
            # 使用與統計相同的邏輯決定顯示金額
            if original_total is not None:
                display_amount = original_total
            elif calculated_total is not None:
                display_amount = calculated_total
            else:
                display_amount = 0
            
            # 添加問題標記
            problem_indicator = ""
            if trip_id in problematic_trips:
                problem_indicator = " ⚠️"
            elif original_total != calculated_total and original_total is not None and calculated_total is not None:
                problem_indicator = " 🔄"  # 金額不一致
            elif display_amount == 0:
                # 車資為0元：檢查是否有合理的備註說明（如請假、免費等）
                if modification_reason and any(kw in modification_reason for kw in ["免費", "請假", "贈送", "優惠"]):
                    problem_indicator = " 🏷️(0元)"  # 有備註的0元
                else:
                    problem_indicator = " ⚠️(0元)"  # 異常的0元
            
            lines.append(f"#{trip_id} 🚗{driver_id_result} {start_point}→{end_point} ${display_amount}{problem_indicator}")
            displayed_count += 1
    
    # 分頁提示
    if page_info:
        total_items = page_info.get('total_items', total_trips)
        current_page = page_info.get('current', 1)
        has_more = page_info.get('has_more', False)
        
        if has_more:
            lines.append(f"")
            lines.append(f"📄 第 {current_page} 頁，共 {total_items} 筆")
            lines.append(f"💡 輸入「更多」查看下一頁")
    elif total_trips > max_display:
        lines.append(f"...")
        lines.append(f"還有 {total_trips - max_display} 筆班次未顯示")
    
    # 添加診斷信息
    if problematic_trips:
        lines.append("")
        lines.append(f"⚠️ 發現 {len(problematic_trips)} 筆問題班次（無金額或計算異常）")
        lines.append("🔄 標記表示原始金額與計算金額不一致")
    
    return "\n".join(lines)

def format_current_trips_range_result(trips, start_date, end_date, driver_id=None, category=None, page_info=None):
    """
    格式化進行中班次範圍查詢結果
    page_info: {'current': 1, 'total_items': 50, 'has_more': True}
    """
    if not trips:
        filter_desc = []
        if driver_id:
            filter_desc.append(f"司機{driver_id}")
        if category:
            filter_desc.append(f"{category}班次")
        
        filter_text = "".join(filter_desc) if filter_desc else ""
        
        return f"""❌ 找不到符合條件的班次

📅 查詢範圍：{start_date.strftime('%Y-%m-%d')} 至 {end_date.strftime('%Y-%m-%d')}
🔍 篩選條件：{filter_text if filter_text else "無"}

💡 建議：
• 確認日期範圍是否正確
• 嘗試擴大查詢範圍
• 檢查司機號碼和類別是否正確"""

    # 統計信息
    total_trips = len(trips)
    
    # 按日期分組
    trips_by_date = {}
    for trip in trips:
        date_str = trip[1]  # date欄位
        if date_str not in trips_by_date:
            trips_by_date[date_str] = []
        trips_by_date[date_str].append(trip)
    
    # 建立回應
    lines = []
    lines.append("🔍 班次查詢結果")
    lines.append("")
    
    # 查詢條件摘要
    filter_desc = []
    if driver_id:
        filter_desc.append(f"司機{driver_id}")
    if category:
        filter_desc.append(f"{category}班次")
    
    lines.append(f"📅 查詢範圍：{start_date.strftime('%m/%d')} - {end_date.strftime('%m/%d')}")
    if filter_desc:
        lines.append(f"🔍 篩選條件：{' '.join(filter_desc)}")
    lines.append("")
    
    # 統計摘要
    lines.append(f"📊 找到 {total_trips} 筆班次")
    lines.append("-" * 30)
    
    # 按日期列出班次（最多顯示前20筆）
    displayed_count = 0
    max_display = 20
    
    for date_str in sorted(trips_by_date.keys()):
        if displayed_count >= max_display:
            break
            
        date_trips = trips_by_date[date_str]
        lines.append(f"📅 {date_str}")
        
        for trip in date_trips:
            if displayed_count >= max_display:
                break
                
            trip_id = trip[0]
            date_val = trip[1]
            time_val = trip[2]
            start_point = trip[3]
            end_point = trip[4]
            category_val = trip[5]
            driver_id_result = trip[6]
            status = trip[7]
            trip_type = trip[8]
            custom_start_point = trip[9] if len(trip) > 9 else None
            custom_end_point = trip[10] if len(trip) > 10 else None
            # custom_via_point = trip[11] if len(trip) > 11 else None
            # passenger_leave_reason = trip[12] if len(trip) > 12 else None
            
            # 顯示地點：temp 使用 custom 欄位
            if trip_type == 'temp':
                loc_start = custom_start_point or start_point
                loc_end = custom_end_point or end_point
            else:
                loc_start = start_point
                loc_end = end_point
            
            time_str = time_val.strftime('%H:%M') if time_val else '--:--'
            status_emoji = {"待派": "⏳", "準備": "🚀", "已完成": "✅"}.get(status, "❓")
            
            lines.append(f"#{trip_id} {time_str} 🚗{driver_id_result} {loc_start}→{loc_end} {status_emoji}{status}")
            displayed_count += 1
    
    # 分頁提示
    if page_info:
        total_items = page_info.get('total_items', total_trips)
        current_page = page_info.get('current', 1)
        has_more = page_info.get('has_more', False)
        
        if has_more:
            lines.append(f"")
            lines.append(f"📄 第 {current_page} 頁，共 {total_items} 筆")
            lines.append(f"💡 輸入「更多」查看下一頁")
    elif total_trips > max_display:
        lines.append(f"...")
        lines.append(f"還有 {total_trips - max_display} 筆班次未顯示")
    
    return "\n".join(lines)

def handle_query_completed_trips_range(message_text, user_id=None):
    """
    處理已完成班次範圍查詢命令
    格式：查已完成範圍 7/28-7/30 [司機ID] [類別]
    支援翻頁
    """
    try:
        parts = message_text.split()
        if len(parts) < 2:
            return "❌ 請提供日期範圍，格式：查已完成範圍 7/28-7/30 [司機ID] [類別]"
        
        # 解析日期範圍
        date_range_str = parts[1]
        start_date, end_date = parse_date_range(date_range_str)
        
        if not start_date or not end_date:
            return f"❌ 日期範圍格式不正確：{date_range_str}\n支援格式：7/28-7/30, 2025-07-28-2025-07-30"
        
        # 解析可選參數
        driver_id = None
        category = None
        
        for part in parts[2:]:
            token = part.strip()
            if not token:
                continue
            if token.isdigit():
                driver_id = int(token)
                continue
            if token in ["診所", "東洋", "臨時"]:
                category = token
                continue
            # 更彈性的解析：支援「司機5386」「司機5386所有班次」「5386診所班次」等
            import re
            # 1) 司機前綴，抓取數字
            if token.startswith("司機"):
                m = re.search(r"司機(\d+)", token)
                if m:
                    driver_id = int(m.group(1))
                    # 也檢查是否帶有類別關鍵字
                    if "診所" in token:
                        category = "診所"
                    elif "東洋" in token:
                        category = "東洋"
                    elif "臨時" in token:
                        category = "臨時"
                    continue
            # 2) 數字+類別的組合，如 "5386診所班次"
            m2 = re.match(r'^(\d+)(診所|東洋|臨時)', token)
            if m2:
                driver_id = int(m2.group(1))
                category = m2.group(2)
                continue
            # 3) 任意含數字的token（抓第一段連續數字作為司機ID），忽略尾綴
            m3 = re.search(r"(\d+)", token)
            if m3 and driver_id is None:
                driver_id = int(m3.group(1))
        
        # 查詢數據
        trips = query_completed_trips_range(start_date, end_date, driver_id, category)
        
        # 如果提供了 user_id，保存查詢結果以支援翻頁
        if user_id and len(trips) > 10:
            from modules.utils.conversation_context import get_conversation_context
            from linebot.v3.messaging import QuickReply, QuickReplyItem, MessageAction
            
            # 計算總金額（使用所有結果）
            total_fare = 0
            for trip in trips:
                calculated_total = trip[7]
                coalesced_total = trip[8]
                original_total = trip[9]
                
                if original_total is not None:
                    trip_amount = original_total
                elif calculated_total is not None:
                    trip_amount = calculated_total
                else:
                    trip_amount = 0
                total_fare += trip_amount
            
            # 轉換 tuple 為 dict 格式以便翻頁處理
            trips_dict = []
            for trip in trips:
                trip_dict = {
                    'id': trip[0],
                    'date': trip[1].strftime('%Y-%m-%d') if trip[1] else 'N/A',
                    'start_point': trip[2],
                    'end_point': trip[3],
                    'category': trip[4],
                    'meter_fare': trip[5],
                    'extra_fare': trip[6],
                    'driver_id': trip[10]
                }
                trips_dict.append(trip_dict)
            
            context = get_conversation_context(user_id)
            context.save_query_result(
                query_type='completed_trips_range',
                command=message_text,
                all_results=trips_dict,
                conditions={
                    'start_date': start_date.strftime('%Y-%m-%d'),
                    'end_date': end_date.strftime('%Y-%m-%d'),
                    'driver_id': driver_id,
                    'category': category,
                    'total_fare': total_fare  # 保存總金額
                }
            )
            # 格式化第一頁結果（前10筆，但傳遞總金額）
            result = format_completed_trips_range_result(
                trips[:10], start_date, end_date, driver_id, category, 
                page_info={
                    'current': 1, 
                    'total_items': len(trips), 
                    'total_fare': total_fare,  # 傳遞總金額
                    'has_more': True
                }
            )
            
            # 添加 Quick Reply 按鈕
            quick_reply = QuickReply(items=[
                QuickReplyItem(
                    action=MessageAction(
                        label="📄 下一頁",
                        text="下一頁"
                    )
                ),
                QuickReplyItem(
                    action=MessageAction(
                        label="🔍 重新查詢",
                        text="重新查詢"
                    )
                )
            ])
            
            # 返回帶 Quick Reply 的結果
            return {'message': result, 'quick_reply': quick_reply}
        else:
            # 格式化結果（全部顯示，最多20筆）
            result = format_completed_trips_range_result(trips, start_date, end_date, driver_id, category)
            return result
        
    except Exception as e:
        logger.error(f"處理已完成班次範圍查詢失敗: {e}")
        return f"❌ 查詢失敗：{str(e)}"

def handle_query_current_trips_range(message_text, user_id=None):
    """
    處理進行中班次範圍查詢命令
    格式：查班次範圍 8/1-8/5 [司機ID] [類別]
    支援翻頁
    """
    try:
        parts = message_text.split()
        if len(parts) < 2:
            return "❌ 請提供日期範圍，格式：查班次範圍 8/1-8/5 [司機ID] [類別]"
        
        # 解析日期範圍
        date_range_str = parts[1]
        start_date, end_date = parse_date_range(date_range_str)
        
        if not start_date or not end_date:
            return f"❌ 日期範圍格式不正確：{date_range_str}\n支援格式：8/1-8/5, 2025-08-01-2025-08-05"
        
        # 解析可選參數
        driver_id = None
        category = None
        
        for part in parts[2:]:
            token = part.strip()
            if not token:
                continue
            if token.isdigit():
                driver_id = int(token)
                continue
            if token in ["診所", "東洋", "臨時"]:
                category = token
                continue
            # 更彈性的解析：支援「司機5386」「司機5386所有班次」「5386診所班次」等
            import re
            # 1) 司機前綴，抓取數字
            if token.startswith("司機"):
                m = re.search(r"司機(\d+)", token)
                if m:
                    driver_id = int(m.group(1))
                    if "診所" in token:
                        category = "診所"
                    elif "東洋" in token:
                        category = "東洋"
                    elif "臨時" in token:
                        category = "臨時"
                    continue
            # 2) 數字+類別的組合，如 "5386診所班次"
            m2 = re.match(r'^(\d+)(診所|東洋|臨時)', token)
            if m2:
                driver_id = int(m2.group(1))
                category = m2.group(2)
                continue
            # 3) 任意含數字的token（抓第一段連續數字作為司機ID），忽略尾綴
            m3 = re.search(r"(\d+)", token)
            if m3 and driver_id is None:
                driver_id = int(m3.group(1))
        
        # 判斷是否為「混合範圍」（跨過去與今天/未來）
        today = get_taiwan_date()
        if start_date < today <= end_date:
            # 1) 過去部分：完成倉庫
            past_end = today - timedelta(days=1)
            completed_part = query_completed_trips_range(start_date, past_end, driver_id, category)
            completed_text = format_completed_trips_range_result(completed_part, start_date, past_end, driver_id, category)
            # 2) 現在/未來部分：生產線
            current_part = query_current_trips_range(today, end_date, driver_id, category)
            current_text = format_current_trips_range_result(current_part, today, end_date, driver_id, category)
            # 合併輸出（清楚標註兩部分）
            header = "🔀 混合日期範圍（已完成 + 現在/未來）\n" + "─"*30
            return f"{header}\n\n【已完成（過去）】\n{completed_text}\n\n【現在/未來（trips）】\n{current_text}"
        else:
            # 純現在/未來範圍
            trips = query_current_trips_range(start_date, end_date, driver_id, category)
            
            # 如果提供了 user_id，保存查詢結果以支援翻頁
            if user_id and len(trips) > 10:
                from modules.utils.conversation_context import get_conversation_context
                from linebot.v3.messaging import QuickReply, QuickReplyItem, MessageAction
                
                # 轉換 tuple 為 dict 格式以便翻頁處理
                trips_dict = []
                for trip in trips:
                    trip_dict = {
                        'trip_id': trip[0],
                        'date': trip[1].strftime('%Y-%m-%d') if trip[1] else 'N/A',
                        'time': trip[2],
                        'start_point': trip[3],
                        'end_point': trip[4],
                        'category': trip[5],
                        'driver_id': trip[6],
                        'status': trip[7],
                        'trip_type': trip[8]
                    }
                    trips_dict.append(trip_dict)
                
                context = get_conversation_context(user_id)
                context.save_query_result(
                    query_type='current_trips_range',
                    command=message_text,
                    all_results=trips_dict,
                    conditions={
                        'start_date': start_date.strftime('%Y-%m-%d'),
                        'end_date': end_date.strftime('%Y-%m-%d'),
                        'driver_id': driver_id,
                        'category': category
                    }
                )
                # 格式化第一頁結果（前10筆）
                result = format_current_trips_range_result(trips[:10], start_date, end_date, driver_id, category,
                                                          page_info={'current': 1, 'total_items': len(trips), 'has_more': True})
                
                # 添加 Quick Reply 按鈕
                quick_reply = QuickReply(items=[
                    QuickReplyItem(
                        action=MessageAction(
                            label="📄 下一頁",
                            text="下一頁"
                        )
                    ),
                    QuickReplyItem(
                        action=MessageAction(
                            label="🔍 重新查詢",
                            text="重新查詢"
                        )
                    )
                ])
                
                # 返回帶 Quick Reply 的結果
                return {'message': result, 'quick_reply': quick_reply}
            else:
                # 格式化結果（全部顯示，最多20筆）
                result = format_current_trips_range_result(trips, start_date, end_date, driver_id, category)
                return result
        
    except Exception as e:
        logger.error(f"處理進行中班次範圍查詢失敗: {e}")
        return f"❌ 查詢失敗：{str(e)}"