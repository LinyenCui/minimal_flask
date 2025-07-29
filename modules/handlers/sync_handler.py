#!/usr/bin/env python3
"""
資料庫同步處理器
通過Line Bot介面觸發增量同步
"""

import logging
import threading
from datetime import datetime
from modules.services.incremental_sync_service import IncrementalSyncService
from modules.utils.line_bot import reply_text, reply_flex

logger = logging.getLogger(__name__)

class SyncHandler:
    """同步處理器類"""
    
    def __init__(self):
        self.sync_service = IncrementalSyncService()
        self.running_syncs = {}  # 追蹤正在運行的同步
    
    def create_sync_status_flex(self, status: str, message: str, details: dict = None):
        """創建同步狀態Flex訊息"""
        color = {
            'running': '#FFB800',    # 橙色
            'success': '#00C851',    # 綠色  
            'error': '#FF4444',      # 紅色
            'info': '#2196F3'        # 藍色
        }.get(status, '#757575')     # 預設灰色
        
        emoji = {
            'running': '🔄',
            'success': '✅',
            'error': '❌',
            'info': 'ℹ️'
        }.get(status, '📋')
        
        flex_content = {
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": f"{emoji} 資料庫同步狀態",
                        "weight": "bold",
                        "size": "md",
                        "color": color
                    },
                    {
                        "type": "separator",
                        "margin": "md"
                    },
                    {
                        "type": "text",
                        "text": message,
                        "wrap": True,
                        "margin": "md"
                    }
                ]
            }
        }
        
        # 添加詳細信息
        if details:
            details_box = {
                "type": "box",
                "layout": "vertical",
                "margin": "md",
                "contents": []
            }
            
            for key, value in details.items():
                details_box["contents"].append({
                    "type": "text",
                    "text": f"{key}: {value}",
                    "size": "sm",
                    "color": "#666666"
                })
            
            flex_content["body"]["contents"].append(details_box)
        
        # 添加時間戳
        flex_content["body"]["contents"].append({
            "type": "text",
            "text": f"時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "size": "xs",
            "color": "#999999",
            "margin": "md"
        })
        
        return flex_content
    
    def sync_in_background(self, reply_token: str, sync_type: str = 'preserve'):
        """在背景執行同步"""
        try:
            logger.info(f"開始背景同步: {sync_type}")
            
            if sync_type == 'preserve':
                results = self.sync_service.preserve_local_data_sync()
            else:
                results = self.sync_service.full_incremental_sync()
            
            # 發送完成通知
            if results['success']:
                message = f"資料庫同步成功完成!"
                details = {
                    "同步表數": f"{results.get('synced_tables', 0)}/{results.get('total_tables', 0)}",
                    "新增記錄": results.get('total_new_records', 0)
                }
                flex_msg = self.create_sync_status_flex('success', message, details)
            else:
                message = "資料庫同步失敗"
                details = {
                    "錯誤數量": len(results.get('errors', [])),
                    "部分成功": f"{results.get('synced_tables', 0)} 個表"
                }
                flex_msg = self.create_sync_status_flex('error', message, details)
            
            reply_flex(reply_token, "同步完成通知", flex_msg)
            
        except Exception as e:
            logger.error(f"背景同步失敗: {e}")
            error_flex = self.create_sync_status_flex(
                'error', 
                f"同步過程中發生錯誤: {str(e)}"
            )
            reply_flex(reply_token, "同步錯誤", error_flex)
        
        finally:
            # 清理追蹤
            if reply_token in self.running_syncs:
                del self.running_syncs[reply_token]
    
    def handle_sync_request(self, message_text: str, reply_token: str) -> bool:
        """
        處理同步請求
        
        命令格式:
        - 資料庫同步
        - 增量同步  
        - 保護同步
        - 同步狀態
        """
        message_text = message_text.strip()
        
        # 檢查是否為同步命令
        sync_commands = ['資料庫同步', '增量同步', '保護同步', '同步狀態', 'db sync', 'sync']
        
        if not any(cmd in message_text for cmd in sync_commands):
            return False
        
        logger.info(f"處理同步命令: {message_text}")
        
        try:
            # 檢查是否已有同步在運行
            if reply_token in self.running_syncs:
                running_msg = self.create_sync_status_flex(
                    'running',
                    "同步正在進行中，請稍候..."
                )
                reply_flex(reply_token, "同步狀態", running_msg)
                return True
            
            # 解析同步類型
            if '保護' in message_text or 'preserve' in message_text:
                sync_type = 'preserve'
                sync_desc = "保護性增量同步"
            elif '增量' in message_text or 'incremental' in message_text:
                sync_type = 'incremental' 
                sync_desc = "標準增量同步"
            elif '狀態' in message_text or 'status' in message_text:
                # 顯示同步狀態
                if self.running_syncs:
                    status_msg = f"目前有 {len(self.running_syncs)} 個同步任務正在執行"
                else:
                    status_msg = "目前沒有正在執行的同步任務"
                
                status_flex = self.create_sync_status_flex('info', status_msg)
                reply_flex(reply_token, "同步狀態", status_flex)
                return True
            else:
                sync_type = 'preserve'  # 預設使用保護性同步
                sync_desc = "保護性增量同步"
            
            # 記錄同步開始
            self.running_syncs[reply_token] = {
                'start_time': datetime.now(),
                'type': sync_type
            }
            
            # 發送開始通知
            start_msg = self.create_sync_status_flex(
                'running',
                f"正在啟動{sync_desc}...\n這可能需要幾分鐘時間，完成後會通知您。"
            )
            reply_flex(reply_token, "同步開始", start_msg)
            
            # 在背景執行同步
            sync_thread = threading.Thread(
                target=self.sync_in_background,
                args=(reply_token, sync_type),
                daemon=True
            )
            sync_thread.start()
            
            return True
            
        except Exception as e:
            logger.error(f"處理同步請求失敗: {e}")
            error_flex = self.create_sync_status_flex(
                'error',
                f"啟動同步失敗: {str(e)}"
            )
            reply_flex(reply_token, "同步錯誤", error_flex)
            return True

# 全域實例
sync_handler = SyncHandler()

def handle_database_sync_command(message_text: str, reply_token: str) -> bool:
    """處理資料庫同步命令的主要入口函數"""
    return sync_handler.handle_sync_request(message_text, reply_token)