import jieba
import re
from datetime import datetime

class NLPProcessor:
    def __init__(self):
        self.commands = {
            '派車': self._process_dispatch,
            '查詢': self._process_query,
            '取消': self._process_cancel,
            '狀態': self._process_status
        }
        
    def process_message(self, message):
        """處理用戶輸入的自然語言消息"""
        words = list(jieba.cut(message))
        
        # 識別命令類型
        command_type = None
        for cmd in self.commands:
            if cmd in words:
                command_type = cmd
                break
        
        if not command_type:
            return {
                'status': 'error',
                'message': '無法識別的命令。支持的命令：派車、查詢、取消、狀態'
            }
            
        return self.commands[command_type](message)
    
    def _process_dispatch(self, message):
        """處理派車請求"""
        try:
            # 提取時間信息
            time_pattern = r'(\d{1,2}[點時](\d{1,2}分)?)'
            times = re.findall(time_pattern, message)
            
            # 提取地點信息
            locations = []
            words = list(jieba.cut(message))
            idx = 0
            while idx < len(words):
                if '從' in words[idx] or '到' in words[idx]:
                    if idx + 1 < len(words):
                        locations.append(words[idx + 1])
                idx += 1
            
            return {
                'status': 'success',
                'action': 'dispatch',
                'data': {
                    'times': times,
                    'locations': locations
                }
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': f'處理派車請求時出錯：{str(e)}'
            }
    
    def _process_query(self, message):
        """處理查詢請求"""
        return {
            'status': 'success',
            'action': 'query',
            'data': {
                'query_text': message
            }
        }
    
    def _process_cancel(self, message):
        """處理取消請求"""
        try:
            # 提取訂單編號
            order_pattern = r'訂單(\d+)'
            order_match = re.search(order_pattern, message)
            if order_match:
                order_id = order_match.group(1)
                return {
                    'status': 'success',
                    'action': 'cancel',
                    'data': {
                        'order_id': order_id
                    }
                }
            return {
                'status': 'error',
                'message': '未能找到訂單編號'
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': f'處理取消請求時出錯：{str(e)}'
            }
    
    def _process_status(self, message):
        """處理狀態查詢請求"""
        return {
            'status': 'success',
            'action': 'status',
            'data': {
                'status_text': message
            }
        } 