# 班次服務層 - 負責業務邏輯

from datetime import datetime, timedelta
import re
from sqlalchemy import text
from database import engine, Session
from flask import current_app
import traceback
# 導入時區相關函數
from modules.utils.taiwan_time import get_taiwan_time, get_taiwan_date

from modules.models.base import db

def get_trips_by_date(date, category=None):
    """根據日期和類別獲取班次列表"""
    query = """
    SELECT 
        t.trip_id, 
        t.time, 
        c_start.name as start_name,
        c_via.name as via_name,
        c_end.name as end_name,
        t.status,
        d.id as driver_id,
        d.plate_number
    FROM 
        trips t
    LEFT JOIN 
        customers c_start ON t.start_point = c_start.short_name
    LEFT JOIN 
        customers c_via ON t.via_point = c_via.short_name
    LEFT JOIN 
        customers c_end ON t.end_point = c_end.short_name
    LEFT JOIN 
        drivers d ON t.driver_id = d.id
    WHERE 
        t.date = :date
    """
    
    if category:
        query += " AND t.category = :category"
    
    query += " ORDER BY t.time"
    
    with engine.connect() as conn:
        if category:
            result = conn.execute(text(query), {"date": date, "category": category})
        else:
            result = conn.execute(text(query), {"date": date})
        trips = [dict(row) for row in result]
    
    return trips

def get_trip_details(trip_id):
    """獲取班次詳細信息"""
    query = """
    SELECT 
        t.trip_id, 
        t.date, 
        t.time, 
        c_start.name as start_name, 
        c_via.name as via_name,
        c_end.name as end_name, 
        t.start_point, 
        t.via_point,
        t.end_point,
        t.status,
        d.id as driver_id,
        d.plate_number,
        t.category,
        t.fixed_trip_id,
        t.meter_fare,
        t.extra_fare,
        t.actual_fare,
        t.passenger_name
    FROM 
        trips t
    LEFT JOIN 
        customers c_start ON t.start_point = c_start.short_name
    LEFT JOIN 
        customers c_via ON t.via_point = c_via.short_name
    LEFT JOIN 
        customers c_end ON t.end_point = c_end.short_name
    LEFT JOIN 
        drivers d ON t.driver_id = d.id
    WHERE 
        t.trip_id = :trip_id
    """
    
    with engine.connect() as conn:
        result = conn.execute(text(query), {"trip_id": trip_id})
        trip = dict(result.first()) if result.rowcount > 0 else None
    
    return trip 

# 註：update_completed_trips() 函數已移至 scheduler_service.py 統一管理
# 如需使用遷移功能，請使用：from modules.services.scheduler_service import update_completed_trips 