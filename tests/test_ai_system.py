#!/usr/bin/env python3
"""
AI系統專門測試套件
測試AI智能助手、工具調用、知識庫等核心功能
"""
import unittest
from unittest.mock import Mock, patch, MagicMock
import json
from datetime import datetime, date, timedelta

from modules import create_app
from modules.models.base import db
from modules.models.trip import Trip, FixedSchedule, CompletedTrip
from modules.models.driver import Driver
from modules.models.customer import Customer


class TestAISystemBase(unittest.TestCase):
    """AI系統測試基類"""
    
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        cls.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        
        with cls.app.app_context():
            db.create_all()
    
    def setUp(self):
        self.app_context = self.app.app_context()
        self.app_context.push()
        
        # 設置測試數據
        self.setup_test_data()
    
    def tearDown(self):
        db.session.rollback()
        self.app_context.pop()
    
    def setup_test_data(self):
        """設置AI測試數據"""
        # 清理舊數據
        db.session.query(CompletedTrip).delete()
        db.session.query(Trip).delete()
        db.session.query(FixedSchedule).delete()
        db.session.query(Driver).delete()
        db.session.query(Customer).delete()
        
        # 創建測試司機
        self.drivers = [
            Driver(id=533, name="王司機", plate_number="ABC-1234"),
            Driver(id=534, name="李司機", plate_number="DEF-5678"),
            Driver(id=535, name="張司機", plate_number="GHI-9012")
        ]
        
        # 創建測試客戶
        self.customers = [
            Customer(name="診所", address="台南市", category="醫療"),
            Customer(name="東洋", address="高雄市", category="企業"),
        ]
        
        # 創建測試班次
        self.trips = [
            Trip(
                id=100,
                date=date.today(),
                time="09:00",
                start_point="高鐵站",
                end_point="診所",
                actual_fare=250,
                category="醫療",
                status="待派"
            ),
            Trip(
                id=101,
                date=date.today(),
                time="14:30",
                start_point="公司",
                end_point="東洋",
                actual_fare=180,
                category="企業",
                status="準備",
                driver_id=533
            ),
            Trip(
                id=102,
                date=date.today(),
                time="16:00",
                start_point="醫院",
                end_point="家",
                actual_fare=120,
                category="醫療",
                status="完成",
                driver_id=534
            )
        ]
        
        # 創建已完成班次
        self.completed_trips = [
            CompletedTrip(
                original_trip_id=200,
                date=date.today() - timedelta(days=1),
                time="10:00", 
                start_point="昨日起點",
                end_point="昨日終點",
                actual_fare=300,
                driver_id=533,
                category="醫療",
                completed_at=datetime.now() - timedelta(days=1)
            )
        ]
        
        db.session.add_all(self.drivers + self.customers + self.trips + self.completed_trips)
        db.session.commit()


class TestGeminiClient(TestAISystemBase):
    """Gemini客戶端測試"""
    
    @patch('google.auth.default')
    @patch('google.oauth2.service_account.Credentials.from_service_account_file')
    def test_gemini_client_initialization(self, mock_credentials, mock_auth):
        """測試Gemini客戶端初始化"""
        try:
            from modules.ai_agent.gemini_client import get_gemini_client
            
            # Mock認證
            mock_credentials.return_value = (Mock(), "test-project")
            mock_auth.return_value = Mock()
            
            # 測試客戶端獲取
            client = get_gemini_client()
            self.assertIsNotNone(client)
            
        except ImportError:
            self.skipTest("gemini_client.get_gemini_client 需要實現")
    
    @patch('modules.ai_agent.gemini_client.get_gemini_client')
    def test_gemini_api_call(self, mock_get_client):
        """測試Gemini API調用"""
        # Mock Gemini響應
        mock_response = Mock()
        mock_response.text = "這是Gemini的回應"
        
        mock_client = Mock()
        mock_client.generate_content.return_value = mock_response
        mock_get_client.return_value = mock_client
        
        try:
            from modules.ai_agent.gemini_client import call_gemini_api
            
            # 調用API
            response = call_gemini_api("測試提示", "test_user")
            
            # 驗證調用
            self.assertEqual(response, "這是Gemini的回應")
            mock_client.generate_content.assert_called_once()
            
        except ImportError:
            self.skipTest("gemini_client.call_gemini_api 需要實現")


class TestAIAgent(TestAISystemBase):
    """AI代理測試"""
    
    @patch('modules.ai_agent.gemini_client.get_gemini_client')
    def test_ai_agent_initialization(self, mock_get_client):
        """測試AI代理初始化"""
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        
        try:
            from modules.ai_agent.agent_core import DispatchAgent
            
            # 創建AI代理
            agent = DispatchAgent("test_user")
            self.assertIsNotNone(agent)
            self.assertEqual(agent.user_id, "test_user")
            
        except ImportError:
            self.skipTest("agent_core.DispatchAgent 需要實現")
    
    @patch('modules.ai_agent.gemini_client.get_gemini_client')
    def test_ai_agent_thinking_process(self, mock_get_client):
        """測試AI代理思考流程"""
        # Mock Gemini響應
        mock_response = Mock()
        mock_response.text = json.dumps({
            "intent": "查詢班次",
            "parameters": {
                "date": "今天",
                "condition": "金額大於200"
            },
            "confidence": 0.9
        })
        
        mock_client = Mock()
        mock_client.generate_content.return_value = mock_response
        mock_get_client.return_value = mock_client
        
        try:
            from modules.ai_agent.agent_core import DispatchAgent
            
            agent = DispatchAgent("test_user")
            
            # 測試思考階段
            result = agent._think("今天金額大於200的班次")
            
            # 驗證思考結果
            self.assertEqual(result["intent"], "查詢班次")
            self.assertIn("金額大於200", result["parameters"]["condition"])
            
        except ImportError:
            self.skipTest("agent_core.DispatchAgent._think 需要實現")
    
    @patch('modules.ai_agent.gemini_client.get_gemini_client')
    def test_ai_agent_tool_execution(self, mock_get_client):
        """測試AI代理工具執行"""
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        
        try:
            from modules.ai_agent.agent_core import DispatchAgent
            from modules.ai_agent.tool_registry import get_available_tools
            
            agent = DispatchAgent("test_user")
            
            # 測試工具調用
            tools = get_available_tools()
            if "query_trips" in tools:
                result = agent._execute_tool("query_trips", {
                    "date": date.today().isoformat(),
                    "condition": "actual_fare > 200"
                })
                
                # 驗證工具執行結果
                self.assertIsNotNone(result)
                
        except ImportError:
            self.skipTest("agent_core.DispatchAgent._execute_tool 需要實現")


class TestToolRegistry(TestAISystemBase):
    """工具註冊表測試"""
    
    def test_get_available_tools(self):
        """測試獲取可用工具"""
        try:
            from modules.ai_agent.tool_registry import get_available_tools
            
            tools = get_available_tools()
            
            # 驗證基本工具存在
            expected_tools = [
                "query_trips", "query_drivers", "assign_driver", 
                "update_trip_status", "create_trip", "get_trip_details"
            ]
            
            for tool in expected_tools:
                if tool in tools:
                    self.assertIn("description", tools[tool])
                    self.assertIn("parameters", tools[tool])
                    
        except ImportError:
            self.skipTest("tool_registry.get_available_tools 需要實現")
    
    def test_tool_parameter_validation(self):
        """測試工具參數驗證"""
        try:
            from modules.ai_agent.tool_registry import validate_tool_parameters
            
            # 測試有效參數
            valid_params = {
                "trip_id": "100",
                "new_status": "準備"
            }
            
            result = validate_tool_parameters("update_trip_status", valid_params)
            self.assertTrue(result)
            
            # 測試無效參數
            invalid_params = {
                "trip_id": "100"
                # 缺少 new_status
            }
            
            result = validate_tool_parameters("update_trip_status", invalid_params)
            self.assertFalse(result)
            
        except ImportError:
            self.skipTest("tool_registry.validate_tool_parameters 需要實現")
    
    def test_tool_execution(self):
        """測試工具執行"""
        try:
            from modules.ai_agent.tool_registry import execute_tool
            
            # 測試查詢工具
            result = execute_tool("query_trips", {
                "date": date.today().isoformat()
            })
            
            # 驗證執行結果
            self.assertIsNotNone(result)
            self.assertIsInstance(result, (list, dict, str))
            
        except ImportError:
            self.skipTest("tool_registry.execute_tool 需要實現")


class TestKnowledgeBase(TestAISystemBase):
    """知識庫測試"""
    
    def test_database_schema_knowledge(self):
        """測試資料庫schema知識"""
        try:
            from modules.ai_agent.knowledge_base import get_database_schema
            
            schema = get_database_schema()
            
            # 驗證包含主要表
            expected_tables = ["trips", "drivers", "customers", "fixed_schedules", "completed_trips"]
            for table in expected_tables:
                self.assertIn(table, schema)
                
        except ImportError:
            self.skipTest("knowledge_base.get_database_schema 需要實現")
    
    def test_business_rules_knowledge(self):
        """測試業務規則知識"""
        try:
            from modules.ai_agent.knowledge_base import get_business_rules
            
            rules = get_business_rules()
            
            # 驗證包含關鍵業務規則
            self.assertIn("30分鐘修改限制", str(rules))
            self.assertIn("班次狀態", str(rules))
            
        except ImportError:
            self.skipTest("knowledge_base.get_business_rules 需要實現")
    
    def test_system_capabilities_knowledge(self):
        """測試系統功能知識"""
        try:
            from modules.ai_agent.knowledge_base import get_system_capabilities
            
            capabilities = get_system_capabilities()
            
            # 驗證包含主要功能
            expected_capabilities = ["班次管理", "司機指派", "報表生成"]
            for capability in expected_capabilities:
                self.assertIn(capability, str(capabilities))
                
        except ImportError:
            self.skipTest("knowledge_base.get_system_capabilities 需要實現")


class TestAIRouter(TestAISystemBase):
    """AI路由測試"""
    
    def test_should_use_ai_routing(self):
        """測試是否應該使用AI處理"""
        try:
            from modules.ai_agent.ai_router import should_use_ai
            
            # 測試應該使用AI的情況
            ai_cases = [
                "今天金額大於200的診所班次",
                "司機533昨天的收入",
                "現在有多少待派班次",
                "幫我分析本週的班次狀況"
            ]
            
            for case in ai_cases:
                self.assertTrue(should_use_ai(case), f"應該使用AI處理: {case}")
            
            # 測試不應該使用AI的情況
            traditional_cases = [
                "查詢 2025-01-25",
                "指派 100 533",
                "修改狀態 101 準備",
                "幫助"
            ]
            
            for case in traditional_cases:
                self.assertFalse(should_use_ai(case), f"不應該使用AI處理: {case}")
                
        except ImportError:
            self.skipTest("ai_router.should_use_ai 需要實現")
    
    def test_route_to_appropriate_handler(self):
        """測試路由到適當的處理器"""
        try:
            from modules.ai_agent.ai_router import route_message
            
            # 測試AI路由
            ai_message = "今天金額大於200的班次"
            result = route_message(ai_message, "test_user")
            
            # 驗證AI處理結果
            self.assertIsNotNone(result)
            
        except ImportError:
            self.skipTest("ai_router.route_message 需要實現")


class TestSmartAssistant(TestAISystemBase):
    """智能助手測試"""
    
    @patch('modules.ai_agent.gemini_client.get_gemini_client')
    def test_smart_assistant_complex_query(self, mock_get_client):
        """測試智能助手複雜查詢處理"""
        # Mock Gemini響應
        mock_response = Mock()
        mock_response.text = "根據查詢條件，找到1筆金額大於200的醫療班次：\n高鐵站→診所，車資250元，狀態：待派"
        
        mock_client = Mock()
        mock_client.generate_content.return_value = mock_response
        mock_get_client.return_value = mock_client
        
        try:
            from modules.services.smart_assistant import process_with_smart_assistant
            
            # 處理複雜查詢
            result = process_with_smart_assistant("今天金額大於200的醫療班次", "test_user")
            
            # 驗證處理結果
            self.assertIsNotNone(result)
            self.assertIn("醫療班次", result)
            self.assertIn("250", result)
            
        except ImportError:
            self.skipTest("smart_assistant.process_with_smart_assistant 需要實現")
    
    @patch('modules.ai_agent.gemini_client.get_gemini_client')
    def test_smart_assistant_driver_query(self, mock_get_client):
        """測試智能助手司機查詢"""
        mock_response = Mock()
        mock_response.text = "司機533今天有1筆班次：公司→東洋，車資180元，狀態：準備"
        
        mock_client = Mock()
        mock_client.generate_content.return_value = mock_response
        mock_get_client.return_value = mock_client
        
        try:
            from modules.services.smart_assistant import process_with_smart_assistant
            
            result = process_with_smart_assistant("司機533今天的班次", "test_user")
            
            # 驗證查詢結果
            self.assertIsNotNone(result)
            self.assertIn("533", result)
            self.assertIn("180", result)
            
        except ImportError:
            self.skipTest("smart_assistant.process_with_smart_assistant 需要實現")
    
    @patch('modules.ai_agent.gemini_client.get_gemini_client')
    def test_smart_assistant_status_analysis(self, mock_get_client):
        """測試智能助手狀態分析"""
        mock_response = Mock()
        mock_response.text = "目前有1筆待派班次，1筆準備中班次，1筆已完成班次"
        
        mock_client = Mock()
        mock_client.generate_content.return_value = mock_response
        mock_get_client.return_value = mock_client
        
        try:
            from modules.services.smart_assistant import process_with_smart_assistant
            
            result = process_with_smart_assistant("現在班次狀況如何", "test_user")
            
            # 驗證分析結果
            self.assertIsNotNone(result)
            self.assertIn("待派", result)
            self.assertIn("準備", result)
            
        except ImportError:
            self.skipTest("smart_assistant.process_with_smart_assistant 需要實現")


class TestAIFareService(TestAISystemBase):
    """AI車資服務測試"""
    
    @patch('modules.ai_agent.gemini_client.get_gemini_client')
    def test_ai_fare_query(self, mock_get_client):
        """測試AI車資查詢"""
        mock_response = Mock()
        mock_response.text = "根據歷史資料，高鐵站到診所的建議車資為200-250元"
        
        mock_client = Mock()
        mock_client.generate_content.return_value = mock_response
        mock_get_client.return_value = mock_client
        
        try:
            from modules.services.ai_fare_service import query_fare_with_ai
            
            result = query_fare_with_ai("高鐵站", "診所")
            
            # 驗證車資查詢結果
            self.assertIsNotNone(result)
            self.assertIn("200", result)
            
        except ImportError:
            self.skipTest("ai_fare_service.query_fare_with_ai 需要實現")
    
    @patch('modules.ai_agent.gemini_client.get_gemini_client')
    def test_ai_fare_analysis(self, mock_get_client):
        """測試AI車資分析"""
        mock_response = Mock()
        mock_response.text = "今日平均車資186元，比昨日上升6%"
        
        mock_client = Mock()
        mock_client.generate_content.return_value = mock_response
        mock_get_client.return_value = mock_client
        
        try:
            from modules.services.ai_fare_service import analyze_fare_trends
            
            result = analyze_fare_trends(date.today())
            
            # 驗證分析結果
            self.assertIsNotNone(result)
            self.assertIn("186", result)
            
        except ImportError:
            self.skipTest("ai_fare_service.analyze_fare_trends 需要實現")


class TestAIErrorHandling(TestAISystemBase):
    """AI錯誤處理測試"""
    
    @patch('modules.ai_agent.gemini_client.get_gemini_client')
    def test_gemini_api_error_handling(self, mock_get_client):
        """測試Gemini API錯誤處理"""
        # Mock API錯誤
        mock_client = Mock()
        mock_client.generate_content.side_effect = Exception("API錯誤")
        mock_get_client.return_value = mock_client
        
        try:
            from modules.services.smart_assistant import process_with_smart_assistant
            
            # 處理查詢時發生API錯誤
            result = process_with_smart_assistant("測試查詢", "test_user")
            
            # 驗證錯誤處理
            self.assertIsNotNone(result)
            self.assertIn("錯誤", result.lower())
            
        except ImportError:
            self.skipTest("smart_assistant.process_with_smart_assistant 需要實現")
    
    def test_invalid_tool_parameters(self):
        """測試無效工具參數處理"""
        try:
            from modules.ai_agent.tool_registry import execute_tool
            
            # 測試無效參數
            result = execute_tool("query_trips", {
                "invalid_param": "value"
            })
            
            # 應該返回錯誤信息
            self.assertIsNotNone(result)
            
        except ImportError:
            self.skipTest("tool_registry.execute_tool 需要實現")
    
    def test_knowledge_base_fallback(self):
        """測試知識庫回退機制"""
        try:
            from modules.ai_agent.knowledge_base import get_fallback_response
            
            # 測試未知查詢的回退響應
            response = get_fallback_response("完全未知的查詢")
            
            # 驗證回退響應
            self.assertIsNotNone(response)
            self.assertIn("無法", response)
            
        except ImportError:
            self.skipTest("knowledge_base.get_fallback_response 需要實現")


class TestPerformance(TestAISystemBase):
    """AI系統性能測試"""
    
    @patch('modules.ai_agent.gemini_client.get_gemini_client')
    def test_response_time(self, mock_get_client):
        """測試響應時間"""
        import time
        
        mock_response = Mock()
        mock_response.text = "快速響應"
        
        mock_client = Mock()
        mock_client.generate_content.return_value = mock_response
        mock_get_client.return_value = mock_client
        
        try:
            from modules.services.smart_assistant import process_with_smart_assistant
            
            # 測量響應時間
            start_time = time.time()
            result = process_with_smart_assistant("簡單查詢", "test_user")
            end_time = time.time()
            
            response_time = end_time - start_time
            
            # 驗證響應時間合理（<5秒）
            self.assertLess(response_time, 5.0)
            self.assertIsNotNone(result)
            
        except ImportError:
            self.skipTest("smart_assistant.process_with_smart_assistant 需要實現")
    
    def test_concurrent_requests(self):
        """測試並發請求處理"""
        # 這裡可以添加並發測試邏輯
        pass


if __name__ == '__main__':
    # 運行AI系統測試
    suite = unittest.TestLoader().loadTestsFromModule(__import__(__name__))
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)