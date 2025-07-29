"""
服務模組初始化
"""
from modules.services.message_service import handle_message
from modules.services.postback_service import handle_postback

__all__ = ['handle_message', 'handle_postback']

# 初始化服務層包 