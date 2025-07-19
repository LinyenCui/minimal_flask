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

def get_completed_trip_details(trip_id):
    """獲取已完成班次的詳細信息"""
    try:
        query = """
        SELECT 
            ct.id, 
            ct.date, 
            ct.start_point, 
            ct.via_point,
            ct.end_point, 
            ct.category,
            ct.driver_id,
            d.name as driver_name,
            d.plate_number,
            ct.meter_fare,
            ct.extra_fare,
            (ct.meter_fare + ct.extra_fare) as total_amount,
            ct.modification_reason,
            ct.trip_type
        FROM 
            completed_trips ct
        LEFT JOIN 
            drivers d ON ct.driver_id = d.id
        WHERE 
            ct.id = :trip_id
        """
        
        result = db.session.execute(text(query), {"trip_id": trip_id})
        trip = result.fetchone()
        
        if not trip:
            return None
        
        # 格式化結果為文本
        trip_date = trip.date
        weekday_names = ["一", "二", "三", "四", "五", "六", "日"]
        weekday = weekday_names[trip_date.weekday()] if trip_date else ""
        formatted_date = trip_date.strftime("%Y-%m-%d") if trip_date else "未設置"
        
        driver_info = f"司機{trip.driver_id}"
        if trip.driver_name:
            driver_info += f"({trip.driver_name})"
        if trip.plate_number:
            driver_info += f" - {trip.plate_number}"
        
        result_text = f"""📋 已完成班次 #{trip.id} 詳細信息：

📅 日期: {formatted_date} (星期{weekday})
📍 起點: {trip.start_point or '未指定'}"""
        
        if trip.via_point:
            result_text += f"\n🚩 經由: {trip.via_point}"
            
        result_text += f"\n🏁 終點: {trip.end_point or '未指定'}"
        result_text += f"\n🚕 {driver_info}"
        result_text += f"\n📊 類別: {trip.category or '未分類'}"
        
        # 顯示費用信息
        meter_fare = trip.meter_fare or 0
        extra_fare = trip.extra_fare or 0
        total_amount = trip.total_amount or 0
        
        if extra_fare >= 0:
            result_text += f"\n💰 費用: 錶價{meter_fare} + 加成{extra_fare} = {total_amount}元"
        else:
            result_text += f"\n💰 費用: 錶價{meter_fare} - 減免{abs(extra_fare)} = {total_amount}元"
        
        if trip.modification_reason:
            result_text += f"\n📝 備註: {trip.modification_reason}"
            
        result_text += f"\n✅ 狀態: 已完成"
        
        return result_text
        
    except Exception as e:
        current_app.logger.error(f"查詢已完成班次詳情失敗: {e}")
        traceback.print_exc()
        return f"❌ 查詢已完成班次 #{trip_id} 失敗: {str(e)}" 