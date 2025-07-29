#!/usr/bin/env python3
"""
直接在現有應用框架內測試資料庫查詢
"""
import sys
import os
sys.path.append(os.path.dirname(__file__))

from app import create_app
from modules.models.base import db
from sqlalchemy.sql import text
import logging

# 設定日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_fixed_schedule_query():
    """直接測試固定班次查詢"""
    app = create_app()
    
    with app.app_context():
        try:
            # 1. 測試查詢所有固定班次ID
            logger.info("🔍 Step 1: 查詢所有固定班次ID...")
            all_ids_query = "SELECT id FROM fixed_schedules ORDER BY id"
            all_ids = db.session.execute(text(all_ids_query)).fetchall()
            
            id_list = [row[0] for row in all_ids]
            logger.info(f"📊 現有固定班次ID: {id_list}")
            logger.info(f"📊 總數: {len(id_list)}")
            
            if 17 in id_list:
                logger.info("✅ ID=17 確實存在於資料庫中")
            else:
                logger.warning("❌ ID=17 不存在於資料庫中")
                logger.info(f"🔍 最接近的ID: {[i for i in id_list if abs(i-17) <= 2]}")
            
            # 2. 使用與 fixed_schedule_leave_handler.py 完全相同的查詢
            logger.info("\n🔍 Step 2: 使用完全相同的查詢語句...")
            exact_query = """
            SELECT 
                fs.id, 
                fs.route_number, 
                fs.departure_time, 
                fs.start_point,
                fs.end_point,
                fs.category,
                fs.status,
                fs.note,
                fs.base_fare,
                fs.surcharge,
                fs.total_fare
            FROM 
                fixed_schedules fs
            WHERE 
                fs.id = :fixed_schedule_id
            """
            
            schedule = db.session.execute(text(exact_query), {"fixed_schedule_id": 17}).fetchone()
            
            if schedule:
                logger.info("✅ 使用相同查詢找到ID=17:")
                logger.info(f"   ID: {schedule[0]}")
                logger.info(f"   Route: {schedule[1]}")
                logger.info(f"   Time: {schedule[2]}")
                logger.info(f"   Start: {schedule[3]}")
                logger.info(f"   End: {schedule[4]}")
                logger.info(f"   Status: {schedule[6]}")
                logger.info(f"   Note: {schedule[7]}")
            else:
                logger.error("❌ 使用相同查詢找不到ID=17!")
            
            # 3. 測試 fixed_schedule_query_handler.py 的查詢
            logger.info("\n🔍 Step 3: 測試查詢按鈕生成的邏輯...")
            # 假設查詢固定班次是根據某個客戶名稱
            # 先找出ID=17關聯的客戶名稱
            if 17 in id_list:
                customer_query = """
                SELECT start_point, via_point, end_point 
                FROM fixed_schedules 
                WHERE id = 17
                """
                customer_data = db.session.execute(text(customer_query)).fetchone()
                
                if customer_data:
                    logger.info(f"   ID=17的路線: {customer_data[0]} → {customer_data[1] or '(無途經)'} → {customer_data[2]}")
                    
                    # 嘗試用起點名稱查詢
                    if customer_data[0]:
                        customer_search_query = """
                        SELECT 
                            fs.id, 
                            fs.route_number, 
                            fs.departure_time, 
                            fs.start_point,
                            fs.via_point,
                            fs.end_point,
                            fs.base_fare,
                            fs.surcharge,
                            fs.total_fare,
                            fs.category,
                            fs.driver_id,
                            fs.direction,
                            fs.status,
                            fs.note,
                            fs.modified_by,
                            fs.modification_time
                        FROM 
                            fixed_schedules fs
                        WHERE 
                            fs.start_point = :customer_name 
                            OR fs.via_point = :customer_name 
                            OR fs.end_point = :customer_name
                        ORDER BY fs.departure_time
                        """
                        
                        search_results = db.session.execute(text(customer_search_query), {"customer_name": customer_data[0]}).fetchall()
                        logger.info(f"   用起點'{customer_data[0]}'搜尋到 {len(search_results)} 個班次")
                        
                        found_17 = any(row[0] == 17 for row in search_results)
                        logger.info(f"   搜尋結果中包含ID=17: {'✅ 是' if found_17 else '❌ 否'}")
            
        except Exception as e:
            logger.error(f"🚨 測試過程出錯: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    print("🚀 開始直接測試資料庫查詢...")
    test_fixed_schedule_query()
    print("\n🎯 測試完成!")