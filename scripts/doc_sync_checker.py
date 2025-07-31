#!/usr/bin/env python3
"""
自動檢測代碼與文檔的不一致性
運行方式：python scripts/doc_sync_checker.py
"""
import os
import re
from pathlib import Path
from datetime import datetime

class DocumentSyncChecker:
    def __init__(self):
        self.project_root = Path("/Users/linyancui/ai_experiments/minimal_flask")
        self.issues = []
    
    def check_date_parser_status(self):
        """檢查日期解析函數狀態"""
        print("🔍 檢查日期解析函數狀態...")
        
        # 檢查是否還有重複實現
        duplicate_implementations = []
        unified_usages = []
        
        for py_file in self.project_root.rglob("*.py"):
            if any(skip in str(py_file) for skip in ["CLEANUP_BACKUP", "venv", ".git", "__pycache__"]):
                continue
                
            try:
                content = py_file.read_text(encoding='utf-8')
                
                # 檢查重複實現（排除已知的合理情況）
                if "def parse_date_input" in content:
                    if "unified_date_parser" in content or "轉發到統一解析器" in content:
                        # 這是合理的轉發實現
                        pass
                    elif "日期範圍" in content or "batch_allowance" in str(py_file):
                        # batch_allowance_handler的特殊實現是合理的
                        pass
                    else:
                        duplicate_implementations.append(str(py_file.relative_to(self.project_root)))
                
                # 檢查統一解析器使用情況
                if "from modules.utils.unified_date_parser import" in content:
                    unified_usages.append(str(py_file.relative_to(self.project_root)))
                    
            except Exception as e:
                print(f"   ⚠️ 無法讀取文件 {py_file}: {e}")
                continue
        
        print(f"   ✅ 使用統一日期解析器的文件: {len(unified_usages)} 個")
        print(f"   ⚠️ 可能重複實現的文件: {len(duplicate_implementations)} 個")
        
        if duplicate_implementations:
            print("   重複實現文件:")
            for file in duplicate_implementations:
                print(f"     - {file}")
        
        # 檢查INITIAL.md是否還在提到重複問題
        initial_md = self.project_root / "INITIAL.md"
        if initial_md.exists():
            content = initial_md.read_text()
            if "6個不同模組各自實現parse_date_input函數" in content:
                if len(duplicate_implementations) <= 2:  # 實際已大幅改善
                    self.issues.append({
                        "type": "OUTDATED_DOCUMENTATION",
                        "file": "INITIAL.md",
                        "line": "約161行",
                        "issue": "日期解析重複問題已大幅改善，但文檔未更新",
                        "current_status": f"統一使用: {len(unified_usages)} 個文件, 重複實現: {len(duplicate_implementations)} 個",
                        "suggestion": "更新INITIAL.md，標記為✅已解決或大幅改善"
                    })
    
    def check_quick_reply_status(self):
        """檢查Quick Reply功能實現狀態"""
        print("🔍 檢查Quick Reply功能狀態...")
        
        quick_reply_files = [
            "modules/handlers/trip_status_handler.py",
            "modules/services/postback_service.py", 
            "modules/flex_designs/trip_details_flex.py",
            "modules/handlers/text_message_handler.py"
        ]
        
        implemented_files = []
        for file_path in quick_reply_files:
            full_path = self.project_root / file_path
            if full_path.exists():
                try:
                    content = full_path.read_text()
                    if "QuickReply" in content or "quick_reply" in content:
                        implemented_files.append(file_path)
                except:
                    continue
        
        print(f"   ✅ 包含Quick Reply實現的文件: {len(implemented_files)} 個")
        for file in implemented_files:
            print(f"     - {file}")
        
        if len(implemented_files) >= 3:  # 大部分關鍵文件都有實現
            self.issues.append({
                "type": "FEATURE_COMPLETION_NOT_DOCUMENTED",
                "feature": "Quick Reply Exit Mechanism",
                "status": f"已在{len(implemented_files)}個關鍵文件中實現",
                "files": implemented_files,
                "suggestion": "考慮在INITIAL.md或功能文檔中標記此功能為✅已實現"
            })
    
    def check_handler_split_status(self):
        """檢查處理器拆分狀態"""
        print("🔍 檢查處理器拆分狀態...")
        
        text_handler = self.project_root / "modules/handlers/text_message_handler.py"
        if text_handler.exists():
            try:
                content = text_handler.read_text()
                line_count = len(content.split('\n'))
                print(f"   📊 text_message_handler.py 行數: {line_count}")
                
                if line_count > 800:  # 仍然很大
                    self.issues.append({
                        "type": "TECHNICAL_DEBT_STILL_EXISTS",
                        "file": "modules/handlers/text_message_handler.py",
                        "issue": f"文件仍有{line_count}行，需要拆分",
                        "suggestion": "按照INITIAL.md的建議拆分為booking_handler, query_handler, status_handler"
                    })
                else:
                    print("   ✅ 文件大小合理")
            except:
                print("   ⚠️ 無法讀取text_message_handler.py")
    
    def check_completed_features(self):
        """檢查已完成但未標記的功能"""
        print("🔍 檢查已完成但未在文檔中標記的功能...")
        
        # 檢查trip_leave_exit相關文件
        test_files = list(self.project_root.glob("test_*_exit_*.py"))
        if test_files:
            print(f"   📋 發現{len(test_files)}個退出機制測試文件:")
            for file in test_files:
                print(f"     - {file.name}")
            
            self.issues.append({
                "type": "COMPLETED_FEATURE_NOT_DOCUMENTED",
                "feature": "Trip Leave Exit Mechanism",
                "evidence": f"存在{len(test_files)}個相關測試文件",
                "suggestion": "在功能文檔中記錄此功能的完成狀態"
            })
    
    def generate_sync_report(self):
        """生成同步報告"""
        print("📋 開始文檔同步檢查...")
        print("=" * 50)
        
        self.check_date_parser_status()
        print()
        self.check_quick_reply_status()
        print()
        self.check_handler_split_status()
        print()
        self.check_completed_features()
        print()
        
        report = f"""# 文檔同步檢查報告

**生成時間:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  
**檢查項目:** {len(self.issues)} 個不一致問題

## 摘要
本次檢查發現 {len(self.issues)} 個文檔與代碼不一致的問題，需要人工確認和修正。

## 發現的問題詳情
"""
        
        if not self.issues:
            report += "\n🎉 **恭喜！** 沒有發現明顯的文檔同步問題。\n"
        else:
            for i, issue in enumerate(self.issues, 1):
                report += f"""
### {i}. {issue['type'].replace('_', ' ').title()}

**問題描述:** {issue.get('issue', issue.get('status', 'N/A'))}

**相關文件:** {issue.get('file', issue.get('files', 'N/A'))}

**建議行動:** {issue['suggestion']}

**當前狀態:** {issue.get('current_status', '待確認')}

---
"""
        
        report += f"""
## 建議的後續行動

### 🔥 立即行動
1. 檢查並修正 INITIAL.md 中已過時的問題描述
2. 為已完成的功能添加 ✅ 標記
3. 更新技術債清單，移除已解決的項目

### 📋 流程改進
1. 建立任務完成檢查清單，確保文檔同步更新
2. 在 Git 提交前運行此檢查腳本
3. 定期（如每月）運行完整的文檔同步檢查

### 🤖 自動化增強
1. 將此腳本加入 CI/CD 流程
2. 設置 Git Hook 在重要文件修改時提醒更新文檔  
3. 考慮使用 AI 輔助生成文檔更新建議

---

**生成工具:** scripts/doc_sync_checker.py  
**使用方法:** `python scripts/doc_sync_checker.py`
"""
        
        return report

def main():
    checker = DocumentSyncChecker()
    report = checker.generate_sync_report()
    
    # 輸出到文件
    report_file = checker.project_root / "DOC_SYNC_REPORT.md"
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(report)
    
    print("=" * 50)
    print(f"📄 文檔同步檢查完成！")
    print(f"📋 詳細報告已生成: {report_file}")
    print()
    
    if checker.issues:
        print(f"⚠️  發現 {len(checker.issues)} 個需要關注的問題")
        print("💡 請查看報告並採取相應行動")
    else:
        print("✅ 沒有發現明顯的同步問題")

if __name__ == "__main__":
    main()