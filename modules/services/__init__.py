"""
服務模組初始化
"""
from modules.services.message_service import handle_message
from modules.services.postback_service import handle_postback
from modules.services.report_service import handle_generate_weekly_report

__all__ = ['handle_message', 'handle_postback', 'handle_generate_weekly_report']

# 初始化服務層包 