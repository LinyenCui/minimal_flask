#!/usr/bin/env python3
"""
記憶體洩露修復腳本
清理APScheduler中的過期任務並優化任務管理
"""
import sys
import os
sys.path.insert(0, os.path.abspath('.'))

from modules import create_app
from datetime import datetime, timedelta
from modules.utils.taiwan_time import get_taiwan_time
from flask_apscheduler import APScheduler

def fix_scheduler_memory_leak():
    """修復排程器記憶體洩露"""
    app = create_app()
    
    # 初始化排程器 (模擬app.py中的邏輯)
    scheduler = APScheduler()
    app.scheduler = scheduler
    
    with app.app_context():
        scheduler.init_app(app)
        scheduler.start()
        
        scheduler = app.scheduler
        
        print("🔍 檢查排程器狀態...")
        
        # 獲取所有任務
        jobs = scheduler.get_jobs()
        print(f"📊 目前任務總數: {len(jobs)}")
        
        now = get_taiwan_time()
        removed_count = 0
        
        # 清理過期的單次任務
        for job in jobs:
            # 檢查是否為班次更新任務
            if job.id.startswith('update_trip_'):
                # 檢查任務是否已過期
                if hasattr(job, 'next_run_time') and job.next_run_time:
                    if job.next_run_time < now:
                        print(f"🗑️  移除過期任務: {job.id} (執行時間: {job.next_run_time})")
                        scheduler.remove_job(job.id)
                        removed_count += 1
                else:
                    # 沒有下次執行時間的任務也應該清理
                    print(f"🗑️  移除無效任務: {job.id}")
                    scheduler.remove_job(job.id)
                    removed_count += 1
        
        print(f"✅ 清理完成！移除了 {removed_count} 個過期任務")
        print(f"📊 剩餘任務數: {len(scheduler.get_jobs())}")
        
        # 顯示剩餘的重要任務
        remaining_jobs = scheduler.get_jobs()
        print("\n📋 剩餘重要任務:")
        for job in remaining_jobs:
            if not job.id.startswith('update_trip_'):
                print(f"  - {job.id}: {job.next_run_time}")

if __name__ == '__main__':
    fix_scheduler_memory_leak()