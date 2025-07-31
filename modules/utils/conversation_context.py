"""
AI對話上下文管理模塊
用於維持多輪對話的連續性，讓AI能記住之前的查詢結果和操作意圖
🔥 新增：統一對話狀態管理系統，防止智能助手搶戲
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import json
import time

logger = logging.getLogger(__name__)

# 全域變數存儲會話狀態
conversation_states = {}

@dataclass
class ActiveConversation:
    """活躍對話狀態"""
    user_id: str
    conversation_type: str  # 'fare_modification', 'temp_booking', 'passenger_leave', 'driver_assign'
    current_step: str      # 'waiting_reason', 'waiting_confirmation', 'waiting_info'
    context_data: Dict     # 相關的數據
    created_at: datetime
    expires_at: datetime
    prompt_message: str    # 系統提示用戶的消息
    cancel_commands: List[str]  # 可以取消的命令
    
    def is_expired(self) -> bool:
        """檢查對話是否已過期"""
        return datetime.now() > self.expires_at
    
    def can_cancel_with(self, message: str) -> bool:
        """檢查消息是否可以取消對話"""
        message_lower = message.lower().strip()
        return any(cmd in message_lower for cmd in self.cancel_commands)
    
    def to_dict(self) -> Dict:
        """轉換為字典格式"""
        return {
            'user_id': self.user_id,
            'conversation_type': self.conversation_type,
            'current_step': self.current_step,
            'context_data': self.context_data,
            'created_at': self.created_at.isoformat(),
            'expires_at': self.expires_at.isoformat(),
            'prompt_message': self.prompt_message,
            'cancel_commands': self.cancel_commands
        }

@dataclass
class QueryResult:
    """查詢結果數據結構"""
    query: str
    criteria: Dict
    trips: List[Dict]
    timestamp: datetime
    result_type: str  # 'single', 'multiple', 'none'
    confidence: str

class ConversationContext:
    """會話上下文管理器 - 管理用戶的查詢結果和翻頁狀態"""
    
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.state_key = f"context_{user_id}"
    
    def save_query_result(self, query_type: str, command: str, all_results: List, conditions: Dict = None):
        """保存查詢結果供翻頁使用"""
        global conversation_states
        
        state = {
            'query_type': query_type,  # 'completed_trips' 或 'current_trips'
            'command': command,
            'all_results': all_results,
            'conditions': conditions or {},
            'current_page': 0,
            'page_size': 10,
            'timestamp': time.time()
        }
        
        conversation_states[self.state_key] = state
        
    def get_query_result(self) -> Optional[Dict]:
        """獲取保存的查詢結果"""
        global conversation_states
        
        if self.state_key not in conversation_states:
            return None
            
        state = conversation_states[self.state_key]
        
        # 檢查時效性（5分鐘內有效）
        if time.time() - state['timestamp'] > 300:
            self.clear_context()
            return None
            
        return state
    
    def get_page_results(self, page_num: int = 0, page_size: int = 10) -> Dict:
        """獲取分頁結果"""
        state = self.get_query_result()
        if not state:
            return {'type': 'error', 'message': '沒有可用的查詢結果'}
        
        all_results = state['all_results']
        total_results = len(all_results)
        
        if total_results == 0:
            return {'type': 'no_results', 'message': '沒有找到符合條件的記錄'}
        
        # 計算分頁
        start_idx = page_num * page_size
        end_idx = start_idx + page_size
        page_results = all_results[start_idx:end_idx]
        
        if not page_results:
            return {'type': 'error', 'message': '頁面超出範圍'}
        
        # 更新當前頁數
        state['current_page'] = page_num
        conversation_states[self.state_key] = state
        
        # 格式化結果
        result_text = f"📊 查詢結果 (第 {page_num + 1} 頁)\n"
        result_text += f"找到 {total_results} 筆記錄，顯示第 {start_idx + 1}-{min(end_idx, total_results)} 筆\n\n"
        
        query_type = state['query_type']
        
        # 根據查詢類型格式化結果
        if query_type == 'completed_trips':
            # 已完成班次
            for trip in page_results:
                trip_id = trip.get('id', 'N/A')
                date_str = trip.get('date', 'N/A')
                start_point = trip.get('start_point', 'N/A')
                end_point = trip.get('end_point', 'N/A')
                driver_id = trip.get('driver_id', 'N/A')
                
                result_text += f"  🚗 #{trip_id} - {start_point} → {end_point}"
                result_text += f" | 🚕{driver_id} | {date_str}\n"
                
        else:
            # 當前班次 (current_trips) - 🔥 修正：使用狀態分組顯示
            # 🔥 修正：按狀態分組顯示，考慮請假情況
            status_groups = {}
            for trip in page_results:
                # 支援不同的資料結構，統一提取欄位
                if hasattr(trip, 'trip_id'):
                    # SQLAlchemy Row 對象
                    trip_data = {
                        'trip_id': trip.trip_id,
                        'start_point': trip.start_point,
                        'end_point': trip.end_point,
                        'custom_start_point': getattr(trip, 'custom_start_point', None),
                        'custom_end_point': getattr(trip, 'custom_end_point', None),
                        'driver_id': trip.driver_id,
                        'status': trip.status,
                        'trip_type': getattr(trip, 'trip_type', 'fixed'),
                        'passenger_leave_reason': getattr(trip, 'passenger_leave_reason', None),
                        'actual_fare': getattr(trip, 'actual_fare', None)
                    }
                else:
                    # 字典格式
                    trip_data = trip
                
                # 檢查是否為請假狀態（狀態是準備但有請假原因）
                if trip_data.get('status') == '準備' and trip_data.get('passenger_leave_reason'):
                    display_status = '請假'
                else:
                    display_status = trip_data.get('status') or '未知'
                
                if display_status not in status_groups:
                    status_groups[display_status] = []
                status_groups[display_status].append(trip_data)
            
            # 按狀態分組顯示
            for status, status_trips in status_groups.items():
                # 🔥 新增：根據狀態使用不同圖示，保持一致性
                if status == '準備':
                    status_icon = "🟢"
                elif status == '待派':
                    status_icon = "🔴"
                elif status == '已完成':
                    status_icon = "✅"
                elif status == '取消':
                    status_icon = "❌"
                elif status == '衝突':
                    status_icon = "🟠"
                elif status == '請假':
                    status_icon = "🔵"
                else:
                    status_icon = "🎯"
                
                result_text += f"{status_icon} {status} ({len(status_trips)}個)：\n"
                
                for trip_data in status_trips:
                    # 統一處理顯示格式
                    trip_id = trip_data.get('trip_id', 'N/A')
                    driver_id = trip_data.get('driver_id')
                    trip_type = trip_data.get('trip_type', 'fixed')
                    
                    # 司機信息顯示
                    driver_info = f"🚕{driver_id}" if driver_id else "未指派"
                    
                    # 根據trip_type決定使用哪個起點終點
                    if trip_type == 'temp':
                        start_point = trip_data.get('custom_start_point') or trip_data.get('start_point') or '未知'
                        end_point = trip_data.get('custom_end_point') or trip_data.get('end_point') or '未知'
                    else:
                        start_point = trip_data.get('start_point') or '未知'
                        end_point = trip_data.get('end_point') or '未知'
                    
                    # 顯示actual_fare金額（如果有的話）
                    actual_fare = trip_data.get('actual_fare')
                    fare_info = f" 💰{actual_fare}" if actual_fare else ""
                    
                    # 🔥 修改：使用新格式，去掉📍圖示，加上金額
                    result_text += f"#{trip_id}-{start_point}→{end_point}|{driver_info}{fare_info}\n"
                result_text += "\n"
        
        # 計算總頁數
        total_pages = (total_results + page_size - 1) // page_size
        
        # 🔥 新增：為翻頁結果添加Quick Reply支持
        quick_reply_items = []
        
        # 如果還有下一頁，添加下一頁按鈕
        if page_num + 1 < total_pages:
            result_text += f"\n💡 點擊下方按鈕查看第 {page_num + 2} 頁"
            
            from linebot.v3.messaging import QuickReply, QuickReplyItem, MessageAction
            
            quick_reply_items.extend([
                QuickReplyItem(
                    action=MessageAction(
                        label="📄 下一頁",
                        text="下一頁"
                    )
                ),
                QuickReplyItem(
                    action=MessageAction(
                        label="🔍 重新查詢",
                        text="重新查詢"
                    )
                ),
                QuickReplyItem(
                    action=MessageAction(
                        label="❌ 放棄",
                        text="放棄"
                    )
                )
            ])
        else:
            result_text += f"\n🔚 已顯示全部結果"
            
            # 最後一頁只顯示重新查詢按鈕
            from linebot.v3.messaging import QuickReply, QuickReplyItem, MessageAction
            
            quick_reply_items.append(
                QuickReplyItem(
                    action=MessageAction(
                        label="🔍 重新查詢",
                        text="重新查詢"
                    )
                )
            )
        
        result_dict = {
            'type': 'success',
            'message': result_text,
            'page': page_num + 1,
            'total_pages': total_pages
        }
        
        # 🔥 新增：如果有Quick Reply項目，添加到返回結果中
        if quick_reply_items:
            quick_reply = QuickReply(items=quick_reply_items)
            result_dict['quick_reply'] = quick_reply
        
        return result_dict
    
    def clear_context(self):
        """清除會話上下文"""
        global conversation_states
        if self.state_key in conversation_states:
            del conversation_states[self.state_key]
    
    def has_cached_results(self) -> bool:
        """檢查是否有緩存的查詢結果"""
        return self.get_query_result() is not None
    
    def get_next_page(self) -> Optional[str]:
        """獲取下一頁結果"""
        state = self.get_query_result()
        if not state:
            return None
        
        current_page = state.get('current_page', 0)
        page_size = state.get('page_size', 10)
        all_results = state['all_results']
        total_results = len(all_results)
        
        # 計算下一頁
        next_page = current_page + 1
        start_idx = next_page * page_size
        
        # 檢查是否還有下一頁
        if start_idx >= total_results:
            return "📊 已經是最後一頁了\n\n💡 可以重新執行查詢命令獲取新的結果"
        
        # 獲取下一頁結果
        page_result = self.get_page_results(next_page, page_size)
        
        if page_result.get('type') == 'error':
            return page_result['message']
        
        return page_result.get('message', "無法格式化結果")


def save_pagination_context(query_type: str, all_results: List, page_size: int = 15, user_id: str = "default"):
    """保存分頁查詢結果到上下文"""
    global conversation_states
    
    state_key = f"query_results_{user_id}"
    
    # 保存查詢結果
    state = {
        'query_type': query_type,
        'all_results': all_results,
        'page_size': page_size,
        'current_page': 0,
        'timestamp': time.time()
    }
    
    conversation_states[state_key] = state
    logger.info(f"已保存 {query_type} 分頁上下文：{len(all_results)} 筆結果，頁面大小 {page_size}")


class ConversationManager:
    """全局對話管理器 - 管理所有用戶的對話狀態"""
    
    def __init__(self):
        # 存儲各種用戶狀態
        self.user_states = {}
        # 用戶最近操作的班次ID
        self.recent_trip_ids = {}
        # 用戶最近操作的固定班次ID  
        self.recent_fixed_schedule_ids = {}
        # 用戶請假模式狀態
        self.leave_modes = {}
        # 待執行的修改操作
        self.pending_modifications = {}
        # 🔥 新增：活躍對話狀態
        self.active_conversations = {}
    
    # === 🔥 統一對話狀態管理 ===
    
    def start_conversation(self, user_id: str, conversation_type: str, 
                          current_step: str, context_data: Dict, 
                          prompt_message: str, duration_minutes: int = 5) -> ActiveConversation:
        """開始一個新的對話流程"""
        now = datetime.now()
        expires_at = now + timedelta(minutes=duration_minutes)
        
        # 定義各種對話的取消命令
        cancel_commands_map = {
            'fare_modification': ['取消修改', '取消', '放棄修改', '退出', '不修改'],
            'temp_booking': ['取消預約', '取消', '放棄預約', '退出', '不預約'],
            'passenger_leave': ['取消請假', '取消', '放棄請假', '退出', '不請假', '放棄', '放棄操作'],
            'driver_assign': ['取消指派', '取消', '放棄指派', '退出', '不指派'],
            'fixed_schedule': ['取消', '放棄', '退出', '放棄操作']
        }
        
        conversation = ActiveConversation(
            user_id=user_id,
            conversation_type=conversation_type,
            current_step=current_step,
            context_data=context_data,
            created_at=now,
            expires_at=expires_at,
            prompt_message=prompt_message,
            cancel_commands=cancel_commands_map.get(conversation_type, ['取消', '退出'])
        )
        
        # 清除該用戶的舊對話（如果有）
        if user_id in self.active_conversations:
            logger.info(f"清除用戶 {user_id} 的舊對話: {self.active_conversations[user_id].conversation_type}")
        
        self.active_conversations[user_id] = conversation
        logger.info(f"開始對話: 用戶={user_id}, 類型={conversation_type}, 步驟={current_step}")
        
        return conversation
    
    def get_active_conversation(self, user_id: str) -> Optional[ActiveConversation]:
        """獲取用戶的活躍對話"""
        if user_id not in self.active_conversations:
            return None
            
        conversation = self.active_conversations[user_id]
        
        # 檢查是否已過期
        if conversation.is_expired():
            logger.info(f"對話已過期，自動清除: 用戶={user_id}, 類型={conversation.conversation_type}")
            self.end_conversation(user_id)
            return None
        
        return conversation
    
    def has_active_conversation(self, user_id: str) -> bool:
        """檢查用戶是否有活躍對話"""
        return self.get_active_conversation(user_id) is not None
    
    def update_conversation(self, user_id: str, current_step: str = None, 
                           context_data: Dict = None, prompt_message: str = None):
        """更新對話狀態"""
        if user_id not in self.active_conversations:
            logger.warning(f"嘗試更新不存在的對話: 用戶={user_id}")
            return
        
        conversation = self.active_conversations[user_id]
        
        if current_step:
            conversation.current_step = current_step
        if context_data:
            conversation.context_data.update(context_data)
        if prompt_message:
            conversation.prompt_message = prompt_message
            
        logger.info(f"更新對話: 用戶={user_id}, 步驟={conversation.current_step}")
    
    def end_conversation(self, user_id: str, reason: str = "正常結束"):
        """結束對話"""
        if user_id in self.active_conversations:
            conversation = self.active_conversations[user_id]
            logger.info(f"結束對話: 用戶={user_id}, 類型={conversation.conversation_type}, 原因={reason}")
            del self.active_conversations[user_id]
        
        # 同時清理舊的狀態
        self.clear_pending_modification(user_id)
        self.clear_leave_mode(user_id)
    
    def can_user_cancel_with_message(self, user_id: str, message: str) -> bool:
        """檢查用戶消息是否可以取消當前對話"""
        conversation = self.get_active_conversation(user_id)
        if not conversation:
            return False
        return conversation.can_cancel_with(message)
    
    def get_conversation_status_message(self, user_id: str) -> Optional[str]:
        """獲取對話狀態提示消息"""
        conversation = self.get_active_conversation(user_id)
        if not conversation:
            return None
        
        time_left = conversation.expires_at - datetime.now()
        minutes_left = int(time_left.total_seconds() / 60)
        
        cancel_text = "、".join(conversation.cancel_commands[:2])  # 只顯示前兩個取消命令
        
        return f"""🤖 正在等待您的回答...

{conversation.prompt_message}

💡 請回覆內容，或輸入「{cancel_text}」放棄
⏰ 此對話將在 {minutes_left} 分鐘後自動過期"""
    
    # === 舊API兼容性方法 ===
    
    def set_recent_trip_id(self, user_id: str, trip_id: int):
        """設定用戶最近操作的班次ID"""
        self.recent_trip_ids[user_id] = trip_id
        logger.info(f"設定用戶 {user_id} 最近班次ID: {trip_id}")
    
    def get_recent_trip_id(self, user_id: str) -> Optional[int]:
        """獲取用戶最近操作的班次ID"""
        # 🔥 修復：優先從請假模式中獲取
        if user_id in self.leave_modes:
            mode_data = self.leave_modes[user_id]
            # 檢查時效性
            if time.time() - mode_data['timestamp'] <= 300:  # 5分鐘內有效
                return mode_data.get('trip_id')
        
        # 回退到普通記錄
        return self.recent_trip_ids.get(user_id)
    
    def set_recent_fixed_schedule_id(self, user_id: str, schedule_id: int):
        """設定用戶最近操作的固定班次ID"""
        self.recent_fixed_schedule_ids[user_id] = schedule_id
        logger.info(f"設定用戶 {user_id} 最近固定班次ID: {schedule_id}")
    
    def get_recent_fixed_schedule_id(self, user_id: str) -> Optional[int]:
        """獲取用戶最近操作的固定班次ID，優先使用leave_mode中的ID"""
        # 🔥 修復：優先從請假模式中獲取固定班次ID
        if user_id in self.leave_modes:
            mode_data = self.leave_modes[user_id]
            # 檢查時效性
            if time.time() - mode_data['timestamp'] <= 300:  # 5分鐘內有效
                fixed_schedule_id = mode_data.get('fixed_schedule_id')
                if fixed_schedule_id:
                    return fixed_schedule_id
        
        # 回退到普通記錄
        return self.recent_fixed_schedule_ids.get(user_id)
    
    def set_leave_mode(self, user_id: str, trip_id: int = None, fixed_schedule_id: int = None):
        """設定用戶進入請假模式"""
        if trip_id is None and fixed_schedule_id is None:
            logger.error(f"設定請假模式時必須提供 trip_id 或 fixed_schedule_id")
            return
            
        self.leave_modes[user_id] = {
            'trip_id': trip_id,
            'fixed_schedule_id': fixed_schedule_id,
            'timestamp': time.time()
        }
        
        if trip_id:
            logger.info(f"用戶 {user_id} 進入普通班次請假模式，班次ID: {trip_id}")
        elif fixed_schedule_id:
            logger.info(f"用戶 {user_id} 進入固定班次請假模式，固定班次ID: {fixed_schedule_id}")
    
    def is_in_leave_mode(self, user_id: str) -> bool:
        """檢查用戶是否在請假模式"""
        if user_id not in self.leave_modes:
            return False
        
        # 檢查時效性（5分鐘內有效）
        mode_data = self.leave_modes[user_id]
        if time.time() - mode_data['timestamp'] > 300:
            self.clear_leave_mode(user_id)
            return False
        
        return True
    
    def clear_leave_mode(self, user_id: str):
        """清除用戶的請假模式"""
        if user_id in self.leave_modes:
            del self.leave_modes[user_id]
            logger.info(f"清除用戶 {user_id} 的請假模式")
    
    def get_pending_modification(self, user_id: str) -> Optional[Dict]:
        """獲取用戶待執行的修改操作"""
        if user_id not in self.pending_modifications:
            return None
            
        # 檢查時效性（5分鐘內有效）
        modification_data = self.pending_modifications[user_id]
        if time.time() - modification_data['timestamp'] > 300:
            self.clear_pending_modification(user_id)
            return None
        
        return modification_data
    
    def set_pending_modification(self, user_id: str, modification_data: Dict):
        """設定用戶待執行的修改操作"""
        modification_data['timestamp'] = time.time()
        self.pending_modifications[user_id] = modification_data
        logger.info(f"設定用戶 {user_id} 待執行修改: {modification_data}")
    
    def clear_pending_modification(self, user_id: str):
        """清除用戶待執行的修改操作"""
        if user_id in self.pending_modifications:
            del self.pending_modifications[user_id]
            logger.info(f"清除用戶 {user_id} 的待執行修改")
    
    def reset_context(self, user_id: str):
        """重置用戶的所有上下文狀態"""
        self.recent_trip_ids.pop(user_id, None)
        self.recent_fixed_schedule_ids.pop(user_id, None)
        self.clear_leave_mode(user_id)
        self.clear_pending_modification(user_id)
        # 🔥 新增：也清除活躍對話
        self.end_conversation(user_id, "重置上下文")
        logger.info(f"重置用戶 {user_id} 的所有上下文狀態")


def get_conversation_context(user_id: str) -> ConversationContext:
    """獲取用戶的會話上下文"""
    return ConversationContext(user_id)

def clear_all_expired_contexts():
    """清理所有過期的會話上下文（定期清理）"""
    global conversation_states
    current_time = time.time()
    expired_keys = [
        key for key, state in conversation_states.items()
        if current_time - state['timestamp'] > 300  # 5分鐘過期
    ]
    
    for key in expired_keys:
        del conversation_states[key]
    
    if expired_keys:
        print(f"清理了 {len(expired_keys)} 個過期的會話上下文")

# 🔥 創建全局conversation_manager實例
conversation_manager = ConversationManager() 