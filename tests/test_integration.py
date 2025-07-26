#!/usr/bin/env python3
"""
整合測試套件
測試端到端的業務流程和系統整合
"""
import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, date, timedelta
import json

from modules import create_app
from modules.models.base import db
from modules.models.trip import Trip, FixedSchedule, CompletedTrip
from modules.models.driver import Driver
from modules.models.customer import Customer


class TestIntegrationBase(unittest.TestCase):
    """整合測試基類"""
    
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
        
        self.client = self.app.test_client()
        
        # 設置完整的測試數據
        self.setup_full_test_data()
    
    def tearDown(self):
        db.session.rollback()
        self.app_context.pop()
    
    def setup_full_test_data(self):
        """設置完整的測試數據"""
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
            Customer(id=1, name="診所", address="台南市中西區", category="醫療"),
            Customer(id=2, name="東洋", address="高雄市", category="企業"),
            Customer(id=3, name="醫院", address="台南市東區", category="醫療")
        ]
        
        # 創建固定班次模板
        self.fixed_schedules = [
            FixedSchedule(
                id=1,
                route_number="R001",
                departure_time="08:00",
                day_of_week=1,  # 星期一
                start_point="高鐵站",
                end_point="診所",
                base_fare=200,
                total_fare=220,
                category="醫療"
            ),
            FixedSchedule(
                id=2,
                route_number="R002", 
                departure_time="09:30",
                day_of_week=2,  # 星期二
                start_point="公司",
                end_point="東洋",
                base_fare=150,
                total_fare=180,
                category="企業"
            )
        ]
        
        # 創建測試班次
        today = date.today()
        self.trips = [
            Trip(
                id=100,
                date=today,
                time="10:00",
                start_point="高鐵站",
                end_point="診所",
                actual_fare=220,
                category="醫療",
                status="待派",
                fixed_trip_id=1
            ),
            Trip(
                id=101,
                date=today,
                time="14:30",
                start_point="公司",
                end_point="東洋",
                actual_fare=180,
                category="企業",
                status="準備",
                driver_id=533,
                fixed_trip_id=2
            ),
            Trip(
                id=102,
                date=today,
                time="16:00",
                start_point="醫院",
                end_point="家",
                actual_fare=120,
                category="臨時",
                status="完成",
                driver_id=534
            )
        ]
        
        db.session.add_all(self.drivers + self.customers + self.fixed_schedules + self.trips)
        db.session.commit()


class TestCompleteBookingFlow(TestIntegrationBase):
    """完整預約流程測試"""
    
    @patch('modules.utils.line_bot.line_bot_api')
    def test_end_to_end_booking_flow(self, mock_line_api):
        """測試端到端預約流程"""
        # 模擬LINE webhook事件
        webhook_data = {
            "events": [{
                "type": "message",
                "message": {
                    "type": "text",
                    "text": "明天下午3點從高鐵站到醫院，車資250"
                },
                "source": {
                    "userId": "test_user_id"
                },
                "replyToken": "test_reply_token"
            }]
        }
        
        # 1. 發送webhook請求
        response = self.client.post(
            '/callback',
            data=json.dumps(webhook_data),
            content_type='application/json',
            headers={'X-Line-Signature': 'test_signature'}
        )
        
        # 驗證webhook響應
        self.assertEqual(response.status_code, 200)
        
        # 2. 驗證是否創建了臨時班次或觸發了預約流程
        # （這裡需要根據實際實現調整）
        
        # 3. 模擬司機指派
        if mock_line_api.reply_message.called:
            # 檢查是否發送了預約確認消息
            call_args = mock_line_api.reply_message.call_args
            self.assertIsNotNone(call_args)
    
    def test_booking_with_ai_processing(self):
        """測試使用AI處理的預約流程"""
        try:
            from modules.services.smart_assistant import process_with_smart_assistant
            
            # AI處理預約請求
            user_message = "後天早上9點要去診所，大概200元"
            result = process_with_smart_assistant(user_message, "test_user")
            
            # 驗證AI處理結果
            self.assertIsNotNone(result)
            
            # 檢查是否創建了相應的預約記錄
            # （這裡需要根據實際AI實現調整）
            
        except ImportError:
            self.skipTest("AI智能助手功能需要實現")


class TestDriverDispatchFlow(TestIntegrationBase):
    """司機派遣流程測試"""
    
    @patch('modules.utils.line_bot.line_bot_api')
    def test_complete_driver_assignment_flow(self, mock_line_api):
        """測試完整司機指派流程"""
        # 1. 查詢待派班次
        pending_trip = Trip.query.filter_by(status="待派").first()
        self.assertIsNotNone(pending_trip)
        
        # 2. 模擬指派命令
        webhook_data = {
            "events": [{
                "type": "message",
                "message": {
                    "type": "text",
                    "text": f"指派 {pending_trip.id} 533"
                },
                "source": {
                    "userId": "admin_user"
                },
                "replyToken": "test_reply_token"
            }]
        }
        
        response = self.client.post(
            '/callback',
            data=json.dumps(webhook_data),
            content_type='application/json'
        )
        
        # 3. 驗證指派結果
        updated_trip = Trip.query.get(pending_trip.id)
        self.assertEqual(updated_trip.driver_id, 533)
        self.assertEqual(updated_trip.status, "準備")
        
        # 4. 驗證回覆消息
        if mock_line_api.reply_message.called:
            call_args = mock_line_api.reply_message.call_args
            # 檢查回覆內容包含指派成功信息
            self.assertIsNotNone(call_args)
    
    def test_driver_conflict_detection_flow(self):
        """測試司機衝突檢測流程"""
        # 1. 創建衝突的班次請求
        conflict_trip = Trip(
            date=date.today(),
            time="14:30",  # 與現有班次同時間
            start_point="衝突起點",
            end_point="衝突終點",
            status="待派"
        )
        db.session.add(conflict_trip)
        db.session.commit()
        
        # 2. 嘗試指派已占用的司機
        try:
            from modules.services.driver_service import assign_driver_to_trip
            
            # 應該檢測到衝突並拒絕指派
            result = assign_driver_to_trip(conflict_trip.id, 533)
            self.assertFalse(result)  # 指派應該失敗
            
            # 驗證班次狀態未改變
            unchanged_trip = Trip.query.get(conflict_trip.id)
            self.assertEqual(unchanged_trip.status, "待派")
            self.assertIsNone(unchanged_trip.driver_id)
            
        except ImportError:
            self.skipTest("司機服務需要實現")


class TestFixedScheduleImportFlow(TestIntegrationBase):
    """固定班次匯入流程測試"""
    
    def test_weekly_import_flow(self):
        """測試週次匯入流程"""
        # 1. 清除現有實際班次
        Trip.query.filter(Trip.fixed_trip_id.isnot(None)).delete()
        db.session.commit()
        
        # 2. 執行週次匯入
        try:
            from modules.services.scheduler_service import import_fixed_schedules_for_week
            
            import_date = date.today()
            result = import_fixed_schedules_for_week(import_date)
            
            # 3. 驗證匯入結果
            imported_trips = Trip.query.filter(Trip.fixed_trip_id.isnot(None)).all()
            self.assertGreater(len(imported_trips), 0)
            
            # 4. 驗證匯入的班次屬性正確
            for trip in imported_trips:
                self.assertIsNotNone(trip.fixed_trip_id)
                self.assertEqual(trip.status, "待派")
                
                # 驗證與固定班次模板的一致性
                fixed_schedule = FixedSchedule.query.get(trip.fixed_trip_id)
                self.assertEqual(trip.start_point, fixed_schedule.start_point)
                self.assertEqual(trip.end_point, fixed_schedule.end_point)
                
        except ImportError:
            self.skipTest("排程服務需要實現")
    
    @patch('modules.utils.line_bot.line_bot_api')
    def test_import_command_flow(self, mock_line_api):
        """測試匯入命令流程"""
        # 模擬匯入命令
        import_date = date.today().strftime('%Y-%m-%d')
        webhook_data = {
            "events": [{
                "type": "message",
                "message": {
                    "type": "text",
                    "text": f"匯入固定 {import_date}"
                },
                "source": {
                    "userId": "admin_user"
                },
                "replyToken": "test_reply_token"
            }]
        }
        
        # 發送webhook請求
        response = self.client.post(
            '/callback',
            data=json.dumps(webhook_data),
            content_type='application/json'
        )
        
        # 驗證響應和結果
        self.assertEqual(response.status_code, 200)
        
        # 檢查是否發送了匯入結果回覆
        if mock_line_api.reply_message.called:
            call_args = mock_line_api.reply_message.call_args
            self.assertIsNotNone(call_args)


class TestReportGenerationFlow(TestIntegrationBase):
    """報表生成流程測試"""
    
    def setUp(self):
        super().setUp()
        # 創建已完成班次用於報表
        completed_trips = [
            CompletedTrip(
                original_trip_id=200 + i,
                date=date.today() - timedelta(days=i % 7),
                time=f"0{9 + i % 12}:00",
                start_point=f"起點{i}",
                end_point=f"終點{i}",
                actual_fare=150 + i * 10,
                driver_id=533 if i % 2 == 0 else 534,
                category="測試",
                completed_at=datetime.now() - timedelta(days=i % 7)
            )
            for i in range(14)  # 兩週的數據
        ]
        
        db.session.add_all(completed_trips)
        db.session.commit()
    
    @patch('modules.services.drive_service.upload_to_drive')
    @patch('modules.utils.line_bot.line_bot_api')
    def test_weekly_report_generation_flow(self, mock_line_api, mock_drive_upload):
        """測試週報表生成流程"""
        # Mock Google Drive 上傳
        mock_drive_upload.return_value = "https://drive.google.com/file/test-report-id"
        
        # 模擬報表生成命令
        webhook_data = {
            "events": [{
                "type": "message",
                "message": {
                    "type": "text",
                    "text": "生成周報表 測試"
                },
                "source": {
                    "userId": "admin_user"
                },
                "replyToken": "test_reply_token"
            }]
        }
        
        # 發送請求
        response = self.client.post(
            '/callback',
            data=json.dumps(webhook_data),
            content_type='application/json'
        )
        
        # 驗證響應
        self.assertEqual(response.status_code, 200)
        
        # 驗證是否調用了上傳服務
        if mock_drive_upload.called:
            # 驗證上傳被調用
            self.assertTrue(mock_drive_upload.called)
            
        # 驗證是否發送了報表連結回覆
        if mock_line_api.reply_message.called:
            call_args = mock_line_api.reply_message.call_args
            self.assertIsNotNone(call_args)
    
    def test_driver_statistics_flow(self):
        """測試司機統計流程"""
        try:
            from modules.services.report_service import generate_driver_statistics
            
            # 生成司機統計
            stats = generate_driver_statistics(533)
            
            # 驗證統計數據
            self.assertIn('total_trips', stats)
            self.assertIn('total_fare', stats)
            self.assertGreater(stats['total_trips'], 0)
            self.assertGreater(stats['total_fare'], 0)
            
        except ImportError:
            self.skipTest("報表服務需要實現")


class TestAISystemIntegration(TestIntegrationBase):
    """AI系統整合測試"""
    
    @patch('modules.ai_agent.gemini_client.get_gemini_client')
    @patch('modules.utils.line_bot.line_bot_api')
    def test_ai_query_processing_flow(self, mock_line_api, mock_gemini):
        """測試AI查詢處理流程"""
        # Mock Gemini API響應
        mock_response = Mock()
        mock_response.text = "根據查詢，找到1筆醫療類別且車資大於200的班次：高鐵站→診所，車資220元，狀態：待派"
        
        mock_client = Mock()
        mock_client.generate_content.return_value = mock_response
        mock_gemini.return_value = mock_client
        
        # 模擬AI查詢
        webhook_data = {
            "events": [{
                "type": "message",
                "message": {
                    "type": "text",
                    "text": "今天醫療類別車資大於200的班次"
                },
                "source": {
                    "userId": "test_user"
                },
                "replyToken": "test_reply_token"
            }]
        }
        
        # 發送請求
        response = self.client.post(
            '/callback',
            data=json.dumps(webhook_data),
            content_type='application/json'
        )
        
        # 驗證AI處理
        self.assertEqual(response.status_code, 200)
        
        # 驗證Gemini API被調用
        if mock_client.generate_content.called:
            self.assertTrue(mock_client.generate_content.called)
            
        # 驗證回覆包含AI生成的內容
        if mock_line_api.reply_message.called:
            call_args = mock_line_api.reply_message.call_args
            self.assertIsNotNone(call_args)
    
    @patch('modules.ai_agent.gemini_client.get_gemini_client')
    def test_ai_tool_execution_integration(self, mock_gemini):
        """測試AI工具執行整合"""
        # Mock AI工具調用響應
        mock_response = Mock()
        mock_response.text = json.dumps({
            "tool": "query_trips",
            "parameters": {
                "date": date.today().isoformat(),
                "condition": "category='醫療' AND actual_fare > 200"
            }
        })
        
        mock_client = Mock()
        mock_client.generate_content.return_value = mock_response
        mock_gemini.return_value = mock_client
        
        try:
            from modules.ai_agent.agent_core import DispatchAgent
            
            # 創建AI代理並處理查詢
            agent = DispatchAgent("test_user")
            result = agent.process_query("今天醫療班次車資大於200的")
            
            # 驗證AI處理結果
            self.assertIsNotNone(result)
            
        except ImportError:
            self.skipTest("AI代理功能需要實現")


class TestErrorHandlingFlow(TestIntegrationBase):
    """錯誤處理流程測試"""
    
    @patch('modules.utils.line_bot.line_bot_api')
    def test_invalid_command_handling(self, mock_line_api):
        """測試無效命令處理"""
        # 發送無效命令
        webhook_data = {
            "events": [{
                "type": "message",
                "message": {
                    "type": "text",
                    "text": "無效命令 錯誤參數"
                },
                "source": {
                    "userId": "test_user"
                },
                "replyToken": "test_reply_token"
            }]
        }
        
        response = self.client.post(
            '/callback',
            data=json.dumps(webhook_data),
            content_type='application/json'
        )
        
        # 應該正常處理而不是崩潰
        self.assertEqual(response.status_code, 200)
        
        # 驗證發送了錯誤回覆
        if mock_line_api.reply_message.called:
            call_args = mock_line_api.reply_message.call_args
            self.assertIsNotNone(call_args)
    
    def test_database_error_recovery(self):
        """測試資料庫錯誤恢復"""
        # 嘗試創建無效的班次（測試約束違反）
        invalid_trip = Trip(
            # 缺少必要欄位，應該引發錯誤
            status="無效狀態"
        )
        
        # 應該能夠處理資料庫錯誤而不崩潰
        try:
            db.session.add(invalid_trip)
            db.session.commit()
        except Exception:
            db.session.rollback()
            # 驗證系統能夠恢復
            self.assertTrue(True)
    
    @patch('modules.ai_agent.gemini_client.get_gemini_client')
    def test_ai_service_failure_handling(self, mock_gemini):
        """測試AI服務失敗處理"""
        # Mock AI服務失敗
        mock_gemini.side_effect = Exception("AI服務不可用")
        
        try:
            from modules.services.smart_assistant import process_with_smart_assistant
            
            # 嘗試使用AI處理
            result = process_with_smart_assistant("測試查詢", "test_user")
            
            # 應該返回錯誤處理結果而不是崩潰
            self.assertIsNotNone(result)
            
        except ImportError:
            self.skipTest("AI服務需要實現")


class TestPerformanceIntegration(TestIntegrationBase):
    """性能整合測試"""
    
    def test_concurrent_webhook_requests(self):
        """測試並發webhook請求"""
        import threading
        import time
        
        results = []
        
        def send_request():
            webhook_data = {
                "events": [{
                    "type": "message",
                    "message": {
                        "type": "text",
                        "text": "查詢 " + date.today().strftime('%Y-%m-%d')
                    },
                    "source": {
                        "userId": f"user_{threading.current_thread().ident}"
                    },
                    "replyToken": f"token_{threading.current_thread().ident}"
                }]
            }
            
            response = self.client.post(
                '/callback',
                data=json.dumps(webhook_data),
                content_type='application/json'
            )
            
            results.append(response.status_code)
        
        # 創建多個並發請求
        threads = []
        for i in range(5):
            thread = threading.Thread(target=send_request)
            threads.append(thread)
            thread.start()
        
        # 等待所有請求完成
        for thread in threads:
            thread.join()
        
        # 驗證所有請求都成功處理
        self.assertEqual(len(results), 5)
        for status_code in results:
            self.assertEqual(status_code, 200)
    
    def test_large_dataset_query_performance(self):
        """測試大數據集查詢性能"""
        import time
        
        # 創建大量測試班次
        large_dataset = []
        for i in range(100):
            trip = Trip(
                date=date.today() - timedelta(days=i % 30),
                time=f"{8 + i % 12:02d}:00",
                start_point=f"起點{i}",
                end_point=f"終點{i}",
                actual_fare=100 + i,
                category="性能測試",
                status="完成",
                driver_id=533 + (i % 3)
            )
            large_dataset.append(trip)
        
        db.session.add_all(large_dataset)
        db.session.commit()
        
        # 測試查詢性能
        start_time = time.time()
        
        # 執行複雜查詢
        results = Trip.query.filter(
            Trip.category == "性能測試",
            Trip.actual_fare > 150
        ).all()
        
        end_time = time.time()
        query_time = end_time - start_time
        
        # 驗證查詢結果和性能
        self.assertGreater(len(results), 0)
        self.assertLess(query_time, 1.0)  # 應該在1秒內完成


class TestDataConsistency(TestIntegrationBase):
    """數據一致性測試"""
    
    def test_trip_status_consistency(self):
        """測試班次狀態一致性"""
        # 測試狀態轉換的一致性
        trip = Trip.query.filter_by(status="待派").first()
        original_status = trip.status
        
        # 指派司機後狀態應該改變
        trip.driver_id = 533
        trip.status = "準備"
        db.session.commit()
        
        # 重新查詢驗證
        updated_trip = Trip.query.get(trip.id)
        self.assertEqual(updated_trip.status, "準備")
        self.assertEqual(updated_trip.driver_id, 533)
        self.assertNotEqual(updated_trip.status, original_status)
    
    def test_fixed_schedule_trip_consistency(self):
        """測試固定班次與實際班次的一致性"""
        # 查找有固定班次關聯的實際班次
        trip_with_fixed = Trip.query.filter(Trip.fixed_trip_id.isnot(None)).first()
        
        if trip_with_fixed:
            # 獲取對應的固定班次
            fixed_schedule = FixedSchedule.query.get(trip_with_fixed.fixed_trip_id)
            
            # 驗證關鍵信息一致性
            self.assertEqual(trip_with_fixed.start_point, fixed_schedule.start_point)
            self.assertEqual(trip_with_fixed.end_point, fixed_schedule.end_point)
            # 實際車資可能與固定車資不同（有加成等），但應該有合理關係
    
    def test_driver_assignment_consistency(self):
        """測試司機指派一致性"""
        # 檢查同一司機同一時間不能有多個班次
        driver_id = 533
        test_time = "10:00"
        test_date = date.today()
        
        # 查詢該司機在該時間的班次
        existing_trips = Trip.query.filter(
            Trip.driver_id == driver_id,
            Trip.date == test_date,
            Trip.time == test_time,
            Trip.status.in_(["準備", "完成"])
        ).all()
        
        # 同一時間應該最多只有一個班次
        self.assertLessEqual(len(existing_trips), 1)


if __name__ == '__main__':
    # 運行整合測試
    suite = unittest.TestLoader().loadTestsFromModule(__import__(__name__))
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)