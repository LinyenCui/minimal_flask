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

def query_completed_trips_aggregation(start_date, end_date, driver_id=None, category=None, location=None):
    """
    聚合查詢日期範圍內的已完成班次（直接用SQL計算統計）

    Args:
        start_date: 開始日期
        end_date: 結束日期
        driver_id: 司機ID（可選）
        category: 班次類別（可選）
        location: 地點關鍵字（可選）

    Returns:
        dict: {
            'total_count': 總筆數,
            'filled_count': 有金額筆數,
            'unfilled_count': 無金額筆數,
            'sum_amount': 總金額
        }
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

        # 添加地點過濾條件
        if location:
            where_conditions.append("(start_point LIKE :location OR via_point LIKE :location OR end_point LIKE :location)")
            params["location"] = f"%{location}%"

        where_clause = " AND ".join(where_conditions)

        aggregation_sql = f"""
        SELECT
            COUNT(*) as total_count,
            COUNT(CASE
                WHEN meter_fare IS NOT NULL OR extra_fare IS NOT NULL THEN 1
            END) as filled_count,
            COUNT(CASE
                WHEN meter_fare IS NULL AND extra_fare IS NULL THEN 1
            END) as unfilled_count,
            SUM(CASE
                WHEN meter_fare IS NULL AND extra_fare IS NULL THEN 0
                WHEN meter_fare IS NULL THEN extra_fare
                WHEN extra_fare IS NULL THEN meter_fare
                ELSE meter_fare + extra_fare
            END) as sum_amount
        FROM completed_trips
        WHERE {where_clause}
        """

        logger.info(f"🔍 執行聚合SQL查詢:")
        logger.info(f"   SQL: {aggregation_sql}")
        logger.info(f"   參數: {params}")

        result = db.session.execute(text(aggregation_sql), params).fetchone()

        aggregation_result = {
            'total_count': result.total_count or 0,
            'filled_count': result.filled_count or 0,
            'unfilled_count': result.unfilled_count or 0,
            'sum_amount': float(result.sum_amount or 0)
        }

        logger.info(f"📊 聚合結果: {aggregation_result}")

        return aggregation_result

    except Exception as e:
        logger.error(f"聚合查詢已完成班次失敗: {e}")
        import traceback
        logger.error(f"詳細錯誤: {traceback.format_exc()}")
        return {
            'total_count': 0,
            'filled_count': 0,
            'unfilled_count': 0,
            'sum_amount': 0
        }


def query_completed_trips_range(start_date, end_date, driver_id=None, category=None, location=None):
    """
    查詢日期範圍內的已完成班次

    Args:
        start_date: 開始日期
        end_date: 結束日期
        driver_id: 司機ID（可選）
        category: 班次類別（可選）
        location: 地點關鍵字（可選）🔥 2025-12-17 新增

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
        
        # 🔥 2025-12-17 新增：添加地點過濾條件
        if location:
            where_conditions.append("(start_point LIKE :location OR via_point LIKE :location OR end_point LIKE :location)")
            params["location"] = f"%{location}%"
        
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

def format_aggregation_summary(agg_result, start_date, end_date, driver_id=None, category=None, location=None):
    """
    格式化聚合查詢結果為摘要文字

    Args:
        agg_result: 聚合結果字典 {total_count, filled_count, unfilled_count, sum_amount}
        start_date: 開始日期
        end_date: 結束日期
        driver_id: 司機ID（可選）
        category: 班次類別（可選）
        location: 地點關鍵字（可選）

    Returns:
        str: 格式化的摘要文字
    """
    lines = []
    lines.append("📊 金額統計摘要")
    lines.append("=" * 30)
    lines.append("")

    # 查詢條件
    filter_desc = []
    if driver_id:
        filter_desc.append(f"司機{driver_id}")
    if category:
        filter_desc.append(f"{category}班次")
    if location:
        filter_desc.append(f"地點「{location}」")

    lines.append(f"📅 統計範圍：{start_date.strftime('%Y-%m-%d')} 至 {end_date.strftime('%Y-%m-%d')}")
    if filter_desc:
        lines.append(f"🔍 篩選條件：{' '.join(filter_desc)}")
    lines.append("")

    # 統計數據
    total_count = agg_result.get('total_count', 0)
    filled_count = agg_result.get('filled_count', 0)
    unfilled_count = agg_result.get('unfilled_count', 0)
    sum_amount = agg_result.get('sum_amount', 0)

    lines.append("📈 統計結果：")
    lines.append(f"  • 總班次數：{total_count} 筆")
    lines.append(f"  • 已填金額：{filled_count} 筆")
    lines.append(f"  • 未填金額：{unfilled_count} 筆")
    lines.append("")
    lines.append(f"💰 總金額：${sum_amount:,.0f}")

    # 提示信息
    if unfilled_count > 0:
        lines.append("")
        lines.append(f"⚠️ 提醒：有 {unfilled_count} 筆班次尚未填寫金額")

    return "\n".join(lines)


def query_current_trips_range(start_date, end_date, driver_id=None, category=None, location=None):
    """
    查詢日期範圍內的進行中班次(trips表)
    
    Args:
        start_date: 開始日期
        end_date: 結束日期
        driver_id: 司機ID（可選）
        category: 班次類別（可選）
        location: 地點關鍵字（可選）🔥 2025-12-17 新增
    
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
        
        # 🔥 2025-12-17 新增：添加地點過濾條件
        if location:
            where_conditions.append("(start_point LIKE :location OR via_point LIKE :location OR end_point LIKE :location OR custom_start_point LIKE :location OR custom_end_point LIKE :location)")
            params["location"] = f"%{location}%"
        
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


def handle_query_trips_range(start_date, end_date, driver_id=None, category=None, trip_type=None, user_id=None, location=None, force_completed=False, mode="list"):
    """
    薄 wrapper：統一入口供 ActionDispatcher 使用。
    - 支援混合範圍（過去→completed_trips；今天/未來→trips）
    - 支援列表查詢（mode="list"）和聚合查詢（mode="aggregate"）
    - 回傳格式：{"text": str, "quick_reply": Optional[obj], "meta": dict}

    🔥 2025-12-17 新增：支援 location 參數，按地點過濾班次
    🔥 2025-12-18 重要修復：支援 force_completed 參數
    🔥 2026-01-06 重要新增：支援 mode 參數，統一處理聚合查詢

    Args:
        mode: "list" 列表查詢（預設）或 "aggregate" 聚合查詢
        force_completed: 若為 True，表示用戶明確指定「已完成」，
                        今天的資料應查 completed_trips 而非 trips

    今天的時間態邊界規則：
    - 今天是一個「流動的邊界」
    - 若有「已完成」關鍵字（force_completed=True）：今天查 completed_trips
    - 若無「已完成」關鍵字（force_completed=False）：今天查 trips

    聚合查詢特性：
    - 只返回統計摘要，不返回班次列表
    - 不保存查詢結果到對話上下文（無分頁）
    - 直接使用 SQL 聚合函數計算
    """
    try:
        if not start_date or not end_date:
            return None

        today = get_taiwan_date()
        meta = {
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d"),
            "driver_id": driver_id,
            "category": category,
            "trip_type": trip_type,
            "location": location,  # 🔥 記錄地點過濾
            "force_completed": force_completed,  # 🔥 記錄是否強制查已完成
            "mode": mode,  # 🔥 記錄查詢模式
        }

        # 🔥 聚合查詢模式：只查詢 completed_trips（已完成班次才有金額統計意義）
        if mode == "aggregate":
            logger.info(f"📊 聚合查詢模式：start={start_date}, end={end_date}, driver={driver_id}, category={category}")

            # 聚合查詢只對過去的已完成班次有意義
            # 如果查詢範圍包含未來，自動截止到今天
            effective_end = min(end_date, today)

            # 執行聚合查詢
            agg_result = query_completed_trips_aggregation(
                start_date, effective_end, driver_id, category, location
            )

            # 格式化聚合摘要
            text = format_aggregation_summary(
                agg_result, start_date, effective_end, driver_id, category, location
            )

            # 聚合查詢不保存到上下文（不支援分頁）
            return {"text": text, "quick_reply": None, "meta": meta}

        # 全過去（end_date < today）
        # 🔥 2026-01-27：添加分頁支持
        if end_date < today:
            from linebot.v3.messaging import QuickReply, QuickReplyItem, MessageAction

            trips = query_completed_trips_range(start_date, end_date, driver_id, category, location=location)
            MAX_DISPLAY = 20

            if len(trips) > MAX_DISPLAY:
                # 結果過多，需要分頁
                # 🔥 先計算全部班次的總金額
                total_fare = 0
                for trip in trips:
                    calculated_total = trip[7]
                    original_total = trip[9]
                    if original_total is not None:
                        total_fare += original_total
                    elif calculated_total is not None:
                        total_fare += calculated_total

                page_info = {'current': 1, 'total_items': len(trips), 'has_more': True, 'total_fare': total_fare}
                text = format_completed_trips_range_result(
                    trips[:MAX_DISPLAY], start_date, end_date, driver_id, category,
                    page_info=page_info, location=location
                )

                # 構建分頁按鈕
                quick_reply_items = [
                    QuickReplyItem(action=MessageAction(
                        label="📄 下一頁",
                        text="下一頁"
                    ))
                ]
                quick_reply = QuickReply(items=quick_reply_items)

                # 保存查詢結果以支持翻頁
                if user_id:
                    from modules.utils.conversation_context import get_conversation_context
                    trips_dict = []
                    for trip in trips:
                        trips_dict.append({
                            'trip_id': trip[0],
                            'date': trip[1].strftime('%Y-%m-%d') if hasattr(trip[1], 'strftime') else str(trip[1]),
                            'start_point': trip[2],
                            'end_point': trip[3],
                            'category': trip[4],
                            'meter_fare': trip[5],
                            'extra_fare': trip[6],
                            'calculated_total': trip[7],
                            'coalesced_total': trip[8],
                            'original_total': trip[9],
                            'driver_id': trip[10],
                            'modification_reason': trip[11],
                            'trip_type': trip[12] if len(trip) > 12 else None
                        })

                    date_str = f"{start_date.month}/{start_date.day}"
                    if start_date != end_date:
                        date_str += f"-{end_date.month}/{end_date.day}"
                    driver_suffix = f" 司機{driver_id}" if driver_id else ""
                    category_suffix = f" {category}" if category else ""

                    context = get_conversation_context(user_id)
                    context.save_query_result(
                        query_type='completed_trips_range',
                        command=f"查已完成範圍 {date_str}{driver_suffix}{category_suffix}",
                        all_results=trips_dict,
                        conditions={
                            'start_date': start_date.strftime('%Y-%m-%d'),
                            'end_date': end_date.strftime('%Y-%m-%d'),
                            'driver_id': driver_id,
                            'category': category,
                            'location': location
                        }
                    )
                    logger.info(f"📱 過去態查詢保存分頁上下文: {len(trips)} 筆")

                return {"text": text, "quick_reply": quick_reply, "meta": meta}
            else:
                # 結果不多，無需分頁
                text = format_completed_trips_range_result(trips, start_date, end_date, driver_id, category, location=location)
                return {"text": text, "quick_reply": None, "meta": meta}

        # 🔥 2025-12-18：force_completed 模式下，全部查 completed_trips
        # （這用於「12/1-12/25 司機61553 診所已完成班次」這類查詢）
        # 🔥 2026-01-27：添加分頁支持
        if force_completed:
            from linebot.v3.messaging import QuickReply, QuickReplyItem, MessageAction

            # 只查到今天為止的已完成班次（未來不可能有已完成）
            effective_end = min(end_date, today)
            trips = query_completed_trips_range(start_date, effective_end, driver_id, category, location=location)
            MAX_DISPLAY = 20

            if len(trips) > MAX_DISPLAY:
                # 結果過多，需要分頁
                # 🔥 先計算全部班次的總金額
                total_fare = 0
                for trip in trips:
                    calculated_total = trip[7]
                    original_total = trip[9]
                    if original_total is not None:
                        total_fare += original_total
                    elif calculated_total is not None:
                        total_fare += calculated_total

                page_info = {'current': 1, 'total_items': len(trips), 'has_more': True, 'total_fare': total_fare}
                text = format_completed_trips_range_result(
                    trips[:MAX_DISPLAY], start_date, effective_end, driver_id, category,
                    page_info=page_info, location=location
                )

                # 構建分頁按鈕
                quick_reply_items = [
                    QuickReplyItem(action=MessageAction(
                        label="📄 下一頁",
                        text="下一頁"
                    ))
                ]
                quick_reply = QuickReply(items=quick_reply_items)

                # 保存查詢結果以支持翻頁
                if user_id:
                    from modules.utils.conversation_context import get_conversation_context
                    trips_dict = []
                    for trip in trips:
                        trips_dict.append({
                            'trip_id': trip[0],
                            'date': trip[1].strftime('%Y-%m-%d') if hasattr(trip[1], 'strftime') else str(trip[1]),
                            'start_point': trip[2],
                            'end_point': trip[3],
                            'category': trip[4],
                            'meter_fare': trip[5],
                            'extra_fare': trip[6],
                            'calculated_total': trip[7],
                            'coalesced_total': trip[8],
                            'original_total': trip[9],
                            'driver_id': trip[10],
                            'modification_reason': trip[11],
                            'trip_type': trip[12] if len(trip) > 12 else None
                        })

                    date_str = f"{start_date.month}/{start_date.day}"
                    if start_date != effective_end:
                        date_str += f"-{effective_end.month}/{effective_end.day}"
                    driver_suffix = f" 司機{driver_id}" if driver_id else ""
                    category_suffix = f" {category}" if category else ""

                    context = get_conversation_context(user_id)
                    context.save_query_result(
                        query_type='completed_trips_range',
                        command=f"查已完成範圍 {date_str}{driver_suffix}{category_suffix}",
                        all_results=trips_dict,
                        conditions={
                            'start_date': start_date.strftime('%Y-%m-%d'),
                            'end_date': effective_end.strftime('%Y-%m-%d'),
                            'driver_id': driver_id,
                            'category': category,
                            'location': location
                        }
                    )
                    logger.info(f"📱 force_completed 查詢保存分頁上下文: {len(trips)} 筆")

                return {"text": text, "quick_reply": quick_reply, "meta": meta}
            else:
                # 結果不多，無需分頁
                text = format_completed_trips_range_result(trips, start_date, effective_end, driver_id, category, location=location)
                return {"text": text, "quick_reply": None, "meta": meta}

        # 全現在/未來（start_date > today，或 start_date == today 且無 force_completed）
        # 🔥 2026-01-12：添加分頁支持
        if start_date >= today:
            from linebot.v3.messaging import QuickReply, QuickReplyItem, MessageAction

            trips = query_current_trips_range(start_date, end_date, driver_id, category, location=location)
            MAX_DISPLAY = 20

            if len(trips) > MAX_DISPLAY:
                # 結果過多，需要分頁
                page_info = {'current': 1, 'total_items': len(trips), 'has_more': True}
                text = format_current_trips_range_result(
                    trips[:MAX_DISPLAY], start_date, end_date, driver_id, category,
                    page_info=page_info, location=location
                )

                # 構建分頁按鈕
                date_str = f"{start_date.month}/{start_date.day}"
                if start_date != end_date:
                    date_str += f"-{end_date.month}/{end_date.day}"
                driver_suffix = f" {driver_id}" if driver_id else ""
                category_suffix = f" {category}" if category else ""

                quick_reply_items = [
                    QuickReplyItem(action=MessageAction(
                        label="📄 下一頁",
                        text="下一頁"
                    ))
                ]
                quick_reply = QuickReply(items=quick_reply_items)

                # 保存查詢結果以支持翻頁
                if user_id:
                    from modules.utils.conversation_context import get_conversation_context
                    trips_dict = []
                    for trip in trips:
                        trips_dict.append({
                            'trip_id': trip[0],
                            'date': trip[1].strftime('%Y-%m-%d') if trip[1] else 'N/A',
                            'time': trip[2],
                            'start_point': trip[3],
                            'end_point': trip[4],
                            'category': trip[5],
                            'driver_id': trip[6],
                            'status': trip[7],
                            'trip_type': trip[8],
                            'passenger_leave_reason': trip[12] if len(trip) > 12 else None
                        })
                    context = get_conversation_context(user_id)
                    context.save_query_result(
                        query_type='current_trips_range',
                        command=f"查班次範圍 {date_str}{driver_suffix}{category_suffix}",
                        all_results=trips_dict,
                        conditions={
                            'start_date': start_date.strftime('%Y-%m-%d'),
                            'end_date': end_date.strftime('%Y-%m-%d'),
                            'driver_id': driver_id,
                            'category': category
                        }
                    )
                    logger.info(f"📱 現在態查詢保存分頁上下文: {len(trips)} 筆")

                return {"text": text, "quick_reply": quick_reply, "meta": meta}
            else:
                # 結果不多，無需分頁
                text = format_current_trips_range_result(trips, start_date, end_date, driver_id, category, location=location)
                return {"text": text, "quick_reply": None, "meta": meta}

        # 混合：拆分為過去 + 現在/未來（start_date < today <= end_date）
        # 🔥 2026-01-06：添加分頁支持，避免消息過長
        from linebot.v3.messaging import QuickReply, QuickReplyItem, MessageAction

        past_end = today - timedelta(days=1)
        completed_part = query_completed_trips_range(start_date, past_end, driver_id, category, location=location)
        current_part = query_current_trips_range(today, end_date, driver_id, category, location=location)

        total_count = len(completed_part) + len(current_part)
        MAX_ITEMS_PER_SECTION = 8  # 每部分最多顯示 8 筆

        # 格式化已完成部分（限制數量）
        completed_display = completed_part[:MAX_ITEMS_PER_SECTION]
        completed_text = format_completed_trips_range_result(
            completed_display, start_date, past_end, driver_id, category, location=location
        )
        if len(completed_part) > MAX_ITEMS_PER_SECTION:
            completed_text += f"\n... 還有 {len(completed_part) - MAX_ITEMS_PER_SECTION} 筆"

        # 格式化現在態部分（限制數量）
        current_display = current_part[:MAX_ITEMS_PER_SECTION]
        current_text = format_current_trips_range_result(
            current_display, today, end_date, driver_id, category, location=location
        )
        if len(current_part) > MAX_ITEMS_PER_SECTION:
            current_text += f"\n... 還有 {len(current_part) - MAX_ITEMS_PER_SECTION} 筆"

        combined = "🔀 混合日期範圍（已完成 + 現在/未來）\n" + "─" * 30
        combined += f"\n📊 共 {total_count} 筆（已完成 {len(completed_part)} + 現在態 {len(current_part)}）"
        combined += f"\n\n【已完成（過去）】\n{completed_text}\n\n【現在/未來（trips）】\n{current_text}"

        # 如果結果被截斷，添加 Quick Reply 按鈕
        has_more = len(completed_part) > MAX_ITEMS_PER_SECTION or len(current_part) > MAX_ITEMS_PER_SECTION
        quick_reply = None

        if has_more:
            combined += f"\n\n💡 點擊下方按鈕分開查詢"

            # 構建查詢命令（加 / 前綴讓群組能識別）
            driver_suffix = f" {driver_id}" if driver_id else ""
            category_suffix = f" {category}" if category else ""

            completed_cmd = f"/查已完成範圍 {start_date.month}/{start_date.day}-{past_end.month}/{past_end.day}{driver_suffix}{category_suffix}"
            current_cmd = f"/查班次範圍 {today.month}/{today.day}-{end_date.month}/{end_date.day}{driver_suffix}{category_suffix}"

            quick_reply_items = []

            # 只有已完成部分有更多時才添加按鈕
            if len(completed_part) > MAX_ITEMS_PER_SECTION:
                quick_reply_items.append(
                    QuickReplyItem(
                        action=MessageAction(
                            label=f"📦 已完成({len(completed_part)}筆)",
                            text=completed_cmd
                        )
                    )
                )

            # 只有現在態部分有更多時才添加按鈕
            if len(current_part) > MAX_ITEMS_PER_SECTION:
                quick_reply_items.append(
                    QuickReplyItem(
                        action=MessageAction(
                            label=f"⚡ 現在態({len(current_part)}筆)",
                            text=current_cmd
                        )
                    )
                )

            if quick_reply_items:
                quick_reply = QuickReply(items=quick_reply_items)
                logger.info(f"📱 混合查詢添加 Quick Reply: {len(quick_reply_items)} 個按鈕")

        return {"text": combined, "quick_reply": quick_reply, "meta": meta}
    except Exception as e:
        logger.error(f"handle_query_trips_range 失敗: {e}")
        return None

def format_completed_trips_range_result(trips, start_date, end_date, driver_id=None, category=None, page_info=None, location=None):
    """
    格式化已完成班次範圍查詢結果
    page_info: {'current': 1, 'total_items': 50, 'has_more': True}
    🔥 2025-12-17 新增：支援 location 參數
    """
    if not trips:
        filter_desc = []
        if driver_id:
            filter_desc.append(f"司機{driver_id}")
        if category:
            filter_desc.append(f"{category}班次")
        if location:
            filter_desc.append(f"地點「{location}」")
        
        filter_text = "、".join(filter_desc) if filter_desc else ""
        
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

def format_current_trips_range_result(trips, start_date, end_date, driver_id=None, category=None, page_info=None, location=None):
    """
    格式化進行中班次範圍查詢結果（統一使用分組格式）
    """
    if not trips:
        filter_desc = []
        if driver_id:
            filter_desc.append(f"司機{driver_id}")
        if category:
            filter_desc.append(f"{category}班次")
        if location:
            filter_desc.append(f"地點「{location}」")
        
        filter_text = "、".join(filter_desc) if filter_desc else ""
        
        return f"""❌ 找不到符合條件的班次

📅 查詢範圍：{start_date.strftime('%Y-%m-%d')} 至 {end_date.strftime('%Y-%m-%d')}
🔍 篩選條件：{filter_text if filter_text else "無"}

💡 建議：
• 確認日期範圍是否正確
• 嘗試擴大查詢範圍
• 檢查司機號碼和類別是否正確"""

    # 統計信息
    total_trips = len(trips)
    max_display = 20
    
    # 建立回應
    lines = []
    lines.append(f"📊 查詢結果 (第 {page_info['current'] if page_info else 1} 頁)")
    lines.append(f"找到 {total_trips} 筆記錄")
    lines.append("")
    
    # 按狀態分組
    status_groups = {}
    for trip in trips:
        # Trip Tuple Mapping:
        # 0:id, 1:date, 2:time, 3:start, 4:end, 5:cat, 6:driver, 7:status, 8:type
        # 9:custom_start, 10:custom_end, 11:custom_via, 12:leave_reason
        
        t_id = trip[0]
        t_date = trip[1]
        t_time = trip[2]
        t_start = trip[3]
        t_end = trip[4]
        t_driver = trip[6]
        t_status = trip[7]
        t_type = trip[8]

        t_custom_start = trip[9] if len(trip) > 9 else None
        t_custom_end = trip[10] if len(trip) > 10 else None
        t_leave_reason = trip[12] if len(trip) > 12 else None

        display_status = t_status
        if t_status == '準備' and t_leave_reason:
            display_status = '請假'

        if display_status not in status_groups:
            status_groups[display_status] = []

        status_groups[display_status].append({
            'id': t_id,
            'date': t_date,
            'time': t_time,
            'driver': t_driver,
            'start': t_custom_start or t_start,
            'end': t_custom_end or t_end,
            'type': t_type
        })

    # Render Groups
    # Order: 準備 -> 請假 -> 待派 -> 其他
    preferred_order = ['準備', '請假', '待派', '已完成', '註銷', '衝突']
    sorted_keys = sorted(status_groups.keys(), key=lambda k: preferred_order.index(k) if k in preferred_order else 99)
    
    for status in sorted_keys:
        group_items = status_groups[status]
        
        # Icons
        icon = "🎯"
        if status == '準備': icon = "🟢"
        elif status == '請假': icon = "🔵"
        elif status == '待派': icon = "🔴"
        elif status == '已完成': icon = "✅"
        elif status == '註銷': icon = "❌"
        elif status == '衝突': icon = "🟠"
        
        lines.append(f"{icon} {status} ({len(group_items)}個) :")
        
        for item in group_items:
            # #1321 12/28 11:50-馬鎮宮->診所|🚕5386
            date_str = item['date'].strftime('%m/%d') if item['date'] else ''
            t_str = item['time'].strftime('%H:%M') if item['time'] else '--:--'
            d_str = f"🚕{item['driver']}" if item['driver'] else "未指派"

            # Format: #ID Date Time-Start->End|Driver
            lines.append(f"#{item['id']} {date_str} ⏰{t_str}-{item['start']}→{item['end']}|{d_str}")
        
        lines.append("")

    # 分頁提示
    if page_info:
        total_items = page_info.get('total_items', total_trips)
        current_page = page_info.get('current', 1)
        has_more = page_info.get('has_more', False)
        
        if has_more:
            # lines.append(f"") # Already added empty line after group
            lines.append(f"📄 第 {current_page} 頁，共 {total_items} 筆")
            lines.append(f"💡 輸入「下一頁」查看更多")
    elif total_trips > max_display:
        lines.append(f"...")
        lines.append(f"還有 {total_trips - max_display} 筆班次未顯示 (此模式無分頁)")
    
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
    
    🔥 2025-12-18 重要修復：
    此函數名稱雖為 current_trips，但實際上會根據日期範圍自動分流到正確的時間態：
    - 過去日期 → completed_trips
    - 今天（無「已完成」關鍵字）→ trips
    - 未來日期 → trips
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
            
            # 2) 現在/未來部分：生產線
            current_part = query_current_trips_range(today, end_date, driver_id, category)
            
            # 3) 統一數據結構以便分頁
            all_results = []
            
            # 處理已完成 (Source: completed)
            for trip in completed_part:
                all_results.append({
                    'id': trip[0],
                    'date': trip[1].strftime('%Y-%m-%d') if trip[1] else 'N/A',
                    'start_point': trip[2],
                    'end_point': trip[3],
                    'category': trip[4],
                    'meter_fare': trip[5], # index 5
                    'driver_id': trip[10], # index 10
                    '_source': 'completed'
                })
                
            # 處理進行中 (Source: current)
            for trip in current_part:
                all_results.append({
                    'id': trip[0],
                    'date': trip[1].strftime('%Y-%m-%d') if trip[1] else 'N/A',
                    'time': trip[2].strftime('%H:%M') if trip[2] else '',
                    'start_point': trip[3],
                    'end_point': trip[4],
                    'category': trip[5],
                    'driver_id': trip[6],
                    'status': trip[7],
                    'passenger_leave_reason': trip[12] if len(trip) > 12 else None,
                    '_source': 'current'
                })
                
            # 4) 保存上下文以支援翻頁
            if user_id and len(all_results) > 10:
                from modules.utils.conversation_context import get_conversation_context
                from linebot.v3.messaging import QuickReply, QuickReplyItem, MessageAction
                
                context = get_conversation_context(user_id)
                context.save_query_result(
                    query_type='hybrid_range', # 新增類型，需要在 pagination_router 處理
                    command=message_text,
                    all_results=all_results,
                    conditions={
                        'start_date': start_date.strftime('%Y-%m-%d'),
                        'end_date': end_date.strftime('%Y-%m-%d')
                    }
                )
                
                # 格式化第一頁 (前10筆)
                result_text = format_hybrid_results(
                    all_results[:10], start_date, end_date, driver_id, category,
                    page_info={'current': 1, 'total_items': len(all_results), 'has_more': True}
                )
                
                quick_reply = QuickReply(items=[
                    QuickReplyItem(action=MessageAction(label="📄 下一頁", text="下一頁")),
                    QuickReplyItem(action=MessageAction(label="🔍 重新查詢", text="重新查詢"))
                ])
                return {'message': result_text, 'quick_reply': quick_reply}
            
            else:
                # 無需分頁，直接全顯示
                return format_hybrid_results(all_results, start_date, end_date, driver_id, category)
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
                        'trip_type': trip[8],
                        'passenger_leave_reason': trip[12] if len(trip) > 12 else None
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

def format_hybrid_results(items, start_date, end_date, driver_id=None, category=None, page_info=None):
    """
    格式化混合查詢結果 (Completed + Current)
    items: list of dicts (normalized)
    """
    lines = []
    
    total_count = page_info.get('total_items', len(items)) if page_info else len(items)
    lines.append(f"📊 混合查詢結果 (第 {page_info['current'] if page_info else 1} 頁)")
    lines.append(f"📅 範圍：{start_date.strftime('%m/%d')} - {end_date.strftime('%m/%d')}，共 {total_count} 筆")
    lines.append("─" * 30)
    
    # Split by source
    completed_items = [i for i in items if i.get('_source') == 'completed']
    current_items = [i for i in items if i.get('_source') == 'current']
    
    # 1. Render Completed (Grouped by Date)
    if completed_items:
        lines.append("【已完成 (過去)】")
        
        # Group by date
        comp_by_date = {}
        for item in completed_items:
            d = item.get('date', 'N/A')
            if d not in comp_by_date:
                comp_by_date[d] = []
            comp_by_date[d].append(item)
            
        # Render groups
        for d in sorted(comp_by_date.keys()):
            lines.append(f"📅 {d}")
            group = comp_by_date[d]
            for item in group:
                # Completed Style: #ID Driver Start->End $Fare
                fare = item.get('meter_fare', 0) or 0
                lines.append(f"#{item['id']} 🚗{item.get('driver_id')} {item['start_point']}→{item['end_point']} ${fare}")
            # Space between date groups? Maybe not needed for compactness in hybrid view
            # lines.append("") 
        
        lines.append("")
        
    # 2. Render Current (Grouped by Status)
    if current_items:
        lines.append("【進行中 (現在/未來)】")
        
        status_groups = {}
        for item in current_items:
            # Extract info
            t_status = item.get('status', '未知')
            if item.get('passenger_leave_reason'):
                t_status = '請假'
            
            # Check for leave (not explicitly stored in normalized dict? 
            # In handle_query_current_trips_range, we didn't store passenger_leave_reason in the normalized dict!
            # We must assume status from DB is enough or update normalization logic.
            # For now, use raw status. 
            # Wait, user screenshot showed specific Leave handling.
            # If I want Leave detection here, I need to check if 'status' has extra info or update normalization.
            # Let's check `handle_query_current_trips_range` normalization again?
            # It just saved 'status': trip[7].
            # It didn't save leave reason.
            # So "請假" might be missed if it's just "準備" + Reason.
            # *Self-correction*: I should update `handle_query_current_trips_range` to inject a better status 
            # or save leave reason. But for now, I will stick to formatting what I have.
            # If `item['status']` is '請假', it works. If it relied on reason... 
            # Let's just group by `t_status`.
            
            if t_status not in status_groups:
                status_groups[t_status] = []
            status_groups[t_status].append(item)
            
        # Render Groups
        preferred_order = ['準備', '請假', '待派', '已完成', '註銷', '衝突']
        sorted_keys = sorted(status_groups.keys(), key=lambda k: preferred_order.index(k) if k in preferred_order else 99)
        
        for status in sorted_keys:
            group = status_groups[status]
            icon = "🎯"
            if status == '準備': icon = "🟢"
            elif status == '請假': icon = "🔵"
            elif status == '待派': icon = "🔴"
            elif status == '已完成': icon = "✅"
            elif status == '註銷': icon = "❌"
            elif status == '衝突': icon = "🟠"
            
            lines.append(f"{icon} {status} ({len(group)}個) :")
            for item in group:
                # #ID Date Time Start->End|Driver
                # Time is string HH:MM
                t_str = item.get('time', '--:--')
                d_str = f"🚕{item.get('driver_id')}" if item.get('driver_id') else "未指派"
                
                # 🔥 Add simple date prefix like "12/31"
                date_full = item.get('date', '') # Expect YYYY-MM-DD
                simple_date = ""
                if date_full and len(date_full) >= 10:
                    try:
                        # Extract 12-31 from 2025-12-31, replace - with /
                        simple_date = date_full[5:].replace('-', '/') + " "
                    except: 
                        pass
                
                lines.append(f"#{item['id']} {simple_date}⏰{t_str}-{item.get('start_point')}→{item.get('end_point')}|{d_str}")
            lines.append("")

    # Pagination Footer
    if page_info and page_info.get('has_more'):
        lines.append(f"📄 第 {page_info['current']} 頁")
        lines.append("💡 輸入「下一頁」查看更多")
        
    return "\n".join(lines)
