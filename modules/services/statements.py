"""
月結單數據服務模組
處理月結單相關的數據查詢和計算
"""

import logging
from datetime import date, datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from zoneinfo import ZoneInfo
from sqlalchemy import text

from modules.models.base import db
from modules.utils.taiwan_time import get_taiwan_date

logger = logging.getLogger(__name__)

@dataclass
class StatementData:
    """月結單數據結構"""
    total_month: int  # 月總額
    deposits: List[Dict[str, Any]]  # 入金清單
    last4_common: str  # 最常出現的銀行帳戶後四碼
    drivers_top3: List[Tuple[str, int]]  # 司機前3名 (姓名, 金額)
    drivers_other_amt: int  # 其他司機金額
    rides_count: int  # 配班總數
    missing_amount_count: int  # 無金額紀錄筆數
    diff: int  # 對帳差額

def build_monthly_statement_cover(month: date) -> StatementData:
    """
    建立月結單封面數據
    
    Args:
        month: 目標月份 (例如: date(2025, 7, 1))
        
    Returns:
        StatementData: 月結單數據
    """
    try:
        # 計算期間邊界 (Asia/Taipei)
        start_date = month.replace(day=1)
        if month.month == 12:
            end_date = month.replace(year=month.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            end_date = month.replace(month=month.month + 1, day=1) - timedelta(days=1)
        
        # 轉換為台北時區的開始和結束時間
        start_datetime = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=ZoneInfo("Asia/Taipei"))
        end_datetime = datetime.combine(end_date, datetime.max.time()).replace(tzinfo=ZoneInfo("Asia/Taipei"))
        
        logger.info(f"計算月結單數據，期間: {start_datetime} 至 {end_datetime}")
        
        # A. 月總額 (account_ledger weekly_charge)
        total_month = _get_monthly_total(start_datetime, end_datetime)
        
        # B. 入金清單
        deposits = _get_deposits(start_datetime, end_datetime)
        last4_common = _get_most_common_last4(deposits)
        
        # C. 司機小計與配班次
        drivers_data = _get_drivers_summary(start_date, end_date)
        drivers_top3 = drivers_data['top3']
        drivers_other_amt = drivers_data['other_amt']
        rides_count = drivers_data['rides_count']
        missing_amount_count = drivers_data['missing_amount_count']
        
        # D. 對帳差額
        drivers_total = sum(amt for _, amt in drivers_top3) + drivers_other_amt
        diff = drivers_total - total_month
        
        return StatementData(
            total_month=total_month,
            deposits=deposits,
            last4_common=last4_common,
            drivers_top3=drivers_top3,
            drivers_other_amt=drivers_other_amt,
            rides_count=rides_count,
            missing_amount_count=missing_amount_count,
            diff=diff
        )
        
    except Exception as e:
        logger.error(f"建立月結單數據失敗: {str(e)}", exc_info=True)
        raise

def _get_monthly_total(start_datetime: datetime, end_datetime: datetime) -> int:
    """獲取月總額 (使用與現有診所班次加總完全一致的邏輯)"""
    try:
        # 使用與現有診所班次加總完全一致的查詢邏輯
        query = text("""
            SELECT COALESCE(SUM(COALESCE(ct.meter_fare, 0) + COALESCE(ct.extra_fare, 0)), 0) as total
            FROM completed_trips ct
            WHERE ct.date >= :start_date 
              AND ct.date <= :end_date
              AND ct.category = '診所'
        """)
        
        # 轉換為日期格式（去掉時區信息）
        start_date = start_datetime.date()
        end_date = end_datetime.date()
        
        result = db.session.execute(query, {
            'start_date': start_date,
            'end_date': end_date
        }).fetchone()
        
        total = int(result[0]) if result and result[0] else 0
        logger.info(f"月總額 (診所班次加總): {total:,}")
        return total
        
    except Exception as e:
        logger.error(f"查詢月總額失敗: {str(e)}")
        return 0

def _get_deposits(start_datetime: datetime, end_datetime: datetime) -> List[Dict[str, Any]]:
    """獲取入金清單 (最多5筆)"""
    try:
        query = text("""
            SELECT occurred_at, amount_in, bank_name, bank_account_last4
            FROM account_ledger 
            WHERE type = 'deposit' 
              AND occurred_at >= :start_time 
              AND occurred_at <= :end_time
            ORDER BY occurred_at ASC 
            LIMIT 5
        """)
        
        result = db.session.execute(query, {
            'start_time': start_datetime,
            'end_time': end_datetime
        }).fetchall()
        
        deposits = []
        for row in result:
            deposits.append({
                'occurred_at': row[0],
                'amount_in': int(row[1]) if row[1] else 0,
                'bank_name': row[2] or '',
                'bank_account_last4': row[3] or ''
            })
        
        logger.info(f"找到 {len(deposits)} 筆入金記錄")
        return deposits
        
    except Exception as e:
        logger.error(f"查詢入金清單失敗: {str(e)}")
        return []

def _get_most_common_last4(deposits: List[Dict[str, Any]]) -> str:
    """獲取最常出現的銀行帳戶後四碼"""
    if not deposits:
        return "＊＊＊＊"
    
    last4_counts = {}
    for deposit in deposits:
        last4 = deposit.get('bank_account_last4', '')
        if last4:
            last4_counts[last4] = last4_counts.get(last4, 0) + 1
    
    if not last4_counts:
        return "＊＊＊＊"
    
    # 返回出現次數最多的後四碼
    most_common = max(last4_counts.items(), key=lambda x: x[1])[0]
    return most_common

def _get_drivers_summary(start_date: date, end_date: date) -> Dict[str, Any]:
    """獲取司機小計與配班次統計"""
    try:
        # 查詢司機金額統計
        query = text("""
            SELECT 
                d.name as driver_name,
                COALESCE(SUM(ct.meter_fare + COALESCE(ct.extra_fare, 0)), 0) as total_amount
            FROM completed_trips ct
            LEFT JOIN drivers d ON ct.driver_id = d.id
            WHERE ct.date >= :start_date 
              AND ct.date <= :end_date
              AND ct.category = '診所'
            GROUP BY d.id, d.name
            ORDER BY total_amount DESC
        """)
        
        result = db.session.execute(query, {
            'start_date': start_date,
            'end_date': end_date
        }).fetchall()
        
        # 處理司機數據
        drivers_data = [(row[0] or f"司機{row[1]}", int(row[1])) for row in result]
        
        # 取前3名，其餘歸為"其他"
        top3 = drivers_data[:3]
        other_amt = sum(amt for _, amt in drivers_data[3:])
        
        # 查詢配班總數
        rides_query = text("""
            SELECT COUNT(*) as rides_count
            FROM completed_trips 
            WHERE date >= :start_date 
              AND date <= :end_date
              AND category = '診所'
        """)
        
        rides_result = db.session.execute(rides_query, {
            'start_date': start_date,
            'end_date': end_date
        }).fetchone()
        
        rides_count = int(rides_result[0]) if rides_result and rides_result[0] else 0
        
        # 查詢無金額紀錄筆數
        missing_query = text("""
            SELECT COUNT(*) as missing_count
            FROM completed_trips 
            WHERE date >= :start_date 
              AND date <= :end_date
              AND category = '診所'
              AND (meter_fare IS NULL OR meter_fare = 0)
        """)
        
        missing_result = db.session.execute(missing_query, {
            'start_date': start_date,
            'end_date': end_date
        }).fetchone()
        
        missing_amount_count = int(missing_result[0]) if missing_result and missing_result[0] else 0
        
        logger.info(f"司機統計: 前3名 {len(top3)} 人, 其他 {other_amt:,}, 配班總數 {rides_count}, 無金額 {missing_amount_count}")
        
        return {
            'top3': top3,
            'other_amt': other_amt,
            'rides_count': rides_count,
            'missing_amount_count': missing_amount_count
        }
        
    except Exception as e:
        logger.error(f"查詢司機統計失敗: {str(e)}")
        return {
            'top3': [],
            'other_amt': 0,
            'rides_count': 0,
            'missing_amount_count': 0
        }