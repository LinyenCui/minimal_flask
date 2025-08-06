"""
Quick Reply 重構測試
驗證新的 QuickReplyManager 和 ResponseHandler 系統
"""
import unittest
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# 添加項目根目錄到 Python 路徑
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from modules.utils.quick_reply_manager import QuickReplyManager
from modules.utils.response_handler import ResponseHandler, send_text_response, send_flex_response

class TestQuickReplyRefactor(unittest.TestCase):
    """測試 Quick Reply 重構的功能"""
    
    def setUp(self):
        """測試設置"""
        self.sample_buttons = [
            {"label": "確認", "text": "確認", "type": "message"},
            {"label": "取消", "text": "取消", "type": "message"}
        ]
        
        self.sample_flex_content = {
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": "測試 Flex 內容"
                    }
                ]
            }
        }
    
    def test_quick_reply_manager_create_text_response(self):
        """測試 QuickReplyManager 創建文字響應"""
        # 測試無按鈕的文字響應
        response = QuickReplyManager.create_text_response("測試文字")
        
        self.assertEqual(response["type"], QuickReplyManager.ResponseType.TEXT_ONLY)
        self.assertEqual(response["text"], "測試文字")
        self.assertNotIn("quick_reply", response)
        
        # 測試帶按鈕的文字響應
        response_with_buttons = QuickReplyManager.create_text_response("測試文字", self.sample_buttons)
        
        self.assertEqual(response_with_buttons["type"], QuickReplyManager.ResponseType.TEXT_WITH_QUICK_REPLY)
        self.assertEqual(response_with_buttons["text"], "測試文字")
        self.assertIn("quick_reply", response_with_buttons)
        self.assertIn("items", response_with_buttons["quick_reply"])
    
    def test_quick_reply_manager_create_flex_response(self):
        """測試 QuickReplyManager 創建 Flex 響應"""
        # 測試無按鈕的 Flex 響應
        response = QuickReplyManager.create_flex_response(self.sample_flex_content)
        
        self.assertEqual(response["type"], QuickReplyManager.ResponseType.FLEX_ONLY)
        self.assertEqual(response["flex_message"], self.sample_flex_content)
        self.assertEqual(response["alt_text"], "Flex Message")
        self.assertNotIn("quick_reply", response)
        
        # 測試帶按鈕的 Flex 響應
        response_with_buttons = QuickReplyManager.create_flex_response(
            self.sample_flex_content, 
            "測試 Flex", 
            self.sample_buttons
        )
        
        self.assertEqual(response_with_buttons["type"], QuickReplyManager.ResponseType.FLEX_WITH_QUICK_REPLY)
        self.assertEqual(response_with_buttons["alt_text"], "測試 Flex")
        self.assertIn("quick_reply", response_with_buttons)
    
    def test_quick_reply_data_structure(self):
        """測試 Quick Reply 數據結構的正確性"""
        quick_reply_data = QuickReplyManager._build_quick_reply_data(self.sample_buttons)
        
        self.assertIn("items", quick_reply_data)
        self.assertEqual(len(quick_reply_data["items"]), 2)
        
        # 檢查第一個按鈕
        first_item = quick_reply_data["items"][0]
        self.assertEqual(first_item["type"], "action")
        self.assertEqual(first_item["action"]["type"], "message")
        self.assertEqual(first_item["action"]["label"], "確認")
        self.assertEqual(first_item["action"]["text"], "確認")
    
    def test_convert_to_line_sdk_object(self):
        """測試轉換為 LINE SDK 對象"""
        quick_reply_data = QuickReplyManager._build_quick_reply_data(self.sample_buttons)
        
        with patch('modules.utils.quick_reply_manager.QuickReply') as mock_quick_reply, \
             patch('modules.utils.quick_reply_manager.QuickReplyItem') as mock_quick_reply_item, \
             patch('modules.utils.quick_reply_manager.MessageAction') as mock_message_action:
            
            # 模拟 LINE SDK 對象
            mock_action = Mock()
            mock_message_action.return_value = mock_action
            
            mock_item = Mock()
            mock_quick_reply_item.return_value = mock_item
            
            mock_quick_reply_obj = Mock()
            mock_quick_reply.return_value = mock_quick_reply_obj
            
            result = QuickReplyManager.convert_to_line_sdk_object(quick_reply_data)
            
            # 驗證調用
            self.assertEqual(mock_message_action.call_count, 2)  # 兩個按鈕
            self.assertEqual(mock_quick_reply_item.call_count, 2)
            mock_quick_reply.assert_called_once()
    
    def test_response_format_validation(self):
        """測試響應格式驗證"""
        # 測試有效格式
        valid_response = {
            "type": QuickReplyManager.ResponseType.TEXT_WITH_QUICK_REPLY,
            "text": "測試",
            "quick_reply": {"items": []}
        }
        self.assertTrue(QuickReplyManager.validate_response_format(valid_response))
        
        # 測試無效格式（缺少必要欄位）
        invalid_response = {"text": "測試"}
        self.assertFalse(QuickReplyManager.validate_response_format(invalid_response))
        
        # 測試文字響應缺少 text 欄位
        invalid_text_response = {
            "type": QuickReplyManager.ResponseType.TEXT_ONLY
        }
        self.assertFalse(QuickReplyManager.validate_response_format(invalid_text_response))
    
    def test_common_buttons(self):
        """測試常用按鈕組合"""
        common_buttons = QuickReplyManager.create_common_buttons()
        
        self.assertIn("confirm_cancel", common_buttons)
        self.assertIn("abandon_operation", common_buttons)
        self.assertIn("booking_actions", common_buttons)
        
        # 檢查確認取消按鈕
        confirm_cancel = common_buttons["confirm_cancel"]
        self.assertEqual(len(confirm_cancel), 2)
        self.assertEqual(confirm_cancel[0]["label"], "✅ 確認")
        self.assertEqual(confirm_cancel[1]["label"], "❌ 取消")
    
    @patch('modules.utils.response_handler.reply_text')
    def test_response_handler_legacy_format(self, mock_reply_text):
        """測試 ResponseHandler 處理舊格式"""
        # 測試字符串格式
        success = ResponseHandler.handle_legacy_format("test_token", "測試文字")
        self.assertTrue(success)
        
        # 測試舊的 dict 格式
        legacy_dict = {
            "type": "text_with_quick_reply",
            "text": "測試",
            "quick_reply": {"items": []}
        }
        
        with patch.object(ResponseHandler, 'send_response', return_value=True) as mock_send:
            success = ResponseHandler.handle_legacy_format("test_token", legacy_dict)
            self.assertTrue(success)
            mock_send.assert_called_once()
    
    @patch('modules.utils.response_handler.QuickReplyManager.create_text_response')
    @patch('modules.utils.response_handler.ResponseHandler.send_response')
    def test_send_text_response_convenience_function(self, mock_send_response, mock_create_response):
        """測試便利函數 send_text_response"""
        mock_create_response.return_value = {"type": "text_only", "text": "測試"}
        mock_send_response.return_value = True
        
        success = send_text_response("test_token", "測試文字", self.sample_buttons)
        
        mock_create_response.assert_called_once_with("測試文字", self.sample_buttons)
        mock_send_response.assert_called_once()
        self.assertTrue(success)

if __name__ == '__main__':
    unittest.main()