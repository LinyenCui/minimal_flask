"""
AI對話上下文管理模塊
用於維持多輪對話的連續性，讓AI能記住之前的查詢結果和操作意圖
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import json

logger = logging.getLogger(__name__)

@dataclass
class QueryResult:
    """查詢結果數據結構"""
    query: str
    criteria: Dict
    trips: List[Dict]
    timestamp: datetime
    result_type: str  # 'single', 'multiple', 'none'
    confidence: str

@dataclass
class ConversationContext:
    """對話上下文數據結構"""
    user_id: str
    last_query_result: Optional[QueryResult] = None
    conversation_history: List[Dict] = None
    active_trip_id: Optional[int] = None  # 當前操作的班次ID
    pending_modification: Optional[Dict] = None  # 待執行的修改
    context_expires_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.conversation_history is None:
            self.conversation_history = []
        if self.context_expires_at is None:
            # 上下文有效期30分鐘
            self.context_expires_at = datetime.now() + timedelta(minutes=30)

class ConversationContextManager:
    """對話上下文管理器"""
    
    def __init__(self):
        # 使用內存存儲，實際部署可考慮Redis或數據庫
        self._contexts: Dict[str, ConversationContext] = {}
        self._cleanup_interval = timedelta(minutes=10)
        self._last_cleanup = datetime.now()
    
    def get_context(self, user_id: str) -> ConversationContext:
        """獲取用戶的對話上下文"""
        self._cleanup_expired()
        
        if user_id not in self._contexts:
            self._contexts[user_id] = ConversationContext(user_id=user_id)
        
        context = self._contexts[user_id]
        
        # 檢查上下文是否過期
        if context.context_expires_at and datetime.now() > context.context_expires_at:
            logger.info(f"用戶 {user_id} 的上下文已過期，重置")
            self._contexts[user_id] = ConversationContext(user_id=user_id)
            context = self._contexts[user_id]
        
        return context
    
    def update_query_result(self, user_id: str, query: str, criteria: Dict, 
                           trips: List[Dict], confidence: str):
        """更新查詢結果到上下文"""
        context = self.get_context(user_id)
        
        # 判斷結果類型
        if not trips:
            result_type = 'none'
        elif len(trips) == 1:
            result_type = 'single'
            context.active_trip_id = trips[0]['id']
        else:
            result_type = 'multiple'
            context.active_trip_id = None
        
        query_result = QueryResult(
            query=query,
            criteria=criteria,
            trips=trips,
            timestamp=datetime.now(),
            result_type=result_type,
            confidence=confidence
        )
        
        context.last_query_result = query_result
        context.context_expires_at = datetime.now() + timedelta(minutes=30)
        
        # 添加到對話歷史
        self._add_to_history(context, 'query', {
            'query': query,
            'result_count': len(trips),
            'result_type': result_type
        })
        
        logger.info(f"用戶 {user_id} 查詢結果已更新: {result_type}, {len(trips)} 個班次")
    
    def try_resolve_incomplete_query(self, user_id: str, current_query: str) -> Optional[Dict]:
        """嘗試使用上下文解析不完整的查詢"""
        context = self.get_context(user_id)
        
        if not context.last_query_result:
            return None
        
        last_result = context.last_query_result
        
        # 檢查是否是基於上一次結果的操作
        resolution_patterns = [
            # 基於序號的引用
            (r'第(\d+)個', 'sequence_reference'),
            (r'第([一二三四五六七八九十]+)個', 'sequence_chinese_reference'),  # 🔥 新增：中文數字序號
            (r'第一個|第1個|首個', 'first_item'),
            (r'第二個|第2個', 'second_item'),  # 🔥 新增：明確的第二個
            (r'第三個|第3個', 'third_item'),  # 🔥 新增：明確的第三個
            (r'最後一個|最後', 'last_item'),
            
            # 基於班次ID的操作
            (r'修改班次#?(\d+)', 'trip_id_reference'),
            (r'#(\d+)', 'trip_id_reference'),
            
            # 基於上下文的修改操作
            (r'改成|調整|修改', 'context_modification'),
            (r'錶價|加成|費用', 'context_modification'),
        ]
        
        import re
        for pattern, operation_type in resolution_patterns:
            match = re.search(pattern, current_query, re.IGNORECASE)
            if match:
                return self._resolve_operation(context, current_query, operation_type, match)
        
        return None
    
    def _resolve_operation(self, context: ConversationContext, query: str, 
                          operation_type: str, match) -> Optional[Dict]:
        """解析具體的操作類型"""
        last_result = context.last_query_result
        
        if operation_type == 'sequence_reference':
            # 例如："修改第1個的費用"
            try:
                index = int(match.group(1)) - 1
                if 0 <= index < len(last_result.trips):
                    target_trip = last_result.trips[index]
                    return {
                        'resolved': True,
                        'trip_id': target_trip['id'],
                        'trip': target_trip,
                        'context_info': f"基於上次查詢「{last_result.query}」的第{index+1}個結果"
                    }
            except (ValueError, IndexError):
                pass
        
        elif operation_type == 'sequence_chinese_reference':
            # 例如："修改第二個的費用"
            try:
                chinese_number = match.group(1)
                # 中文數字轉換
                chinese_to_arabic = {
                    '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
                    '六': 6, '七': 7, '八': 8, '九': 9, '十': 10
                }
                if chinese_number in chinese_to_arabic:
                    index = chinese_to_arabic[chinese_number] - 1
                    if 0 <= index < len(last_result.trips):
                        target_trip = last_result.trips[index]
                        return {
                            'resolved': True,
                            'trip_id': target_trip['id'],
                            'trip': target_trip,
                            'context_info': f"基於上次查詢「{last_result.query}」的第{index+1}個結果"
                        }
            except (ValueError, IndexError):
                pass
        
        elif operation_type == 'first_item':
            # 例如："修改第一個"
            if last_result.trips:
                target_trip = last_result.trips[0]
                return {
                    'resolved': True,
                    'trip_id': target_trip['id'],
                    'trip': target_trip,
                    'context_info': f"基於上次查詢「{last_result.query}」的第一個結果"
                }
        
        elif operation_type == 'second_item':
            # 例如："修改第二個"
            if len(last_result.trips) >= 2:
                target_trip = last_result.trips[1]
                return {
                    'resolved': True,
                    'trip_id': target_trip['id'],
                    'trip': target_trip,
                    'context_info': f"基於上次查詢「{last_result.query}」的第二個結果"
                }
        
        elif operation_type == 'third_item':
            # 例如："修改第三個"
            if len(last_result.trips) >= 3:
                target_trip = last_result.trips[2]
                return {
                    'resolved': True,
                    'trip_id': target_trip['id'],
                    'trip': target_trip,
                    'context_info': f"基於上次查詢「{last_result.query}」的第三個結果"
                }
        
        elif operation_type == 'last_item':
            # 例如："修改最後一個"
            if last_result.trips:
                target_trip = last_result.trips[-1]
                return {
                    'resolved': True,
                    'trip_id': target_trip['id'],
                    'trip': target_trip,
                    'context_info': f"基於上次查詢「{last_result.query}」的最後一個結果"
                }
        
        elif operation_type == 'trip_id_reference':
            # 例如："修改班次#309"
            try:
                referenced_id = int(match.group(1))
                # 檢查這個ID是否在上次查詢結果中
                for trip in last_result.trips:
                    if trip['id'] == referenced_id:
                        return {
                            'resolved': True,
                            'trip_id': referenced_id,
                            'trip': trip,
                            'context_info': f"基於上次查詢「{last_result.query}」中的班次#{referenced_id}"
                        }
            except (ValueError, IndexError):
                pass
        
        elif operation_type == 'context_modification':
            # 例如："改成錶價400加成80"
            if last_result.result_type == 'single':
                # 只有一個結果時，可以直接應用修改
                target_trip = last_result.trips[0]
                return {
                    'resolved': True,
                    'trip_id': target_trip['id'],
                    'trip': target_trip,
                    'context_info': f"基於上次查詢「{last_result.query}」的唯一結果"
                }
            elif last_result.result_type == 'multiple':
                # 多個結果時，提示用戶指定
                return {
                    'resolved': False,
                    'needs_clarification': True,
                    'message': f"上次查詢「{last_result.query}」找到了{len(last_result.trips)}個班次，請指定要修改哪一個",
                    'available_trips': last_result.trips
                }
        
        return None
    
    def set_pending_modification(self, user_id: str, modification_data: Dict):
        """設置待執行的修改操作"""
        context = self.get_context(user_id)
        context.pending_modification = modification_data
        context.context_expires_at = datetime.now() + timedelta(minutes=30)
        
        self._add_to_history(context, 'pending_modification', modification_data)
    
    def get_pending_modification(self, user_id: str) -> Optional[Dict]:
        """獲取待執行的修改操作"""
        context = self.get_context(user_id)
        return context.pending_modification
    
    def clear_pending_modification(self, user_id: str):
        """清除待執行的修改操作"""
        context = self.get_context(user_id)
        context.pending_modification = None
    
    def _add_to_history(self, context: ConversationContext, action_type: str, data: Dict):
        """添加操作到對話歷史"""
        history_item = {
            'timestamp': datetime.now().isoformat(),
            'action_type': action_type,
            'data': data
        }
        
        context.conversation_history.append(history_item)
        
        # 保持歷史記錄在合理長度內
        if len(context.conversation_history) > 20:
            context.conversation_history = context.conversation_history[-15:]
    
    def _cleanup_expired(self):
        """清理過期的上下文"""
        now = datetime.now()
        
        if now - self._last_cleanup < self._cleanup_interval:
            return
        
        expired_users = []
        for user_id, context in self._contexts.items():
            if context.context_expires_at and now > context.context_expires_at:
                expired_users.append(user_id)
        
        for user_id in expired_users:
            del self._contexts[user_id]
            logger.info(f"清理用戶 {user_id} 的過期上下文")
        
        self._last_cleanup = now
    
    def get_context_summary(self, user_id: str) -> str:
        """獲取上下文摘要（用於調試）"""
        context = self.get_context(user_id)
        
        if not context.last_query_result:
            return "無活躍上下文"
        
        last_result = context.last_query_result
        age = datetime.now() - last_result.timestamp
        
        return f"""📋 對話上下文摘要：
• 上次查詢：「{last_result.query}」
• 查詢時間：{age.seconds//60}分鐘前
• 結果數量：{len(last_result.trips)}個班次
• 當前操作班次：{context.active_trip_id or '無'}
• 待執行修改：{'是' if context.pending_modification else '否'}"""

# 全局上下文管理器實例
conversation_manager = ConversationContextManager() 