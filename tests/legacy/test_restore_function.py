#!/usr/bin/env python3
"""
測試固定班次恢復功能
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from modules import create_app
from modules.handlers.fixed_schedule_leave_handler import process_fixed_schedule_restore

def test_restore_functionality():
    """測試固定班次恢復功能"""
    app = create_app()
    
    with app.app_context():
        print("🧪 測試固定班次恢復功能")
        print("=" * 50)
        
        test_user_id = "test_user_restore"
        
        # 測試恢復ID=17的班次（目前是請假狀態）
        schedule_id = 17
        
        print(f"1️⃣ 恢復班次 #{schedule_id}")
        print("-" * 30)
        
        try:
            result = process_fixed_schedule_restore(schedule_id, test_user_id)
            
            print("📊 處理結果:")
            print(result)
            
            if "已恢復為準備狀態" in result:
                print("\n✅ 恢復功能正常！")
                
                # 驗證資料庫狀態
                print(f"\n2️⃣ 驗證資料庫狀態")
                print("-" * 30)
                
                from modules.models.base import db
                from sqlalchemy.sql import text
                
                query = """
                SELECT id, status, note, surcharge 
                FROM fixed_schedules 
                WHERE id = :schedule_id
                """
                
                updated_record = db.session.execute(text(query), {"schedule_id": schedule_id}).fetchone()
                
                if updated_record:
                    print(f"ID: {updated_record[0]}")
                    print(f"狀態: {updated_record[1]}")
                    print(f"備註: {updated_record[2]}")
                    print(f"加成: {updated_record[3]}")
                    
                    if updated_record[1] == "準備":
                        print("✅ 資料庫狀態恢復正確")
                    else:
                        print("❌ 資料庫狀態恢復異常")
            else:
                print("\n⚠️  未預期的結果")
                
        except Exception as e:
            print(f"❌ 測試失敗: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    test_restore_functionality()