"""
資料庫初始化模組
"""
import os
import logging
import psycopg2
from sqlalchemy import create_engine, inspect
from sqlalchemy.sql import text
from flask import Flask

from modules.models.base import db
from modules.models.models import Base, Person, Customer, Driver, FixedSchedule, Trip, CompletedTrip
from modules.config import DATABASE_URL

logger = logging.getLogger(__name__)

def create_database():
    """
    創建 PostgreSQL 資料庫（如果不存在）
    """
    try:
        # 創建一個臨時的Flask應用
        app = Flask(__name__)
        app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        
        # 初始化數據庫
        db.init_app(app)
        
        # 創建所有表
        with app.app_context():
            db.create_all()
            logger.info("成功創建所有數據表")
    except Exception as e:
        logger.error(f"創建數據庫時出錯: {e}")
        raise

def init_db():
    """
    初始化資料庫表結構
    """
    try:
        # 創建一個臨時的Flask應用
        app = Flask(__name__)
        app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        
        # 初始化數據庫
        db.init_app(app)
        
        # 添加基本數據
        with app.app_context():
            # 檢查是否已有數據
            if Customer.query.count() == 0:
                # 添加客戶
                customers = [
                    Customer(name="洗腎診所", address="台南市永康區大灣二街", short_name="大灣診所", category="診所"),
                    Customer(name="東洋公司", address="台南市北區中華北路一段", short_name="東洋公司", category="東洋")
                ]
                db.session.add_all(customers)
                logger.info("已添加基本客戶數據")
            
            if Driver.query.count() == 0:
                # 添加司機
                drivers = [
                    Driver(name="崔林彥", plate_number="TDE-5386", car_brand="Toyota", car_model="RAV4"),
                    Driver(name="張先生", plate_number="ABC-1234", car_brand="Toyota", car_model="Corolla")
                ]
                db.session.add_all(drivers)
                logger.info("已添加基本司機數據")
            
            # 提交更改
            db.session.commit()
            logger.info("成功初始化數據庫")
    except Exception as e:
        logger.error(f"初始化數據庫時出錯: {e}")
        raise

def initialize_custom_tables(engine):
    """
    初始化自定義表邏輯和初始數據
    """
    try:
        # 檢查是否需要填充初始數據
        inspector = inspect(engine)
        
        # 例如，確保persons表中至少有一個記錄
        if 'persons' in inspector.get_table_names():
            with engine.connect() as conn:
                # 檢查persons表是否為空
                result = conn.execute(text("SELECT COUNT(*) FROM persons"))
                count = result.scalar()
                
                if count == 0:
                    logger.info("為persons表添加初始數據...")
                    # 添加一個默認管理員記錄
                    conn.execute(text("""
                        INSERT INTO persons (name, contact, email, role, remarks)
                        VALUES ('系統管理員', '0000000000', 'admin@example.com', 'admin', '系統自動創建')
                    """))
                    conn.commit()
                    logger.info("初始數據添加成功")
        
        logger.info("自定義表初始化完成")
    except Exception as e:
        logger.error(f"初始化自定義表時出錯: {e}")
        # 不拋出異常，避免阻止應用啟動
        
# 主初始化函數
def initialize_database():
    """
    主數據庫初始化函數，執行所有需要的初始化步驟
    """
    try:
        # 首先創建數據庫
        create_database()
        
        # 初始化表結構
        init_db()
        
        logger.info("數據庫初始化完成")
        return True
    except Exception as e:
        logger.error(f"數據庫初始化失敗: {e}")
        return False 

if __name__ == "__main__":
    # 設定日誌
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    create_database()
    init_db() 