"""
報表生成服務模組 - 負責生成週報表並上傳到 Google Drive
"""
import os
import logging
from datetime import datetime, timedelta
import pandas as pd
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from flask import current_app
from sqlalchemy import text
from modules.utils.taiwan_time import get_taiwan_time, get_taiwan_date

# 從模型模組導入數據庫連接
from modules.models.base import db

# 導入Google Drive服務
from modules.services.drive_service import upload_file_to_drive

# 建立日誌記錄器
logger = logging.getLogger(__name__)

def generate_weekly_report(category=None):
    """
    生成上週的班次報表
    
    Args:
        category: 選擇性的班次類別過濾（例如"診所"或"東洋"）
        
    Returns:
        tuple: (結果消息, 生成的文件名)
    """
    try:
        # 獲取日期範圍
        today = get_taiwan_date()
        days_since_sunday = today.weekday() + 1 if today.weekday() < 6 else 0
        last_sunday = today - timedelta(days=days_since_sunday + 7)
        last_saturday = last_sunday + timedelta(days=6)
        
        logger.info(f"生成週報表，日期範圍: {last_sunday} 至 {last_saturday}")
        
        # 查詢數據
        query_params = {
            "start_date": last_sunday,
            "end_date": last_saturday
        }
        
        query = """
        SELECT 
            ct.id,
            ct.date, 
            ct.start_point, 
            ct.via_point, 
            ct.end_point, 
            ct.meter_fare, 
            ct.extra_fare,
            COALESCE(ct.meter_fare, 0) + COALESCE(ct.extra_fare, 0) as actual_fare,
            ct.driver_id
        FROM 
            completed_trips ct
        WHERE 
            ct.date >= :start_date AND ct.date <= :end_date
        """
        
        if category:
            if category != "全部":  # 如果不是"全部"，則按類別過濾
                query += " AND ct.category = :category"
                query_params["category"] = category
            logger.info(f"使用類別過濾: {category}")
            
        query += " ORDER BY ct.date, ct.id"
        
        with db.engine.connect() as conn:
            result = conn.execute(text(query), query_params)
            completed_trips = result.fetchall()
        
        if not completed_trips:
            category_text = f"類別「{category}」的" if category and category != "全部" else ""
            logger.warning(f"上周沒有{category_text}已完成的班次")
            return f"上周沒有{category_text}已完成的班次。", None
        
        logger.info(f"找到 {len(completed_trips)} 條班次記錄")
        
        # 創建DataFrame
        df = pd.DataFrame(completed_trips)
        df.columns = ['ID', '日期', '起點', '途經點', '終點', '錶價', '加成', '實收', '司機編號']
        
        # 處理日期和星期
        df['日期'] = pd.to_datetime(df['日期'])
        weekday_map = {0: '一', 1: '二', 2: '三', 3: '四', 4: '五', 5: '六', 6: '日'}
        df['星期'] = df['日期'].dt.dayofweek.map(weekday_map)
        df['日期'] = df['日期'].dt.strftime('%Y-%m-%d')
        
        # 重排列順序
        df = df[['ID', '日期', '星期', '起點', '途經點', '終點', '司機編號', '錶價', '加成', '實收']]
        
        # 計算總計
        total_meter_fare = df['錶價'].sum()
        total_extra_fare = df['加成'].sum() if df['加成'].notna().any() else 0
        total_actual_fare = df['實收'].sum()
        
        # 按司機分組統計
        driver_stats = df.groupby('司機編號').agg({
            'ID': 'count',
            '實收': 'sum'
        }).reset_index()
        driver_stats.columns = ['司機編號', '班次數', '金額']
        
        # 創建Excel文件
        report_date = get_taiwan_date().strftime('%Y%m%d')
        category_suffix = f"_{category}" if category and category != "全部" else ""
        filename = f"weekly_report{category_suffix}_{report_date}.xlsx"
        
        # 直接使用 openpyxl 創建工作簿
        workbook = openpyxl.Workbook()
        worksheet = workbook.active
        worksheet.title = '班次詳情'
        
        # 添加標題
        title = f"診所班次請款單 ({last_sunday.strftime('%Y/%m/%d')} - {last_saturday.strftime('%Y/%m/%d')})"
        worksheet.cell(row=1, column=1).value = title
        worksheet.merge_cells('A1:J1')
        
        # 添加表頭
        headers = ['ID', '日期', '星期', '起點', '途經點', '終點', '司機編號', '錶價', '加成', '實收']
        for col_num, header in enumerate(headers, 1):
            worksheet.cell(row=2, column=col_num).value = header
        
        # 添加數據
        for row_num, row_data in enumerate(df.values, 3):
            for col_num, cell_value in enumerate(row_data, 1):
                worksheet.cell(row=row_num, column=col_num).value = cell_value
        
        # 添加總計行
        total_row = len(df) + 3
        worksheet.cell(row=total_row, column=9).value = "加總:"
        worksheet.cell(row=total_row, column=10).value = total_actual_fare
        
        # 添加司機統計
        driver_stats_row = total_row + 3  # 在總計行下方留出空行
        
        # 添加司機統計標題
        worksheet.cell(row=driver_stats_row, column=1).value = "司機統計:"
        worksheet.cell(row=driver_stats_row, column=1).font = Font(name='微軟正黑體', size=12, bold=True)
        
        # 添加司機統計表頭
        driver_stats_headers = ['司機編號', '班次數', '金額']
        for col_num, header in enumerate(driver_stats_headers, 1):
            cell = worksheet.cell(row=driver_stats_row + 1, column=col_num)
            cell.value = header
            cell.font = Font(name='微軟正黑體', size=11, bold=True)
            cell.alignment = Alignment(horizontal='center')
            cell.fill = PatternFill(start_color='D9E1F2', end_color='D9E1F2', fill_type='solid')  # 淺藍色
        
        # 添加司機統計數據
        for row_num, row_data in enumerate(driver_stats.values, driver_stats_row + 2):
            for col_num, cell_value in enumerate(row_data, 1):
                cell = worksheet.cell(row=row_num, column=col_num)
                cell.value = cell_value
                if col_num == 3:  # 金額列
                    cell.alignment = Alignment(horizontal='right')
                    cell.number_format = '#,##0'
                    
        # 添加签名栏 (在司机统计表右侧)
        # 计算签名栏的位置和大小
        signature_col = 6  # 从F列开始
        signature_row = driver_stats_row  # 与司机统计标题在同一行
        signature_width = 4  # 占用4列
        signature_height = 2 + len(driver_stats)  # 与司机统计表相同高度
        
        # 添加签名栏标题
        worksheet.cell(row=signature_row, column=signature_col).value = "領款人簽名:"
        worksheet.cell(row=signature_row, column=signature_col).font = Font(name='微軟正黑體', size=12, bold=True)
        
        # 创建签名区域 (合并单元格)
        signature_area_row = signature_row + 1  # 标题下一行
        signature_area_col_start = chr(65 + signature_col - 1)  # 转换为列字母 (F)
        signature_area_col_end = chr(65 + signature_col + signature_width - 2)  # 计算结束列字母
        
        # 合并单元格
        merge_range = f'{signature_area_col_start}{signature_area_row}:{signature_area_col_end}{signature_area_row+signature_height-1}'
        worksheet.merge_cells(merge_range)
        
        # 添加边框（对合并单元格，只需要设置左上角单元格的边框）
        signature_border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )
        worksheet.cell(row=signature_area_row, column=signature_col).border = signature_border
        
        # 設置列寬
        column_widths = {
            'A': 10,  # ID
            'B': 15,  # 日期
            'C': 8,   # 星期
            'D': 15,  # 起點
            'E': 20,  # 途經點
            'F': 15,  # 終點/簽名欄開始
            'G': 12,  # 司機編號/簽名欄中間
            'H': 12,  # 錶價/簽名欄中間
            'I': 12,  # 加成/簽名欄結束
            'J': 12,  # 實收
        }
        
        for col_letter, width in column_widths.items():
            worksheet.column_dimensions[col_letter].width = width
        
        # 添加基本樣式
        # 標題樣式
        title_cell = worksheet.cell(row=1, column=1)
        title_cell.font = Font(name='微軟正黑體', size=16, bold=True)
        title_cell.alignment = Alignment(horizontal='center', vertical='center')
        title_cell.fill = PatternFill(start_color='4472C4', end_color='4472C4', fill_type='solid')
        title_cell.font = Font(name='微軟正黑體', size=16, bold=True, color='FFFFFF')
        
        # 表頭樣式
        header_font = Font(name='微軟正黑體', size=12, bold=True, color='FFFFFF')
        header_fill = PatternFill(start_color='5B9BD5', end_color='5B9BD5', fill_type='solid')
        header_alignment = Alignment(horizontal='center', vertical='center')
        
        for col in range(1, len(headers) + 1):
            cell = worksheet.cell(row=2, column=col)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_alignment
        
        # 數據行樣式 - 交替行顏色
        for row in range(3, len(df) + 3):
            for col in range(1, len(headers) + 1):
                cell = worksheet.cell(row=row, column=col)
                # 交替行顏色
                if row % 2 == 0:
                    cell.fill = PatternFill(start_color='EDF2F9', end_color='EDF2F9', fill_type='solid')  # 淺藍色
                
                # 數字列右對齊
                if col in [8, 9, 10]:  # 錶價、加成、實收列
                    cell.alignment = Alignment(horizontal='right', vertical='center')
                    if isinstance(cell.value, (int, float)):
                        cell.number_format = '#,##0'
                else:
                    cell.alignment = Alignment(horizontal='center', vertical='center')
        
        # 總計行樣式
        total_label = worksheet.cell(row=total_row, column=9)
        total_label.font = Font(name='微軟正黑體', size=12, bold=True)
        total_label.alignment = Alignment(horizontal='right', vertical='center')
        total_label.fill = PatternFill(start_color='BDD7EE', end_color='BDD7EE', fill_type='solid')  # 中藍色
        
        total_cell = worksheet.cell(row=total_row, column=10)
        total_cell.font = Font(name='微軟正黑體', size=12, bold=True)
        total_cell.alignment = Alignment(horizontal='right', vertical='center')
        total_cell.number_format = '#,##0'
        total_cell.fill = PatternFill(start_color='BDD7EE', end_color='BDD7EE', fill_type='solid')  # 中藍色
        
        # 添加邊框
        thin_border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )
        
        # 為主表格添加邊框
        for row in range(1, len(df) + 4):  # 包括標題、表頭、數據和總計行
            for col in range(1, len(headers) + 1):
                worksheet.cell(row=row, column=col).border = thin_border
        
        # 為司機統計表添加邊框
        for row in range(driver_stats_row + 1, driver_stats_row + 2 + len(driver_stats)):
            for col in range(1, 4):
                worksheet.cell(row=row, column=col).border = thin_border
        
        # 保存工作簿
        workbook.save(filename)
        logger.info(f"報表已成功生成: {filename}")
        
        category_text = f"類別「{category}」的" if category and category != "全部" else ""
        return f"已生成上周 ({last_sunday.strftime('%m/%d')} - {last_saturday.strftime('%m/%d')}) {category_text}報表。", filename
        
    except Exception as e:
        logger.error(f"生成報表失敗: {str(e)}", exc_info=True)
        return f"生成報表失敗: {str(e)}", None

def upload_to_google_drive(file_path, folder_id=None):
    """
    將文件上傳到Google Drive並設置分享權限
    
    Args:
        file_path: 要上傳的文件路徑
        folder_id: Google Drive文件夾ID（可選）
        
    Returns:
        str: 文件分享鏈接或錯誤消息
    """
    try:
        logger.info(f"嘗試上傳文件到Google Drive: {file_path}")
        
        # 使用drive_service模組中的上傳函數
        success, result = upload_file_to_drive(file_path, folder_id=folder_id)
        
        if success:
            logger.info(f"文件上傳成功，分享鏈接: {result}")
            return result
        else:
            logger.error(f"上傳到Google Drive失敗: {result}")
            return f"上傳到Google Drive失敗: {result}"
    
    except Exception as e:
        logger.error(f"上傳到Google Drive過程中出錯: {str(e)}", exc_info=True)
        return f"上傳到Google Drive失敗: {str(e)}"

def handle_generate_weekly_report(text):
    """
    處理生成周報表命令
    
    Args:
        text: 用戶輸入的文本命令
        
    Returns:
        str: 處理結果消息
    """
    # 解析命令參數
    parts = text.strip().split()
    category = None
    
    if len(parts) > 1:
        category = parts[1]
    
    # 類別與文件夾 ID 的映射
    CATEGORY_FOLDER_MAPPING = {
        "診所": "1Wwp1xIxnn9m9qlvX_BwpE30K0AgLVdYe",  # 診所文件夾 ID
        "東洋": "1dctU8QPRWNPn57LxpcYTeKKcsGn_dLOU",   # 東洋文件夾 ID
        "全部": None  # 全部類別不指定特定文件夾
    }
    
    # 根據類別獲取對應的文件夾ID
    folder_id = None
    if category and category in CATEGORY_FOLDER_MAPPING:
        folder_id = CATEGORY_FOLDER_MAPPING[category]
        logger.info(f"使用類別: {category}, 對應文件夾ID: {folder_id}")
    
    try:
        logger.info(f"開始生成週報表，類別: {category}")
        # 生成報表
        result, filename = generate_weekly_report(category)
        
        if not filename:
            logger.warning("沒有生成報表文件")
            return result
        
        # 上傳到Google Drive
        logger.info(f"報表生成成功，準備上傳到Google Drive: {filename}")
        drive_url = upload_to_google_drive(filename, folder_id)
        
        if drive_url and not drive_url.startswith("上傳到Google Drive失敗"):
            logger.info(f"報表已成功上傳: {drive_url}")
            return f"{result}\n報表已上傳到Google Drive: {drive_url}"
        else:
            logger.warning(f"報表上傳失敗: {drive_url}")
            return f"{result}\n報表已生成，但上傳到Google Drive失敗: {drive_url}"
    except Exception as e:
        logger.error(f"處理生成週報表命令時出錯: {str(e)}", exc_info=True)
        return f"生成報表時出錯: {str(e)}" 