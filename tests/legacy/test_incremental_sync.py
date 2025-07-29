#!/usr/bin/env python3
"""
測試增量同步功能
"""

import sys
from pathlib import Path

# 添加項目根目錄到路徑
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from modules.services.incremental_sync_service import IncrementalSyncService

def test_sync_service():
    """測試同步服務初始化"""
    print("🧪 測試增量同步服務...")
    
    try:
        # 初始化服務
        sync_service = IncrementalSyncService()
        print("✅ 同步服務初始化成功")
        
        # 檢查配置
        print(f"Render主機: {sync_service.render_config.get('host', 'N/A')}")
        print(f"本地主機: {sync_service.local_config.get('host', 'N/A')}")
        
        # 檢查生成欄位配置
        print(f"生成欄位配置: {sync_service.generated_columns}")
        
        return True
        
    except Exception as e:
        print(f"❌ 同步服務測試失敗: {e}")
        return False

def test_connection():
    """測試資料庫連接"""
    print("\n🔌 測試資料庫連接...")
    
    try:
        sync_service = IncrementalSyncService()
        
        # 測試本地連接
        local_conn = sync_service.get_connection(sync_service.local_config, "Local")
        if local_conn:
            print("✅ 本地資料庫連接成功")
            local_conn.close()
        else:
            print("❌ 本地資料庫連接失敗")
            return False
        
        # 如果有Render配置，測試Render連接
        if all(sync_service.render_config.values()):
            render_conn = sync_service.get_connection(sync_service.render_config, "Render")
            if render_conn:
                print("✅ Render資料庫連接成功")
                render_conn.close()
            else:
                print("❌ Render資料庫連接失敗")
                return False
        else:
            print("⚠️  Render資料庫配置不完整，跳過連接測試")
        
        return True
        
    except Exception as e:
        print(f"❌ 連接測試失敗: {e}")
        return False

def test_table_inspection():
    """測試表結構檢查"""
    print("\n📋 測試表結構檢查...")
    
    try:
        sync_service = IncrementalSyncService()
        local_conn = sync_service.get_connection(sync_service.local_config, "Local")
        
        if not local_conn:
            print("❌ 無法連接本地資料庫")
            return False
        
        # 檢查幾個重要的表
        test_tables = ['trips', 'drivers', 'customers']
        
        for table in test_tables:
            try:
                columns = sync_service.get_table_columns(local_conn, table)
                filtered_columns = sync_service.filter_generated_columns(table, columns)
                print(f"✅ {table}: {len(columns)} 欄位 → {len(filtered_columns)} 過濾後")
            except Exception as e:
                print(f"⚠️  {table}: 無法檢查 ({e})")
        
        local_conn.close()
        return True
        
    except Exception as e:
        print(f"❌ 表結構檢查失敗: {e}")
        return False

def main():
    """主測試函數"""
    print("🚀 增量同步功能測試")
    print("=" * 50)
    
    tests = [
        ("同步服務初始化", test_sync_service),
        ("資料庫連接", test_connection),
        ("表結構檢查", test_table_inspection),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n📝 {test_name}")
        print("-" * 30)
        
        if test_func():
            passed += 1
            print(f"✅ {test_name} 通過")
        else:
            print(f"❌ {test_name} 失敗")
    
    print("\n" + "=" * 50)
    print(f"📊 測試結果: {passed}/{total} 通過")
    
    if passed == total:
        print("🎉 所有測試通過！增量同步功能準備就緒")
        return True
    else:
        print("⚠️  部分測試失敗，請檢查配置")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)