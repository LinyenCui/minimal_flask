"""
AI 車資查詢專用 Flex Message 設計
"""

import logging
from datetime import datetime
from linebot.v3.messaging import QuickReply, QuickReplyItem, MessageAction
from modules.utils.quick_reply_manager import QuickReplyManager

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
            
        else:
            # 🔥 新方案：用可點擊的班次列表，就像東洋班次那樣
            body_contents.append({
                "type": "text",
                "text": f"🎯 找到 {len(trips)} 個匹配班次：",
                "size": "md",
                "color": "#4CAF50" if len(trips) == 1 else "#FF9800",
                "weight": "bold",
                "margin": "md"
            })
            
            # 顯示可點擊的班次列表（顯示所有班次）
            for i, trip in enumerate(trips):  # 🔥 修復：移除20個限制，顯示所有班次
                meter_fare = trip.get('meter_fare', 0) or 0
                extra_fare = trip.get('extra_fare', 0) or 0
                total_fare = meter_fare + extra_fare
                
                # 🔥 微調：簡化金額顯示，只顯示總金額
                fare_display = f"💰{total_fare}"
                
                driver_display = trip.get('driver_id', 'N/A')
                if driver_display and driver_display != 'N/A':
                    driver_display = f"🚕{driver_display}"
                else:
                    driver_display = "🚕未指派"
                
                # 🔥 新格式：像現在態一樣的排版，但用橘色代表過去態
                trip_box = {
                    "type": "box",
                    "layout": "horizontal",
                    "spacing": "sm",
                    "contents": [
                        # 班次ID（移除橘點，節省空間）
                        {
                            "type": "text",
                            "text": str(trip['id']),
                            "size": "xxs",  # 🔥 過去態字體小一號：xs → xxs
                            "flex": 1,
                            "weight": "bold",
                            "color": "#FF8C00"  # 橘色
                        },
                        # 地點（前移）
                        {
                            "type": "text",
                            "text": f"{trip.get('start_point', '?')}({trip.get('category', '')})" if trip.get('category') in ['往', '回'] else f"{trip.get('start_point', '?')} → {trip.get('end_point', '?')}",
                            "size": "xxs",  # 🔥 過去態字體小一號：xs → xxs
                            "flex": 3,
                            "wrap": True,
                            "color": "#333333"
                        },
                        # 司機（移除emoji，節省空間）
                        {
                            "type": "text",
                            "text": str(driver_display.replace('🚕', '')),
                            "size": "xxs",  # 🔥 過去態字體小一號：xs → xxs
                            "flex": 1,
                            "color": "#666666"
                        },
                        # 總金額（改用$號）
                        {
                            "type": "text",
                            "text": f"${total_fare}",  # 🔥 改用$號節省空間
                            "size": "xxs",  # 🔥 過去態字體小一號：xs → xxs
                            "flex": 1,
                            "align": "end",
                            "color": "#FF8C00",  # 橘色
                            "weight": "bold"
                        }
                    ],
                    "margin": "sm",
                    "paddingAll": "sm",
                    "backgroundColor": "#FFF8F0",  # 淡橘色背景
                    "cornerRadius": "sm",
                    "action": {
                        "type": "message",
                        "text": f"查看 {trip['id']}"  # 🔥 修復：過去態用"查看"指令
                    }
                }
                
                body_contents.append(trip_box)
            
            # �� 移除限制提示 - 現在顯示所有班次
        
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
                "backgroundColor": "#FF8C00",  # 🔥 改為橘色，代表過去態
                "paddingAll": "md"
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": body_contents
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": "點擊班次查看詳情和操作選項",
                        "size": "xs",
                        "color": "#888888",
                        "wrap": True,
                        "align": "center"
                    }
                ]
            }
        }
        
        # 🔥 簡化：不再需要複雜的Quick Reply，直接點擊班次即可
        return {
            "flex_message": flex_content,
            "quick_reply": None,  # 不需要Quick Reply，直接點擊班次
            "alt_text": f"AI搜索到{len(trips)}個班次: {query}"
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
        
        # 使用新的 Quick Reply 標準格式
        # 🎯 現在可以安全使用「取消」一詞：trips狀態已從「取消」改為「註銷」，語意衝突已解決
        quick_reply_buttons = [
            {"label": "✅ 確認修改", "text": f"確認AI修改 {trip_id} {new_meter} {new_extra} {reason}", "type": "message"},
            {"label": "❌ 放棄修改", "text": "放棄AI修改", "type": "message"},
            {"label": "📋 查看詳情", "text": f"查看 {trip_id}", "type": "message"}
        ]
        
        # 使用 QuickReplyManager 建立標準格式的 Quick Reply 數據
        quick_reply_data = QuickReplyManager._build_quick_reply_data(quick_reply_buttons)
        
        # 🔥 返回字典格式
        return {
            "flex_message": flex_content,
            "quick_reply": quick_reply_data,
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