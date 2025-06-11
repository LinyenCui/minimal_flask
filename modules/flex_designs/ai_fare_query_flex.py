"""
AI 車資查詢專用 Flex Message 設計
"""

import logging
from datetime import datetime
from linebot.v3.messaging import FlexMessage, FlexContainer, QuickReply, QuickReplyItem, MessageAction

logger = logging.getLogger(__name__)

def create_ai_search_result_flex(search_info, trips, confidence):
    """
    創建AI搜索結果的Flex Message
    
    Args:
        search_info: 搜索信息字典
        trips: 搜索到的班次列表
        confidence: 搜索信心度
    
    Returns:
        FlexMessage: AI搜索結果的Flex Message
    """
    try:
        query = search_info.get('query', '')
        criteria_text = search_info.get('criteria_text', '')
        
        # 構建表頭
        header_text = "🔍 AI智能搜索結果"
        if confidence == 'low':
            header_text += " (需確認)"
        elif confidence == 'very_low':
            header_text += " (待澄清)"
        
        # 構建主體內容
        body_contents = [
            {
                "type": "text",
                "text": f"💬 {query}",
                "size": "sm",
                "color": "#666666",
                "wrap": True
            }
        ]
        
        if criteria_text:
            body_contents.append({
                "type": "text", 
                "text": f"🧠 {criteria_text}",
                "size": "xs",
                "color": "#999999", 
                "wrap": True,
                "margin": "sm"
            })
        
        body_contents.append({
            "type": "separator",
            "margin": "md"
        })
        
        # 處理搜索結果
        if not trips:
            body_contents.append({
                "type": "text",
                "text": "❌ 找不到符合條件的班次記錄",
                "size": "md",
                "color": "#FF6B6E",
                "weight": "bold",
                "margin": "md"
            })
            
            body_contents.append({
                "type": "text",
                "text": "💡 建議嘗試更寬泛的條件或使用「查已完成」查看完整列表",
                "size": "xs",
                "color": "#666666",
                "wrap": True,
                "margin": "sm"
            })
            
        elif len(trips) == 1:
            # 單個結果
            trip = trips[0]
            meter_fare = trip.get('meter_fare', 0) or 0
            extra_fare = trip.get('extra_fare', 0) or 0
            
            if extra_fare >= 0:
                fare_display = f"錶價 {meter_fare}, 加成 {extra_fare}"
            else:
                fare_display = f"錶價 {meter_fare}, 加成 {extra_fare}"
            
            body_contents.extend([
                {
                    "type": "text",
                    "text": "🎯 找到唯一匹配的班次：",
                    "size": "md",
                    "color": "#4CAF50",
                    "weight": "bold",
                    "margin": "md"
                },
                {
                    "type": "text",
                    "text": f"📋 班次 #{trip['id']} ({trip.get('category', '未分類')})",
                    "size": "sm",
                    "weight": "bold",
                    "margin": "sm"
                },
                {
                    "type": "text", 
                    "text": f"📍 {trip.get('start_point', '?')} → {trip.get('end_point', '?')}",
                    "size": "sm",
                    "margin": "xs"
                },
                {
                    "type": "text",
                    "text": f"🚕 {trip.get('driver_id', 'N/A')} | 💰 {fare_display}",
                    "size": "sm", 
                    "margin": "xs"
                }
            ])
            
        else:
            # 多個結果 - 顯示前5個
            body_contents.append({
                "type": "text",
                "text": f"🎯 找到 {len(trips)} 個匹配班次：",
                "size": "md",
                "color": "#FF9800",
                "weight": "bold",
                "margin": "md"
            })
            
            display_count = min(5, len(trips))
            for i, trip in enumerate(trips[:display_count]):
                meter_fare = trip.get('meter_fare', 0) or 0
                extra_fare = trip.get('extra_fare', 0) or 0
                
                if extra_fare >= 0:
                    fare_display = f"{meter_fare}+{extra_fare}"
                else:
                    fare_display = f"{meter_fare}{extra_fare}"
                
                body_contents.append({
                    "type": "text",
                    "text": f"📍 {i+1}. #{trip['id']} ({trip.get('category', '?')}) - {trip.get('start_point', '?')} → {trip.get('end_point', '?')} | 🚕{trip.get('driver_id', 'N/A')} | 💰{fare_display}",
                    "size": "xs",
                    "wrap": True,
                    "margin": "xs"
                })
            
            if len(trips) > 5:
                body_contents.append({
                    "type": "text",
                    "text": f"...還有 {len(trips) - 5} 個班次",
                    "size": "xs",
                    "color": "#666666",
                    "margin": "xs"
                })
        
        # 構建 Flex Message
        flex_content = {
            "type": "bubble",
            "header": {
                "type": "box",
                "layout": "vertical", 
                "contents": [
                    {
                        "type": "text",
                        "text": header_text,
                        "weight": "bold",
                        "size": "lg",
                        "color": "#FFFFFF"
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
        
        # 創建 Quick Reply (如果有單個結果)
        quick_reply = None
        if len(trips) == 1:
            trip = trips[0]
            quick_reply_items = [
                QuickReplyItem(
                    action=MessageAction(
                        label="💰 修改車資",
                        text=f"修改班次#{trip['id']} 車資"
                    )
                ),
                QuickReplyItem(
                    action=MessageAction(
                        label="📋 查看詳情", 
                        text=f"班次詳情 {trip['id']}"
                    )
                )
            ]
            quick_reply = QuickReply(items=quick_reply_items)
        
        # 🔥 修復：返回字典格式，和司機指派確認一致
        return {
            "flex_message": flex_content,  # 直接返回字典
            "quick_reply": quick_reply,    # Quick Reply 對象
            "alt_text": f"AI搜索結果: {query}"
        }
        
    except Exception as e:
        logger.error(f"創建AI搜索結果Flex Message時出錯: {e}")
        return None

def create_ai_very_low_confidence_flex(search_info):
    """創建信心度很低時的澄清Flex Message"""
    query = search_info.get('query', '')
    
    flex_content = {
        "type": "bubble",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "🤔 需要更多信息",
                    "weight": "bold",
                    "size": "lg", 
                    "color": "#FFFFFF"
                }
            ],
            "backgroundColor": "#FF9800",
            "paddingAll": "md"
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": f"💬 {query}",
                    "size": "sm",
                    "color": "#666666",
                    "wrap": True
                },
                {
                    "type": "separator",
                    "margin": "md"
                },
                {
                    "type": "text",
                    "text": "💡 請嘗試更明確的描述：",
                    "size": "md",
                    "weight": "bold",
                    "margin": "md"
                },
                {
                    "type": "text",
                    "text": "• 日期：「5/30」、「今天」、「昨天」\n• 司機：「司機123」、「123號司機」\n• 類別：「診所」、「東洋」、「臨時」\n• 班次ID：「班次#322」",
                    "size": "sm",
                    "wrap": True,
                    "margin": "sm"
                }
            ]
        }
    }
    
    # 🔥 修復：返回字典格式
    return {
        "flex_message": flex_content,
        "quick_reply": None,
        "alt_text": "AI查詢需要澄清"
    }

def create_ai_low_confidence_flex(search_info, understood_criteria):
    """創建信心度低時的確認Flex Message"""
    query = search_info.get('query', '')
    
    flex_content = {
        "type": "bubble", 
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "⚠️ 請確認理解",
                    "weight": "bold",
                    "size": "lg",
                    "color": "#FFFFFF"
                }
            ],
            "backgroundColor": "#FF9800",
            "paddingAll": "md"
        },
        "body": {
            "type": "box",
            "layout": "vertical", 
            "contents": [
                {
                    "type": "text",
                    "text": f"💬 {query}",
                    "size": "sm",
                    "color": "#666666",
                    "wrap": True
                },
                {
                    "type": "separator",
                    "margin": "md"
                },
                {
                    "type": "text",
                    "text": understood_criteria,
                    "size": "sm",
                    "wrap": True,
                    "margin": "md"
                }
            ]
        }
    }
    
    quick_reply = QuickReply(items=[
        QuickReplyItem(
            action=MessageAction(
                label="✅ 確認",
                text="確認"
            )
        ),
        QuickReplyItem(
            action=MessageAction(
                label="❌ 重新描述",
                text="重新查詢"
            )
        )
    ])
    
    # 🔥 修復：返回字典格式
    return {
        "flex_message": flex_content,
        "quick_reply": quick_reply,
        "alt_text": "AI查詢確認"
    }

def create_ai_clarification_flex(search_info, message, available_trips):
    """創建需要澄清的Flex Message"""
    query = search_info.get('query', '')
    
    body_contents = [
        {
            "type": "text",
            "text": f"💬 {query}",
            "size": "sm",
            "color": "#666666",
            "wrap": True
        },
        {
            "type": "separator",
            "margin": "md"
        },
        {
            "type": "text",
            "text": f"⚠️ {message}",
            "size": "sm",
            "color": "#FF6B6E",
            "wrap": True,
            "margin": "md"
        }
    ]
    
    # 添加可用班次摘要
    if available_trips:
        body_contents.append({
            "type": "text",
            "text": f"📋 找到 {len(available_trips)} 個相關班次：",
            "size": "md",
            "weight": "bold",
            "margin": "md"
        })
        
        for i, trip in enumerate(available_trips[:3]):
            body_contents.append({
                "type": "text",
                "text": f"{i+1}. #{trip['id']} - {trip.get('start_point', '?')} → {trip.get('end_point', '?')}",
                "size": "sm",
                "margin": "xs"
            })
    
    flex_content = {
        "type": "bubble",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "🤔 需要澄清",
                    "weight": "bold",
                    "size": "lg",
                    "color": "#FFFFFF"
                }
            ],
            "backgroundColor": "#FF9800",
            "paddingAll": "md"
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": body_contents
        }
    }
    
    # 🔥 修復：返回字典格式
    return {
        "flex_message": flex_content,
        "quick_reply": None,
        "alt_text": "AI查詢澄清"
    }

def create_ai_modification_result_flex(modification_info):
    """
    創建AI修改完成結果的Flex Message
    
    Args:
        modification_info: 修改信息字典，包含:
            - trip_id: 班次ID
            - category: 班次類別
            - route: 路線（start_point → end_point）
            - driver_id: 司機ID
            - old_meter: 舊錶價
            - old_extra: 舊加成
            - new_meter: 新錶價
            - new_extra: 新加成
            - reason: 修改原因
            - total_change: 總變化金額
    """
    try:
        trip_id = modification_info.get('trip_id')
        category = modification_info.get('category', '未分類')
        route = modification_info.get('route', '? → ?')
        driver_id = modification_info.get('driver_id', 'N/A')
        old_meter = modification_info.get('old_meter', 0)
        old_extra = modification_info.get('old_extra', 0)
        new_meter = modification_info.get('new_meter', 0)
        new_extra = modification_info.get('new_extra', 0)
        reason = modification_info.get('reason', '透過AI智能修改')
        total_change = modification_info.get('total_change', 0)
        
        # 構建變更詳情
        fare_change_text = f"💰 費用變更：{old_meter}+{old_extra} → {new_meter}+{new_extra}"
        total_change_text = f"📊 總計變化：{total_change:+d} 元"
        
        body_contents = [
            {
                "type": "text",
                "text": "🤖 AI智能修改完成",
                "size": "md",
                "weight": "bold",
                "color": "#4CAF50"
            },
            {
                "type": "separator",
                "margin": "md"
            },
            {
                "type": "text",
                "text": f"📋 班次：#{trip_id} ({category})",
                "size": "sm",
                "weight": "bold",
                "margin": "md"
            },
            {
                "type": "text",
                "text": f"📍 路線：{route}",
                "size": "sm",
                "margin": "xs"
            },
            {
                "type": "text",
                "text": f"🚕 司機：{driver_id}",
                "size": "sm",
                "margin": "xs"
            },
            {
                "type": "separator",
                "margin": "md"
            },
            {
                "type": "text",
                "text": fare_change_text,
                "size": "sm",
                "margin": "md"
            },
            {
                "type": "text",
                "text": total_change_text,
                "size": "sm",
                "weight": "bold",
                "color": "#FF9800" if total_change != 0 else "#4CAF50",
                "margin": "xs"
            },
            {
                "type": "text",
                "text": f"📝 修改原因：{reason}",
                "size": "sm",
                "margin": "sm"
            }
        ]
        
        # 構建 Flex Message
        flex_content = {
            "type": "bubble",
            "header": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": "✅ 修改成功",
                        "weight": "bold",
                        "size": "lg",
                        "color": "#FFFFFF"
                    }
                ],
                "backgroundColor": "#4CAF50",
                "paddingAll": "md"
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": body_contents
            }
        }
        
        # 創建有用的 Quick Reply 按鈕
        quick_reply_items = [
            QuickReplyItem(
                action=MessageAction(
                    label="📋 查看詳情",
                    text=f"班次詳情 {trip_id}"
                )
            ),
            QuickReplyItem(
                action=MessageAction(
                    label="🔍 查詢其他",
                    text="查詢今天完成班次"
                )
            ),
            QuickReplyItem(
                action=MessageAction(
                    label="📊 查看歷史",
                    text=f"查詢司機{driver_id}本週班次"
                )
            )
        ]
        
        quick_reply = QuickReply(items=quick_reply_items)
        
        # 🔥 修復：返回字典格式，和司機指派確認一致
        return {
            "flex_message": flex_content,  # 直接返回字典
            "quick_reply": quick_reply,    # Quick Reply 對象
            "alt_text": f"AI修改完成: 班次#{trip_id}"
        }
        
    except Exception as e:
        logger.error(f"創建AI修改結果Flex Message時出錯: {e}")
        return None 