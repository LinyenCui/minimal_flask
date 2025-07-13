#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
颱風假加成批量更新 - Render 資料庫
為 2025-07-07 診所類別的已完成班次加上 50 元颱風假加成
"""

import sys
import os
from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import traceback

# Render 資料庫連接資訊
RENDER_DATABASE_URL = "postgresql://dispatch_system_db_user:rfmy454LJ5JTtPZjsq60KzzhFf0jsMlP@dpg-cvhb8fdrie7s73emf81g-a.singapore-postgres.render.com/dispatch_system_db"

def add_typhoon_allowance():
    """為 7/7 診所已完成班次加上颱風假加成"""
    try:
        print("🌪️  颱風假加成批量更新")
        print("=" * 60)
        print("🔗 正在連接到 Render 資料庫...")
        
        engine = create_engine(RENDER_DATABASE_URL, echo=False)
        Session = sessionmaker(bind=engine)
        session = Session()
        print("✅ 成功連接到 Render 資料庫")
        
        # 目標日期
        target_date = "2025-07-07"
        print(f"📅 目標日期: {target_date}")
        
        # 1. 先查詢符合條件的班次
        query_sql = """
        SELECT 
            id, start_point, end_point, category, 
            meter_fare, extra_fare, 
            COALESCE(meter_fare, 0) + COALESCE(extra_fare, 0) as current_total,
            driver_id, remarks
        FROM completed_trips 
        WHERE date = :target_date 
        AND category = '診所'
        ORDER BY id
        """
        
        results = session.execute(text(query_sql), {"target_date": target_date}).fetchall()
        
        if not results:
            print(f"❌ 沒有找到 {target_date} 診所類別的已完成班次")
            return
        
        print(f"🔍 找到 {len(results)} 筆符合條件的班次：")
        print("-" * 60)
        
        total_original = 0
        total_new = 0
        
        for row in results:
            id, start_point, end_point, category = row[:4]
            meter_fare, extra_fare, current_total = row[4:7]
            driver_id, remarks = row[7:9]
            
            current_extra = extra_fare if extra_fare is not None else 0
            new_extra = current_extra + 50
            new_total = (meter_fare if meter_fare else 0) + new_extra
            
            print(f"#{id:3d} | {start_point:10s} → {end_point:10s} | 司機:{driver_id}")
            print(f"       加成: {current_extra:3d} → {new_extra:3d} (+50) | 總計: {current_total} → {new_total}")
            
            total_original += current_total if current_total else 0
            total_new += new_total
        
        print("-" * 60)
        print(f"📊 總計影響: {len(results)} 筆班次")
        print(f"💰 總金額變化: {total_original} → {total_new} (+{total_new - total_original})")
        
        # 2. 確認是否執行更新
        print("\n⚠️  即將執行批量更新，這將會：")
        print("   1. 每筆班次的 extra_fare 增加 50 元")
        print("   2. 設定 modification_reason 為 '颱風假加成'")
        print("   3. 記錄修改時間和修改者")
        
        confirm = input("\n請輸入 'YES' 確認執行批量更新: ").strip()
        
        if confirm != 'YES':
            print("❌ 取消更新操作")
            return
        
        # 3. 執行批量更新
        print("\n🔄 開始執行批量更新...")
        
        update_sql = """
        UPDATE completed_trips 
        SET 
            extra_fare = COALESCE(extra_fare, 0) + 50,
            modification_reason = CASE 
                WHEN modification_reason IS NULL OR modification_reason = '' 
                THEN '颱風假加成'
                ELSE modification_reason || '; 颱風假加成'
            END,
            modified_by = 'System',
            modification_time = CURRENT_TIMESTAMP
        WHERE date = :target_date 
        AND category = '診所'
        """
        
        result = session.execute(text(update_sql), {"target_date": target_date})
        updated_count = result.rowcount
        
        # 提交事務
        session.commit()
        
        print(f"✅ 成功更新 {updated_count} 筆班次")
        
        # 4. 驗證更新結果
        print("\n🔍 驗證更新結果...")
        
        verify_sql = """
        SELECT 
            id, start_point, end_point,
            meter_fare, extra_fare, 
            COALESCE(meter_fare, 0) + COALESCE(extra_fare, 0) as total_fare,
            modification_reason, modification_time
        FROM completed_trips 
        WHERE date = :target_date 
        AND category = '診所'
        AND modification_reason LIKE '%颱風假加成%'
        ORDER BY id
        LIMIT 5
        """
        
        verify_results = session.execute(text(verify_sql), {"target_date": target_date}).fetchall()
        
        print("前 5 筆更新結果：")
        print("-" * 60)
        
        for row in verify_results:
            id, start_point, end_point = row[:3]
            meter_fare, extra_fare, total_fare = row[3:6]
            modification_reason, modification_time = row[6:8]
            
            print(f"#{id:3d} | {start_point:10s} → {end_point:10s}")
            print(f"       錶價:{meter_fare} + 加成:{extra_fare} = 總計:{total_fare}")
            print(f"       修改原因: {modification_reason}")
            print(f"       修改時間: {modification_time}")
            print("-" * 60)
        
        print(f"\n🎉 颱風假加成批量更新完成！")
        print(f"   📊 更新班次數: {updated_count}")
        print(f"   💰 總加成金額: {updated_count * 50} 元")
        print(f"   📝 修改原因: 颱風假加成")
        
    except Exception as e:
        if 'session' in locals():
            session.rollback()
        print(f"❌ 更新失敗: {str(e)}")
        print(traceback.format_exc())
    
    finally:
        if 'session' in locals():
            session.close()

def main():
    """主函數"""
    add_typhoon_allowance()

if __name__ == "__main__":
    main() 