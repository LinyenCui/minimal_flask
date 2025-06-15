#!/usr/bin/env python3
"""
為 fixed_schedules 表新增 status 和 note 欄位
用於支援長期請假班次功能
"""

import os
import sys
from sqlalchemy import text

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from modules.models.base import db

def add_status_and_note_columns():
    """為 fixed_schedules 表新增 status 和 note 欄位"""
    app = create_app()
    with app.app_context():
        print("🔧 為 fixed_schedules 表新增欄位")
        print("="*50)
        
        try:
            # 檢查欄位是否已經存在
            check_status_query = """
            SELECT COUNT(*) 
            FROM information_schema.columns 
            WHERE table_name = 'fixed_schedules' 
            AND column_name = 'status'
            """
            
            check_note_query = """
            SELECT COUNT(*) 
            FROM information_schema.columns 
            WHERE table_name = 'fixed_schedules' 
            AND column_name = 'note'
            """
            
            status_exists = db.session.execute(text(check_status_query)).fetchone()[0] > 0
            note_exists = db.session.execute(text(check_note_query)).fetchone()[0] > 0
            
            operations = []
            
            # 新增 status 欄位
            if not status_exists:
                add_status_query = """
                ALTER TABLE fixed_schedules 
                ADD COLUMN status VARCHAR(20) DEFAULT '準備'
                """
                db.session.execute(text(add_status_query))
                operations.append("✅ 新增 status 欄位")
            else:
                operations.append("⚠️ status 欄位已存在")
            
            # 新增 note 欄位
            if not note_exists:
                add_note_query = """
                ALTER TABLE fixed_schedules 
                ADD COLUMN note TEXT
                """
                db.session.execute(text(add_note_query))
                operations.append("✅ 新增 note 欄位")
            else:
                operations.append("⚠️ note 欄位已存在")
            
            # 提交變更
            db.session.commit()
            
            print("\n".join(operations))
            
            # 驗證結果
            verify_query = """
            SELECT column_name, data_type, column_default
            FROM information_schema.columns 
            WHERE table_name = 'fixed_schedules' 
            AND column_name IN ('status', 'note')
            ORDER BY column_name
            """
            
            columns = db.session.execute(text(verify_query)).fetchall()
            
            print(f"\n📋 新增欄位驗證:")
            for col in columns:
                print(f"   {col[0]}: {col[1]} (預設值: {col[2]})")
            
            print(f"\n🎉 資料庫遷移完成！")
            return True
            
        except Exception as e:
            print(f"❌ 遷移失敗: {e}")
            db.session.rollback()
            return False

def show_sample_data():
    """顯示範例資料結構"""
    print("\n📋 使用範例:")
    print("1. status 欄位值：")
    print("   - '準備': 正常班次，匯入時設為準備狀態")
    print("   - '請假': 請假班次，匯入時設為請假狀態")
    print("2. note 欄位：")
    print("   - 存放請假原因或其他備註")
    print("   - 例如：'司機請假', '臨時調度', '車輛維修'")

if __name__ == '__main__':
    import sys
    
    print("🏗️ Fixed Schedules 表結構升級工具")
    print("="*50)
    
    if len(sys.argv) > 1 and sys.argv[1] in ['--help', '-h']:
        print("使用方法：")
        print("  python add_fixed_schedules_status_migration.py    # 執行遷移")
        print("  python add_fixed_schedules_status_migration.py -h # 顯示說明")
        show_sample_data()
        sys.exit(0)
    
    print("此工具將為 fixed_schedules 表新增以下欄位：")
    print("  - status VARCHAR(20) DEFAULT '準備'")
    print("  - note TEXT")
    print("\n⚠️ 請確保已備份資料庫！\n")
    
    confirm = input("確定要繼續嗎？(y/N): ").strip().lower()
    if confirm == 'y':
        success = add_status_and_note_columns()
        if success:
            show_sample_data()
        else:
            print("❌ 遷移失敗，請檢查錯誤訊息")
    else:
        print("已取消操作") 