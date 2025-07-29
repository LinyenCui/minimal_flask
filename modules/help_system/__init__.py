"""
幫助系統模組
新一代動態、上下文感知的幫助系統
"""

from .help_handler import HelpHandler
from .help_manager import HelpManager
from .help_config import HelpSystemConfig

# 全局幫助處理器實例
help_handler = HelpHandler()

def handle_help_message(message_text: str, user_id: str, reply_token: str) -> bool:
    """
    處理幫助相關訊息
    
    Args:
        message_text: 訊息內容
        user_id: 用戶ID
        reply_token: 回覆Token
        
    Returns:
        bool: 是否為幫助訊息並已處理
    """
    return help_handler.handle_help_request(message_text, user_id, reply_token)

def get_quick_help(command: str, user_id: str) -> str:
    """
    獲取命令的快速幫助
    
    Args:
        command: 命令名稱
        user_id: 用戶ID
        
    Returns:
        str: 快速幫助文字
    """
    return help_handler.help_manager.get_quick_help(user_id, command)

__all__ = [
    'HelpHandler',
    'HelpManager', 
    'HelpSystemConfig',
    'help_handler',
    'handle_help_message',
    'get_quick_help'
]