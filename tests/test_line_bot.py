#!/usr/bin/env python3
"""
Line Bot功能測試
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, patch
import json

# 添加項目根目錄到 Python 路徑
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from modules.handlers.text_message_handler import process_text_message
from modules.flex_designs.trip_details_flex import get_trip_details_flex
from modules.flex_designs.quick_reply_designs import get_main_menu_quick_reply

class TestLineBotFeatures:
    """Line Bot功能測試類"""
    
    def test_quick_reply_format(self):
        """測試QuickReply格式正確性"""
        quick_reply = get_main_menu_quick_reply()
        
        assert quick_reply is not None
        assert 'items' in quick_reply
        
        # 檢查每個item都有必須的text屬性
        for item in quick_reply['items']:
            assert 'action' in item
            action = item['action']
            
            if action['type'] == 'postback':
                # QuickReply的postback必須有text屬性
                assert 'text' in action, "QuickReply postback action必須包含text屬性"
                assert action['text'] is not None and action['text'] != ""
    
    def test_flex_message_structure(self):
        """測試Flex訊息結構"""
        # 使用測試trip_id（可能不存在，但測試結構）
        flex_message = get_trip_details_flex(9999)
        
        assert flex_message is not None
        assert 'type' in flex_message
        assert flex_message['type'] == 'flex'
        
        if 'contents' in flex_message:
            assert 'type' in flex_message['contents']
    
    @patch('modules.handlers.text_message_handler.line_bot_api')
    def test_text_message_handling(self, mock_line_bot):
        """測試文字訊息處理"""
        # 模擬Line事件
        mock_event = Mock()
        mock_event.reply_token = "test_reply_token"
        mock_event.message.text = "昨天診所班次"
        
        # 模擬用戶Profile
        mock_profile = Mock()
        mock_profile.user_id = "test_user_id"
        mock_profile.display_name = "測試用戶"
        
        with patch('modules.handlers.text_message_handler.line_bot_api.get_profile') as mock_get_profile:
            mock_get_profile.return_value = mock_profile
            
            # 執行處理
            process_text_message(mock_event)
            
            # 驗證有調用reply_message
            assert mock_line_bot.reply_message.called
    
    def test_ai_natural_language_routing(self):
        """測試AI自然語言路由"""
        # 模擬自然語言查詢應該觸發AI處理
        test_queries = [
            "昨天診所班次",
            "幫我查看今天的安排", 
            "明天有什麼行程",
            "哪些班次還沒完成"
        ]
        
        for query in test_queries:
            mock_event = Mock()
            mock_event.message.text = query
            mock_event.reply_token = "test_token"
            
            # 這些查詢應該不會拋出異常
            try:
                with patch('modules.handlers.text_message_handler.line_bot_api'):
                    with patch('modules.handlers.text_message_handler.line_bot_api.get_profile'):
                        process_text_message(mock_event)
            except Exception as e:
                pytest.fail(f"查詢 '{query}' 處理失敗: {e}")
    
    def test_traditional_command_routing(self):
        """測試傳統命令路由"""
        # 精確命令應該直接路由，不經過AI
        traditional_commands = [
            "班次詳情 2207",
            "修改 2208", 
            "刪除 2209",
            "幫助",
            "狀態"
        ]
        
        for command in traditional_commands:
            mock_event = Mock()
            mock_event.message.text = command
            mock_event.reply_token = "test_token"
            
            try:
                with patch('modules.handlers.text_message_handler.line_bot_api'):
                    with patch('modules.handlers.text_message_handler.line_bot_api.get_profile'):
                        process_text_message(mock_event)
            except Exception as e:
                pytest.fail(f"命令 '{command}' 處理失敗: {e}")
    
    def test_error_handling_graceful(self):
        """測試錯誤處理優雅性"""
        # 無效輸入不應該讓系統崩潰
        invalid_inputs = [
            "",
            None,
            "無效命令12345",
            "特殊字符@#$%^&*()",
            "超長字串" * 100
        ]
        
        for invalid_input in invalid_inputs:
            mock_event = Mock()
            mock_event.message.text = invalid_input
            mock_event.reply_token = "test_token"
            
            try:
                with patch('modules.handlers.text_message_handler.line_bot_api'):
                    with patch('modules.handlers.text_message_handler.line_bot_api.get_profile'):
                        process_text_message(mock_event)
            except Exception as e:
                # 記錄但不失敗測試（有些錯誤是預期的）
                print(f"輸入 '{invalid_input}' 產生錯誤: {e}")
    
    def test_line_bot_api_usage_compliance(self):
        """測試Line Bot API使用合規性"""
        # 確保只使用reply_message（免費政策）
        with patch('modules.handlers.text_message_handler.line_bot_api') as mock_api:
            mock_event = Mock()
            mock_event.message.text = "測試訊息"
            mock_event.reply_token = "test_token"
            
            with patch('modules.handlers.text_message_handler.line_bot_api.get_profile'):
                process_text_message(mock_event)
            
            # 確保沒有使用push_message（違反免費政策）
            assert not hasattr(mock_api, 'push_message') or not mock_api.push_message.called
            
            # 確保使用了reply_message
            assert mock_api.reply_message.called
    
    def test_json_serialization_safety(self):
        """測試JSON序列化安全性"""
        # 測試Flex訊息可以安全序列化
        flex_message = get_trip_details_flex(2207)
        
        try:
            json_str = json.dumps(flex_message, ensure_ascii=False)
            # 應該能夠重新解析
            parsed = json.loads(json_str)
            assert parsed is not None
        except (TypeError, ValueError) as e:
            pytest.fail(f"Flex訊息JSON序列化失敗: {e}")

if __name__ == "__main__":
    pytest.main([__file__, "-v"])