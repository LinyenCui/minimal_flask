"""
AI 車資查詢專用 Flex Message 設計
"""

import logging
from datetime import datetime
from linebot.v3.messaging import QuickReply, QuickReplyItem, MessageAction

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
            
            MAX_DISPLAY = 15  # 調高顯示上限，與未完成班次清單風格一致
            display_count = min(MAX_DISPLAY, len(trips))
            for i, trip in enumerate(trips[:display_count]):
                meter_fare = trip.get('meter_fare', 0) or 0
                extra_fare = trip.get('extra_fare', 0) or 0
                
                if extra_fare >= 0:
                    fare_display = f"{meter_fare}+{extra_fare}"
                else:
                    fare_display = f"{meter_fare}{extra_fare}"
                
                driver_display = trip.get('driver_id', 'N/A')
                if driver_display and driver_display != 'N/A':
                    driver_display = f"#{driver_display}"
                
                body_contents.append({
                    "type": "text",
                    "text": f"📍 {i+1}. #{trip['id']} ({trip.get('category', '?')}) - {trip.get('start_point', '?')} → {trip.get('end_point', '?')} | 🚕{driver_display} | 💰{fare_display}",
                    "size": "xs",
                    "wrap": True,
                    "margin": "xs"
                })
            
            if len(trips) > MAX_DISPLAY:
                body_contents.append({
                    "type": "text",
                    "text": f"...還有 {len(trips) - MAX_DISPLAY} 個班次",
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

def create_ai_modification_confirm_flex(modification_info):
    """
    創建AI修改確認界面的Flex Message（參考預約叫車模式）
    
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
        
        # 格式化司機顯示
        driver_display = f"#{driver_id}" if driver_id and driver_id != 'N/A' else 'N/A'
        
        body_contents = [
            {
                "type": "text",
                "text": "🤖 AI智能修改確認",
                "size": "md",
                "weight": "bold",
                "color": "#FF9800"
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
                "text": f"🚕 司機：{driver_display}",
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
            },
            {
                "type": "separator",
                "margin": "md"
            },
            {
                "type": "text",
                "text": "請確認是否執行此修改？",
                "size": "sm",
                "color": "#FF9800",
                "weight": "bold",
                "margin": "md"
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
                        "text": "⚠️ 確認修改",
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
        
        # 創建確認/取消 Quick Reply 按鈕
        quick_reply_items = [
            QuickReplyItem(
                action=MessageAction(
                    label="✅ 確認修改",
                    text=f"確認AI修改 {trip_id} {new_meter} {new_extra} {reason}"
                )
            ),
            QuickReplyItem(
                action=MessageAction(
                    label="❌ 取消修改",
                    text="取消AI修改"
                )
            ),
            QuickReplyItem(
                action=MessageAction(
                    label="📋 查看詳情",
                    text=f"查看 {trip_id}"
                )
            )
        ]
        
        quick_reply = QuickReply(items=quick_reply_items)
        
        # 🔥 返回字典格式
        return {
            "flex_message": flex_content,
            "quick_reply": quick_reply,
            "alt_text": f"AI修改確認: 班次#{trip_id}"
        }
        
    except Exception as e:
        logger.error(f"創建AI修改確認Flex Message時出錯: {e}")
        return None

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
        
        # 格式化司機顯示  
        driver_display = f"#{driver_id}" if driver_id and driver_id != 'N/A' else 'N/A'
        
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
                "text": f"🚕 司機：{driver_display}",
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
                    text=f"查看 {trip_id}"
                )
            ),
            QuickReplyItem(
                action=MessageAction(
                    label="🔍 查詢其他",
                    text="查已完成 診所"  # 直接指定類別，避免觸發類別選擇
                )
            )
        ]
        
        # 只有當司機ID不是N/A時，才添加司機歷史查詢按鈕
        if driver_id and driver_id != 'N/A':
            quick_reply_items.append(
                QuickReplyItem(
                    action=MessageAction(
                        label="📊 查看歷史",
                        text="診所班次"  # 使用正確的診所班次命令
                    )
                )
            )
        else:
            quick_reply_items.append(
                QuickReplyItem(
                    action=MessageAction(
                        label="🤖 AI查詢",
                        text="查詢今天診所車資"
                    )
                )
            )
        
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

def create_ai_modification_cancel_flex():
    """
    創建AI修改取消確認的Flex Message（參考預約成功模式）
    """
    try:
        # 構建取消確認界面
        flex_content = {
            "type": "bubble",
            "header": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": "❌ 修改已取消",
                        "weight": "bold",
                        "size": "lg",
                        "color": "#FFFFFF"
                    }
                ],
                "backgroundColor": "#4CAF50",  # 使用綠色背景，表示操作成功
                "paddingAll": "md"
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": "✅ AI修改已成功取消！",
                        "size": "lg",
                        "weight": "bold",
                        "color": "#4CAF50",
                        "margin": "md"
                    },
                    {
                        "type": "separator",
                        "margin": "md"
                    },
                    {
                        "type": "text",
                        "text": "🔒 數據庫未被修改",
                        "size": "sm",
                        "color": "#666666",
                        "margin": "md"
                    },
                    {
                        "type": "text",
                        "text": "💡 您可以重新發起修改命令或使用其他功能",
                        "size": "sm",
                        "color": "#666666",
                        "margin": "sm",
                        "wrap": True
                    }
                ]
            }
        }
        
        # 創建有用的 Quick Reply 按鈕
        quick_reply_items = [
            QuickReplyItem(
                action=MessageAction(
                    label="🔍 重新查詢",
                    text="查詢今天完成班次"
                )
            ),
            QuickReplyItem(
                action=MessageAction(
                    label="🤖 AI查詢",
                    text="查詢今天診所車資"
                )
            ),
            QuickReplyItem(
                action=MessageAction(
                    label="💡 查看幫助",
                    text="幫助"
                )
            )
        ]
        
        quick_reply = QuickReply(items=quick_reply_items)
        
        # 返回字典格式
        return {
            "flex_message": flex_content,
            "quick_reply": quick_reply,
            "alt_text": "AI修改已取消"
        }
        
    except Exception as e:
        logger.error(f"創建AI修改取消Flex Message時出錯: {e}")
        return None 