#!/usr/bin/env python3
"""
智能資料庫同步工具
提供多種同步模式，確保數據安全
"""

import sys
import os
import argparse
from pathlib import Path

# 添加項目根目錄到路徑
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from modules.services.incremental_sync_service import IncrementalSyncService

def print_banner():
    """打印橫幅"""
    print("=" * 70)
    print("🔄 智能資料庫同步工具")
    print("   保護本地數據 + 增量同步Render數據")
    print("=" * 70)

def print_results(results):
    """打印同步結果"""
    print("\n📊 同步結果統計:")
    print("-" * 40)
    print(f"成功狀態: {'✅ 成功' if results['success'] else '❌ 失敗'}")
    print(f"同步表數: {results.get('synced_tables', 0)}/{results.get('total_tables', 0)}")
    print(f"新增記錄: {results.get('total_new_records', 0)}")
    
    if results.get('table_results'):
        print("\n📋 各表詳細結果:")
        for table_result in results['table_results']:
            status = "✅" if table_result['success'] else "❌"
            print(f"  {status} {table_result['table']}: {table_result['new_records']} 筆")
    
    if results.get('errors'):
        print("\n⚠️  錯誤信息:")
        for error in results['errors']:
            print(f"  - {error}")

def main():
    parser = argparse.ArgumentParser(
        description="智能資料庫同步工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用範例:
  python scripts/smart_sync.py                     # 執行完整增量同步
  python scripts/smart_sync.py --preserve-days 10  # 保護10天本地數據
  python scripts/smart_sync.py --tables trips      # 只同步指定表
  python scripts/smart_sync.py --dry-run           # 乾跑模式（即將支援）
        """
    )
    
    parser.add_argument(
        '--preserve-days', 
        type=int, 
        default=7,
        help='保留本地數據的天數 (預設: 7天)'
    )
    
    parser.add_argument(
        '--tables',
        nargs='+',
        help='指定要同步的表 (預設: 所有表)'
    )
    
    parser.add_argument(
        '--mode',
        choices=['incremental', 'preserve'],
        default='preserve',
        help='同步模式: incremental(增量) 或 preserve(保護性) (預設: preserve)'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='乾跑模式，只顯示將要執行的操作'
    )
    
    args = parser.parse_args()
    
    print_banner()
    
    if args.dry_run:
        print("🧪 乾跑模式 - 僅顯示計劃操作")
        print("   [此功能尚未實現，將直接執行]")
        print()
    
    # 初始化同步服務
    sync_service = IncrementalSyncService()
    
    try:
        if args.mode == 'preserve':
            print(f"🛡️  模式: 保護性同步 (保留 {args.preserve_days} 天本地數據)")
            results = sync_service.preserve_local_data_sync(backup_days=args.preserve_days)
        else:
            print("🔄 模式: 標準增量同步")
            results = sync_service.full_incremental_sync(tables=args.tables)
        
        print_results(results)
        
        if results['success']:
            print("\n🎉 同步完成!")
            return True
        else:
            print("\n💥 同步失敗，請檢查上述錯誤信息")
            return False
            
    except KeyboardInterrupt:
        print("\n\n⏹️  用戶中斷同步")
        return False
    except Exception as e:
        print(f"\n💥 執行過程中發生錯誤: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)