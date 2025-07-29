#!/usr/bin/env python3
"""
大規模專案清理腳本
清理冗餘檔案、重複實現、未使用目錄
"""

import os
import shutil
import glob
from pathlib import Path

class ProjectCleaner:
    def __init__(self, project_root="/Users/linyancui/ai_experiments/minimal_flask"):
        self.project_root = Path(project_root)
        self.backup_dir = self.project_root / "CLEANUP_BACKUP"
        self.deleted_files = []
        self.moved_files = []
        
    def create_backup_dir(self):
        """創建備份目錄"""
        self.backup_dir.mkdir(exist_ok=True)
        print(f"✅ 創建備份目錄: {self.backup_dir}")
    
    def safe_delete(self, path):
        """安全刪除（移動到備份目錄）"""
        if isinstance(path, str):
            path = Path(path)
        
        if path.exists():
            backup_path = self.backup_dir / path.name
            if backup_path.exists():
                backup_path = self.backup_dir / f"{path.name}_backup_{len(self.deleted_files)}"
            
            shutil.move(str(path), str(backup_path))
            self.deleted_files.append(str(path))
            print(f"🗑️  刪除: {path}")
            return True
        return False
    
    def safe_move(self, source, destination):
        """安全移動檔案"""
        if isinstance(source, str):
            source = Path(source)
        if isinstance(destination, str):
            destination = Path(destination)
            
        if source.exists():
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(destination))
            self.moved_files.append(f"{source} -> {destination}")
            print(f"📦 移動: {source} -> {destination}")
            return True
        return False
    
    def clean_obvious_redundant_dirs(self):
        """清理明顯冗餘的目錄"""
        print("\n🧹 Phase 1: 清理明顯冗餘目錄")
        
        redundant_dirs = [
            "ai_system_backup",      # 完整備份
            "backup_20250323",       # 舊版備份  
            "fresh_venv",           # 舊虛擬環境
            "new_venv",             # 舊虛擬環境
            "temp_files",           # 臨時檔案
            "Backup",               # 小備份
            "models.test",          # 測試模型
            "dispatch_bot",         # 舊架構（基本空白）
            "handlers",             # 根目錄舊handlers
            "utils",                # 根目錄空utils
        ]
        
        for dir_name in redundant_dirs:
            dir_path = self.project_root / dir_name
            if dir_path.exists():
                self.safe_delete(dir_path)
    
    def clean_sql_backups(self):
        """清理散落的SQL備份檔案"""
        print("\n🧹 Phase 2: 清理SQL備份檔案")
        
        sql_patterns = [
            "*.sql",
            "render_sync_*.sql", 
            "auto_backup_*.sql",
            "local_backup_*.sql",
            "render_backup_*.sql"
        ]
        
        for pattern in sql_patterns:
            for sql_file in self.project_root.glob(pattern):
                if sql_file.is_file():
                    self.safe_delete(sql_file)
    
    def clean_scattered_md_files(self):
        """清理散落的MD檔案，移到docs"""
        print("\n📚 Phase 3: 整理散落的文檔")
        
        # 根目錄的MD檔案（除了重要的）
        important_md = {"README.md", "INITIAL.md", "CLEANUP_ANALYSIS.md"}
        
        for md_file in self.project_root.glob("*.md"):
            if md_file.name not in important_md:
                dest_path = self.project_root / "docs" / md_file.name
                self.safe_move(md_file, dest_path)
    
    def clean_test_files(self):
        """清理散落的測試檔案"""
        print("\n🧪 Phase 4: 整理測試檔案")
        
        # 根目錄的test_*.py檔案移到tests/legacy/
        legacy_test_dir = self.project_root / "tests" / "legacy"
        legacy_test_dir.mkdir(parents=True, exist_ok=True)
        
        for test_file in self.project_root.glob("test_*.py"):
            dest_path = legacy_test_dir / test_file.name
            self.safe_move(test_file, dest_path)
    
    def clean_duplicate_functions(self):
        """清理重複函數檔案"""
        print("\n🔧 Phase 5: 清理重複實現檔案")
        
        # 保留統一版本，刪除重複
        files_to_delete = [
            "modules/utils/enhanced_date_parser.py",  # 保留unified_date_parser.py
            "modules/services/ai_enhanced_fare_service.py",  # 保留ai_fare_service.py
            "modules/services/ai_fare_service_simple_backup.py",  # 備份檔案
            "modules/services/ai_service.py",  # 重複服務
            "modules/handlers/text_message_handler.py.bak",  # 備份檔案
        ]
        
        for file_path in files_to_delete:
            full_path = self.project_root / file_path
            if full_path.exists():
                self.safe_delete(full_path)
    
    def clean_empty_dirs(self):
        """清理空目錄"""
        print("\n📁 Phase 6: 清理空目錄")
        
        def is_empty_dir(path):
            if not path.is_dir():
                return False
            try:
                return len(list(path.iterdir())) == 0
            except:
                return False
        
        # 多次掃描，因為刪除子目錄後父目錄可能變空
        for _ in range(3):
            for root, dirs, files in os.walk(self.project_root, topdown=False):
                for dir_name in dirs:
                    dir_path = Path(root) / dir_name
                    if is_empty_dir(dir_path):
                        try:
                            dir_path.rmdir()
                            print(f"📁 刪除空目錄: {dir_path}")
                        except:
                            pass
    
    def generate_cleanup_report(self):
        """生成清理報告"""
        report_path = self.project_root / "CLEANUP_REPORT.md"
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("# 🧹 專案清理報告\n\n")
            f.write(f"清理時間: {os.popen('date').read().strip()}\n\n")
            
            f.write("## 🗑️ 已刪除檔案/目錄\n\n")
            for deleted in self.deleted_files:
                f.write(f"- {deleted}\n")
            
            f.write("\n## 📦 已移動檔案\n\n")  
            for moved in self.moved_files:
                f.write(f"- {moved}\n")
            
            f.write(f"\n## 📊 統計\n\n")
            f.write(f"- 刪除項目: {len(self.deleted_files)}\n")
            f.write(f"- 移動項目: {len(self.moved_files)}\n")
            f.write(f"- 備份位置: {self.backup_dir}\n")
        
        print(f"\n📋 清理報告已生成: {report_path}")
    
    def run_cleanup(self):
        """執行完整清理流程"""
        print("🚀 開始大規模專案清理...")
        print("⚠️  所有刪除的檔案都會備份到 CLEANUP_BACKUP 目錄")
        
        self.create_backup_dir()
        self.clean_obvious_redundant_dirs()
        self.clean_sql_backups()
        self.clean_scattered_md_files()
        self.clean_test_files()
        self.clean_duplicate_functions()
        self.clean_empty_dirs()
        self.generate_cleanup_report()
        
        print(f"\n✅ 清理完成！")
        print(f"📊 刪除了 {len(self.deleted_files)} 個項目")
        print(f"📦 移動了 {len(self.moved_files)} 個檔案")
        print(f"💾 備份位置: {self.backup_dir}")

if __name__ == "__main__":
    cleaner = ProjectCleaner()
    
    print("⚠️  這將執行大規模清理，請確認：")
    print("1. 這是複製的專案，可以安全清理")
    print("2. 所有刪除項目會備份到 CLEANUP_BACKUP/")
    print("3. 重要檔案已標記保留")
    print("4. 用戶已確認可以進行清理")
    
    # 直接執行清理（已確認為複製專案）
    cleaner.run_cleanup()