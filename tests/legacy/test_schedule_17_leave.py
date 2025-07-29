#!/usr/bin/env python3
"""
測試班次#17請假功能（已恢復為準備狀態）
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from modules import create_app
from modules.handlers.fixed_schedule_leave_handler import process_fixed_schedule_leave

def test_schedule_17_leave():
    """測試班次#17的請假功能"""
    app = create_app()
    
    with app.app_context():
        print("🧪 測試班次#17請假功能（用戶原問題場景）")
        print("=" * 50)
        
        test_user_id = "original_user"
        schedule_id = 17  # 用戶原問題中的班次ID
        
        print(f"1️⃣ 對班次 #{schedule_id} 執行請假（測試 -0）")
        print("-" * 40)
        
        try:
            result = process_fixed_schedule_leave(
                fixed_schedule_id=schedule_id,
                surcharge=0,  # 用戶輸入的 "-0"
                reason="測試",  # 用戶輸入的 "測試"
                user_id=test_user_id
            )
            
            print("📊 處理結果:")
            print(result)
            
            if "請假設置完成" in result:
                print("\n✅ 成功！用戶現在可以正常請假了")
            elif "已經處於請假狀態" in result:
                print("\n⚠️  班次已在請假狀態（正常行為）")
            elif "找不到ID為" in result:
                print("\n❌ 這是用戶遇到的錯誤")
            else:
                print("\n⚠️  其他結果")
                
        except Exception as e:
            print(f"❌ 測試失敗: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    test_schedule_17_leave()