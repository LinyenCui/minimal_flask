from sqlalchemy import (
    Column, Integer, String, Date, Time, Text, ForeignKey, func
)
from sqlalchemy.orm import relationship, declarative_base
from flask_sqlalchemy import SQLAlchemy

Base = declarative_base()

# 創建SQLAlchemy實例，但不立即初始化
db = SQLAlchemy()

class Customer(Base):
    __tablename__ = 'customers'

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    address = Column(String(200), nullable=False)
    short_name = Column(String(50), unique=True)  # 設為唯一索引，避免外鍵錯誤
    category = Column(String(50))
    remarks = Column(Text)

class Driver(Base):
    __tablename__ = 'drivers'

    id = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False)
    plate_number = Column(String(20))
    car_brand = Column(String(50))
    car_model = Column(String(50))

class FixedSchedule(Base):
    __tablename__ = 'fixed_schedules'

    id = Column(Integer, primary_key=True)
    route_number = Column(String(10))
    departure_time = Column(Time, nullable=False)
    start_point = Column(Integer, ForeignKey('customers.id'))  # 改用 ID 避免 `short_name` 問題
    via_point = Column(Integer, ForeignKey('customers.id'), nullable=True)  
    end_point = Column(Integer, ForeignKey('customers.id'))
    base_fare = Column(Integer)
    surcharge = Column(Integer)
    total_fare = Column(Integer)  # 讓應用層計算
    category = Column(String(50))
    driver_id = Column(Integer, ForeignKey('drivers.id'))

class Trip(Base):
    __tablename__ = 'trips'

    trip_id = Column(Integer, primary_key=True, autoincrement=True)
    fixed_trip_id = Column(Integer, ForeignKey('fixed_schedules.id'), nullable=True)
    week_number = Column(Integer)
    date = Column(Date)
    time = Column(Time)
    start_point = Column(Integer, ForeignKey('customers.id'))
    via_point = Column(Integer, ForeignKey('customers.id'), nullable=True)
    end_point = Column(Integer, ForeignKey('customers.id'))
    meter_fare = Column(Integer)
    extra_fare = Column(Integer)
    actual_fare = Column(Integer)  # 讓應用層計算
    category = Column(String(50))
    driver_id = Column(Integer, ForeignKey('drivers.id'))
    status = Column(String(20))

class CompletedTrip(Base):
    __tablename__ = 'completed_trips'

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False)
    start_point = Column(Integer, ForeignKey('customers.id'))
    via_point = Column(Integer, ForeignKey('customers.id'), nullable=True)
    end_point = Column(Integer, ForeignKey('customers.id'))
    meter_fare = Column(Integer)
    extra_fare = Column(Integer)
    actual_fare = Column(Integer)  # 讓應用層計算
    category = Column(String(50))
    driver_id = Column(Integer, ForeignKey('drivers.id'))
    remarks = Column(Text)
    created_at = Column(Date, default=func.now())  # 記錄完整時間戳記
