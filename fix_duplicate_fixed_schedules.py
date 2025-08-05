#!/usr/bin/env python3
"""
修復固定班次表中的重複數據
"""
import sys
sys.path.insert(0, '.')

from modules.models.base import db
from sqlalchemy import text
from modules import create_app

def find_and_fix_duplicates():
    """查找並修復固定班次表中的重複數據"""
    
    app = create_app()
    with app.app_context():
        print("🔍 開始檢查固定班次表中的重複數據...")
        
        # 查找所有重複的班次
        query = """
        SELECT 
            departure_time, start_point, end_point, category, driver_id,
            array_agg(id ORDER BY id) as duplicate_ids,
            count(*) as count
        FROM fixed_schedules 
        GROUP BY departure_time, start_point, end_point, category, driver_id
        HAVING count(*) > 1
        ORDER BY departure_time, start_point
        """
        
        result = db.session.execute(text(query))
        duplicates = result.fetchall()
        
        if not duplicates:
            print("✅ 沒有發現重複的固定班次")
            return
        
        print(f"⚠️ 發現 {len(duplicates)} 組重複班次:")
        print("=" * 80)
        
        total_to_delete = 0
        
        for dup in duplicates:
            time, start, end, category, driver, ids, count = dup
            ids_list = ids  # PostgreSQL array_agg returns a list
            
            print(f"時間: {time}, 起點: {start}, 終點: {end}")
            print(f"類別: {category}, 司機: {driver}")
            print(f"重複ID: {ids_list} (共{count}筆)")
            
            # 保留最小的ID，刪除其他的
            keep_id = min(ids_list)
            delete_ids = [id for id in ids_list if id != keep_id]
            
            print(f"✅ 保留ID: {keep_id}")
            print(f"🗑️ 刪除ID: {delete_ids}")
            print("-" * 60)
            
            total_to_delete += len(delete_ids)
        
        print(f"\\n總共需要刪除 {total_to_delete} 筆重複記錄")
        
        # 自動執行刪除（非交互模式）
        print("\\n🚀 自動執行刪除重複記錄...")
        confirm = True
        
        if confirm:
            print("\\n🚀 開始刪除重複記錄...")
            
            deleted_count = 0
            for dup in duplicates:
                ids_list = dup[5]  # duplicate_ids
                keep_id = min(ids_list)
                delete_ids = [id for id in ids_list if id != keep_id]
                
                if delete_ids:
                    # 先檢查這些ID是否被trips表引用
                    check_query = """
                    SELECT COUNT(*) FROM trips WHERE fixed_trip_id = ANY(:delete_ids)
                    """
                    
                    trips_count = db.session.execute(
                        text(check_query), 
                        {"delete_ids": delete_ids}
                    ).fetchone()[0]
                    
                    if trips_count > 0:
                        print(f"⚠️ 警告：ID {delete_ids} 被 {trips_count} 筆班次引用，跳過刪除")
                        continue
                    
                    # 執行刪除
                    delete_query = """
                    DELETE FROM fixed_schedules WHERE id = ANY(:delete_ids)
                    """
                    
                    result = db.session.execute(
                        text(delete_query), 
                        {"delete_ids": delete_ids}
                    )
                    
                    deleted_count += result.rowcount
                    print(f"✅ 刪除了 {result.rowcount} 筆記錄 (IDs: {delete_ids})")
            
            # 提交事務
            db.session.commit()
            print(f"\\n🎉 成功刪除 {deleted_count} 筆重複記錄")
            
            # 重新檢查
            print("\\n🔍 重新檢查重複情況...")
            result2 = db.session.execute(text(query))
            duplicates2 = result2.fetchall()
            
            if not duplicates2:
                print("✅ 已無重複記錄")
            else:
                print(f"⚠️ 仍有 {len(duplicates2)} 組重複記錄")
        else:
            print("❌ 取消刪除操作")

if __name__ == "__main__":
    find_and_fix_duplicates()