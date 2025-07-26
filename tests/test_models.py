#!/usr/bin/env python3
"""
資料模型測試套件
測試所有資料模型的基本CRUD操作和業務邏輯
"""
import unittest
import pytest
from datetime import datetime, date, timedelta
from modules import create_app
from modules.models.base import db
from modules.models.customer import Customer
from modules.models.driver import Driver
from modules.models.trip import Trip, FixedSchedule, CompletedTrip


class TestModels(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        """設置測試環境"""
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        cls.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        
        with cls.app.app_context():
            db.create_all()
    
    def setUp(self):
        """每個測試前的設置"""
        self.app_context = self.app.app_context()
        self.app_context.push()
        
        # 清理測試數據
        db.session.query(CompletedTrip).delete()
        db.session.query(Trip).delete()
        db.session.query(FixedSchedule).delete()
        db.session.query(Customer).delete()
        db.session.query(Driver).delete()
        db.session.commit()
    
    def tearDown(self):
        """每個測試後的清理"""
        db.session.rollback()
        self.app_context.pop()
    
    @classmethod
    def tearDownClass(cls):
        """清理測試環境"""
        with cls.app.app_context():
            db.drop_all()


class TestCustomerModel(TestModels):
    """客戶模型測試"""
    
    def test_customer_creation(self):
        """測試客戶創建"""
        customer = Customer(
            name="測試診所",
            address="台南市中西區",
            short_name="診所",
            category="醫療"
        )
        db.session.add(customer)
        db.session.commit()
        
        # 驗證創建成功
        saved_customer = Customer.query.first()
        self.assertEqual(saved_customer.name, "測試診所")
        self.assertEqual(saved_customer.short_name, "診所")
        self.assertEqual(saved_customer.category, "醫療")
    
    def test_customer_unique_constraints(self):
        """測試客戶唯一性約束"""
        # 創建第一個客戶
        customer1 = Customer(name="重複診所", address="地址1")
        db.session.add(customer1)
        db.session.commit()
        
        # 嘗試創建同名客戶
        customer2 = Customer(name="重複診所", address="地址2")
        db.session.add(customer2)
        
        with self.assertRaises(Exception):
            db.session.commit()


class TestDriverModel(TestModels):
    """司機模型測試"""
    
    def test_driver_creation(self):
        """測試司機創建"""
        driver = Driver(
            name="王司機",
            plate_number="ABC-1234",
            car_brand="Toyota",
            car_model="Camry"
        )
        db.session.add(driver)
        db.session.commit()
        
        # 驗證創建成功
        saved_driver = Driver.query.first()
        self.assertEqual(saved_driver.name, "王司機")
        self.assertEqual(saved_driver.plate_number, "ABC-1234")
    
    def test_driver_plate_number_unique(self):
        """測試車牌號碼唯一性"""
        driver1 = Driver(name="司機1", plate_number="ABC-1234")
        driver2 = Driver(name="司機2", plate_number="ABC-1234")
        
        db.session.add(driver1)
        db.session.commit()
        
        db.session.add(driver2)
        with self.assertRaises(Exception):
            db.session.commit()


class TestTripModel(TestModels):
    """班次模型測試"""
    
    def setUp(self):
        super().setUp()
        # 創建測試用的客戶和司機
        self.customer = Customer(name="測試客戶", address="測試地址")
        self.driver = Driver(name="測試司機", plate_number="TEST-123")
        db.session.add_all([self.customer, self.driver])
        db.session.commit()
    
    def test_trip_creation(self):
        """測試班次創建"""
        trip_date = date.today()
        trip = Trip(
            date=trip_date,
            time="14:30",
            start_point="起點",
            via_point="經過",
            end_point="終點",
            meter_fare=100,
            extra_fare=50,
            actual_fare=150,
            category="測試",
            status="待派"
        )
        db.session.add(trip)
        db.session.commit()
        
        # 驗證創建成功
        saved_trip = Trip.query.first()
        self.assertEqual(saved_trip.date, trip_date)
        self.assertEqual(saved_trip.status, "待派")
        self.assertEqual(saved_trip.actual_fare, 150)
    
    def test_trip_status_transitions(self):
        """測試班次狀態轉換"""
        trip = Trip(
            date=date.today(),
            time="10:00",
            start_point="A",
            end_point="B",
            status="待派"
        )
        db.session.add(trip)
        db.session.commit()
        
        # 狀態轉換：待派 -> 準備
        trip.status = "準備"
        trip.driver_id = self.driver.id
        db.session.commit()
        
        updated_trip = Trip.query.first()
        self.assertEqual(updated_trip.status, "準備")
        self.assertEqual(updated_trip.driver_id, self.driver.id)
    
    def test_trip_30min_restriction(self):
        """測試30分鐘修改限制邏輯"""
        now = datetime.now()
        
        # 創建一個25分鐘後的班次（應該允許修改）
        future_trip = Trip(
            date=now.date(),
            time=(now + timedelta(minutes=25)).strftime("%H:%M"),
            start_point="A",
            end_point="B",
            status="準備"
        )
        
        # 創建一個35分鐘後的班次（應該允許修改）
        safe_trip = Trip(
            date=now.date(),
            time=(now + timedelta(minutes=35)).strftime("%H:%M"),
            start_point="C",
            end_point="D",
            status="準備"
        )
        
        db.session.add_all([future_trip, safe_trip])
        db.session.commit()
        
        # 這裡可以添加具體的30分鐘限制邏輯測試
        # 實際的業務邏輯應該在服務層測試


class TestFixedScheduleModel(TestModels):
    """固定班次模型測試"""
    
    def test_fixed_schedule_creation(self):
        """測試固定班次創建"""
        schedule = FixedSchedule(
            route_number="R001",
            departure_time="08:30",
            day_of_week=1,  # 星期一
            start_point="固定起點",
            end_point="固定終點",
            base_fare=200,
            total_fare=250,
            category="固定"
        )
        db.session.add(schedule)
        db.session.commit()
        
        saved_schedule = FixedSchedule.query.first()
        self.assertEqual(saved_schedule.route_number, "R001")
        self.assertEqual(saved_schedule.day_of_week, 1)
        self.assertEqual(saved_schedule.total_fare, 250)
    
    def test_fixed_schedule_week_import(self):
        """測試固定班次週次匯入邏輯"""
        # 創建一週的固定班次
        for day in range(7):  # 0=星期日, 1=星期一, ..., 6=星期六
            schedule = FixedSchedule(
                route_number=f"R00{day}",
                departure_time="09:00",
                day_of_week=day,
                start_point="起點",
                end_point="終點",
                total_fare=150
            )
            db.session.add(schedule)
        
        db.session.commit()
        
        # 驗證7個固定班次都創建成功
        schedules = FixedSchedule.query.all()
        self.assertEqual(len(schedules), 7)
        
        # 驗證星期覆蓋完整
        week_days = {schedule.day_of_week for schedule in schedules}
        self.assertEqual(week_days, {0, 1, 2, 3, 4, 5, 6})


class TestCompletedTripModel(TestModels):
    """已完成班次模型測試"""
    
    def test_completed_trip_creation(self):
        """測試已完成班次記錄創建"""
        completed_trip = CompletedTrip(
            original_trip_id=123,
            date=date.today(),
            time="16:00",
            start_point="完成起點",
            end_point="完成終點",
            actual_fare=300,
            driver_id=1,
            completed_at=datetime.now()
        )
        db.session.add(completed_trip)
        db.session.commit()
        
        saved_trip = CompletedTrip.query.first()
        self.assertEqual(saved_trip.original_trip_id, 123)
        self.assertEqual(saved_trip.actual_fare, 300)
        self.assertIsNotNone(saved_trip.completed_at)


class TestModelRelationships(TestModels):
    """模型關係測試"""
    
    def setUp(self):
        super().setUp()
        # 創建測試數據
        self.customer = Customer(name="關係測試客戶", address="地址")
        self.driver = Driver(name="關係測試司機", plate_number="REL-123")
        db.session.add_all([self.customer, self.driver])
        db.session.commit()
    
    def test_trip_driver_relationship(self):
        """測試班次-司機關係"""
        trip = Trip(
            date=date.today(),
            time="12:00",
            start_point="A",
            end_point="B",
            driver_id=self.driver.id
        )
        db.session.add(trip)
        db.session.commit()
        
        # 測試關係查詢
        saved_trip = Trip.query.first()
        self.assertEqual(saved_trip.driver_id, self.driver.id)
        
        # 如果有定義外鍵關係，可以測試關聯查詢
        # self.assertEqual(saved_trip.driver.name, "關係測試司機")
    
    def test_fixed_schedule_to_trip_conversion(self):
        """測試固定班次轉換為實際班次"""
        # 創建固定班次
        schedule = FixedSchedule(
            route_number="CONV001",
            departure_time="07:00",
            day_of_week=1,
            start_point="固定A",
            end_point="固定B",
            total_fare=180
        )
        db.session.add(schedule)
        db.session.commit()
        
        # 模擬從固定班次創建實際班次
        trip = Trip(
            date=date.today(),
            time=schedule.departure_time,
            start_point=schedule.start_point,
            end_point=schedule.end_point,
            actual_fare=schedule.total_fare,
            fixed_trip_id=schedule.id,  # 關聯到固定班次
            status="待派"
        )
        db.session.add(trip)
        db.session.commit()
        
        # 驗證轉換成功
        saved_trip = Trip.query.first()
        self.assertEqual(saved_trip.fixed_trip_id, schedule.id)
        self.assertEqual(saved_trip.start_point, "固定A")
        self.assertEqual(saved_trip.actual_fare, 180)


if __name__ == '__main__':
    # 運行測試
    unittest.main(verbosity=2)