from datetime import date, datetime, timezone, timedelta
from sqlalchemy import text as sql_text
from flask import current_app
import traceback

from modules.models.base import db
from modules.utils.helpers import parse_date_input, get_taiwan_time, get_taiwan_date

def handle_query_fixed_trips_flex(message_text=None):
    """返回Flex Message格式的固定班次查詢結果"""
    try:
        current_app.logger.info(f"handle_query_fixed_trips_flex被調用，參數: {message_text}")
        # 解析日期參數（如果有）
        if message_text and len(message_text.split()) > 1:
            try:
                # 嘗試解析指定日期
                current_app.logger.info(f"嘗試解析日期: {message_text.split()[1]}")
                query_date = parse_date_input(message_text.split()[1])
                current_app.logger.info(f"解析結果: {query_date}")
            except ValueError as e:
                current_app.logger.error(f"日期解析錯誤: {str(e)}")
                return None, f"日期格式不正確: {str(e)}\n\n支持的格式：\n- YYYY-MM-DD (例如: 2025-03-11)\n- MM-DD (例如: 03-11)\n- MM/DD (例如: 3/11)\n- MM月DD日 (例如: 3月11日)\n- MMDD (例如: 0311)\n- 今天, 明天, 後天"
        else:
            # 默認使用今天的台灣時間日期
            query_date = get_taiwan_date()
            current_app.logger.info(f"使用默認日期（今天台灣時間）: {query_date}")
        
        # 查詢指定日期的固定班次
        query = f"""
        SELECT 
            t.trip_id, 
            t.time, 
            t.start_point, 
            t.via_point,
            t.end_point, 
            fs.direction,
            t.status,
            d.id as driver_id
        FROM 
            trips t
        JOIN
            fixed_schedules fs ON t.fixed_trip_id = fs.id
        LEFT JOIN 
            drivers d ON t.driver_id = d.id
        WHERE 
            t.date = '{query_date}'
        ORDER BY 
            t.time
        """
        
        current_app.logger.info(f"執行SQL查詢: {query}")
        trips = db.session.execute(sql_text(query)).fetchall()
        current_app.logger.info(f"查詢結果: {len(trips)} 條記錄")
        
        if not trips:
            # 使用友好的日期格式
            weekday_names = ["一", "二", "三", "四", "五", "六", "日"]
            weekday = weekday_names[query_date.weekday()]
            formatted_date = f"{query_date.month}/{query_date.day} (星期{weekday})"
            current_app.logger.info(f"沒有找到固定班次: {formatted_date}")
            return None, f"{formatted_date} 沒有固定班次。"
        
        # 使用友好的日期格式
        weekday_names = ["一", "二", "三", "四", "五", "六", "日"]
        weekday = weekday_names[query_date.weekday()]
        formatted_date = f"{query_date.month}/{query_date.day} (星期{weekday})"
        current_app.logger.info(f"格式化日期: {formatted_date}")
        
        # 創建Flex Message內容
        bubble = {
            "type": "bubble",
            "header": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": f"固定班次 {formatted_date}",
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
                "contents": [
                    {
                        "type": "box",
                        "layout": "horizontal",
                        "contents": [
                            {
                                "type": "text",
                                "text": "班次",
                                "size": "xs",
                                "color": "#aaaaaa",
                                "flex": 3
                            },
                            {
                                "type": "text",
                                "text": "時間",
                                "size": "xs",
                                "color": "#aaaaaa",
                                "flex": 2
                            },
                            {
                                "type": "text",
                                "text": "地點",
                                "size": "xs",
                                "color": "#aaaaaa",
                                "flex": 5
                            },
                            {
                                "type": "text",
                                "text": "司機",
                                "size": "xs",
                                "color": "#aaaaaa",
                                "flex": 2,
                                "align": "end"
                            }
                        ],
                        "margin": "xs"
                    },
                    {
                        "type": "separator",
                        "margin": "sm"
                    }
                ],
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
        
        # 添加班次信息
        for trip in trips:
            trip_id = trip[0]
            time_val = trip[1].strftime("%H:%M") if trip[1] else "--:--"
            direction = trip[5] or "來"  # 默認為"來"
            
            # 根據方向決定顯示起點還是終點
            if direction == "來":
                location = trip[2] or "未指定"  # 起點
            else:  # "回"
                location = trip[4] or "未指定"  # 終點
            
            status = trip[6] or "未指定"
            driver_id = trip[7] or "未指派"
            
            # 根據狀態添加不同的表情符號
            status_emoji = {
                "準備": "🟢",
                "完成": "✅",
                "取消": "❌",
                "衝突": "⚠️",
                "請假": "🔵",
                "待派": "🟠"
            }.get(status, "⚪")
            
            # 添加班次信息
            trip_box = {
                "type": "box",
                "layout": "horizontal",
                "contents": [
                    {
                        "type": "text",
                        "text": f"{status_emoji} #{trip_id}",
                        "size": "xs",
                        "flex": 3
                    },
                    {
                        "type": "text",
                        "text": time_val,
                        "size": "xs",
                        "flex": 2
                    },
                    {
                        "type": "text",
                        "text": f"{location}{direction}",
                        "size": "xs",
                        "flex": 5,
                        "wrap": True
                    },
                    {
                        "type": "text",
                        "text": f"🚕{driver_id}",
                        "size": "xs",
                        "flex": 2,
                        "align": "end"
                    }
                ],
                "margin": "sm",
                "action": {
                    "type": "message",
                    "text": f"班次詳情 {trip_id}"
                }
            }
            
            bubble["body"]["contents"].append(trip_box)
        
        current_app.logger.info("成功創建固定班次Flex Message")
        return bubble, None
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        current_app.logger.error(f"處理查詢固定班次時出錯: {str(e)}")
        return None, f"查詢固定班次錯誤: {str(e)}"

def handle_query_fixed_trips(message_text=None):
    """返回文本格式的固定班次查詢結果"""
    try:
        # 解析日期參數（如果有）
        if message_text and len(message_text.split()) > 1:
            try:
                # 嘗試解析指定日期
                query_date = parse_date_input(message_text.split()[1])
            except ValueError as e:
                return f"日期格式不正確: {str(e)}\n\n支持的格式：\n- YYYY-MM-DD (例如: 2025-03-11)\n- MM-DD (例如: 03-11)\n- MM/DD (例如: 3/11)\n- MM月DD日 (例如: 3月11日)\n- MMDD (例如: 0311)\n- 今天, 明天, 後天"
        else:
            # 默認使用今天的台灣時間日期
            query_date = get_taiwan_date()
        
        # 查詢指定日期的固定班次
        query = f"""
        SELECT 
            t.trip_id, 
            t.time, 
            t.start_point, 
            t.via_point,
            t.end_point, 
            fs.direction,
            t.status,
            d.id as driver_id
        FROM 
            trips t
        JOIN
            fixed_schedules fs ON t.fixed_trip_id = fs.id
        LEFT JOIN 
            drivers d ON t.driver_id = d.id
        WHERE 
            t.date = '{query_date}'
        ORDER BY 
            t.time
        """
        
        trips = db.session.execute(sql_text(query)).fetchall()
        
        if not trips:
            # 使用友好的日期格式
            weekday_names = ["一", "二", "三", "四", "五", "六", "日"]
            weekday = weekday_names[query_date.weekday()]
            formatted_date = f"{query_date.month}/{query_date.day} (星期{weekday})"
            return f"{formatted_date} 沒有固定班次。"
        
        # 格式化班次信息為簡潔的列表
        # 使用友好的日期格式
        weekday_names = ["一", "二", "三", "四", "五", "六", "日"]
        weekday = weekday_names[query_date.weekday()]
        formatted_date = f"{query_date.month}/{query_date.day} (星期{weekday})"
        reply_text = f"📅 {formatted_date} 固定班次總覽：\n\n"
        
        for trip in trips:
            trip_id = trip[0]
            time_val = trip[1].strftime("%H:%M") if trip[1] else "--:--"
            direction = trip[5] or "來"  # 默認為"來"
            
            # 根據方向決定顯示起點還是終點
            if direction == "來":
                location = trip[2] or "未指定"  # 起點
            else:  # "回"
                location = trip[4] or "未指定"  # 終點
            
            status = trip[6] or "未指定"
            driver_id = trip[7] or "未指派"  # 使用司機ID
            
            # 根據狀態添加不同的表情符號
            status_emoji = {
                "準備": "🟢",
                "完成": "✅",
                "取消": "❌",
                "衝突": "⚠️",
                "請假": "🔵"
            }.get(status, "⚪")
            
            # 使用黃色小車表情符號代替"司機#"
            # 格式化為簡潔的一行，添加班次ID，使用司機ID
            reply_text += f"{status_emoji} #{trip_id} {time_val} {location}{direction} - 🚕{driver_id}\n"
        
        reply_text += "\n輸入「班次詳情 [ID]」查看特定班次的詳細信息。"
        
        return reply_text
        
    except Exception as e:
        return f"查詢固定班次錯誤: {str(e)}" 