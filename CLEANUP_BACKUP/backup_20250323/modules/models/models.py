"""
資料庫模型定義
"""
from sqlalchemy import (
    Column, Integer, String, Date, Time, Text, ForeignKey, func
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from database import Base

class Person(Base):
    __tablename__ = 'persons'

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    contact = Column(String(100))
    email = Column(String(200))
    role = Column(String(50))  # 角色: driver, customer, admin 等
    remarks = Column(Text)

class Customer(Base):
    __tablename__ = 'customers'

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    address = Column(String(200), nullable=False)
    short_name = Column(String(50))
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
    start_point = Column(String(100), ForeignKey('customers.short_name'))
    via_point = Column(String(100), ForeignKey('customers.short_name'))
    end_point = Column(String(100), ForeignKey('customers.short_name'))
    base_fare = Column(Integer)
    surcharge = Column(Integer)
    total_fare = Column(Integer)
    category = Column(String(50))
    driver_id = Column(String(10))

class Trip(Base):
    __tablename__ = 'trips'

    trip_id = Column(Integer, primary_key=True)
    fixed_trip_id = Column(Integer, ForeignKey('fixed_schedules.id'))
    week_number = Column(Integer)
    date = Column(Date)
    time = Column(Time)
    start_point = Column(String(100), ForeignKey('customers.short_name'))
    via_point = Column(String(100), ForeignKey('customers.short_name'))
    end_point = Column(String(100), ForeignKey('customers.short_name'))
    meter_fare = Column(Integer)
    extra_fare = Column(Integer)
    actual_fare = Column(Integer)
    category = Column(String(50))
    driver_id = Column(Integer, ForeignKey('drivers.id'))
    status = Column(String(20))
    location = Column(String(200))  # 添加location字段
    notes = Column(Text)  # 添加notes字段
    is_fixed = Column(Integer, default=0)  # 添加is_fixed字段
    unique_code = Column(String(50))  # 添加unique_code字段
    person_id = Column(Integer, ForeignKey('persons.id'), nullable=True)  # 添加person_id字段

class CompletedTrip(Base):
    __tablename__ = 'completed_trips'

    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False)
    start_point = Column(String(100), ForeignKey('customers.short_name'))
    via_point = Column(String(100), ForeignKey('customers.short_name'))
    end_point = Column(String(100), ForeignKey('customers.short_name'))
    meter_fare = Column(Integer)
    extra_fare = Column(Integer)
    actual_fare = Column(Integer)
    category = Column(String(50))
    driver_id = Column(Integer, ForeignKey('drivers.id'))
    remarks = Column(Text)
    created_at = Column('created_at') 