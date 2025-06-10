"""
此模塊包含班次詳情的 Flex Message 設計
"""

import logging
logger = logging.getLogger(__name__)
from datetime import datetime, timedelta

def get_trip_details_flex(trip_id, trip_data):
    """
    生成班次詳情的 Flex Message (最新版本：藍色表頭，無內部按鈕，新 Quick Reply)
    支援基於執行時間的30分鐘修改限制功能
    """
    logger.info(f">>>>> EXECUTING LATEST VERSION OF: /modules/flex_designs/trip_details_flex.py - get_trip_details_flex for trip {trip_id} <<<<<")
    
    # 🚨 新增：檢查基於執行時間的30分鐘修改限制
    can_modify_status = True
    restriction_message = ""
    
    try:
        # 從資料庫查詢完整的Trip對象以獲取時間信息
        from modules.models.trip import Trip
        from modules.models.base import db
        
        trip = db.session.query(Trip).filter_by(trip_id=trip_id).first()
        
        if trip:
            can_modify_status = trip.can_modify_status()
            if not can_modify_status:
                restriction_message = trip.get_restriction_message()
                logger.info(f"班次 {trip_id} 在時間限制內，不顯示狀態修改按鈕")
            else:
                logger.info(f"班次 {trip_id} 可以修改狀態")
    except Exception as e:
        logger.error(f"檢查修改權限時出錯: {e}")
        # 如果檢查失敗，預設允許修改（向下兼容）
    
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

    flex_message_payload = {
        "type": "bubble",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": f"班次 {trip_id} 詳細資訊", # 移除了 (v2) 和 (SERVICE LOCAL)
                    "weight": "bold",
                    "size": "lg",
                    "color": "#FFFFFF",
                    "align": "center"
                }
            ],
            "backgroundColor": "#3B82F6", # 期望的藍色
            "paddingAll": "md"
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "box", "layout": "horizontal", "margin":"md",
                    "contents": [
                        { "type": "text", "text": "日期", "size": "sm", "color": "#555555", "flex": 2 },
                        { "type": "text", "text": formatted_date, "size": "sm", "color": "#111111", "flex": 5 }
                    ]
                },
                {
                    "type": "box", "layout": "horizontal", "margin":"md",
                    "contents": [
                        { "type": "text", "text": "時間", "size": "sm", "color": "#555555", "flex": 2 },
                        { "type": "text", "text": formatted_time, "size": "sm", "color": "#111111", "flex": 5 }
                    ]
                },
                {
                    "type": "box", "layout": "horizontal", "margin":"md",
                    "contents": [
                        { "type": "text", "text": "起點", "size": "sm", "color": "#555555", "flex": 2 },
                        { "type": "text", "text": trip_data.get('display_start_point', trip_data.get('start_point')) or '未指定', "size": "sm", "color": "#111111", "flex": 5, "wrap": True }
                    ]
                }
                # ... 在此處繼續添加 via_point, end_point, status, driver, plate, category, base_fare 等顯示欄位 ...
                # 確保這裡沒有添加內部按鈕的邏輯
            ]
        }
        # Footer (內部按鈕) 已被移除
    }

    # 完整 body.contents 的構建 (複製自之前確認的正確版本，並移除內部按鈕部分)
    body_contents = [
        { "type": "box", "layout": "horizontal", "margin":"md", "contents": [ { "type": "text", "text": "日期", "size": "sm", "color": "#555555", "flex": 2 },{ "type": "text", "text": formatted_date, "size": "sm", "color": "#111111", "flex": 5 }]},
        { "type": "box", "layout": "horizontal", "margin":"md", "contents": [ { "type": "text", "text": "時間", "size": "sm", "color": "#555555", "flex": 2 },{ "type": "text", "text": formatted_time, "size": "sm", "color": "#111111", "flex": 5 }]},
        { "type": "box", "layout": "horizontal", "margin":"md", "contents": [ { "type": "text", "text": "起點", "size": "sm", "color": "#555555", "flex": 2 },{ "type": "text", "text": trip_data.get('display_start_point', trip_data.get('start_point')) or '未指定', "size": "sm", "color": "#111111", "flex": 5, "wrap": True }]}
    ]

    display_via_point = trip_data.get('display_via_point', trip_data.get('via_point'))
    if display_via_point:
        body_contents.append({ "type": "box", "layout": "horizontal", "margin": "md", "contents": [ { "type": "text", "text": "途經", "size": "sm", "color": "#555555", "flex": 2 },{ "type": "text", "text": display_via_point, "size": "sm", "color": "#111111", "flex": 5, "wrap": True }]})
    
    body_contents.append({ "type": "box", "layout": "horizontal", "margin": "md", "contents": [ { "type": "text", "text": "終點", "size": "sm", "color": "#555555", "flex": 2 },{ "type": "text", "text": trip_data.get('display_end_point', trip_data.get('end_point')) or '未指定', "size": "sm", "color": "#111111", "flex": 5, "wrap": True }]})
    
    # 🔥 新增：檢查是否為乘客請假狀態
    from modules.handlers.passenger_leave_handler import get_display_status
    
    # 創建一個臨時對象來傳遞給 get_display_status
    class TempTrip:
        def __init__(self, trip_data):
            self.status = trip_data.get('status')
            self.modification_reason = trip_data.get('modification_reason')
            self.passenger_leave_reason = trip_data.get('passenger_leave_reason')
    
    temp_trip = TempTrip(trip_data)
    display_status = get_display_status(temp_trip)
    
    status_color_map = { "待派": "#FF6B6E", "準備": "#6CD8A0", "取消": "#888888", "衝突": "#FF9153", "請假": "#A0A0FF", "完成": "#1DB446" }
    # 提取顯示狀態的主要部分來選擇顏色
    main_status = display_status.split()[0] if display_status else '未指定'
    status_color = status_color_map.get(main_status, "#111111")
    
    body_contents.append({ "type": "box", "layout": "horizontal", "margin": "md", "contents": [ { "type": "text", "text": "狀態", "size": "sm", "color": "#555555", "flex": 2 },{ "type": "text", "text": display_status, "size": "sm", "color": status_color, "weight": "bold", "flex": 5, "wrap": True }]})
    
    if trip_data.get('driver_id'):
        body_contents.append({ "type": "box", "layout": "horizontal", "margin": "md", "contents": [ { "type": "text", "text": "司機", "size": "sm", "color": "#555555", "flex": 2 },{ "type": "text", "text": f"🚕{trip_data.get('driver_id')}", "size": "sm", "color": "#111111", "flex": 5 }]})
        # 🔥 移除車牌顯示（按用戶要求）
    else:
        body_contents.append({ "type": "box", "layout": "horizontal", "margin": "md", "contents": [ { "type": "text", "text": "司機", "size": "sm", "color": "#555555", "flex": 2 },{ "type": "text", "text": "未指派", "size": "sm", "color": "#111111", "flex": 5 }]})
    
    # 🔥 調整順序：先顯示基本車資
    if trip_data.get('base_fare') is not None:
        body_contents.append({ "type": "box", "layout": "horizontal", "margin": "md", "contents": [ { "type": "text", "text": "基本車資", "size": "sm", "color": "#555555", "flex": 2 },{ "type": "text", "text": f"{trip_data.get('base_fare')} 元", "size": "sm", "color": "#111111", "flex": 5 }]})

    # 🔥 然後顯示加成
    extra_fare = trip_data.get('extra_fare')
    if extra_fare is not None:
        extra_fare_text = f"+{extra_fare}" if extra_fare >= 0 else str(extra_fare)
        body_contents.append({ "type": "box", "layout": "horizontal", "margin": "md", "contents": [ { "type": "text", "text": "加成", "size": "sm", "color": "#555555", "flex": 2 },{ "type": "text", "text": f"{extra_fare_text} 元", "size": "sm", "color": "#111111", "flex": 5 }]})

    body_contents.append({ "type": "box", "layout": "horizontal", "margin":"md", "contents": [ { "type": "text", "text": "類別", "size": "sm", "color": "#555555", "flex": 2 },{ "type": "text", "text": trip_data.get('category') or '未分類', "size": "sm", "color": "#111111", "flex": 5 }]})
    
    # 🔥 新增：顯示請假原因（如果有）
    passenger_leave_reason = trip_data.get('passenger_leave_reason')
    if passenger_leave_reason:
        body_contents.append({ "type": "box", "layout": "horizontal", "margin": "md", "contents": [ { "type": "text", "text": "請假原因", "size": "sm", "color": "#555555", "flex": 2 },{ "type": "text", "text": passenger_leave_reason, "size": "sm", "color": "#A0A0FF", "flex": 5, "wrap": True }]})
    
    # 🔥 新增：顯示修改原因（如果有且不是請假相關）
    modification_reason = trip_data.get('modification_reason')
    if modification_reason and not passenger_leave_reason:  # 避免重複顯示請假原因
        body_contents.append({ "type": "box", "layout": "horizontal", "margin": "md", "contents": [ { "type": "text", "text": "修改原因", "size": "sm", "color": "#555555", "flex": 2 },{ "type": "text", "text": modification_reason, "size": "sm", "color": "#FF9153", "flex": 5, "wrap": True }]})
    
    # 🚨 新增：如果有時間限制，顯示提示信息
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
    
    flex_message_payload["body"]["contents"] = body_contents
    
    # Construct Quick Reply based on actionable statuses
    quick_reply_items = []
    
    # 🚨 修改：只有在可以修改狀態時才顯示Quick Reply按鈕
    if can_modify_status:
        actionable_statuses = {
            "取消": "❌ 取消", 
            "衝突": "⚠️ 衝突", 
            "請假": "🔵 請假"
        }
        current_trip_status = trip_data.get('status') or '未指定'

        # 1. Offer "改回準備" if current status is not "準備" and not "完成"
        if current_trip_status not in ["準備", "完成"]:
            quick_reply_items.append({
                "type": "action",
                "action": {
                    "type": "postback", "label": "🟢 改回準備",
                    "data": f"action=update_status&trip_id={trip_id}&status=準備",
                    "displayText": f"將班次 {trip_id} 狀態修改為 準備"
                }
            })
            # logger.info(f"Trip {trip_id}: Added '改回準備' QR.")

        # 2. Offer other actionable statuses if current status is not "完成"
        if current_trip_status != "完成":
            for status_value, status_label in actionable_statuses.items():
                if status_value != current_trip_status:
                    quick_reply_items.append({
                        "type": "action",
                        "action": {
                            "type": "postback", "label": status_label,
                            "data": f"action=update_status&trip_id={trip_id}&status={status_value}",
                            "displayText": f"將班次 {trip_id} 狀態修改為 {status_value}"
                        }
                    })
                    # logger.info(f"Trip {trip_id}: Added '{status_label}' QR.")
    else:
        logger.info(f"班次 {trip_id} 在時間限制內，不顯示Quick Reply按鈕")
    
    final_quick_reply = {"items": quick_reply_items} if quick_reply_items else None
    # logger.info(f"Trip {trip_id}: Final quick_reply_items count: {len(quick_reply_items) if quick_reply_items else 0}")
            
    return {
        "flex_message": flex_message_payload,
        "quick_reply": final_quick_reply
    }

if __name__ == '__main__':
    from datetime import date, time
    test_data = {
        'date': date(2025, 3, 17), 'time': datetime.strptime('09:50', '%H:%M').time(),
        'start_point': '仁和路', 'via_point': "經由點A", 'end_point': '診所', 'status': '準備',
        'driver_id': '533', 'plate_number': 'XYZ-789', 'category': '診所', 'base_fare': 220,
        'display_start_point': '仁和路', 'display_via_point': "經由點A", 'display_end_point': '診所'
    }
    import json
    print("Testing LATEST get_trip_details_flex:")
    print(json.dumps(get_trip_details_flex('test_id_123', test_data), indent=2, ensure_ascii=False))

    test_data_no_via = {
        'date': date(2025, 3, 18), 'time': datetime.strptime('10:50', '%H:%M').time(),
        'start_point': '家裡', 'via_point': None, 'end_point': '公司', 'status': '待派',
        'driver_id': None, 'plate_number': None, 'category': '臨時', 'base_fare': 150,
        'display_start_point': '家裡', 'display_via_point': None, 'display_end_point': '公司'
    }
    print("\nTesting LATEST get_trip_details_flex (no via, to be assigned):")
    print(json.dumps(get_trip_details_flex('test_id_456', test_data_no_via), indent=2, ensure_ascii=False))

    test_data_completed = {
        'date': date(2025, 3, 19), 'time': datetime.strptime('11:50', '%H:%M').time(),
        'start_point': 'A點', 'via_point': "B點", 'end_point': 'C點', 'status': '完成',
        'driver_id': '777', 'plate_number': 'ABC-123', 'category': '東洋', 'base_fare': 300,
        'display_start_point': 'A點', 'display_via_point': "B點", 'display_end_point': 'C點'
    }
    print("\nTesting LATEST get_trip_details_flex (completed):")
    print(json.dumps(get_trip_details_flex('test_id_789', test_data_completed), indent=2, ensure_ascii=False)) 