"""
Google Sheets 服務模組
處理Google Sheets的創建、格式化和數據寫入
"""

import logging
import os
import tempfile
from datetime import date
from typing import Optional, Dict, Any

import gspread
from google.oauth2 import service_account

from modules.services.statements import StatementData, build_monthly_statement_cover
from modules.services.sheets_writer import write_statement_cover

logger = logging.getLogger(__name__)

def get_google_sheets_service():
    """獲取Google Sheets服務並認證"""
    SCOPES = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]
    
    try:
        # 首先嘗試使用Secret File
        secret_file_path = '/etc/secrets/credentials.json'
        if os.path.exists(secret_file_path):
            logger.info(f"使用Secret File: {secret_file_path}")
            credentials = service_account.Credentials.from_service_account_file(
                secret_file_path, scopes=SCOPES)
            gc = gspread.authorize(credentials)
            return gc
        
        # 如果Secret File不存在，嘗試從環境變量獲取
        logger.info("Secret File不存在，嘗試從環境變量獲取憑證")
        creds_json = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS_JSON')
        
        if creds_json:
            # 使用環境變量中的憑證內容（適用於Render部署）
            # 創建臨時文件
            fd, path = tempfile.mkstemp()
            try:
                with os.fdopen(fd, 'w') as tmp:
                    tmp.write(creds_json)
                credentials = service_account.Credentials.from_service_account_file(
                    path, scopes=SCOPES)
                gc = gspread.authorize(credentials)
                return gc
            finally:
                # 確保臨時文件被刪除
                os.remove(path)
        else:
            # 本地開發使用本地憑證文件
            service_account_file = 'plucky-mile-456412-p0-ad63114b0da5.json'
            if not os.path.exists(service_account_file):
                logger.error(f"找不到服務帳戶金鑰文件: {service_account_file}")
                return None
                
            credentials = service_account.Credentials.from_service_account_file(
                service_account_file, scopes=SCOPES)
            gc = gspread.authorize(credentials)
            return gc
    except Exception as e:
        logger.error(f"Google Sheets認證失敗: {str(e)}")
        return None

def create_monthly_statement_sheet(month: date, category: str = "診所") -> Optional[str]:
    """
    創建月結單Google Sheets
    
    Args:
        month: 目標月份
        category: 班次類別
        
    Returns:
        str: Google Sheets URL，失敗返回None
    """
    try:
        # 獲取Google Sheets服務
        gc = get_google_sheets_service()
        if not gc:
            logger.error("無法連接到Google Sheets服務")
            return None
        
        # 生成結單號碼
        stmt_no = f"STMT-{month.strftime('%Y%m')}"
        
        # 創建新的試算表
        sheet_title = f"派班系統月結單_{month.strftime('%Y%m')}_{category}"
        spreadsheet = gc.create(sheet_title)
        
        # 獲取第一個工作表並重命名為"月結單封面"
        worksheet = spreadsheet.sheet1
        worksheet.update_title("月結單封面")
        
        # 建立月結單數據
        statement_data = build_monthly_statement_cover(month)
        
        # 寫入月結單封面
        success = write_statement_cover(worksheet, statement_data, month, stmt_no)
        if not success:
            logger.error("寫入月結單封面失敗")
            return None
        
        # 創建其他工作表（司機統計、車資趨勢等）
        _create_additional_worksheets(spreadsheet, month, category, statement_data)
        
        # 設置分享權限
        spreadsheet.share('', perm_type='anyone', role='reader')
        
        # 返回試算表URL
        spreadsheet_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet.id}"
        logger.info(f"月結單試算表創建成功: {spreadsheet_url}")
        
        return spreadsheet_url
        
    except Exception as e:
        logger.error(f"創建月結單試算表失敗: {str(e)}", exc_info=True)
        return None

def _create_additional_worksheets(spreadsheet, month: date, category: str, statement_data: StatementData):
    """創建其他工作表（司機統計、車資趨勢等）"""
    try:
        # 創建司機統計工作表
        driver_sheet = spreadsheet.add_worksheet(title="司機統計", rows=100, cols=10)
        _populate_driver_statistics(driver_sheet, month, category, statement_data)
        
        # 創建車資趨勢工作表
        trend_sheet = spreadsheet.add_worksheet(title="車資趨勢", rows=100, cols=10)
        _populate_fare_trends(trend_sheet, month, category)
        
        logger.info("其他工作表創建完成")
        
    except Exception as e:
        logger.error(f"創建其他工作表失敗: {str(e)}")

def _populate_driver_statistics(sheet, month: date, category: str, statement_data: StatementData):
    """填充司機統計數據"""
    try:
        # 標題
        sheet.update('A1', [['司機統計報表']])
        sheet.update('A2', [['月份', f"{month.year}年{month.month}月"]])
        sheet.update('A3', [['類別', category]])
        
        # 司機排名
        sheet.update('A5', [['司機排名']])
        sheet.update('A6', [['排名', '司機姓名', '金額']])
        
        row = 7
        for i, (name, amount) in enumerate(statement_data.drivers_top3, 1):
            sheet.update(f'A{row}', [[i, name, amount]])
            row += 1
        
        if statement_data.drivers_other_amt > 0:
            sheet.update(f'A{row}', [['其他', '其他司機', statement_data.drivers_other_amt]])
        
        # 格式化
        sheet.format('A1', {'textFormat': {'bold': True, 'fontSize': 14}})
        sheet.format('A6:C6', {'textFormat': {'bold': True}})
        
    except Exception as e:
        logger.error(f"填充司機統計失敗: {str(e)}")

def _populate_fare_trends(sheet, month: date, category: str):
    """填充車資趨勢數據"""
    try:
        # 標題
        sheet.update('A1', [['車資趨勢分析']])
        sheet.update('A2', [['月份', f"{month.year}年{month.month}月"]])
        sheet.update('A3', [['類別', category]])
        
        # 這裡可以添加更詳細的趨勢分析
        sheet.update('A5', [['趨勢分析功能開發中...']])
        
        # 格式化
        sheet.format('A1', {'textFormat': {'bold': True, 'fontSize': 14}})
        
    except Exception as e:
        logger.error(f"填充車資趨勢失敗: {str(e)}")