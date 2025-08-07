"""
此模塊包含班次詳情的 Flex Message 設計（修正版本）
"""

import logging
logger = logging.getLogger(__name__)
from datetime import datetime, timedelta

def get_trip_details_flex(trip_id, trip_data):
    """
    生成班次詳情的 Flex Message (修正版本：正確處理請假狀態的Quick Reply)
    """
    logger.info(f">>>>> EXECUTING FIXED VERSION OF: trip_details_flex.py - get_trip_details_flex for trip {trip_id} <<<<<")
    
    # 檢查基於執行時間的30分鐘修改限制
    can_modify_status = True
    restriction_message = ""
    
    # 🔥 優化：使用trip_data中的日期和時間，避免重複數據庫查詢
    try:
        if trip_data.get('date') and trip_data.get('time'):
            from datetime import datetime, timedelta
            import pytz
            
            # 設置台灣時區
            taiwan_tz = pytz.timezone('Asia/Taipei')
            current_time = datetime.now(taiwan_tz)
            
            # 組合班次的完整執行時間（台灣時區）
            trip_date = trip_data['date']
            trip_time = trip_data['time'] 
            trip_datetime = datetime.combine(trip_date, trip_time)
            trip_datetime = taiwan_tz.localize(trip_datetime)
            
            # 計算30分鐘前的時間點
            restriction_start_time = trip_datetime - timedelta(minutes=30)
            
            # 檢查是否可以修改
            can_modify_status = current_time < restriction_start_time
            
            if not can_modify_status:
                if current_time >= trip_datetime:
                    restriction_message = f"⚠️ 班次已過執行時間，無法修改狀態 (執行時間: {trip_time.strftime('%H:%M')})"
                else:
                    remaining_time = trip_datetime - current_time
                    remaining_minutes = int(remaining_time.total_seconds() / 60)
                    restriction_message = f"⏰ 執行前30分鐘內不可修改狀態 (還有 {remaining_minutes} 分鐘執行，{restriction_start_time.strftime('%H:%M')}後即不可修改)"
        else:
            logger.warning(f"班次 {trip_id} 缺少日期或時間資訊，預設允許修改")
    except Exception as e:
        logger.error(f"檢查修改權限時出錯: {e}")
        # 🔥 修復：異常時預設允許修改，避免影響Flex Message生成
        can_modify_status = True
        restriction_message = ""
    
    # 格式化日期
    trip_date_obj = trip_data.get('date')
    formatted_date = "日期未定"
    if trip_date_obj:
        weekday_names = ["一", "二", "三", "四", "五", "六", "日"]
        weekday = weekday_names[trip_date_obj.weekday()]
        formatted_date = f"{trip_date_obj.month}/{trip_date_obj.day} (星期{weekday})"
    
    # 格式化時間
    trip_time_obj = trip_data.get('time')
    formatted_time = trip_time_obj.strftime('%H:%M') if trip_time_obj else '時間未定'

    # 構建 body contents
    body_contents = [
        { "type": "box", "layout": "horizontal", "margin":"md", "contents": [ { "type": "text", "text": "日期", "size": "sm", "color": "#555555", "flex": 2 },{ "type": "text", "text": formatted_date, "size": "sm", "color": "#111111", "flex": 5 }]},
        { "type": "box", "layout": "horizontal", "margin":"md", "contents": [ { "type": "text", "text": "時間", "size": "sm", "color": "#555555", "flex": 2 },{ "type": "text", "text": formatted_time, "size": "sm", "color": "#111111", "flex": 5 }]},
        { "type": "box", "layout": "horizontal", "margin":"md", "contents": [ { "type": "text", "text": "起點", "size": "sm", "color": "#555555", "flex": 2 },{ "type": "text", "text": trip_data.get('display_start_point', trip_data.get('start_point')) or '未指定', "size": "sm", "color": "#111111", "flex": 5, "wrap": True }]}
    ]

    display_via_point = trip_data.get('display_via_point', trip_data.get('via_point'))
    if display_via_point:
        body_contents.append({ "type": "box", "layout": "horizontal", "margin": "md", "contents": [ { "type": "text", "text": "途經", "size": "sm", "color": "#555555", "flex": 2 },{ "type": "text", "text": display_via_point, "size": "sm", "color": "#111111", "flex": 5, "wrap": True }]})
    
    body_contents.append({ "type": "box", "layout": "horizontal", "margin": "md", "contents": [ { "type": "text", "text": "終點", "size": "sm", "color": "#555555", "flex": 2 },{ "type": "text", "text": trip_data.get('display_end_point', trip_data.get('end_point')) or '未指定', "size": "sm", "color": "#111111", "flex": 5, "wrap": True }]})
    
    # 獲取顯示狀態
    try:
        from modules.handlers.passenger_leave_handler import get_display_status
        
        class TempTrip:
            def __init__(self, trip_data):
                self.status = trip_data.get('status')
                self.modification_reason = trip_data.get('modification_reason')
                self.passenger_leave_reason = trip_data.get('passenger_leave_reason')
        
        temp_trip = TempTrip(trip_data)
        display_status = get_display_status(temp_trip)
    except Exception as e:
        logger.error(f"獲取顯示狀態失敗: {e}")
        # 🔥 修復：回退到基本狀態，確保Flex Message能正常生成
        display_status = trip_data.get('status', '未指定')
    
    # 🔥 修復：將main_status移到try-catch外面，確保變量作用域正確
    main_status = display_status.split()[0] if display_status else '未指定'
    status_color_map = { "待派": "#FF6B6E", "準備": "#6CD8A0", "註銷": "#888888", "衝突": "#FF9153", "請假": "#A0A0FF", "完成": "#1DB446" }
    status_color = status_color_map.get(main_status, "#111111")
    
    body_contents.append({ "type": "box", "layout": "horizontal", "margin": "md", "contents": [ { "type": "text", "text": "狀態", "size": "sm", "color": "#555555", "flex": 2 },{ "type": "text", "text": display_status, "size": "sm", "color": status_color, "weight": "bold", "flex": 5, "wrap": True }]})
    
    # 司機
    if trip_data.get('driver_id'):
        body_contents.append({ "type": "box", "layout": "horizontal", "margin": "md", "contents": [ { "type": "text", "text": "司機", "size": "sm", "color": "#555555", "flex": 2 },{ "type": "text", "text": f"🚕{trip_data.get('driver_id')}", "size": "sm", "color": "#111111", "flex": 5 }]})
    else:
        body_contents.append({ "type": "box", "layout": "horizontal", "margin": "md", "contents": [ { "type": "text", "text": "司機", "size": "sm", "color": "#555555", "flex": 2 },{ "type": "text", "text": "未指派", "size": "sm", "color": "#111111", "flex": 5 }]})
    
    # 搭載人員
    passenger_name = trip_data.get('passenger_name')
    if passenger_name:
        try:
            from modules.utils.passenger_name_handler import get_passengers_display_text
            display_passenger = get_passengers_display_text(passenger_name)
            body_contents.append({ "type": "box", "layout": "horizontal", "margin": "md", "contents": [ { "type": "text", "text": "搭載人員", "size": "sm", "color": "#555555", "flex": 2 },{ "type": "text", "text": display_passenger, "size": "sm", "color": "#111111", "flex": 5, "wrap": True }]})
        except Exception as e:
            body_contents.append({ "type": "box", "layout": "horizontal", "margin": "md", "contents": [ { "type": "text", "text": "搭載人員", "size": "sm", "color": "#555555", "flex": 2 },{ "type": "text", "text": passenger_name, "size": "sm", "color": "#111111", "flex": 5, "wrap": True }]})
    
    # 車資
    if trip_data.get('base_fare') is not None:
        body_contents.append({ "type": "box", "layout": "horizontal", "margin": "md", "contents": [ { "type": "text", "text": "基本車資", "size": "sm", "color": "#555555", "flex": 2 },{ "type": "text", "text": f"{trip_data.get('base_fare')} 元", "size": "sm", "color": "#111111", "flex": 5 }]})

    extra_fare = trip_data.get('extra_fare')
    if extra_fare is not None:
        extra_fare_text = f"+{extra_fare}" if extra_fare >= 0 else str(extra_fare)
        body_contents.append({ "type": "box", "layout": "horizontal", "margin": "md", "contents": [ { "type": "text", "text": "加成", "size": "sm", "color": "#555555", "flex": 2 },{ "type": "text", "text": f"{extra_fare_text} 元", "size": "sm", "color": "#111111", "flex": 5 }]})

    body_contents.append({ "type": "box", "layout": "horizontal", "margin":"md", "contents": [ { "type": "text", "text": "類別", "size": "sm", "color": "#555555", "flex": 2 },{ "type": "text", "text": trip_data.get('category') or '未分類', "size": "sm", "color": "#111111", "flex": 5 }]})
    
    # 請假原因
    passenger_leave_reason = trip_data.get('passenger_leave_reason')
    if passenger_leave_reason:
        body_contents.append({ "type": "box", "layout": "horizontal", "margin": "md", "contents": [ { "type": "text", "text": "請假原因", "size": "sm", "color": "#555555", "flex": 2 },{ "type": "text", "text": passenger_leave_reason, "size": "sm", "color": "#A0A0FF", "flex": 5, "wrap": True }]})
    
    # 修改原因（非請假相關）
    modification_reason = trip_data.get('modification_reason')
    if modification_reason and not passenger_leave_reason:
        body_contents.append({ "type": "box", "layout": "horizontal", "margin": "md", "contents": [ { "type": "text", "text": "修改原因", "size": "sm", "color": "#555555", "flex": 2 },{ "type": "text", "text": modification_reason, "size": "sm", "color": "#FF9153", "flex": 5, "wrap": True }]})
    
    # 時間限制提示
    if not can_modify_status and restriction_message:
        body_contents.append({
            "type": "separator",
            "margin": "md"
        })
        body_contents.append({
            "type": "box",
            "layout": "vertical",
            "margin": "md",
            "contents": [
                {
                    "type": "text",
                    "text": restriction_message,
                    "size": "xs",
                    "color": "#FF6B6E",
                    "wrap": True,
                    "weight": "bold"
                }
            ],
            "backgroundColor": "#FFF5F5",
            "cornerRadius": "md",
            "paddingAll": "sm"
        })

    flex_message_payload = {
        "type": "bubble",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": f"班次 {trip_id} 詳細資訊",
                    "weight": "bold",
                    "size": "lg",
                    "color": "#FFFFFF",
                    "align": "center"
                }
            ],
            "backgroundColor": "#3B82F6",
            "paddingAll": "md"
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": body_contents
        }
    }
    
    # 🔧 修正：正確的 Quick Reply 邏輯
    quick_reply_items = []
    
    if can_modify_status:
        actionable_statuses = {
            "註銷": "❌ 註銷", 
            "衝突": "⚠️ 衝突", 
            "請假": "🔵 請假"
        }
        current_trip_status = trip_data.get('status') or '未指定'
        
        # 關鍵修正：基於 display_status 判斷
        is_leave_status = (main_status == "請假")

        if is_leave_status:
            # 請假狀態：只顯示「改回準備」
            quick_reply_items.append({
                "type": "action",
                "action": {
                    "type": "postback", 
                    "label": "🟢 改回準備",
                    "text": "🟢",  # 🔥 修復：簡短的 text 避免觸發命令處理
                    "data": f"action=update_status&trip_id={trip_id}&status=準備",
                    "displayText": "⏸️"  # 🔥 使用不在 KNOWN_COMMANDS 中的符號
                }
            })
        elif current_trip_status != "完成":
            # 非請假狀態：顯示正常按鈕
            if current_trip_status != "準備":
                quick_reply_items.append({
                    "type": "action",
                    "action": {
                        "type": "postback", 
                        "label": "🟢 改回準備",
                        "text": "🟢",  # 🔥 修復：簡短的 text 避免觸發命令處理
                        "data": f"action=update_status&trip_id={trip_id}&status=準備",
                        "displayText": "⏸️"  # 🔥 使用不在 KNOWN_COMMANDS 中的符號
                    }
                })
            
            for status_value, status_label in actionable_statuses.items():
                if status_value != current_trip_status:
                    # 為不同狀態使用不同的簡短 emoji
                    emoji_map = {"註銷": "❌", "衝突": "⚠️", "請假": "🔵"}
                    text_emoji = emoji_map.get(status_value, "🎯")
                    
                    quick_reply_items.append({
                        "type": "action",
                        "action": {
                            "type": "postback", 
                            "label": status_label,
                            "text": text_emoji,  # 🔥 修復：簡短的 emoji 避免觸發命令處理
                            "data": f"action=update_status&trip_id={trip_id}&status={status_value}",
                            "displayText": "⏸️"  # 🔥 使用不在 KNOWN_COMMANDS 中的符號
                        }
                    })
    
    final_quick_reply = {"items": quick_reply_items} if quick_reply_items else None
            
    return {
        "flex_message": flex_message_payload,
        "quick_reply": final_quick_reply
    } 