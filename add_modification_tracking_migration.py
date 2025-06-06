#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
資料庫遷移：添加修改追蹤欄位
為trips和completed_trips表添加修改追蹤功能所需的欄位
"""

import sqlite3
import sys
from datetime import datetime

def check_column_exists(cursor, table_name, column_name):
    """檢查欄位是否已存在"""
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in cursor.fetchall()]
    return column_name in columns

def add_modification_tracking_fields():
    """添加修改追蹤欄位到trips和completed_trips表"""
    
    # 連接到資料庫
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    
    try:
        print("🔍 檢查資料庫當前狀態...")
        
        # 檢查completed_trips表
        print("\n📋 檢查completed_trips表...")
        completed_trips_needs_update = False
        
        for field in ['modified_by', 'modification_reason', 'modification_time']:
            if not check_column_exists(cursor, 'completed_trips', field):
                print(f"  ❌ 缺少欄位: {field}")
                completed_trips_needs_update = True
            else:
                print(f"  ✅ 已存在欄位: {field}")
        
        # 檢查trips表  
        print("\n📋 檢查trips表...")
        trips_needs_update = False
        
        for field in ['modified_by', 'modification_reason', 'modification_time']:
            if not check_column_exists(cursor, 'trips', field):
                print(f"  ❌ 缺少欄位: {field}")
                trips_needs_update = True
            else:
                print(f"  ✅ 已存在欄位: {field}")
        
        # 如果都已存在，無需更新
        if not completed_trips_needs_update and not trips_needs_update:
            print("\n✅ 所有欄位都已存在，無需遷移！")
            return
        
        print(f"\n🔧 開始資料庫遷移...")
        
        # 為completed_trips表添加欄位
        if completed_trips_needs_update:
            print("\n📝 更新completed_trips表...")
            
            if not check_column_exists(cursor, 'completed_trips', 'modified_by'):
                cursor.execute("""
                    ALTER TABLE completed_trips 
                    ADD COLUMN modified_by TEXT
                """)
                print("  ✅ 添加modified_by欄位")
            
            if not check_column_exists(cursor, 'completed_trips', 'modification_reason'):
                cursor.execute("""
                    ALTER TABLE completed_trips 
                    ADD COLUMN modification_reason TEXT
                """)
                print("  ✅ 添加modification_reason欄位")
            
            if not check_column_exists(cursor, 'completed_trips', 'modification_time'):
                cursor.execute("""
                    ALTER TABLE completed_trips 
                    ADD COLUMN modification_time DATETIME
                """)
                print("  ✅ 添加modification_time欄位")
        
        # 為trips表添加欄位
        if trips_needs_update:
            print("\n📝 更新trips表...")
            
            if not check_column_exists(cursor, 'trips', 'modified_by'):
                cursor.execute("""
                    ALTER TABLE trips 
                    ADD COLUMN modified_by TEXT
                """)
                print("  ✅ 添加modified_by欄位")
            
            if not check_column_exists(cursor, 'trips', 'modification_reason'):
                cursor.execute("""
                    ALTER TABLE trips 
                    ADD COLUMN modification_reason TEXT
                """)
                print("  ✅ 添加modification_reason欄位")
            
            if not check_column_exists(cursor, 'trips', 'modification_time'):
                cursor.execute("""
                    ALTER TABLE trips 
                    ADD COLUMN modification_time DATETIME
                """)
                print("  ✅ 添加modification_time欄位")
        
        # 提交變更
        conn.commit()
        print(f"\n🎉 資料庫遷移完成！")
        
        # 驗證結果
        print("\n🔍 驗證遷移結果...")
        
        # 驗證completed_trips
        cursor.execute("PRAGMA table_info(completed_trips)")
        completed_trips_columns = [row[1] for row in cursor.fetchall()]
        print(f"\n📋 completed_trips表欄位: {len(completed_trips_columns)}個")
        for col in ['modified_by', 'modification_reason', 'modification_time']:
            status = "✅" if col in completed_trips_columns else "❌"
            print(f"  {status} {col}")
        
        # 驗證trips
        cursor.execute("PRAGMA table_info(trips)")
        trips_columns = [row[1] for row in cursor.fetchall()]
        print(f"\n📋 trips表欄位: {len(trips_columns)}個")
        for col in ['modified_by', 'modification_reason', 'modification_time']:
            status = "✅" if col in trips_columns else "❌"
            print(f"  {status} {col}")
        
        print(f"\n✅ 遷移成功完成！現在可以使用修改追蹤功能了。")
        
    except Exception as e:
        print(f"\n❌ 遷移失敗: {str(e)}")
        conn.rollback()
        return False
    finally:
        conn.close()
    
    return True

def main():
    """主函數"""
    print("🚀 資料庫修改追蹤欄位遷移工具")
    print("=" * 50)
    
    # 確認執行
    response = input("\n❓ 確定要執行資料庫遷移嗎？(y/N): ")
    if response.lower() != 'y':
        print("❌ 取消遷移")
        return
    
    # 執行遷移
    success = add_modification_tracking_fields()
    
    if success:
        print("\n🎯 遷移說明:")
        print("• modified_by: 記錄修改操作的用戶ID")
        print("• modification_reason: 記錄修改原因")
        print("• modification_time: 記錄修改時間")
        print("\n💡 這些欄位將支援AI車資修改和審計追蹤功能")
    else:
        print("\n❌ 請檢查錯誤信息並重試")
        sys.exit(1)

if __name__ == "__main__":
    main() 