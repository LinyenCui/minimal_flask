"""
資料庫模型初始化模組
"""
from modules.models.base import db, init_db_app, get_db
from modules.models.models import (
    Base, Customer, Driver, FixedSchedule, Trip, CompletedTrip
)

# 導入所有模型以便在其他地方使用
from modules.models.customer import Customer
from modules.models.driver import Driver
from modules.models.trip import Trip, FixedSchedule, CompletedTrip

__all__ = [
    'db', 'init_db_app', 'get_db',
    'Base', 'Customer', 'Driver', 'FixedSchedule', 'Trip', 'CompletedTrip'
] 