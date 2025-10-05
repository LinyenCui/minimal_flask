"""
Google Sheets 寫入服務模組
處理月結單封面的Google Sheets格式化和寫入
"""

import logging
from datetime import date, datetime, timedelta
from typing import List, Dict, Any, Optional
from zoneinfo import ZoneInfo

from modules.services.statements import StatementData

logger = logging.getLogger(__name__)

def write_statement_cover(sheet, data: StatementData, month: date, stmt_no: str) -> bool:
    """
    寫入月結單封面到Google Sheets
    
    Args:
        sheet: Google Sheets工作表對象
        data: 月結單數據
        month: 目標月份
        stmt_no: 結單號碼
        
    Returns:
        bool: 是否成功
    """
    try:
        # 清空現有內容
        sheet.clear()
        
        # 設定列寬
        _set_column_widths(sheet)
        
        # 寫入標題
        _write_header(sheet, month, stmt_no)
        
        # 寫入左側資訊區
        _write_left_info(sheet, data, month)
        
        # 寫入右側金額區
        _write_right_amounts(sheet, data)
        
        # 寫入底部摘要
        _write_bottom_summary(sheet, data)
        
        # 寫入說明
        _write_footer(sheet)
        
        logger.info("月結單封面寫入完成")
        return True
        
    except Exception as e:
        logger.error(f"寫入月結單封面失敗: {str(e)}", exc_info=True)
        return False

def _set_column_widths(sheet):
    """設定列寬"""
    try:
        # 設定列寬 (A=44, B=22, C=18, D=22, E=18, F=22)
        sheet.format('A:A', {'columnWidth': 44})
        sheet.format('B:B', {'columnWidth': 22})
        sheet.format('C:C', {'columnWidth': 18})
        sheet.format('D:D', {'columnWidth': 22})
        sheet.format('E:E', {'columnWidth': 18})
        sheet.format('F:F', {'columnWidth': 22})
    except Exception as e:
        logger.warning(f"設定列寬失敗: {str(e)}")

def _write_header(sheet, month: date, stmt_no: str):
    """寫入標題區域"""
    try:
        # 標題 "派班系統 月結單"
        sheet.update('A1', [['派班系統 月結單']])
        sheet.format('A1', {
            'textFormat': {'bold': True, 'fontSize': 18},
            'horizontalAlignment': 'LEFT'
        })
        
        # 結單號碼 (右上角)
        sheet.update('F1', [[f'結單號碼：{stmt_no}']])
        sheet.format('F1', {
            'textFormat': {'fontSize': 10},
            'horizontalAlignment': 'RIGHT'
        })
        
    except Exception as e:
        logger.error(f"寫入標題失敗: {str(e)}")

def _write_left_info(sheet, data: StatementData, month: date):
    """寫入左側資訊區"""
    try:
        # 付款人
        sheet.update('A3', [['付款人']])
        sheet.update('B3', [['達恩診所']])
        
        # 帳戶
        sheet.update('A4', [['帳戶']])
        account_info = f"{data.deposits[0].get('bank_name', '')} ＊＊＊＊{data.last4_common}" if data.deposits else "＊＊＊＊"
        sheet.update('B4', [[account_info]])
        
        # 期間
        sheet.update('A6', [['期間']])
        period_text = f"{month.year}年{month.month}月1日 – {month.year}年{month.month}月{_get_last_day_of_month(month)}日"
        sheet.update('B6', [[period_text]])
        
        # 入金紀錄
        sheet.update('A8', [['入金紀錄']])
        if data.deposits:
            for i, deposit in enumerate(data.deposits[:5]):  # 最多5筆
                row = 9 + i
                occurred_at = deposit['occurred_at']
                if isinstance(occurred_at, str):
                    # 如果是字符串，嘗試解析
                    try:
                        occurred_at = datetime.fromisoformat(occurred_at.replace('Z', '+00:00'))
                    except:
                        occurred_at = datetime.now()
                
                # 轉換為台北時區
                if occurred_at.tzinfo is None:
                    occurred_at = occurred_at.replace(tzinfo=ZoneInfo("Asia/Taipei"))
                else:
                    occurred_at = occurred_at.astimezone(ZoneInfo("Asia/Taipei"))
                
                time_str = occurred_at.strftime('%Y/%m/%d %H:%M')
                amount_str = f"NT${deposit['amount_in']:,}"
                bank_info = deposit.get('bank_account_last4', '')
                deposit_text = f"{time_str}  {amount_str}（{bank_info}）"
                
                sheet.update(f'A{row}', [[deposit_text]])
        else:
            sheet.update('A9', [['本月無入金紀錄']])
        
        # 格式化左側標籤
        sheet.format('A3:A8', {
            'textFormat': {'fontSize': 11, 'bold': True},
            'horizontalAlignment': 'LEFT'
        })
        
    except Exception as e:
        logger.error(f"寫入左側資訊失敗: {str(e)}")

def _write_right_amounts(sheet, data: StatementData):
    """寫入右側金額區"""
    try:
        # 總金額標籤
        sheet.update('D3', [['總金額 (TWD)']])
        sheet.format('D3', {
            'textFormat': {'fontSize': 10},
            'horizontalAlignment': 'LEFT'
        })
        
        # 總金額 (大數字)
        total_text = f"NT$ {data.total_month:,}"
        sheet.update('D4', [[total_text]])
        sheet.format('D4:F7', {
            'textFormat': {'bold': True, 'fontSize': 26},
            'horizontalAlignment': 'CENTER',
            'verticalAlignment': 'MIDDLE'
        })
        
        # 合併儲存格
        sheet.merge_cells('D4:F7')
        
        # 期間彙總標籤
        sheet.update('D8', [['期間彙總']])
        sheet.format('D8', {
            'textFormat': {'fontSize': 10, 'bold': True},
            'horizontalAlignment': 'LEFT'
        })
        
    except Exception as e:
        logger.error(f"寫入右側金額失敗: {str(e)}")

def _write_bottom_summary(sheet, data: StatementData):
    """寫入底部摘要"""
    try:
        row = 9
        
        # 司機小計
        if data.drivers_top3:
            driver_texts = []
            for name, amount in data.drivers_top3:
                driver_texts.append(f"{name} {amount:,}")
            
            if data.drivers_other_amt > 0:
                driver_texts.append(f"其他 {data.drivers_other_amt:,}")
            
            driver_summary = "｜".join(driver_texts)
            sheet.update(f'D{row}', [[f"小計（司機）：{driver_summary}"]])
            row += 1
        
        # 配班次和無金額紀錄
        summary_text = f"配班次：{data.rides_count}    無金額紀錄：{data.missing_amount_count}"
        sheet.update(f'D{row}', [[summary_text]])
        row += 1
        
        # 對帳差額提醒
        if data.diff != 0:
            diff_text = f"注意：對帳差額 NT$ {data.diff:,}"
            sheet.update(f'D{row}', [[diff_text]])
            sheet.format(f'D{row}', {
                'textFormat': {'fontSize': 9, 'foregroundColor': {'red': 1, 'green': 0, 'blue': 0}},
                'horizontalAlignment': 'LEFT'
            })
        
        # 格式化摘要區域
        sheet.format(f'D9:D{row}', {
            'textFormat': {'fontSize': 10},
            'horizontalAlignment': 'LEFT'
        })
        
    except Exception as e:
        logger.error(f"寫入底部摘要失敗: {str(e)}")

def _write_footer(sheet):
    """寫入底部說明"""
    try:
        sheet.update('A15', [['說明：系統會自對應銀行帳戶扣除本月費用；此頁為彙整封面。']])
        sheet.format('A15', {
            'textFormat': {'fontSize': 9, 'foregroundColor': {'red': 0.5, 'green': 0.5, 'blue': 0.5}},
            'horizontalAlignment': 'LEFT'
        })
    except Exception as e:
        logger.error(f"寫入底部說明失敗: {str(e)}")

def _get_last_day_of_month(month: date) -> int:
    """獲取月份的最後一天"""
    if month.month == 12:
        next_month = month.replace(year=month.year + 1, month=1, day=1)
    else:
        next_month = month.replace(month=month.month + 1, day=1)
    
    last_day = next_month - timedelta(days=1)
    return last_day.day