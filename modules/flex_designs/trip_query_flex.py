# modules/flex_designs/trip_query_flex.py
import logging # Logger can be removed if not used elsewhere in this file after cleanup
logger = logging.getLogger(__name__) # Can be removed

def generate_trips_flex(trips_data, date_str=None, is_fixed_trips=False):
    """
    生成班次查詢結果的 Flex Message
    
    參數:
        trips_data: 班次數據列表，每個元素包含班次信息
        date_str: 日期字符串，用於顯示在標題中
        is_fixed_trips: 是否為固定班次查詢
    
    返回:
        Flex Message 字典
    """
    # 創建基本結構
    bubble = {
        "type": "bubble",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": f"班次查詢結果" if not is_fixed_trips else f"固定班次查詢結果",
                    "weight": "bold",
                    "size": "md",
                    "color": "#ffffff"
                }
            ],
            "backgroundColor": "#4682B4",
            "paddingTop": "8px",
            "paddingBottom": "8px",
            "paddingStart": "12px",
            "paddingEnd": "12px"
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [],
            "spacing": "md"
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "輸入「班次詳情 [ID]」查看詳細信息",
                    "size": "xs",
                    "color": "#888888",
                    "wrap": True,
                    "align": "center"
                }
            ]
        }
    }
    
    # 按日期分組處理數據
    current_date = None
    
    for trip_index, trip in enumerate(trips_data):
        # --- REMOVED: Detailed logging for each trip --- 
        # logger.info(f"[generate_trips_flex] Processing trip #{trip_index + 1} - Raw data: {trip}")
        # logger.info(f"[generate_trips_flex] is_fixed_trips param: {is_fixed_trips}")
        # --- END REMOVED LOGGING ---
        try:
            trip_id = trip[0]
            trip_date = trip[1]
            time_val = trip[2].strftime("%H:%M") if trip[2] else "--:--"
            start_point_db = trip[3]
            end_point_db = trip[4]
            direction = trip[5]  # "來" 或 "回"
            status = trip[6] or "未指定"
            driver_id = trip[7] or "未指派"
            trip_type = trip[8] if len(trip) > 8 else "fixed" 
            custom_start_point = trip[9] if len(trip) > 9 else None
            custom_end_point = trip[10] if len(trip) > 10 else None
            category = trip[11] if len(trip) > 11 else None
            passenger_leave_reason = trip[12] if len(trip) > 12 else None
            modification_reason = trip[13] if len(trip) > 13 else None
            
            # --- REMOVED: Logging for determined trip_type and direction --- 
            # logger.info(f"[generate_trips_flex] Trip ID {trip_id}: Determined trip_type='{trip_type}', direction='{direction}'")
            # logger.info(f"[generate_trips_flex] Trip ID {trip_id}: start_point_db='{start_point_db}', end_point_db='{end_point_db}'")
            # logger.info(f"[generate_trips_flex] Trip ID {trip_id}: custom_start_point='{custom_start_point}', custom_end_point='{custom_end_point}'")
            # --- END REMOVED LOGGING --- 

            location_display_text = ""
            if trip_type == "temp":
                # --- MODIFIED: For temp trips, only show the start point --- 
                start = custom_start_point or start_point_db or "未提供起點"
                location_display_text = start
                # --- END MODIFICATION ---
            
            else: # Fixed trips or other types
                # logger.info(f"[generate_trips_flex] Trip ID {trip_id}: Entered \'else\' (non-temp) type logic.") # Removed
                if direction == "來":
                    location_display_text = (start_point_db or "未指定") + " (來)"
                elif direction == "回":
                    end_point_db = trip[4] # Ensure end_point_db is defined here
                    location_display_text = (end_point_db or "未指定") + " (回)"
                else:
                    s = start_point_db or "?"
                    e = trip[4] or "?" # Ensure end_point_db is defined here
                    location_display_text = f"{s} → {e}"
            
            # logger.info(f"[generate_trips_flex] Trip ID {trip_id}: Final location_display_text=\'{location_display_text}\'\") # Removed
        
            # 如果日期變了，添加日期標題
            if current_date != trip_date:
                current_date = trip_date
                weekday_names = ["一", "二", "三", "四", "五", "六", "日"]
                weekday = weekday_names[current_date.weekday()]
                date_title = f"{current_date.month}/{current_date.day} (星期{weekday})"
            
                # 添加日期分隔線 (如果不是第一個日期)
                if bubble["body"]["contents"]:
                    bubble["body"]["contents"].append({
                        "type": "separator",
                        "margin": "md"
                    })
            
                # 添加日期標題
                bubble["body"]["contents"].append({
                    "type": "text",
                    "text": f"【{date_title}】",
                    "weight": "bold",
                    "size": "md",
                    "margin": "md"
                })
        
            # 🚨 新增：檢查是否為乘客請假狀態
            display_status = status
            
            # 優先檢查新的passenger_leave_reason欄位
            if passenger_leave_reason:
                display_status = "請假"
            # 回退檢查舊的modification_reason欄位
            elif modification_reason and ("乘客請假" in modification_reason or "請假" in modification_reason):
                display_status = "請假"
        
            # 根據狀態添加不同的表情符號
            status_emoji = {
                "準備": "🟢",
                "完成": "✅",
                "取消": "❌",
                "衝突": "⚠️",
                "請假": "🔵",
                "待派": "🟠"
            }.get(display_status, "⚪")
        
            # 根據班次類型設定顏色
            text_color = "#333333" if trip_type == "fixed" else "#0000FF"  # 固定班次為黑色，臨時班次為藍色
            background_color = None if trip_type == "fixed" else "#E6E6FA"  # 臨時班次有淡紫色背景
        
            # 添加班次信息
            trip_box = {
                "type": "box",
                "layout": "horizontal",
                "spacing": "sm",
                "contents": [
                    {
                        "type": "text",
                        "text": f"{status_emoji} {trip_id}",
                        "size": "xs",  # 🔧 改回xs，現在態保持原來字體大小
                        "flex": 3,
                        "color": text_color,
                        "align": "start"
                    },
                    {
                        "type": "text",
                        "text": time_val,
                        "size": "xs",  # 🔧 改回xs，現在態保持原來字體大小
                        "flex": 2,
                        "color": text_color,
                        "align": "start"
                    },
                    {
                        "type": "text",
                        "text": location_display_text,
                        "size": "xs",  # 🔧 改回xs，現在態保持原來字體大小
                        "flex": 4,
                        "wrap": True,
                        "color": text_color,
                        "align": "start"
                    },
                    {
                        "type": "text",
                        "text": f"🚕{driver_id}",
                        "size": "xs",  # 🔧 改回xs，現在態保持原來字體大小
                        "flex": 3,
                        "align": "end",
                        "color": text_color
                    }
                ],
                "margin": "sm",
                "action": {
                    "type": "message",
                    "text": f"班次詳情 {trip_id}"
                }
            }
        
            # 如果是臨時班次，添加背景色
            if background_color:
                trip_box["backgroundColor"] = background_color
                trip_box["cornerRadius"] = "sm"
                trip_box["paddingAll"] = "sm"
        
            bubble["body"]["contents"].append(trip_box)
        except Exception as e:
            # Keep this error logging for individual trip processing errors
            # from flask import current_app # Import current_app only if used here
            # current_app_logger = current_app.logger if current_app else logger
            # current_app_logger.error(f"Error processing trip data in generate_trips_flex: {trip}. Error: {e}", exc_info=True)
            # For simplicity, if current_app is not available here, use the module logger or print
            logger.error(f"Error processing trip data in generate_trips_flex (trip: {trip_id if 'trip_id' in locals() else 'unknown'}): {e}", exc_info=True)
            # ... (error indicator in flex message) ...
            continue
    return bubble
