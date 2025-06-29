"""
Flex設計模塊，用於存放各種Flex Message的設計模板
"""

from .temp_booking_flex import (
    get_temp_booking_start_flex,
    get_temp_booking_time_flex,
    get_temp_booking_confirm_flex
)

# 直接從我們期望的檔案導入，並不使用別名
from .trip_details_flex import get_trip_details_flex 

# 確保其他被正確使用的 Flex 設計函數也被導出
from .help_flex import (
    get_help_flex, 
    get_ai_features_help,
    get_fixed_schedule_help,
    get_leave_status_help,
    get_reports_help,
    get_maintenance_help,
    get_complete_commands_help
)
from .trip_query_flex import generate_trips_flex # 假設這個也需要被導出
# from .driver_assign_flex import get_driver_assignment_flex # 如果有的話

__all__ = [
    'get_temp_booking_start_flex',
    'get_temp_booking_time_flex',
    'get_temp_booking_confirm_flex',
    'get_trip_details_flex', # <--- 使用原始名稱導出
    'get_help_flex',
    'get_ai_features_help',
    'get_fixed_schedule_help',
    'get_leave_status_help',
    'get_reports_help',
    'get_maintenance_help',
    'get_complete_commands_help',
    'generate_trips_flex' # 確保所有需要從 modules.flex_designs 直接導入的都在這裡
    # 'get_driver_assignment_flex'
] 