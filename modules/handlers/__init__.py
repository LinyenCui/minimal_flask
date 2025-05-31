"""
處理程序模組初始化
"""
# REMOVED: from modules.handlers.booking_handler import (
#     handle_booking_start, handle_booking_message, handle_booking_help
# )
from modules.handlers.trip_status_handler import (
    handle_update_trip_status, handle_confirm_cancel_trip,
    handle_confirm_leave_trip, handle_confirm_conflict_trip
)

__all__ = [
    # REMOVED: 'handle_booking_start', 'handle_booking_message', 'handle_booking_help',
    'handle_update_trip_status', 'handle_confirm_cancel_trip',
    'handle_confirm_leave_trip', 'handle_confirm_conflict_trip'
]

# 初始化處理器層包 