#!/usr/bin/env python3
"""
處理器層測試套件
測試所有消息處理器和業務處理邏輯
"""
import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, date, timedelta

from modules import create_app
from modules.models.base import db
from modules.models.trip import Trip, FixedSchedule
from modules.models.driver import Driver
from modules.models.customer import Customer


class TestHandlersBase(unittest.TestCase):
    """處理器測試基類"""
    
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
        
        # 清理並創建測試數據
        self.setup_test_data()
    
    def tearDown(self):
        db.session.rollback()
        self.app_context.pop()
    
    def setup_test_data(self):
        """設置測試數據"""
        # 清理舊數據
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
        
        db.session.add_all(self.drivers + self.customers)
        db.session.commit()


class TestMessageHandler(TestHandlersBase):
    """消息處理器測試"""
    
    def test_message_routing(self):
        """測試消息路由分發"""
        try:
            from modules.handlers.message_handler import should_process
            
            # 測試應該處理的消息
            self.assertTrue(should_process("查詢 2025-01-25"))
            self.assertTrue(should_process("指派 123 533"))
            self.assertTrue(should_process("幫助"))
            
            # 測試不應該處理的消息（可能是AI處理）
            self.assertFalse(should_process("你好"))
            self.assertFalse(should_process("謝謝"))
            
        except ImportError:
            self.skipTest("message_handler.should_process 需要實現")
    
    def test_command_parsing(self):
        """測試命令解析"""
        try:
            from modules.handlers.message_handler import parse_command
            
            # 測試查詢命令解析
            cmd, args = parse_command("查詢 2025-01-25")
            self.assertEqual(cmd, "查詢")
            self.assertEqual(args, ["2025-01-25"])
            
            # 測試指派命令解析
            cmd, args = parse_command("指派 123 533")
            self.assertEqual(cmd, "指派")
            self.assertEqual(args, ["123", "533"])
            
        except ImportError:
            self.skipTest("message_handler.parse_command 需要實現")


class TestTextMessageHandler(TestHandlersBase):
    """文本消息處理器測試"""
    
    @patch('modules.utils.line_bot.line_bot_api')
    def test_help_command(self, mock_line_api):
        """測試幫助命令處理"""
        try:
            from modules.handlers.text_message_handler import handle_text_message
            
            # 模擬LINE事件
            mock_event = Mock()
            mock_event.message.text = "幫助"
            mock_event.source.user_id = "test_user"
            
            # 處理幫助命令
            handle_text_message(mock_event)
            
            # 驗證回覆被發送
            mock_line_api.reply_message.assert_called_once()
            
        except ImportError:
            self.skipTest("text_message_handler.handle_text_message 需要實現")
    
    @patch('modules.utils.line_bot.line_bot_api')
    def test_trip_query_command(self, mock_line_api):
        """測試班次查詢命令"""
        # 創建測試班次
        test_trip = Trip(
            date=date.today(),
            time="14:30",
            start_point="高鐵站",
            end_point="診所",
            status="待派",
            actual_fare=150
        )
        db.session.add(test_trip)
        db.session.commit()
        
        try:
            from modules.handlers.text_message_handler import handle_text_message
            
            # 模擬查詢命令
            mock_event = Mock()
            mock_event.message.text = f"查詢 {date.today().strftime('%Y-%m-%d')}"
            mock_event.source.user_id = "test_user"
            
            handle_text_message(mock_event)
            
            # 驗證回覆包含班次信息
            mock_line_api.reply_message.assert_called_once()
            
        except ImportError:
            self.skipTest("text_message_handler.handle_text_message 需要實現")
    
    @patch('modules.utils.line_bot.line_bot_api')
    def test_driver_assignment_command(self, mock_line_api):
        """測試司機指派命令"""
        # 創建待派班次
        pending_trip = Trip(
            date=date.today(),
            time="15:00",
            start_point="起點",
            end_point="終點",
            status="待派"
        )
        db.session.add(pending_trip)
        db.session.commit()
        
        try:
            from modules.handlers.text_message_handler import handle_text_message
            
            # 模擬指派命令
            mock_event = Mock()
            mock_event.message.text = f"指派 {pending_trip.id} 533"
            mock_event.source.user_id = "test_user"
            
            handle_text_message(mock_event)
            
            # 驗證指派成功回覆
            mock_line_api.reply_message.assert_called_once()
            
            # 驗證班次狀態已更新
            updated_trip = Trip.query.get(pending_trip.id)
            self.assertEqual(updated_trip.driver_id, 533)
            self.assertEqual(updated_trip.status, "準備")
            
        except ImportError:
            self.skipTest("text_message_handler.handle_text_message 需要實現")


class TestTripHandler(TestHandlersBase):
    """班次處理器測試"""
    
    def test_create_trip_handler(self):
        """測試創建班次處理器"""
        try:
            from modules.handlers.trip_handler import handle_create_trip
            
            trip_data = {
                'date': '2025-01-26',
                'time': '16:00',
                'start_point': '車站',
                'end_point': '醫院',
                'actual_fare': '200',
                'category': '醫療'
            }
            
            # 處理創建班次
            result = handle_create_trip(trip_data)
            
            # 驗證班次創建成功
            self.assertIsNotNone(result)
            
            # 檢查數據庫中的班次
            created_trip = Trip.query.filter_by(start_point='車站').first()
            self.assertIsNotNone(created_trip)
            self.assertEqual(created_trip.actual_fare, 200)
            
        except ImportError:
            self.skipTest("trip_handler.handle_create_trip 需要實現")
    
    def test_update_trip_status_handler(self):
        """測試更新班次狀態處理器"""
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
            from modules.handlers.trip_handler import handle_update_trip_status
            
            # 處理狀態更新
            result = handle_update_trip_status(trip.id, "準備")
            
            # 驗證更新成功
            self.assertTrue(result)
            
            # 檢查狀態已更新
            updated_trip = Trip.query.get(trip.id)
            self.assertEqual(updated_trip.status, "準備")
            
        except ImportError:
            self.skipTest("trip_handler.handle_update_trip_status 需要實現")
    
    def test_trip_detail_handler(self):
        """測試班次詳情處理器"""
        # 創建詳細班次
        trip = Trip(
            date=date.today(),
            time="11:30",
            start_point="詳細起點",
            via_point="經過點",
            end_point="詳細終點",
            meter_fare=120,
            extra_fare=30,
            actual_fare=150,
            status="準備",
            driver_id=533,
            category="測試"
        )
        db.session.add(trip)
        db.session.commit()
        
        try:
            from modules.handlers.trip_handler import handle_trip_detail
            
            # 處理詳情查詢
            result = handle_trip_detail(trip.id)
            
            # 驗證返回詳情
            self.assertIsNotNone(result)
            self.assertIn("詳細起點", result)
            self.assertIn("533", result)  # 司機ID
            
        except ImportError:
            self.skipTest("trip_handler.handle_trip_detail 需要實現")


class TestTempBookingHandler(TestHandlersBase):
    """臨時預約處理器測試"""
    
    @patch('modules.utils.line_bot.line_bot_api')
    def test_temp_booking_flow(self, mock_line_api):
        """測試臨時預約流程"""
        try:
            from modules.handlers.temp_booking_handler import handle_temp_booking
            
            # 模擬預約消息
            booking_message = "明天下午3點從高鐵站到醫院，車資200"
            user_id = "test_user"
            
            # 處理臨時預約
            result = handle_temp_booking(booking_message, user_id)
            
            # 驗證處理成功
            self.assertIsNotNone(result)
            
            # 檢查是否創建了臨時班次
            temp_trip = Trip.query.filter_by(start_point="高鐵站").first()
            if temp_trip:
                self.assertEqual(temp_trip.end_point, "醫院")
                self.assertEqual(temp_trip.actual_fare, 200)
            
        except ImportError:
            self.skipTest("temp_booking_handler.handle_temp_booking 需要實現")
    
    def test_booking_confirmation_handler(self):
        """測試預約確認處理器"""
        try:
            from modules.handlers.temp_booking_handler import handle_booking_confirmation
            
            # 創建待確認的臨時預約
            temp_data = {
                'date': date.today() + timedelta(days=1),
                'time': '15:00',
                'start_point': '確認起點',
                'end_point': '確認終點',
                'actual_fare': 180
            }
            
            # 處理確認
            result = handle_booking_confirmation(temp_data, "test_user")
            
            # 驗證確認處理
            self.assertIsNotNone(result)
            
        except ImportError:
            self.skipTest("temp_booking_handler.handle_booking_confirmation 需要實現")


class TestDriverHandler(TestHandlersBase):
    """司機處理器測試（如果存在）"""
    
    def test_assign_driver_handler(self):
        """測試司機指派處理器"""
        # 創建待派班次
        trip = Trip(
            date=date.today(),
            time="09:00",
            start_point="指派測試起點",
            end_point="指派測試終點",
            status="待派"
        )
        db.session.add(trip)
        db.session.commit()
        
        try:
            # 假設有司機處理器模組
            from modules.handlers.driver_handler import handle_driver_assignment
            
            # 處理司機指派
            result = handle_driver_assignment(trip.id, 533)
            
            # 驗證指派成功
            self.assertTrue(result)
            
            # 檢查班次已指派司機
            assigned_trip = Trip.query.get(trip.id)
            self.assertEqual(assigned_trip.driver_id, 533)
            self.assertEqual(assigned_trip.status, "準備")
            
        except ImportError:
            self.skipTest("driver_handler.handle_driver_assignment 可能不存在")
    
    def test_driver_conflict_handler(self):
        """測試司機衝突處理器"""
        trip_time = "12:00"
        trip_date = date.today()
        
        # 創建已占用時段的班次
        existing_trip = Trip(
            date=trip_date,
            time=trip_time,
            start_point="衝突1",
            end_point="衝突1終點",
            driver_id=533,
            status="準備"
        )
        
        # 創建衝突的班次請求
        conflict_trip = Trip(
            date=trip_date,
            time=trip_time,
            start_point="衝突2",
            end_point="衝突2終點",
            status="待派"
        )
        
        db.session.add_all([existing_trip, conflict_trip])
        db.session.commit()
        
        try:
            from modules.handlers.driver_handler import handle_conflict_check
            
            # 檢查衝突
            has_conflict = handle_conflict_check(533, trip_date, trip_time)
            
            # 驗證衝突檢測
            self.assertTrue(has_conflict)
            
        except ImportError:
            self.skipTest("driver_handler.handle_conflict_check 可能不存在")


class TestFixedScheduleHandlers(TestHandlersBase):
    """固定班次處理器測試"""
    
    def test_import_fixed_schedules_handler(self):
        """測試固定班次匯入處理器"""
        # 創建固定班次模板
        schedules = [
            FixedSchedule(
                route_number=f"R00{i}",
                departure_time=f"0{8+i}:00",
                day_of_week=i % 7,
                start_point=f"固定起點{i}",
                end_point=f"固定終點{i}",
                total_fare=150 + i * 10,
                category="固定"
            )
            for i in range(7)
        ]
        
        db.session.add_all(schedules)
        db.session.commit()
        
        try:
            from modules.handlers.import_handler import handle_import_fixed_schedules
            
            # 處理匯入
            import_date = date.today()
            result = handle_import_fixed_schedules(import_date)
            
            # 驗證匯入成功
            self.assertIsNotNone(result)
            
            # 檢查是否創建了實際班次
            imported_trips = Trip.query.filter(Trip.fixed_trip_id.isnot(None)).all()
            self.assertGreater(len(imported_trips), 0)
            
        except ImportError:
            self.skipTest("import_handler.handle_import_fixed_schedules 需要實現")
    
    def test_fixed_schedule_leave_handler(self):
        """測試固定班次請假處理器"""
        # 創建固定班次
        schedule = FixedSchedule(
            route_number="LEAVE001",
            departure_time="10:00",
            day_of_week=1,
            start_point="請假起點",
            end_point="請假終點",
            total_fare=200
        )
        db.session.add(schedule)
        db.session.commit()
        
        # 創建對應的實際班次
        trip = Trip(
            date=date.today(),
            time=schedule.departure_time,
            start_point=schedule.start_point,
            end_point=schedule.end_point,
            fixed_trip_id=schedule.id,
            status="準備"
        )
        db.session.add(trip)
        db.session.commit()
        
        try:
            from modules.handlers.fixed_schedule_leave_handler import handle_fixed_schedule_leave
            
            # 處理固定班次請假
            result = handle_fixed_schedule_leave(trip.id, "客戶請假")
            
            # 驗證請假處理
            self.assertIsNotNone(result)
            
            # 檢查班次狀態
            updated_trip = Trip.query.get(trip.id)
            self.assertEqual(updated_trip.status, "請假")
            
        except ImportError:
            self.skipTest("fixed_schedule_leave_handler.handle_fixed_schedule_leave 需要實現")


class TestSpecialHandlers(TestHandlersBase):
    """特殊功能處理器測試"""
    
    def test_batch_allowance_handler(self):
        """測試批量加成處理器"""
        # 創建需要加成的班次
        trips = [
            Trip(
                date=date.today(),
                time=f"1{i}:00",
                start_point=f"加成起點{i}",
                end_point=f"加成終點{i}",
                actual_fare=100,
                category="測試"
            )
            for i in range(3)
        ]
        
        db.session.add_all(trips)
        db.session.commit()
        
        try:
            from modules.handlers.batch_allowance_handler import handle_batch_allowance
            
            # 處理批量加成（例如：颱風假加成50）
            result = handle_batch_allowance("測試", 50, date.today())
            
            # 驗證加成處理
            self.assertIsNotNone(result)
            
            # 檢查車資是否已加成
            updated_trips = Trip.query.filter(Trip.category == "測試").all()
            for trip in updated_trips:
                self.assertEqual(trip.actual_fare, 150)  # 100 + 50
                
        except ImportError:
            self.skipTest("batch_allowance_handler.handle_batch_allowance 需要實現")
    
    def test_sequence_fix_handler(self):
        """測試序列修復處理器"""
        try:
            from modules.handlers.sequence_fix_handler import handle_sequence_fix
            
            # 處理序列修復
            result = handle_sequence_fix()
            
            # 驗證修復處理
            self.assertIsNotNone(result)
            
        except ImportError:
            self.skipTest("sequence_fix_handler.handle_sequence_fix 需要實現")
    
    def test_database_sync_handler(self):
        """測試資料庫同步處理器"""
        try:
            from modules.handlers.database_sync_handler import handle_database_sync
            
            # 處理資料庫同步
            result = handle_database_sync()
            
            # 驗證同步處理
            self.assertIsNotNone(result)
            
        except ImportError:
            self.skipTest("database_sync_handler.handle_database_sync 需要實現")


class TestErrorHandling(TestHandlersBase):
    """錯誤處理測試"""
    
    @patch('modules.utils.line_bot.line_bot_api')
    def test_invalid_command_handling(self, mock_line_api):
        """測試無效命令處理"""
        try:
            from modules.handlers.text_message_handler import handle_text_message
            
            # 模擬無效命令
            mock_event = Mock()
            mock_event.message.text = "無效命令 參數1 參數2"
            mock_event.source.user_id = "test_user"
            
            # 處理無效命令
            handle_text_message(mock_event)
            
            # 驗證錯誤回覆
            mock_line_api.reply_message.assert_called_once()
            
        except ImportError:
            self.skipTest("text_message_handler.handle_text_message 需要實現")
    
    def test_missing_parameters_handling(self):
        """測試缺少參數的處理"""
        try:
            from modules.handlers.trip_handler import handle_create_trip
            
            # 測試缺少必要參數
            incomplete_data = {
                'date': '2025-01-26',
                # 缺少 time, start_point, end_point
            }
            
            # 應該拋出異常或返回錯誤
            with self.assertRaises((ValueError, KeyError)):
                handle_create_trip(incomplete_data)
                
        except ImportError:
            self.skipTest("trip_handler.handle_create_trip 需要實現")
    
    def test_database_error_handling(self):
        """測試資料庫錯誤處理"""
        try:
            from modules.handlers.trip_handler import handle_update_trip_status
            
            # 測試更新不存在的班次
            result = handle_update_trip_status(99999, "準備")
            
            # 應該返回False或拋出適當的異常
            self.assertFalse(result)
            
        except ImportError:
            self.skipTest("trip_handler.handle_update_trip_status 需要實現")


if __name__ == '__main__':
    # 運行測試
    suite = unittest.TestLoader().loadTestsFromModule(__import__(__name__))
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)