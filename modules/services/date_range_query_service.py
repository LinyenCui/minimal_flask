"""
日期範圍查詢服務
支援跨日期範圍查詢trips和completed_trips表
"""

import logging
from datetime import datetime, timedelta
from sqlalchemy import text
from modules.utils.unified_date_parser import UnifiedDateParser
from modules.utils.taiwan_time import get_taiwan_date

# 延遲導入db避免循環導入
db = None

def get_db():
    """獲取資料庫連接"""
    global db
    if db is None:
        try:
            from database import db as _db
            db = _db
        except ImportError:
            # 測試環境中可能沒有資料庫
            pass
    return db

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
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d")
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
            COALESCE(meter_fare, 0) + COALESCE(extra_fare, 0) as total_fare,
            driver_id, modification_reason, trip_type
        FROM completed_trips 
        WHERE {where_clause}
        ORDER BY date, id
        """
        
        db_conn = get_db()
        if not db_conn:
            return []
        
        results = db_conn.session.execute(text(query_sql), params).fetchall()
        return results
        
    except Exception as e:
        logger.error(f"查詢已完成班次範圍失敗: {e}")
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
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d")
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
            driver_id, status, trip_type, client_id
        FROM trips 
        WHERE {where_clause}
        ORDER BY date, time, trip_id
        """
        
        db_conn = get_db()
        if not db_conn:
            return []
        
        results = db_conn.session.execute(text(query_sql), params).fetchall()
        return results
        
    except Exception as e:
        logger.error(f"查詢進行中班次範圍失敗: {e}")
        return []

def format_completed_trips_range_result(trips, start_date, end_date, driver_id=None, category=None):
    """
    格式化已完成班次範圍查詢結果
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
    total_fare = sum(trip[7] for trip in trips if trip[7] is not None)  # total_fare欄位
    
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
            meter_fare, extra_fare, total_fare = trip[5:8]
            driver_id_result, modification_reason = trip[8:10]
            
            lines.append(f"#{trip_id} 🚗{driver_id_result} {start_point}→{end_point} ${total_fare}")
            displayed_count += 1
    
    if total_trips > max_display:
        lines.append(f"...")
        lines.append(f"還有 {total_trips - max_display} 筆班次未顯示")
    
    return "\n".join(lines)

def format_current_trips_range_result(trips, start_date, end_date, driver_id=None, category=None):
    """
    格式化進行中班次範圍查詢結果
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
                
            trip_id, date, time, start_point, end_point, category = trip[:6]
            driver_id_result, status = trip[6:8]
            
            status_emoji = {"待派": "⏳", "準備": "🚀", "已完成": "✅"}.get(status, "❓")
            
            lines.append(f"#{trip_id} {time} 🚗{driver_id_result} {start_point}→{end_point} {status_emoji}{status}")
            displayed_count += 1
    
    if total_trips > max_display:
        lines.append(f"...")
        lines.append(f"還有 {total_trips - max_display} 筆班次未顯示")
    
    return "\n".join(lines)

def handle_query_completed_trips_range(message_text):
    """
    處理已完成班次範圍查詢命令
    格式：查已完成範圍 7/28-7/30 [司機ID] [類別]
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
            if part.isdigit():
                driver_id = int(part)
            elif part in ["診所", "東洋", "臨時"]:
                category = part
        
        # 查詢數據
        trips = query_completed_trips_range(start_date, end_date, driver_id, category)
        
        # 格式化結果
        result = format_completed_trips_range_result(trips, start_date, end_date, driver_id, category)
        
        return result
        
    except Exception as e:
        logger.error(f"處理已完成班次範圍查詢失敗: {e}")
        return f"❌ 查詢失敗：{str(e)}"

def handle_query_current_trips_range(message_text):
    """
    處理進行中班次範圍查詢命令
    格式：查班次範圍 8/1-8/5 [司機ID] [類別]
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
            if part.isdigit():
                driver_id = int(part)
            elif part in ["診所", "東洋", "臨時"]:
                category = part
        
        # 查詢數據
        trips = query_current_trips_range(start_date, end_date, driver_id, category)
        
        # 格式化結果
        result = format_current_trips_range_result(trips, start_date, end_date, driver_id, category)
        
        return result
        
    except Exception as e:
        logger.error(f"處理進行中班次範圍查詢失敗: {e}")
        return f"❌ 查詢失敗：{str(e)}"