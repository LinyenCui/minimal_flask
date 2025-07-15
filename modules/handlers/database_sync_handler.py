"""
資料庫同步處理器 - 透過 LINE Bot 控制 Render 資料同步
"""
import os
import subprocess
import datetime
import asyncio
from modules.models.base import db
from modules.utils.line_bot import get_user_display_name
import logging

logger = logging.getLogger(__name__)

class DatabaseSyncHandler:
    """資料庫同步處理器"""
    
    def __init__(self):
        self.render_host = os.getenv('RENDER_DB_HOST')
        self.render_user = os.getenv('RENDER_DB_USER') 
        self.render_db = os.getenv('RENDER_DB_NAME')
        self.render_password = os.getenv('RENDER_DB_PASSWORD')
        self.local_db = "dispatch_db"
        
    def check_render_connection(self):
        """檢查 Render 資料庫連線設定"""
        missing = []
        if not self.render_host:
            missing.append("RENDER_DB_HOST")
        if not self.render_user:
            missing.append("RENDER_DB_USER")
        if not self.render_db:
            missing.append("RENDER_DB_NAME")
        if not self.render_password:
            missing.append("RENDER_DB_PASSWORD")
            
        return missing
    
    def get_database_stats(self, is_render=False):
        """獲取資料庫統計資訊"""
        try:
            if is_render:
                # Render 資料庫統計（需要遠程連線）
                env = os.environ.copy()
                env['PGPASSWORD'] = self.render_password
                
                command = f"""psql -h {self.render_host} -U {self.render_user} -d {self.render_db} -t -c "
                SELECT 
                    'trips: ' || COUNT(*) FROM trips
                    UNION ALL
                    SELECT 'completed_trips: ' || COUNT(*) FROM completed_trips
                    UNION ALL  
                    SELECT 'customers: ' || COUNT(*) FROM customers
                    UNION ALL
                    SELECT 'drivers: ' || COUNT(*) FROM drivers;
                \""""
                
                result = subprocess.run(command, shell=True, capture_output=True, 
                                      text=True, env=env, timeout=30)
                if result.returncode == 0:
                    return result.stdout.strip()
                else:
                    return f"連線失敗: {result.stderr}"
            else:
                # 本地資料庫統計
                command = f"""psql -d {self.local_db} -t -c "
                SELECT 
                    'trips: ' || COUNT(*) FROM trips
                    UNION ALL
                    SELECT 'completed_trips: ' || COUNT(*) FROM completed_trips
                    UNION ALL  
                    SELECT 'customers: ' || COUNT(*) FROM customers
                    UNION ALL
                    SELECT 'drivers: ' || COUNT(*) FROM drivers;
                \""""
                
                result = subprocess.run(command, shell=True, capture_output=True, text=True)
                if result.returncode == 0:
                    return result.stdout.strip()
                else:
                    return f"查詢失敗: {result.stderr}"
                    
        except subprocess.TimeoutExpired:
            return "連線超時"
        except Exception as e:
            return f"錯誤: {str(e)}"
    
    def backup_local_database(self):
        """備份本地資料庫"""
        try:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = f"auto_backup_{timestamp}.sql"
            
            command = f"pg_dump -d {self.local_db} > {backup_file}"
            result = subprocess.run(command, shell=True, capture_output=True, text=True)
            
            if result.returncode == 0:
                return backup_file, None
            else:
                return None, result.stderr
                
        except Exception as e:
            return None, str(e)
    
    def sync_from_render(self):
        """從 Render 同步資料"""
        try:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            sync_file = f"render_sync_{timestamp}.sql"
            
            # 設定環境變數
            env = os.environ.copy()
            env['PGPASSWORD'] = self.render_password
            
            # 從 Render 匯出
            export_cmd = f"pg_dump -h {self.render_host} -U {self.render_user} -d {self.render_db} --clean --if-exists > {sync_file}"
            export_result = subprocess.run(export_cmd, shell=True, capture_output=True, 
                                         text=True, env=env, timeout=120)
            
            if export_result.returncode != 0:
                return None, f"匯出失敗: {export_result.stderr}"
            
            # 匯入到本地
            import_cmd = f"psql -d {self.local_db} -f {sync_file}"
            import_result = subprocess.run(import_cmd, shell=True, capture_output=True, text=True)
            
            if import_result.returncode != 0:
                return None, f"匯入失敗: {import_result.stderr}"
            
            return sync_file, None
            
        except subprocess.TimeoutExpired:
            return None, "同步超時（可能資料量太大）"
        except Exception as e:
            return None, str(e)
    
    def fix_sequences_after_sync(self):
        """同步後修復序列"""
        try:
            result = subprocess.run("python fix_sequence_after_import.py --quick", 
                                  shell=True, input="y\n", text=True,
                                  capture_output=True, timeout=60)
            return result.returncode == 0, result.stdout + result.stderr
        except Exception as e:
            return False, str(e)

def handle_database_sync_request(event, line_bot_api):
    """處理資料庫同步請求"""
    user_id = event.source.user_id
    user_name = get_user_display_name(user_id)
    
    logger.info(f"用戶 {user_name} 請求資料庫同步檢查")
    
    sync_handler = DatabaseSyncHandler()
    
    # 檢查 Render 連線設定
    missing_config = sync_handler.check_render_connection()
    if missing_config:
        response = "❌ Render 資料庫連線設定不完整\n"
        response += "缺少以下環境變數：\n"
        response += "\n".join([f"• {config}" for config in missing_config])
        return {"type": "text", "text": response}
    
    # 顯示當前狀態
    response = "📊 資料庫同步狀態檢查\n"
    response += "=" * 30 + "\n\n"
    
    # 本地資料庫統計
    response += "🏠 本地資料庫：\n"
    local_stats = sync_handler.get_database_stats(is_render=False)
    response += local_stats + "\n\n"
    
    # Render 資料庫統計
    response += "☁️ Render 資料庫：\n"
    render_stats = sync_handler.get_database_stats(is_render=True)
    response += render_stats + "\n\n"
    
    if "連線失敗" in render_stats or "錯誤" in render_stats:
        response += "❌ 無法連線到 Render 資料庫\n"
        response += "請檢查網路連線和設定"
        return {"type": "text", "text": response}
    
    response += "⚠️ 同步將會覆蓋本地資料庫\n"
    response += "請選擇操作："
    
    # 創建 Quick Reply 確認選項
    from modules.utils.line_bot import QuickReply, QuickReplyItem, MessageAction
    
    quick_reply_items = [
        QuickReplyItem(
            action=MessageAction(
                label="✅ 確認同步",
                text="確認同步"
            )
        ),
        QuickReplyItem(
            action=MessageAction(
                label="❌ 取消操作",
                text="取消"
            )
        )
    ]
    
    quick_reply = QuickReply(items=quick_reply_items)
    
    return {
        "type": "text",
        "text": response,
        "quick_reply": quick_reply.to_dict()
    }

def handle_database_sync_confirm(event, line_bot_api):
    """處理資料庫同步確認"""
    user_id = event.source.user_id
    user_name = get_user_display_name(user_id)
    
    logger.info(f"用戶 {user_name} 確認執行資料庫同步")
    
    sync_handler = DatabaseSyncHandler()
    
    response = "🚀 開始資料庫同步流程\n"
    response += "=" * 30 + "\n\n"
    
    # 步驟1: 備份本地資料庫
    response += "📂 步驟1: 備份本地資料庫...\n"
    backup_file, backup_error = sync_handler.backup_local_database()
    
    if backup_error:
        response += f"❌ 備份失敗: {backup_error}\n"
        response += "同步中止"
        return response
    
    response += f"✅ 備份完成: {backup_file}\n\n"
    
    # 步驟2: 從 Render 同步
    response += "☁️ 步驟2: 從 Render 同步資料...\n"
    sync_file, sync_error = sync_handler.sync_from_render()
    
    if sync_error:
        response += f"❌ 同步失敗: {sync_error}\n"
        response += f"可使用備份恢復: {backup_file}"
        return response
    
    response += f"✅ 同步完成: {sync_file}\n\n"
    
    # 步驟3: 修復序列
    response += "🔧 步驟3: 修復資料庫序列...\n"
    seq_success, seq_output = sync_handler.fix_sequences_after_sync()
    
    if seq_success:
        response += "✅ 序列修復完成\n\n"
    else:
        response += f"⚠️ 序列修復警告: {seq_output}\n\n"
    
    response += "🎉 資料庫同步完成！\n"
    response += f"📁 備份檔案: {backup_file}\n"
    response += f"📁 同步檔案: {sync_file}"
    
    return response 