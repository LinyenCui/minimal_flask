"""
查询路由决策器 - 统一查询路径
只做决策，不执行查询
"""
from dataclasses import dataclass
from datetime import date
from typing import Optional, Literal, Dict, Any
import logging
import re

logger = logging.getLogger(__name__)

QueryTable = Literal["trips", "completed_trips"]
QueryMode = Literal["list", "aggregate"]

@dataclass(frozen=True)
class QueryRoute:
    """查询路由决策结果"""
    is_direct_query: bool  # 是否为直接查询（非智能助手）
    table: Optional[QueryTable]  # 查询哪个表
    mode: Optional[QueryMode]  # 列表还是聚合
    handler: Optional[str]  # 应该调用的 handler/service
    parsed: Dict[str, Any]  # 解析出的参数
    reason: str  # 决策原因（用于调试）


def decide_query_route(message_text: str, today: date = None) -> QueryRoute:
    """
    统一查询路由决策

    Args:
        message_text: 用户输入的消息文本
        today: 当前日期（用于测试）

    Returns:
        QueryRoute: 路由决策结果
    """
    if today is None:
        from datetime import date as date_cls
        today = date_cls.today()

    # 检查是否为聚合查询
    is_aggregation = any(kw in message_text for kw in
                        ['金額加總', '加總', '合計', '總額', '總和', '總計', '統計金額', '統計'])

    # 解析日期
    parsed = _parse_query_params(message_text, today)

    if not parsed.get('has_date'):
        # 没有日期，不是直接查询
        return QueryRoute(
            is_direct_query=False,
            table=None,
            mode=None,
            handler="smart_assistant",
            parsed=parsed,
            reason="无日期，走智能助手"
        )

    # 判断查询哪个表
    table = _determine_table(parsed, message_text, today)
    mode = "aggregate" if is_aggregation else "list"

    return QueryRoute(
        is_direct_query=True,
        table=table,
        mode=mode,
        handler="date_range_query_service",
        parsed=parsed,
        reason=f"日期查询: {table}, {mode}"
    )


def _parse_query_params(text: str, today: date) -> Dict[str, Any]:
    """解析查询参数"""
    params = {
        'has_date': False,
        'start_date': None,
        'end_date': None,
        'driver_id': None,
        'category': None,
        'location': None,
        'has_completed_keyword': '已完成' in text
    }

    # 解析日期范围
    range_match = re.search(r'(\d{1,2})[/\-](\d{1,2})[~\-至到](\d{1,2})[/\-](\d{1,2})', text)
    if range_match:
        start_month, start_day = int(range_match.group(1)), int(range_match.group(2))
        end_month, end_day = int(range_match.group(3)), int(range_match.group(4))

        year = today.year
        current_month = today.month
        start_year = year
        end_year = year

        # 智能年份判断
        # 1. 如果现在是1-3月，且开始月份是10-12月，说明是去年
        if current_month <= 3 and start_month >= 10:
            start_year = year - 1
            # 如果结束月份也是10-12月，也应该是去年
            if end_month >= 10:
                end_year = year - 1

        # 2. 如果开始月份 > 结束月份，说明跨年
        if start_month > end_month:
            end_year = start_year + 1

        try:
            params['start_date'] = date(start_year, start_month, start_day)
            params['end_date'] = date(end_year, end_month, end_day)
            params['has_date'] = True
        except ValueError:
            pass

    # 解析单一日期
    if not params['has_date']:
        single_match = re.search(r'(\d{1,2})[/\-](\d{1,2})', text)
        if single_match:
            month, day = int(single_match.group(1)), int(single_match.group(2))
            year = today.year
            current_month = today.month

            if current_month <= 3 and month >= 10:
                year = year - 1

            try:
                query_date = date(year, month, day)
                params['start_date'] = query_date
                params['end_date'] = query_date
                params['has_date'] = True
            except ValueError:
                pass

    # 解析司机
    driver_match = re.search(r'司機(\d+)', text)
    if driver_match:
        params['driver_id'] = int(driver_match.group(1))

    # 解析类别
    if '診所' in text:
        params['category'] = '診所'
    elif '東洋' in text:
        params['category'] = '東洋'
    elif '臨時' in text:
        params['category'] = '臨時'

    # 解析地点（移除已知关键字后的剩余）
    location = _extract_location(text)
    if location:
        params['location'] = location

    return params


def _determine_table(parsed: Dict[str, Any], text: str, today: date) -> QueryTable:
    """判断应该查询哪个表"""
    if not parsed.get('start_date') or not parsed.get('end_date'):
        return "trips"

    end_date = parsed['end_date']
    has_completed = parsed.get('has_completed_keyword', False)

    # 结束日期在过去 -> completed_trips
    if end_date < today:
        return "completed_trips"

    # 包含今天或未来，但有"已完成"关键字 -> completed_trips
    if has_completed:
        return "completed_trips"

    # 其他情况 -> trips
    return "trips"


def _extract_location(text: str) -> Optional[str]:
    """提取地点关键字"""
    remaining = text

    # 移除命令前缀
    prefixes = ['查詢班次', '查已完成', '統計金額', '查']
    for prefix in prefixes:
        remaining = remaining.replace(prefix, '')

    # 移除日期
    remaining = re.sub(r'\d{1,2}[/\-]\d{1,2}', '', remaining)

    # 移除司机、类别
    remaining = re.sub(r'司機\d+', '', remaining)
    for cat in ['診所', '東洋', '臨時']:
        remaining = remaining.replace(cat, '')

    # 移除聚合关键字
    for kw in ['金額加總', '加總', '合計', '總額', '班次', '範圍']:
        remaining = remaining.replace(kw, '')

    remaining = remaining.strip()

    if remaining and len(remaining) >= 2:
        return remaining

    return None
