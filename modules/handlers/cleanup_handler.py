"""
清理功能處理器 - 專門清理trips表中過去日期的資料
"""

from datetime import date
from sqlalchemy import text as sql_text
from flask import current_app
import traceback

from modules.models.base import db

def handle_cleanup_trips(message_text):
    """處理清理trips資料的命令"""
    try:
        # 解析命令參數
        parts = message_text.strip().split()
        
        if len(parts) == 1:
            # 只有「清理trips」，顯示可用選項
            return show_cleanup_options()
        
        cleanup_option = parts[1].strip()
        
        if cleanup_option == '已完成':
            return cleanup_completed_trips()
        elif cleanup_option == '過去':
            return cleanup_past_trips()
        elif cleanup_option == '全部':
            return cleanup_all_past_trips()
        else:
            return f"❌ 無效的清理選項: {cleanup_option}\n\n{show_cleanup_options()}"
        
    except Exception as e:
        current_app.logger.error(f"處理清理trips命令失敗: {str(e)}")
        traceback.print_exc()
        return f"處理清理trips命令失敗: {str(e)}"

def show_cleanup_options():
    """顯示可用的清理選項"""
    result = "🗑️ 可用的清理選項：\n\n"
    
    result += "• 清理trips 已完成 - 清理所有已完成狀態的班次\n"
    result += "• 清理trips 過去 - 清理所有過去日期的班次\n"
    result += "• 清理trips 全部 - 清理所有過去日期的班次（包括已完成和未完成）\n"
    
    result += "\n💡 輸入格式：清理trips [選項]\n"
    result += "例如：清理trips 已完成\n"
    result += "例如：清理trips 過去\n"
    
    result += "\n⚠️ 注意：清理功能不會影響今天和未來的班次"
    
    return result

def cleanup_completed_trips():
    """清理所有已完成狀態的班次"""
    try:
        delete_query = "DELETE FROM trips WHERE status = '已完成'"
        result = db.session.execute(sql_text(delete_query))
        deleted_count = result.rowcount
        
        db.session.commit()
        current_app.logger.info(f"已清理 {deleted_count} 筆已完成的trips資料")
        
        return f"🗑️ 已清理 {deleted_count} 筆已完成狀態的班次"
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"清理已完成trips資料失敗: {str(e)}")
        return f"⚠️ 清理已完成trips資料失敗: {str(e)}"

def cleanup_past_trips():
    """清理所有過去日期的班次（保留今天和未來的班次）"""
    try:
        today = date.today()
        delete_query = "DELETE FROM trips WHERE date < :today"
        result = db.session.execute(sql_text(delete_query), {"today": today})
        deleted_count = result.rowcount
        
        db.session.commit()
        current_app.logger.info(f"已清理 {deleted_count} 筆過去時間的trips資料")
        
        return f"🗑️ 已清理 {deleted_count} 筆過去日期的班次（保留今天和未來的班次）"
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"清理過去trips資料失敗: {str(e)}")
        return f"⚠️ 清理過去trips資料失敗: {str(e)}"

def cleanup_all_past_trips():
    """清理所有過去日期的班次（包括已完成和未完成）"""
    try:
        today = date.today()
        delete_query = "DELETE FROM trips WHERE date < :today"
        result = db.session.execute(sql_text(delete_query), {"today": today})
        deleted_count = result.rowcount
        
        db.session.commit()
        current_app.logger.info(f"已清理 {deleted_count} 筆過去時間的trips資料")
        
        return f"🗑️ 已清理 {deleted_count} 筆過去日期的班次（包括已完成和未完成）"
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"清理過去trips資料失敗: {str(e)}")
        return f"⚠️ 清理過去trips資料失敗: {str(e)}" 