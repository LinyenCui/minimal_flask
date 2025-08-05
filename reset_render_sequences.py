#!/usr/bin/env python3
"""
重置 Render 資料庫中 trips 表的序號
"""
import os
import sys
import psycopg2
from dotenv import load_dotenv

load_dotenv()

# Render 資料庫連線設定
RENDER_DB_CONFIG = {
    "host": os.getenv('RENDER_DB_HOST'),
    "user": os.getenv('RENDER_DB_USER'),
    "dbname": os.getenv('RENDER_DB_NAME'),
    "password": os.getenv('RENDER_DB_PASSWORD'),
    "sslmode": 'require'
}

def reset_trips_sequence():
    """重置 Render 資料庫中的 trips 序號"""
    
    # 檢查必要的環境變數
    required_vars = ['RENDER_DB_HOST', 'RENDER_DB_USER', 'RENDER_DB_NAME', 'RENDER_DB_PASSWORD']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"❌ 缺少必要的環境變數: {', '.join(missing_vars)}")
        print("請確保 .env 檔案中包含所有 Render 資料庫連接資訊")
        return False
    
    try:
        print("🔌 正在連接到 Render 資料庫...")
        conn = psycopg2.connect(**RENDER_DB_CONFIG)
        cursor = conn.cursor()
        
        print("✅ 成功連接到 Render 資料庫")
        
        # 檢查當前序列狀態
        print("\n🔍 檢查當前序列狀態...")
        cursor.execute("SELECT last_value FROM trips_trip_id_seq")
        current_value = cursor.fetchone()[0]
        print(f"當前 trips_trip_id_seq 序列值: {current_value}")
        
        # 檢查 trips 表是否為空
        cursor.execute("SELECT COUNT(*) FROM trips")
        trips_count = cursor.fetchone()[0]
        print(f"trips 表中目前有 {trips_count} 筆記錄")
        
        if trips_count > 0:
            print("⚠️  警告：trips 表中仍有數據，重置序號可能導致主鍵衝突")
            confirm = input("是否確定要重置序號？(輸入 'YES' 確認): ")
            if confirm != 'YES':
                print("❌ 操作取消")
                return False
        
        # 重置序列
        print("\n🔧 重置序列...")
        cursor.execute("ALTER SEQUENCE trips_trip_id_seq RESTART WITH 1")
        conn.commit()
        
        print("✅ 成功重置 trips_trip_id_seq 序列")
        
        # 驗證重置結果
        cursor.execute("SELECT last_value FROM trips_trip_id_seq")
        new_value = cursor.fetchone()[0]
        print(f"重置後序列值: {new_value}")
        
        # 可選：同時重置 completed_trips 序列
        reset_completed = input("\n是否也要重置 completed_trips 序號？(y/N): ").strip().lower()
        if reset_completed == 'y':
            cursor.execute("SELECT last_value FROM completed_trips_id_seq")
            current_completed = cursor.fetchone()[0]
            print(f"當前 completed_trips_id_seq 序列值: {current_completed}")
            
            cursor.execute("ALTER SEQUENCE completed_trips_id_seq RESTART WITH 1")
            conn.commit()
            
            cursor.execute("SELECT last_value FROM completed_trips_id_seq")
            new_completed = cursor.fetchone()[0]
            print(f"✅ completed_trips 序列重置為: {new_completed}")
        
        cursor.close()
        conn.close()
        
        print("\n🎉 序號重置完成！下次匯入時將從 1 開始編號")
        return True
        
    except psycopg2.Error as e:
        print(f"❌ 資料庫操作失敗: {e}")
        return False
    except Exception as e:
        print(f"❌ 執行失敗: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Render 資料庫序號重置工具")
    print("=" * 50)
    
    success = reset_trips_sequence()
    
    if success:
        print("\n✅ 操作完成")
    else:
        print("\n❌ 操作失敗")
        sys.exit(1)