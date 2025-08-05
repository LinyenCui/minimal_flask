#!/usr/bin/env python3
"""
修復湖美街12巷重複班次問題
1. 將使用重複固定班次ID的trips更新為使用保留的ID
2. 刪除重複的固定班次記錄
"""
import sys
sys.path.insert(0, '.')

from modules.models.base import db
from sqlalchemy import text
from modules import create_app

def fix_duplicate_references():
    """修復重複引用問題"""
    
    app = create_app()
    with app.app_context():
        print("🔧 開始修復湖美街12巷重複班次問題...")
        
        # 定義重複的固定班次ID和要保留的ID
        keep_id = 83
        duplicate_ids = [85, 86]
        
        print(f"✅ 保留固定班次ID: {keep_id}")
        print(f"🔄 將重複ID {duplicate_ids} 的引用更新為 {keep_id}")
        
        # 步驟1：更新trips表中的引用
        print("\\n步驟1：更新trips表中的固定班次引用...")
        
        for dup_id in duplicate_ids:
            # 檢查當前使用此ID的班次數量
            count_query = "SELECT COUNT(*) FROM trips WHERE fixed_trip_id = :dup_id"
            current_count = db.session.execute(
                text(count_query), {"dup_id": dup_id}
            ).fetchone()[0]
            
            if current_count > 0:
                print(f"🔄 更新 {current_count} 筆使用固定班次ID {dup_id} 的班次...")
                
                # 更新引用
                update_query = """
                UPDATE trips 
                SET fixed_trip_id = :keep_id 
                WHERE fixed_trip_id = :dup_id
                """
                
                result = db.session.execute(text(update_query), {
                    "keep_id": keep_id,
                    "dup_id": dup_id
                })
                
                print(f"✅ 成功更新 {result.rowcount} 筆班次記錄")
            else:
                print(f"ℹ️ 固定班次ID {dup_id} 沒有被任何班次使用")
        
        # 步驟2：檢查是否還有其他表引用這些ID
        print("\\n步驟2：檢查其他表的引用...")
        
        # 檢查是否有其他表可能引用fixed_schedules.id
        tables_to_check = [
            "completed_trips"  # 已完成班次表可能也有fixed_trip_id
        ]
        
        for table in tables_to_check:
            try:
                check_query = f"SELECT COUNT(*) FROM {table} WHERE fixed_trip_id = ANY(:dup_ids)"
                count = db.session.execute(text(check_query), {
                    "dup_ids": duplicate_ids
                }).fetchone()[0]
                
                if count > 0:
                    print(f"⚠️ {table} 表中有 {count} 筆記錄引用重複ID")
                    
                    # 更新引用
                    update_query = f"""
                    UPDATE {table}
                    SET fixed_trip_id = :keep_id 
                    WHERE fixed_trip_id = ANY(:dup_ids)
                    """
                    
                    result = db.session.execute(text(update_query), {
                        "keep_id": keep_id,
                        "dup_ids": duplicate_ids
                    })
                    
                    print(f"✅ 成功更新 {table} 表中的 {result.rowcount} 筆記錄")
                else:
                    print(f"✅ {table} 表中沒有引用重複ID")
                    
            except Exception as e:
                print(f"ℹ️ 檢查 {table} 表時出錯（可能不存在該欄位）: {e}")
        
        # 步驟3：刪除重複的固定班次記錄
        print("\\n步驟3：刪除重複的固定班次記錄...")
        
        # 再次檢查是否還有引用
        final_check_query = "SELECT COUNT(*) FROM trips WHERE fixed_trip_id = ANY(:dup_ids)"
        final_count = db.session.execute(text(final_check_query), {
            "dup_ids": duplicate_ids
        }).fetchone()[0]
        
        if final_count == 0:
            # 刪除重複記錄
            delete_query = "DELETE FROM fixed_schedules WHERE id = ANY(:dup_ids)"
            result = db.session.execute(text(delete_query), {
                "dup_ids": duplicate_ids
            })
            
            print(f"✅ 成功刪除 {result.rowcount} 筆重複的固定班次記錄")
        else:
            print(f"⚠️ 仍有 {final_count} 筆班次引用重複ID，暫不刪除固定班次記錄")
        
        # 提交所有更改
        db.session.commit()
        print("\\n💾 所有更改已提交到數據庫")
        
        # 步驟4：驗證修復結果
        print("\\n步驟4：驗證修復結果...")
        
        # 檢查今天的湖美街12巷班次
        verify_query = """
        SELECT trip_id, date, time, start_point, end_point, fixed_trip_id
        FROM trips 
        WHERE date = '2025-08-04' AND start_point LIKE '%湖美街12巷%'
        ORDER BY time
        """
        
        result = db.session.execute(text(verify_query))
        trips = result.fetchall()
        
        print(f"\\n今天的湖美街12巷班次:")
        for trip in trips:
            print(f"班次ID: {trip[0]}, 時間: {trip[2]}, 固定班次ID: {trip[5]}")
        
        # 檢查重複情況
        id_counts = {}
        for trip in trips:
            fixed_id = trip[5]
            id_counts[fixed_id] = id_counts.get(fixed_id, 0) + 1
        
        duplicate_count = sum(1 for count in id_counts.values() if count > 1)
        
        if duplicate_count == 0:
            print("\\n🎉 修復成功！不再有重複的湖美街12巷班次")
        else:
            print(f"\\n⚠️ 仍有重複班次，需要進一步檢查")
            for fixed_id, count in id_counts.items():
                if count > 1:
                    print(f"固定班次ID {fixed_id}: {count} 筆班次")

if __name__ == "__main__":
    fix_duplicate_references()