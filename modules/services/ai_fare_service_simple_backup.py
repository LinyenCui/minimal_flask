#!/usr/bin/env python3
"""
AI車資查詢和修改服務 - 簡化版
一次顯示所有搜尋結果，不使用翻頁功能
"""

import re
import logging
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional, Tuple
from modules.models.base import db
from modules.models.trip import Trip, CompletedTrip
from modules.utils.taiwan_time import get_taiwan_date
from sqlalchemy import and_, or_, func

logger = logging.getLogger(__name__)

def is_ai_query(message_text: str) -> bool:
    """
    判斷是否為AI查詢請求
    """
    # 車資相關關鍵詞
    fare_keywords = ['車資', '費用', '金額', '收費', '錢', '價格', '票價']
    
    # 查詢/修改動詞
    query_verbs = ['查詢', '查', '看', '顯示', '搜尋', '找', '修改', '改', '更新', '設定']
    
    # 地點關鍵詞
    location_keywords = ['台中', '彰化', '南投', '診所', '醫院', '火車站', '高鐵', '機場']
    
    # 時間關鍵詞
    time_keywords = ['今天', '明天', '昨天', '這週', '上週', '月', '日']
    
    message_lower = message_text.lower()
    
    # 必須包含車資相關詞彙和查詢動詞
    has_fare = any(keyword in message_lower for keyword in fare_keywords)
    has_verb = any(verb in message_lower for verb in query_verbs)
    
    return has_fare and has_verb

def extract_query_params(message_text: str) -> Dict[str, Any]:
    """
    從用戶消息中提取查詢參數
    """
    params = {
        'start_point': None,
        'end_point': None, 
        'date': None,
        'action': 'query'  # 'query' 或 'modify'
    }
    
    # 檢測動作類型
    if any(word in message_text for word in ['修改', '改', '更新', '設定']):
        params['action'] = 'modify'
    
    # 提取地點
    locations = ['台中', '彰化', '南投', '診所', '醫院', '火車站', '高鐵站', '機場']
    found_locations = []
    for loc in locations:
        if loc in message_text:
            found_locations.append(loc)
    
    if len(found_locations) >= 2:
        params['start_point'] = found_locations[0]
        params['end_point'] = found_locations[1]
    elif len(found_locations) == 1:
        params['start_point'] = found_locations[0]
    
    # 提取日期
    today = get_taiwan_date()
    if '今天' in message_text:
        params['date'] = today
    elif '明天' in message_text:
        params['date'] = today + timedelta(days=1)
    elif '昨天' in message_text:
        params['date'] = today - timedelta(days=1)
    
    # 提取具體日期 (MM/DD 格式)
    date_pattern = r'(\d{1,2})/(\d{1,2})'
    date_match = re.search(date_pattern, message_text)
    if date_match:
        month = int(date_match.group(1))
        day = int(date_match.group(2))
        current_year = today.year
        try:
            params['date'] = date(current_year, month, day)
        except ValueError:
            logger.warning(f"無效日期: {month}/{day}")
    
    return params

def search_trips_by_params(params: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    根據參數搜尋班次
    """
    query = db.session.query(Trip)
    
    # 日期篩選
    if params['date']:
        query = query.filter(Trip.date == params['date'])
    
    # 地點篩選
    conditions = []
    if params['start_point']:
        conditions.append(Trip.start_point.ilike(f"%{params['start_point']}%"))
    if params['end_point']:
        conditions.append(Trip.end_point.ilike(f"%{params['end_point']}%"))
    
    if conditions:
        query = query.filter(or_(*conditions))
    
    # 執行查詢
    trips = query.order_by(Trip.date.desc(), Trip.time.desc()).limit(50).all()
    
    result = []
    for trip in trips:
        # 計算總車資
        total_fare = None
        if trip.actual_fare:
            total_fare = trip.actual_fare
        elif trip.meter_fare:
            extra = trip.extra_fare or 0
            total_fare = trip.meter_fare + extra
        
        result.append({
            'trip_id': trip.trip_id,
            'date': trip.date.strftime('%Y-%m-%d'),
            'time': trip.time.strftime('%H:%M'),
            'start_point': trip.start_point,
            'end_point': trip.end_point,
            'category': trip.category,
            'status': trip.status,
            'fare': total_fare,
            'meter_fare': trip.meter_fare,
            'extra_fare': trip.extra_fare,
            'actual_fare': trip.actual_fare,
            'driver_id': trip.driver_id
        })
    
    return result

def format_search_results(trips: List[Dict[str, Any]], query_type: str = "車資查詢") -> str:
    """
    格式化搜尋結果為文字訊息
    """
    if not trips:
        return "🔍 沒有找到符合條件的班次"
    
    total = len(trips)
    response = f"🚗 {query_type}結果 (共找到 {total} 筆)\n"
    response += "=" * 30 + "\n\n"
    
    for i, trip in enumerate(trips, 1):
        # 格式化車資信息
        fare_info = ""
        if trip['actual_fare']:
            fare_info = f"${trip['actual_fare']} (實收)"
        elif trip['meter_fare']:
            meter = trip['meter_fare']
            extra = trip['extra_fare'] or 0
            total = meter + extra
            if extra != 0:
                fare_info = f"${total} (錶價${meter}+加成${extra})"
            else:
                fare_info = f"${meter} (錶價)"
        else:
            fare_info = "未設定"
            
        driver_info = f"司機#{trip['driver_id']}" if trip['driver_id'] else "未指派"
        
        response += f"📍 {i}. 班次#{trip['trip_id']}\n"
        response += f"   📅 {trip['date']} {trip['time']}\n"
        response += f"   🚩 {trip['start_point']} → {trip['end_point']}\n"
        response += f"   💰 車資: {fare_info}\n"
        response += f"   👤 {driver_info}\n"
        response += f"   📊 狀態: {trip['status']} ({trip['category']})\n\n"
    
    # 添加操作提示
    response += "💡 操作提示:\n"
    response += "• 查看詳情: 班次詳情 [班次ID]\n"
    response += "• 修改車資: 記錄車資 [班次ID] [金額]\n"
    response += "• 指派司機: 指派司機 [班次ID]"
    
    return response

def handle_ai_fare_query(message_text: str) -> str:
    """
    處理AI車資查詢
    """
    try:
        logger.info(f"處理AI車資查詢: {message_text}")
        
        # 提取查詢參數
        params = extract_query_params(message_text)
        logger.info(f"查詢參數: {params}")
        
        # 搜尋班次
        trips = search_trips_by_params(params)
        logger.info(f"找到 {len(trips)} 筆班次")
        
        # 格式化結果
        response = format_search_results(trips, "AI車資查詢")
        
        return response
        
    except Exception as e:
        logger.error(f"AI車資查詢出錯: {e}")
        return f"❌ AI查詢出錯: {str(e)}"

def suggest_alternative_queries(original_query: str) -> List[str]:
    """
    建議替代查詢
    """
    suggestions = []
    
    # 基本建議
    suggestions.extend([
        "查詢今天台中車資",
        "查詢明天彰化車資", 
        "查詢診所班次車資",
        "查詢6/1台中到彰化車資"
    ])
    
    return suggestions[:3]  # 限制3個建議

def get_quick_reply_suggestions() -> List[Dict[str, str]]:
    """
    獲取快速回覆建議
    """
    return [
        {"label": "今天車資", "text": "查詢今天車資"},
        {"label": "明天車資", "text": "查詢明天車資"},
        {"label": "台中車資", "text": "查詢台中車資"},
        {"label": "彰化車資", "text": "查詢彰化車資"},
        {"label": "診所車資", "text": "查詢診所車資"}
    ]

# 車資修改功能 (簡化版)
def handle_fare_modification_request(message_text: str) -> str:
    """
    處理車資修改請求
    """
    # 提取班次ID和車資金額
    patterns = [
        r'修改.*?(\d+).*?(\d+)',  # 修改班次123車資500
        r'設定.*?(\d+).*?(\d+)',  # 設定班次123車資500  
        r'班次(\d+).*?(\d+)',     # 班次123車資500
    ]
    
    trip_id = None
    fare_amount = None
    
    for pattern in patterns:
        match = re.search(pattern, message_text)
        if match:
            trip_id = int(match.group(1))
            fare_amount = int(match.group(2))
            break
    
    if not trip_id or not fare_amount:
        return "❌ 無法識別班次ID或車資金額\n範例: 修改班次123車資500"
    
    try:
        # 查找班次
        trip = Trip.query.filter_by(trip_id=trip_id).first()
        if not trip:
            return f"❌ 找不到班次#{trip_id}"
        
        # 更新車資 (設定為actual_fare)
        old_fare = trip.actual_fare
        trip.actual_fare = fare_amount
        db.session.commit()
        
        response = f"✅ 車資修改成功!\n\n"
        response += f"📍 班次#{trip_id}\n"
        response += f"📅 {trip.date} {trip.time}\n"
        response += f"🚩 {trip.start_point} → {trip.end_point}\n"
        response += f"💰 車資: ${old_fare} → ${fare_amount}\n"
        response += f"📊 狀態: {trip.status}"
        
        return response
        
    except Exception as e:
        logger.error(f"修改車資出錯: {e}")
        return f"❌ 修改車資失敗: {str(e)}" 