"""
班次排程任務模塊

這個模塊包含所有與班次狀態自動更新相關的任務
"""
import logging
from datetime import datetime, timedelta
from sqlalchemy.sql import text

from modules.models.base import db
from modules.models.models import Trip

# 建立日誌記錄器
logger = logging.getLogger(__name__)

def schedule_all_trip_updates(app):
    """
    安排所有未來班次的自動更新任務
    
    Args:
        app: Flask應用實例
    """
    with app.app_context():
        try:
            # 獲取當前日期和時間
            now = datetime.now()
            
            # 查詢所有狀態為"準備"且時間在未來的班次
            query = """
            SELECT 
                t.trip_id, 
                t.date, 
                t.time
            FROM 
                trips t
            WHERE 
                t.status = '準備'
                AND (t.date > :current_date OR (t.date = :current_date AND t.time > :current_time))
            ORDER BY
                t.date, t.time
            """
            
            future_trips = db.session.execute(
                text(query), 
                {
                    "current_date": now.date(),
                    "current_time": now.time()
                }
            ).fetchall()
            
            # 為每個未來班次安排更新任務
            from app import scheduler
            for trip in future_trips:
                trip_id = trip[0]
                trip_date = trip[1]
                trip_time = trip[2]
                
                # 計算執行時間（班次時間後5分鐘）
                execution_time = datetime.combine(trip_date, trip_time) + timedelta(minutes=5)
                
                # 如果執行時間已經過去，跳過
                if execution_time < now:
                    continue
                
                # 創建任務ID
                job_id = f"update_trip_{trip_id}"
                
                # 檢查任務是否已經存在
                existing_job = scheduler.get_job(job_id)
                if existing_job:
                    continue
                
                # 安排任務
                scheduler.add_job(
                    id=job_id,
                    func=update_single_trip,
                    args=[app, trip_id],
                    trigger='date',
                    run_date=execution_time
                )
                
                logger.info(f"已安排班次 #{trip_id} 的自動更新任務，執行時間：{execution_time}")
            
            return f"已安排 {len(future_trips)} 個班次的自動更新任務"
        except Exception as e:
            logger.error(f"安排班次更新任務時出錯: {e}")
            return f"安排班次更新任務時出錯: {e}"

def update_single_trip(app, trip_id):
    """
    更新單個班次的狀態（從準備變為完成）
    
    Args:
        app: Flask應用實例
        trip_id: 班次ID
    """
    with app.app_context():
        try:
            # 查詢指定的班次
            trip = Trip.query.get(trip_id)
            
            # 如果班次存在且狀態為"準備"，將其更新為"完成"
            if trip and trip.status == "準備":
                trip.status = "完成"
                db.session.commit()
                logger.info(f"班次 #{trip_id} 已自動更新為完成狀態")
            else:
                logger.info(f"班次 #{trip_id} 無需更新（可能不存在或狀態不是準備）")
                
        except Exception as e:
            logger.error(f"更新班次 #{trip_id} 時出錯: {e}")
            db.session.rollback()

def update_completed_trips():
    """
    將所有已過期的"準備"狀態班次更新為"完成"狀態
    """
    try:
        # 獲取當前日期和時間
        now = datetime.now()
        
        # 查詢所有已過期的準備狀態班次
        query = """
        UPDATE 
            trips
        SET 
            status = '完成'
        WHERE 
            status = '準備'
            AND (date < :current_date OR (date = :current_date AND time < :current_time))
        RETURNING trip_id
        """
        
        result = db.session.execute(
            text(query), 
            {
                "current_date": now.date(),
                "current_time": now.time()
            }
        )
        
        # 獲取更新的班次ID
        updated_trips = [row[0] for row in result.fetchall()]
        db.session.commit()
        
        if updated_trips:
            logger.info(f"已自動將 {len(updated_trips)} 個過期班次更新為完成狀態")
            return f"已自動將 {len(updated_trips)} 個過期班次更新為完成狀態"
        else:
            return "沒有需要更新的過期班次"
            
    except Exception as e:
        logger.error(f"更新過期班次時出錯: {e}")
        db.session.rollback()
        return f"更新過期班次時出錯: {e}"

def initialize_unique_codes():
    """
    為沒有唯一識別碼的班次生成新的識別碼
    """
    try:
        # 查詢所有沒有唯一識別碼的班次
        query = """
        SELECT 
            trip_id
        FROM 
            trips
        WHERE 
            unique_code IS NULL OR unique_code = ''
        """
        
        trips_without_code = db.session.execute(text(query)).fetchall()
        
        # 如果沒有需要更新的班次，直接返回
        if not trips_without_code:
            return "所有班次都已有唯一識別碼"
        
        # 為每個沒有識別碼的班次生成新的識別碼
        for trip_row in trips_without_code:
            trip_id = trip_row[0]
            
            # 生成唯一識別碼（使用班次ID和時間戳）
            import time
            import hashlib
            
            timestamp = int(time.time())
            code_string = f"{trip_id}_{timestamp}"
            hashed = hashlib.md5(code_string.encode()).hexdigest()
            unique_code = hashed[:8]  # 取前8位作為唯一識別碼
            
            # 更新班次的唯一識別碼
            update_query = """
            UPDATE 
                trips
            SET 
                unique_code = :unique_code
            WHERE 
                trip_id = :trip_id
            """
            
            db.session.execute(
                text(update_query), 
                {
                    "unique_code": unique_code,
                    "trip_id": trip_id
                }
            )
        
        # 提交所有更新
        db.session.commit()
        
        return f"已為 {len(trips_without_code)} 個班次生成唯一識別碼"
            
    except Exception as e:
        logger.error(f"生成唯一識別碼時出錯: {e}")
        db.session.rollback()
        return f"生成唯一識別碼時出錯: {e}"

def init_scheduler(app):
    """
    初始化排程器，設置所有定期任務
    
    Args:
        app: Flask應用實例
    """
    try:
        from app import scheduler
        # 嘗試初始化調度器
        scheduler.init_app(app)
        
        # 添加每日更新任務，使用 replace_existing=True
        scheduler.add_job(
            id='schedule_daily_updates',
            func=schedule_all_trip_updates,
            args=[app],
            trigger='cron',
            hour=0,
            minute=0,
            replace_existing=True  # 如果任務已存在，則替換它
        )
        logger.info("已添加/更新每日更新任務")
        
        # 添加每小時更新已完成班次的任務
        scheduler.add_job(
            id='hourly_update_completed',
            func=update_completed_trips,
            trigger='cron',
            hour='*',
            minute=0,
            replace_existing=True
        )
        logger.info("已添加/更新每小時更新已完成班次任務")
        
        # 添加每小時更新唯一識別碼的任務
        scheduler.add_job(
            id='hourly_update_unique_codes',
            func=initialize_unique_codes,
            trigger='cron',
            hour='*',
            minute=30,
            replace_existing=True
        )
        logger.info("已添加/更新每小時更新唯一識別碼任務")
        
        # 啟動調度器
        scheduler.start()
        logger.info("調度器已成功啟動")
    except Exception as e:
        logger.error(f"啟動調度器時出錯: {e}")
        # 繼續執行，不要因為調度器錯誤而停止應用程序
    
    # 應用啟動時，處理所有已過期的班次
    with app.app_context():
        update_completed_trips()
    
    # 應用啟動時，初始化所有沒有唯一識別碼的班次
    with app.app_context():
        try:
            logger.info("正在初始化班次唯一識別碼...")
            result = initialize_unique_codes()
            logger.info(result)
        except Exception as e:
            logger.error(f"初始化班次唯一識別碼時出錯: {e}")
    
    # 應用啟動時，安排所有未來班次的自動更新任務
    with app.app_context():
        schedule_all_trip_updates(app) 