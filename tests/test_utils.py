#!/usr/bin/env python3
"""
工具函數測試套件
測試所有工具模組的功能和邊界條件
"""
import unittest
from unittest.mock import Mock, patch
from datetime import datetime, date, timedelta
import pytz


class TestDateTimeUtils(unittest.TestCase):
    """日期時間工具測試"""
    
    def test_taiwan_time_conversion(self):
        """測試台灣時間轉換"""
        try:
            from modules.utils.taiwan_time import get_taiwan_now, to_taiwan_time
            
            # 測試獲取台灣當前時間
            tw_now = get_taiwan_now()
            self.assertIsInstance(tw_now, datetime)
            
            # 測試UTC轉台灣時間
            utc_time = datetime.now(pytz.UTC)
            tw_time = to_taiwan_time(utc_time)
            
            # 驗證時區轉換正確
            self.assertEqual(tw_time.tzinfo.zone, 'Asia/Taipei')
            
        except ImportError:
            self.skipTest("taiwan_time 模組需要實現")
    
    def test_week_calculation(self):
        """測試週次計算"""
        try:
            from modules.utils.week_utils import get_week_range, get_current_week
            
            # 測試獲取當前週範圍
            start_date, end_date = get_current_week()
            
            # 驗證週範圍（星期日到星期六）
            self.assertEqual(start_date.weekday(), 6)  # 星期日 = 6
            self.assertEqual(end_date.weekday(), 5)    # 星期六 = 5
            self.assertEqual((end_date - start_date).days, 6)
            
        except ImportError:
            self.skipTest("week_utils 模組需要實現")
    
    def test_date_parsing(self):
        """測試日期解析"""
        try:
            from modules.utils.enhanced_date_parser import parse_date_string
            
            # 測試各種日期格式
            test_cases = [
                ("今天", date.today()),
                ("明天", date.today() + timedelta(days=1)),
                ("昨天", date.today() - timedelta(days=1)),
                ("2025-01-25", date(2025, 1, 25)),
                ("01/25", date(date.today().year, 1, 25)),
            ]
            
            for input_str, expected in test_cases:
                result = parse_date_string(input_str)
                self.assertEqual(result, expected, f"解析 '{input_str}' 失敗")
                
        except ImportError:
            self.skipTest("enhanced_date_parser 模組需要實現")
    
    def test_time_parsing(self):
        """測試時間解析"""
        try:
            from modules.utils.enhanced_date_parser import parse_time_string
            
            # 測試各種時間格式
            test_cases = [
                ("下午2點", "14:00"),
                ("上午9點半", "09:30"),
                ("晚上8點", "20:00"),
                ("14:30", "14:30"),
                ("9:00", "09:00"),
            ]
            
            for input_str, expected in test_cases:
                result = parse_time_string(input_str)
                self.assertEqual(result, expected, f"解析 '{input_str}' 失敗")
                
        except ImportError:
            self.skipTest("enhanced_date_parser 模組需要實現")


class TestHelpers(unittest.TestCase):
    """通用助手函數測試"""
    
    def test_format_currency(self):
        """測試貨幣格式化"""
        try:
            from modules.utils.helpers import format_currency
            
            # 測試各種數值格式化
            test_cases = [
                (150, "150元"),
                (1500, "1,500元"),
                (0, "0元"),
                (150.5, "151元"),  # 四捨五入
            ]
            
            for amount, expected in test_cases:
                result = format_currency(amount)
                self.assertEqual(result, expected)
                
        except ImportError:
            self.skipTest("helpers.format_currency 需要實現")
    
    def test_validate_phone_number(self):
        """測試電話號碼驗證"""
        try:
            from modules.utils.helpers import validate_phone_number
            
            # 測試有效電話號碼
            valid_numbers = [
                "0912345678",
                "09-1234-5678",
                "09 1234 5678",
                "+886912345678"
            ]
            
            for number in valid_numbers:
                self.assertTrue(validate_phone_number(number))
            
            # 測試無效電話號碼
            invalid_numbers = [
                "123456789",   # 太短
                "09123456789", # 太長
                "0812345678",  # 錯誤開頭
                "abcd1234567"  # 包含字母
            ]
            
            for number in invalid_numbers:
                self.assertFalse(validate_phone_number(number))
                
        except ImportError:
            self.skipTest("helpers.validate_phone_number 需要實現")
    
    def test_calculate_distance(self):
        """測試距離計算"""
        try:
            from modules.utils.helpers import calculate_distance
            
            # 測試台南市內距離計算
            distance = calculate_distance(
                "台南車站", "成功大學"
            )
            
            # 驗證返回合理距離（公里）
            self.assertIsInstance(distance, (int, float))
            self.assertGreater(distance, 0)
            
        except ImportError:
            self.skipTest("helpers.calculate_distance 需要實現")
    
    def test_extract_numbers_from_text(self):
        """測試從文本提取數字"""
        try:
            from modules.utils.helpers import extract_numbers
            
            # 測試數字提取
            test_cases = [
                ("車資150元", [150]),
                ("班次123，司機533", [123, 533]),
                ("從A到B，距離5.5公里", [5.5]),
                ("沒有數字", []),
            ]
            
            for text, expected in test_cases:
                result = extract_numbers(text)
                self.assertEqual(result, expected)
                
        except ImportError:
            self.skipTest("helpers.extract_numbers 需要實現")


class TestLineBot(unittest.TestCase):
    """LINE Bot工具測試"""
    
    @patch('linebot.LineBotApi')
    def test_line_bot_initialization(self, mock_line_api):
        """測試LINE Bot初始化"""
        try:
            from modules.utils.line_bot import line_bot_api, handler
            
            # 驗證LINE Bot API和handler存在
            self.assertIsNotNone(line_bot_api)
            self.assertIsNotNone(handler)
            
        except ImportError:
            self.skipTest("line_bot 模組需要實現")
    
    @patch('modules.utils.line_bot.line_bot_api')
    def test_send_text_message(self, mock_api):
        """測試發送文本消息"""
        try:
            from modules.utils.line_bot import send_text_message
            
            # 測試發送消息
            user_id = "test_user"
            message = "測試消息"
            
            send_text_message(user_id, message)
            
            # 驗證API被調用
            mock_api.push_message.assert_called_once()
            
        except ImportError:
            self.skipTest("line_bot.send_text_message 需要實現")
    
    @patch('modules.utils.line_bot.line_bot_api')
    def test_send_quick_reply(self, mock_api):
        """測試發送快速回覆"""
        try:
            from modules.utils.line_bot import send_quick_reply
            
            # 測試快速回覆
            user_id = "test_user"
            message = "請選擇"
            quick_reply_items = ["選項1", "選項2", "選項3"]
            
            send_quick_reply(user_id, message, quick_reply_items)
            
            # 驗證API被調用
            mock_api.push_message.assert_called_once()
            
        except ImportError:
            self.skipTest("line_bot.send_quick_reply 需要實現")
    
    def test_create_flex_message(self):
        """測試創建Flex消息"""
        try:
            from modules.utils.line_bot import create_flex_bubble
            
            # 測試創建Flex bubble
            title = "測試標題"
            content = "測試內容"
            
            flex_bubble = create_flex_bubble(title, content)
            
            # 驗證Flex結構
            self.assertEqual(flex_bubble["type"], "bubble")
            self.assertIn("body", flex_bubble)
            
        except ImportError:
            self.skipTest("line_bot.create_flex_bubble 需要實現")


class TestConversationContext(unittest.TestCase):
    """對話上下文測試"""
    
    def test_context_initialization(self):
        """測試上下文初始化"""
        try:
            from modules.utils.conversation_context import ConversationContext
            
            # 創建上下文
            context = ConversationContext("test_user")
            
            # 驗證初始化
            self.assertEqual(context.user_id, "test_user")
            self.assertIsNotNone(context.context_data)
            
        except ImportError:
            self.skipTest("conversation_context.ConversationContext 需要實現")
    
    def test_context_storage_and_retrieval(self):
        """測試上下文存儲和檢索"""
        try:
            from modules.utils.conversation_context import ConversationContext
            
            context = ConversationContext("test_user")
            
            # 存儲上下文
            context.set("booking_state", "waiting_confirmation")
            context.set("temp_data", {"start": "A", "end": "B"})
            
            # 檢索上下文
            state = context.get("booking_state")
            temp_data = context.get("temp_data")
            
            # 驗證存儲和檢索
            self.assertEqual(state, "waiting_confirmation")
            self.assertEqual(temp_data["start"], "A")
            
        except ImportError:
            self.skipTest("conversation_context.ConversationContext 需要實現")
    
    def test_context_expiration(self):
        """測試上下文過期"""
        try:
            from modules.utils.conversation_context import ConversationContext
            
            context = ConversationContext("test_user")
            
            # 設置短過期時間的上下文
            context.set_with_expiry("temp_state", "value", seconds=1)
            
            # 立即檢索應該成功
            value = context.get("temp_state")
            self.assertEqual(value, "value")
            
            # 等待過期後檢索應該返回None
            import time
            time.sleep(2)
            expired_value = context.get("temp_state")
            self.assertIsNone(expired_value)
            
        except ImportError:
            self.skipTest("conversation_context.ConversationContext 需要實現")


class TestPassengerNameHandler(unittest.TestCase):
    """乘客姓名處理測試"""
    
    def test_extract_passenger_name(self):
        """測試提取乘客姓名"""
        try:
            from modules.utils.passenger_name_handler import extract_passenger_name
            
            # 測試各種姓名提取
            test_cases = [
                ("載王先生到醫院", "王先生"),
                ("陳小姐預約明天", "陳小姐"),
                ("李總要用車", "李總"),
                ("沒有姓名的訊息", None),
            ]
            
            for text, expected in test_cases:
                result = extract_passenger_name(text)
                self.assertEqual(result, expected)
                
        except ImportError:
            self.skipTest("passenger_name_handler.extract_passenger_name 需要實現")
    
    def test_validate_passenger_name(self):
        """測試驗證乘客姓名"""
        try:
            from modules.utils.passenger_name_handler import validate_passenger_name
            
            # 測試有效姓名
            valid_names = ["王先生", "陳小姐", "李總", "張醫師"]
            for name in valid_names:
                self.assertTrue(validate_passenger_name(name))
            
            # 測試無效姓名
            invalid_names = ["", "A", "123", "!@#"]
            for name in invalid_names:
                self.assertFalse(validate_passenger_name(name))
                
        except ImportError:
            self.skipTest("passenger_name_handler.validate_passenger_name 需要實現")


class TestModificationUtils(unittest.TestCase):
    """修改工具測試"""
    
    def test_can_modify_trip_time_check(self):
        """測試班次修改時間檢查"""
        try:
            from modules.utils.modification_utils import can_modify_trip_by_time
            
            now = datetime.now()
            
            # 測試30分鐘後的班次（應該可以修改）
            safe_time = (now + timedelta(minutes=35)).time()
            today = now.date()
            
            can_modify = can_modify_trip_by_time(today, safe_time)
            self.assertTrue(can_modify)
            
            # 測試25分鐘後的班次（應該不能修改）
            near_time = (now + timedelta(minutes=25)).time()
            cannot_modify = can_modify_trip_by_time(today, near_time)
            self.assertFalse(cannot_modify)
            
        except ImportError:
            self.skipTest("modification_utils.can_modify_trip_by_time 需要實現")
    
    def test_modification_reason_validation(self):
        """測試修改原因驗證"""
        try:
            from modules.utils.modification_utils import validate_modification_reason
            
            # 測試有效原因
            valid_reasons = ["客戶臨時取消", "司機請假", "交通狀況", "緊急事件"]
            for reason in valid_reasons:
                self.assertTrue(validate_modification_reason(reason))
            
            # 測試無效原因
            invalid_reasons = ["", "   ", "x"]
            for reason in invalid_reasons:
                self.assertFalse(validate_modification_reason(reason))
                
        except ImportError:
            self.skipTest("modification_utils.validate_modification_reason 需要實現")


class TestDatabaseUtils(unittest.TestCase):
    """資料庫工具測試"""
    
    def test_database_connection_check(self):
        """測試資料庫連接檢查"""
        try:
            from modules.utils.db_utils import check_database_connection
            
            # 測試資料庫連接
            is_connected = check_database_connection()
            self.assertIsInstance(is_connected, bool)
            
        except ImportError:
            self.skipTest("db_utils.check_database_connection 需要實現")
    
    def test_safe_database_query(self):
        """測試安全的資料庫查詢"""
        try:
            from modules.utils.db_utils import safe_query
            
            # 測試安全查詢
            result = safe_query("SELECT 1 as test")
            
            # 驗證查詢結果
            self.assertIsNotNone(result)
            
        except ImportError:
            self.skipTest("db_utils.safe_query 需要實現")


class TestPerformanceUtils(unittest.TestCase):
    """性能工具測試"""
    
    def test_timing_decorator(self):
        """測試計時裝飾器"""
        try:
            from modules.utils.helpers import timing
            
            @timing
            def slow_function():
                import time
                time.sleep(0.1)
                return "completed"
            
            # 執行被裝飾的函數
            result = slow_function()
            
            # 驗證函數正常執行
            self.assertEqual(result, "completed")
            
        except ImportError:
            self.skipTest("helpers.timing 裝飾器需要實現")
    
    def test_cache_utils(self):
        """測試緩存工具"""
        try:
            from modules.utils.helpers import cached_result
            
            call_count = 0
            
            @cached_result(expire_seconds=60)
            def expensive_function(param):
                nonlocal call_count
                call_count += 1
                return f"result_{param}"
            
            # 第一次調用
            result1 = expensive_function("test")
            self.assertEqual(call_count, 1)
            
            # 第二次調用應該使用緩存
            result2 = expensive_function("test")
            self.assertEqual(call_count, 1)  # 沒有增加
            self.assertEqual(result1, result2)
            
        except ImportError:
            self.skipTest("helpers.cached_result 需要實現")


class TestErrorHandling(unittest.TestCase):
    """錯誤處理測試"""
    
    def test_safe_execution_wrapper(self):
        """測試安全執行包裝器"""
        try:
            from modules.utils.helpers import safe_execute
            
            # 測試正常執行
            def normal_function():
                return "success"
            
            result = safe_execute(normal_function)
            self.assertEqual(result, "success")
            
            # 測試異常處理
            def error_function():
                raise ValueError("測試錯誤")
            
            result = safe_execute(error_function, default_value="error_handled")
            self.assertEqual(result, "error_handled")
            
        except ImportError:
            self.skipTest("helpers.safe_execute 需要實現")
    
    def test_input_sanitization(self):
        """測試輸入清理"""
        try:
            from modules.utils.helpers import sanitize_input
            
            # 測試各種輸入清理
            test_cases = [
                ("正常輸入", "正常輸入"),
                ("  有空格的輸入  ", "有空格的輸入"),
                ("<script>alert('xss')</script>", ""),  # XSS過濾
                ("SQL'; DROP TABLE--", "SQL DROP TABLE"),  # SQL注入過濾
            ]
            
            for input_text, expected in test_cases:
                result = sanitize_input(input_text)
                self.assertEqual(result, expected)
                
        except ImportError:
            self.skipTest("helpers.sanitize_input 需要實現")


class TestIntegrationUtils(unittest.TestCase):
    """整合工具測試"""
    
    def test_google_drive_utils(self):
        """測試Google Drive工具"""
        try:
            from modules.utils.drive_utils import get_drive_service
            
            # 測試Drive服務初始化
            service = get_drive_service()
            self.assertIsNotNone(service)
            
        except ImportError:
            self.skipTest("drive_utils.get_drive_service 需要實現")
    
    @patch('modules.utils.drive_utils.get_drive_service')
    def test_file_upload_to_drive(self, mock_service):
        """測試檔案上傳到Drive"""
        # Mock Drive API
        mock_drive = Mock()
        mock_drive.files().create().execute.return_value = {'id': 'test_file_id'}
        mock_service.return_value = mock_drive
        
        try:
            from modules.utils.drive_utils import upload_file_to_drive
            
            # 測試檔案上傳
            file_id = upload_file_to_drive("test.txt", "測試內容")
            
            # 驗證上傳
            self.assertEqual(file_id, "test_file_id")
            
        except ImportError:
            self.skipTest("drive_utils.upload_file_to_drive 需要實現")


if __name__ == '__main__':
    # 運行工具測試
    suite = unittest.TestLoader().loadTestsFromModule(__import__(__name__))
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)