#!/usr/bin/env python3
"""
資料搬移後序列修復工具
用於在TRUNCATE + 匯入資料後，自動修復序列
"""

import os
import sys
from sqlalchemy import text

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from modules.models.base import db

def fix_completed_trips_sequence():
    """修復completed_trips表的序列"""
    app = create_app()
    with app.app_context():
        print("🔧 自動修復completed_trips序列")
        print("="*40)
        
        try:
            # 獲取當前最大ID
            max_id_query = "SELECT COALESCE(MAX(id), 0) FROM completed_trips;"
            max_result = db.session.execute(text(max_id_query)).fetchone()
            max_id = max_result[0] if max_result else 0
            
            print(f"📊 當前最大ID: {max_id}")
            
            if max_id == 0:
                print("⚠️ 資料表為空，將序列設為1")
                next_val = 1
            else:
                next_val = max_id + 1
                print(f"🎯 將序列設為: {next_val}")
            
            # 修復序列
            fix_query = f"SELECT setval('completed_trips_id_seq', {next_val}, false);"
            db.session.execute(text(fix_query))
            db.session.commit()
            
            # 驗證結果
            verify_query = "SELECT last_value FROM completed_trips_id_seq;"
            verify_result = db.session.execute(text(verify_query)).fetchone()
            current_seq = verify_result[0] if verify_result else "未知"
            
            print(f"✅ 序列修復完成")
            print(f"✅ 當前序列值: {current_seq}")
            print("✅ 排程功能現在可以正常插入新記錄了")
            
        except Exception as e:
            print(f"❌ 修復失敗: {e}")
            db.session.rollback()
            return False
        
        return True

def fix_all_sequences():
    """修復所有資料表的序列（擴展功能）"""
    app = create_app()
    with app.app_context():
        print("🔧 檢查所有資料表序列")
        print("="*40)
        
        # 可以擴展到其他表
        tables_with_sequences = [
            ('completed_trips', 'completed_trips_id_seq'),
            ('trips', 'trips_trip_id_seq'),
            # 可以添加更多表...
        ]
        
        for table_name, seq_name in tables_with_sequences:
            try:
                print(f"\n🔍 檢查 {table_name} 表...")
                
                # 獲取最大ID
                max_id_query = f"SELECT COALESCE(MAX(id), 0) FROM {table_name};"
                if table_name == 'trips':
                    max_id_query = f"SELECT COALESCE(MAX(trip_id), 0) FROM {table_name};"
                
                max_result = db.session.execute(text(max_id_query)).fetchone()
                max_id = max_result[0] if max_result else 0
                
                # 獲取序列值
                seq_query = f"SELECT last_value FROM {seq_name};"
                seq_result = db.session.execute(text(seq_query)).fetchone()
                current_seq = seq_result[0] if seq_result else 0
                
                print(f"   最大ID: {max_id}, 序列值: {current_seq}")
                
                if current_seq <= max_id:
                    next_val = max_id + 1
                    fix_query = f"SELECT setval('{seq_name}', {next_val}, false);"
                    db.session.execute(text(fix_query))
                    print(f"   ✅ 已修復，設為: {next_val}")
                else:
                    print(f"   ✅ 序列正常")
                    
            except Exception as e:
                print(f"   ❌ 檢查失敗: {e}")
        
        db.session.commit()
        print("\n🎉 所有序列檢查完成")

if __name__ == '__main__':
    print("請選擇操作：")
    print("1. 只修復 completed_trips 序列")
    print("2. 檢查並修復所有序列")
    
    choice = input("\n請輸入選項 (1/2): ").strip()
    
    if choice == '1':
        fix_completed_trips_sequence()
    elif choice == '2':
        fix_all_sequences()
    else:
        print("無效選項") 