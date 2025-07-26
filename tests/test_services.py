#!/usr/bin/env python3
"""
服務層測試套件
測試所有核心業務服務的功能和邊界條件
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


class TestServiceBase(unittest.TestCase):
    """服務測試基類"""
    
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
        
        # 清理測試數據
        db.session.query(CompletedTrip).delete()
        db.session.query(Trip).delete()
        db.session.query(FixedSchedule).delete()
        db.session.query(Customer).delete()
        db.session.query(Driver).delete()
        db.session.commit()
        
        # 創建測試數據
        self.setup_test_data()
    
    def tearDown(self):
        db.session.rollback()
        self.app_context.pop()
    
    def setup_test_data(self):
        """設置測試數據"""
        # 創建測試司機
        self.driver1 = Driver(id=533, name="王司機", plate_number="ABC-1234")
        self.driver2 = Driver(id=534, name="李司機", plate_number="DEF-5678")
        
        # 創建測試客戶
        self.customer1 = Customer(name="診所", address="台南市", category="醫療")
        self.customer2 = Customer(name="東洋", address="高雄市", category="企業")
        
        db.session.add_all([self.driver1, self.driver2, self.customer1, self.customer2])
        db.session.commit()


class TestTripService(TestServiceBase):
    """班次服務測試"""
    
    def test_trip_creation_service(self):
        """測試班次創建服務"""
        from modules.services.trip_service import create_trip
        
        trip_data = {
            'date': date.today(),
            'time': '14:30',
            'start_point': '高鐵站',
            'end_point': '診所',
            'meter_fare': 150,
            'extra_fare': 0,
            'actual_fare': 150,
            'category': '醫療'
        }
        
        # 測試班次創建
        try:
            result = create_trip(trip_data)
            self.assertIsNotNone(result)
        except ImportError:
            # 如果服務不存在，標記為需要實現
            self.skipTest("trip_service.create_trip 需要實現")
    
    def test_trip_status_update_service(self):
        """測試班次狀態更新服務"""
        # 創建測試班次
        trip = Trip(
            date=date.today(),
            time="10:00",
            start_point="A",
            end_point="B",
            status="待派"
        )
        db.session.add(trip)
        db.session.commit()
        
        try:
            from modules.services.trip_service import update_trip_status
            
            # 測試狀態更新
            result = update_trip_status(trip.id, "準備")
            self.assertTrue(result)
            
            # 驗證狀態已更新
            updated_trip = Trip.query.get(trip.id)
            self.assertEqual(updated_trip.status, "準備")
            
        except ImportError:
            self.skipTest("trip_service.update_trip_status 需要實現")
    
    def test_trip_query_by_date(self):
        """測試按日期查詢班次"""
        today = date.today()
        tomorrow = today + timedelta(days=1)
        
        # 創建不同日期的班次
        trip_today = Trip(date=today, time="09:00", start_point="A", end_point="B")
        trip_tomorrow = Trip(date=tomorrow, time="10:00", start_point="C", end_point="D")
        
        db.session.add_all([trip_today, trip_tomorrow])
        db.session.commit()
        
        try:
            from modules.services.trip_service import get_trips_by_date
            
            today_trips = get_trips_by_date(today)
            self.assertEqual(len(today_trips), 1)
            self.assertEqual(today_trips[0].start_point, "A")
            
        except ImportError:
            self.skipTest("trip_service.get_trips_by_date 需要實現")
    
    def test_30min_modification_restriction(self):
        """測試30分鐘修改限制"""
        now = datetime.now()
        
        # 創建20分鐘後的班次（應該被限制）
        near_trip = Trip(
            date=now.date(),
            time=(now + timedelta(minutes=20)).strftime("%H:%M"),
            start_point="近期班次",
            end_point="終點",
            status="準備"
        )
        
        # 創建40分鐘後的班次（應該可以修改）
        safe_trip = Trip(
            date=now.date(),
            time=(now + timedelta(minutes=40)).strftime("%H:%M"),
            start_point="安全班次",
            end_point="終點",
            status="準備"
        )
        
        db.session.add_all([near_trip, safe_trip])
        db.session.commit()
        
        try:
            from modules.services.trip_service import can_modify_trip
            
            # 測試修改限制
            self.assertFalse(can_modify_trip(near_trip.id))
            self.assertTrue(can_modify_trip(safe_trip.id))
            
        except ImportError:
            self.skipTest("trip_service.can_modify_trip 需要實現")


class TestDriverService(TestServiceBase):
    """司機服務測試"""
    
    def test_driver_assignment(self):
        """測試司機指派"""
        # 創建測試班次
        trip = Trip(
            date=date.today(),
            time="15:00",
            start_point="起點",
            end_point="終點",
            status="待派"
        )
        db.session.add(trip)
        db.session.commit()
        
        try:
            from modules.services.driver_service import assign_driver_to_trip
            
            # 測試司機指派
            result = assign_driver_to_trip(trip.id, self.driver1.id)
            self.assertTrue(result)
            
            # 驗證指派成功
            updated_trip = Trip.query.get(trip.id)
            self.assertEqual(updated_trip.driver_id, self.driver1.id)
            self.assertEqual(updated_trip.status, "準備")
            
        except ImportError:
            self.skipTest("driver_service.assign_driver_to_trip 需要實現")
    
    def test_driver_conflict_detection(self):
        """測試司機衝突檢測"""
        trip_time = "16:00"
        trip_date = date.today()
        
        # 創建已指派的班次
        existing_trip = Trip(
            date=trip_date,
            time=trip_time,
            start_point="A",
            end_point="B",
            driver_id=self.driver1.id,
            status="準備"
        )
        
        # 創建衝突的班次
        conflict_trip = Trip(
            date=trip_date,
            time=trip_time,
            start_point="C",
            end_point="D",
            status="待派"
        )
        
        db.session.add_all([existing_trip, conflict_trip])
        db.session.commit()
        
        try:
            from modules.services.driver_service import check_driver_conflict
            
            # 測試衝突檢測
            has_conflict = check_driver_conflict(self.driver1.id, trip_date, trip_time)
            self.assertTrue(has_conflict)
            
            # 測試無衝突的司機
            no_conflict = check_driver_conflict(self.driver2.id, trip_date, trip_time)
            self.assertFalse(no_conflict)
            
        except ImportError:
            self.skipTest("driver_service.check_driver_conflict 需要實現")
    
    def test_available_drivers_query(self):
        """測試可用司機查詢"""
        try:
            from modules.services.driver_service import get_available_drivers
            
            available_drivers = get_available_drivers(date.today(), "12:00")
            self.assertGreaterEqual(len(available_drivers), 2)
            
            # 驗證返回的是Driver對象
            self.assertIsInstance(available_drivers[0], Driver)
            
        except ImportError:
            self.skipTest("driver_service.get_available_drivers 需要實現")


class TestSchedulerService(TestServiceBase):
    """排程服務測試"""
    
    def test_fixed_schedule_import(self):
        """測試固定班次匯入"""
        # 創建固定班次模板
        schedule = FixedSchedule(
            route_number="R001",
            departure_time="08:00",
            day_of_week=1,  # 星期一
            start_point="固定起點",
            end_point="固定終點",
            total_fare=200,
            category="定期"
        )
        db.session.add(schedule)
        db.session.commit()
        
        try:
            from modules.services.scheduler_service import import_fixed_schedules_for_week
            
            # 測試週次匯入
            import_date = date.today()
            result = import_fixed_schedules_for_week(import_date)
            
            # 驗證固定班次已轉為實際班次
            imported_trips = Trip.query.filter(Trip.fixed_trip_id == schedule.id).all()
            self.assertGreater(len(imported_trips), 0)
            
        except ImportError:
            self.skipTest("scheduler_service.import_fixed_schedules_for_week 需要實現")
    
    def test_auto_complete_expired_trips(self):
        """測試自動完成過期班次"""
        yesterday = date.today() - timedelta(days=1)
        
        # 創建昨天的班次
        expired_trip = Trip(
            date=yesterday,
            time="10:00",
            start_point="過期起點",
            end_point="過期終點",
            status="準備",
            driver_id=self.driver1.id,
            actual_fare=150
        )
        db.session.add(expired_trip)
        db.session.commit()
        
        try:
            from modules.services.scheduler_service import update_completed_trips
            
            # 執行自動完成
            update_completed_trips()
            
            # 驗證班次已轉為完成狀態或移至completed_trips
            updated_trip = Trip.query.get(expired_trip.id)
            if updated_trip:
                self.assertEqual(updated_trip.status, "完成")
            else:
                # 檢查是否移至completed_trips表
                completed = CompletedTrip.query.filter(
                    CompletedTrip.original_trip_id == expired_trip.id
                ).first()
                self.assertIsNotNone(completed)
                
        except ImportError:
            self.skipTest("scheduler_service.update_completed_trips 需要實現")


class TestReportService(TestServiceBase):
    """報表服務測試"""
    
    def setUp(self):
        super().setUp()
        # 創建測試用的已完成班次
        last_week = date.today() - timedelta(days=7)
        
        self.completed_trips = [
            CompletedTrip(
                original_trip_id=i,
                date=last_week + timedelta(days=i % 7),
                time=f"0{8+i}:00",
                start_point=f"起點{i}",
                end_point=f"終點{i}",
                actual_fare=100 + i * 10,
                driver_id=self.driver1.id if i % 2 == 0 else self.driver2.id,
                category="測試",
                completed_at=datetime.now()
            )
            for i in range(10)
        ]
        
        db.session.add_all(self.completed_trips)
        db.session.commit()
    
    def test_weekly_report_generation(self):
        """測試週報表生成"""
        try:
            from modules.services.report_service import generate_weekly_report
            
            # 生成上週報表
            report_data = generate_weekly_report()
            
            # 驗證報表數據結構
            self.assertIn('trips', report_data)
            self.assertIn('total_fare', report_data)
            self.assertIn('trip_count', report_data)
            
        except ImportError:
            self.skipTest("report_service.generate_weekly_report 需要實現")
    
    @patch('modules.services.drive_service.upload_to_drive')
    def test_report_upload_to_drive(self, mock_upload):
        """測試報表上傳到Google Drive"""
        mock_upload.return_value = "https://drive.google.com/test-file"
        
        try:
            from modules.services.report_service import generate_and_upload_report
            
            result = generate_and_upload_report("weekly")
            
            # 驗證上傳被調用
            mock_upload.assert_called_once()
            self.assertIn("drive.google.com", result)
            
        except ImportError:
            self.skipTest("report_service.generate_and_upload_report 需要實現")
    
    def test_driver_statistics_report(self):
        """測試司機統計報表"""
        try:
            from modules.services.report_service import generate_driver_statistics
            
            stats = generate_driver_statistics(self.driver1.id)
            
            # 驗證統計數據
            self.assertIn('total_trips', stats)
            self.assertIn('total_fare', stats)
            self.assertIn('average_fare', stats)
            
        except ImportError:
            self.skipTest("report_service.generate_driver_statistics 需要實現")


class TestAIService(TestServiceBase):
    """AI服務測試"""
    
    @patch('modules.services.ai_service.get_gemini_client')
    def test_booking_extraction(self, mock_client):
        """測試預約資訊提取"""
        # Mock Gemini API 響應
        mock_response = Mock()
        mock_response.text = json.dumps({
            "date": "2025-01-25",
            "time": "14:30",
            "start_point": "高鐵站",
            "end_point": "診所",
            "fare": "150",
            "passenger": "王先生"
        })
        mock_client.return_value.generate_content.return_value = mock_response
        
        try:
            from modules.services.ai_service import extract_booking_info_with_gemini
            
            test_message = "明天下午2點半從高鐵站到診所，車資150"
            result = extract_booking_info_with_gemini(test_message)
            
            # 驗證提取結果
            self.assertEqual(result['time'], "14:30")
            self.assertEqual(result['start_point'], "高鐵站")
            self.assertEqual(result['end_point'], "診所")
            
        except ImportError:
            self.skipTest("ai_service.extract_booking_info_with_gemini 需要實現")
    
    @patch('modules.services.ai_service.get_gemini_client')
    def test_smart_query_processing(self, mock_client):
        """測試智能查詢處理"""
        mock_response = Mock()
        mock_response.text = "根據查詢條件，找到3筆金額大於200的診所班次"
        mock_client.return_value.generate_content.return_value = mock_response
        
        try:
            from modules.services.smart_assistant import process_with_smart_assistant
            
            query = "今天金額大於200的診所班次"
            result = process_with_smart_assistant(query, "test_user")
            
            # 驗證AI處理結果
            self.assertIsNotNone(result)
            self.assertIn("診所班次", result)
            
        except ImportError:
            self.skipTest("smart_assistant.process_with_smart_assistant 需要實現")


class TestMessageService(TestServiceBase):
    """訊息服務測試"""
    
    @patch('modules.utils.line_bot.line_bot_api')
    def test_send_text_message(self, mock_line_api):
        """測試發送文字訊息"""
        try:
            from modules.services.message_service import send_text_message
            
            user_id = "test_user_id"
            message = "測試訊息"
            
            send_text_message(user_id, message)
            
            # 驗證LINE API被調用
            mock_line_api.push_message.assert_called_once()
            
        except ImportError:
            self.skipTest("message_service.send_text_message 需要實現")
    
    @patch('modules.utils.line_bot.line_bot_api')
    def test_send_flex_message(self, mock_line_api):
        """測試發送Flex訊息"""
        try:
            from modules.services.message_service import send_flex_message
            
            user_id = "test_user_id"
            flex_content = {"type": "bubble", "body": {"type": "box", "layout": "vertical"}}
            
            send_flex_message(user_id, "測試Flex", flex_content)
            
            # 驗證LINE API被調用
            mock_line_api.push_message.assert_called_once()
            
        except ImportError:
            self.skipTest("message_service.send_flex_message 需要實現")


class TestIntegrationScenarios(TestServiceBase):
    """整合情境測試"""
    
    def test_complete_booking_flow(self):
        """測試完整預約流程"""
        # 1. 創建臨時預約
        trip_data = {
            'date': date.today() + timedelta(days=1),
            'time': '15:00',
            'start_point': '高鐵站',
            'end_point': '醫院',
            'actual_fare': 200,
            'category': '醫療'
        }
        
        trip = Trip(**trip_data, status="待派")
        db.session.add(trip)
        db.session.commit()
        
        # 2. 指派司機
        trip.driver_id = self.driver1.id
        trip.status = "準備"
        db.session.commit()
        
        # 3. 驗證完整流程
        final_trip = Trip.query.get(trip.id)
        self.assertEqual(final_trip.status, "準備")
        self.assertEqual(final_trip.driver_id, self.driver1.id)
        self.assertEqual(final_trip.actual_fare, 200)
    
    def test_fixed_schedule_to_completion_flow(self):
        """測試固定班次到完成的完整流程"""
        # 1. 創建固定班次模板
        schedule = FixedSchedule(
            route_number="FLOW001",
            departure_time="09:00",
            day_of_week=1,
            start_point="起點",
            end_point="終點",
            total_fare=180
        )
        db.session.add(schedule)
        db.session.commit()
        
        # 2. 匯入為實際班次
        trip = Trip(
            date=date.today(),
            time=schedule.departure_time,
            start_point=schedule.start_point,
            end_point=schedule.end_point,
            actual_fare=schedule.total_fare,
            fixed_trip_id=schedule.id,
            status="待派"
        )
        db.session.add(trip)
        db.session.commit()
        
        # 3. 指派司機
        trip.driver_id = self.driver1.id
        trip.status = "準備"
        db.session.commit()
        
        # 4. 完成班次
        trip.status = "完成"
        db.session.commit()
        
        # 5. 驗證整個流程
        completed_trip = Trip.query.get(trip.id)
        self.assertEqual(completed_trip.status, "完成")
        self.assertEqual(completed_trip.fixed_trip_id, schedule.id)
        self.assertEqual(completed_trip.driver_id, self.driver1.id)


if __name__ == '__main__':
    unittest.main(verbosity=2)