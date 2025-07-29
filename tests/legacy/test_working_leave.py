#!/usr/bin/env python3
"""
測試固定班次請假功能 - 使用準備狀態的班次
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from modules import create_app
from modules.utils.conversation_context import conversation_manager
from modules.handlers.fixed_schedule_leave_handler import process_fixed_schedule_leave

def test_leave_on_ready_schedule():
    """測試對準備狀態班次的請假功能"""
    app = create_app()
    
    with app.app_context():
        print("🧪 測試準備狀態班次的請假功能")
        print("=" * 50)
        
        test_user_id = "test_user_ready"
        schedule_id = 5  # 使用ID=5，狀態為「準備」的班次
        
        print(f"1️⃣ 測試班次 #{schedule_id} 請假")
        print("-" * 30)
        
        try:
            result = process_fixed_schedule_leave(
                fixed_schedule_id=schedule_id,
                surcharge=-50,  # 設置-50加成
                reason="測試長期請假功能",
                user_id=test_user_id
            )
            
            print("📊 處理結果:")
            print(result)
            
            if "請假設置完成" in result:
                print("\n✅ 請假設置成功！")
                
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
                    
                    if updated_record[1] == "請假":
                        print("✅ 資料庫狀態更新正確")
                    else:
                        print("❌ 資料庫狀態更新異常")
                
            elif "已經處於請假狀態" in result:
                print("\n⚠️  班次已在請假狀態")
            elif "找不到ID為" in result:
                print("\n❌ 找不到指定班次")
            else:
                print("\n⚠️  未預期的結果")
                
        except Exception as e:
            print(f"❌ 測試失敗: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    test_leave_on_ready_schedule()