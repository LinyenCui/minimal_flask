#!/usr/bin/env python3
"""
設置文檔同步自動化
運行一次即可設置完整的自動化流程
"""
import os
import stat
from pathlib import Path

def setup_git_hook():
    """設置Git Hook"""
    project_root = Path("/Users/linyancui/ai_experiments/minimal_flask")
    hooks_dir = project_root / ".git" / "hooks"
    
    if not hooks_dir.exists():
        print("❌ 找不到 .git/hooks 目錄")
        return False
    
    hook_content = '''#!/bin/bash
# 智能文檔同步檢查 - 自動生成
# 只在修改關鍵文件時提醒檢查

CHANGED_FILES=$(git diff --name-only HEAD~1 HEAD 2>/dev/null || git ls-files --others --exclude-standard)

# 檢查是否修改了關鍵文件
if echo "$CHANGED_FILES" | grep -qE "(modules/handlers/|modules/services/|modules/utils/|INITIAL\.md|README\.md)"; then
    echo ""
    echo "🔍 檢測到關鍵文件修改！"
    echo "📋 建議運行文檔同步檢查："
    echo "   python3 scripts/doc_sync_checker.py"
    echo ""
    echo "💡 修改的關鍵文件："
    echo "$CHANGED_FILES" | grep -E "(modules/|\.md$)" | sed 's/^/   📄 /'
    echo ""
    
    # 可選：自動運行檢查（取消下面註釋即可）
    # echo "🤖 自動運行檢查中..."
    # python3 scripts/doc_sync_checker.py
fi
'''
    
    hook_file = hooks_dir / "post-commit"
    
    try:
        # 寫入hook內容
        with open(hook_file, "w") as f:
            f.write(hook_content)
        
        # 設置執行權限
        os.chmod(hook_file, stat.S_IRWXU | stat.S_IRGRP | stat.S_IROTH)
        
        print(f"✅ Git Hook 已設置：{hook_file}")
        return True
        
    except Exception as e:
        print(f"❌ 設置Git Hook失敗：{e}")
        return False

def create_doc_update_checklist():
    """創建文檔更新檢查清單"""
    project_root = Path("/Users/linyancui/ai_experiments/minimal_flask")
    
    checklist_content = '''# 功能完成檢查清單 📋

## 🎯 完成任務時必做事項

### ✅ 代碼實現確認
- [ ] 功能正常運作
- [ ] 相關測試通過  
- [ ] 代碼已提交到Git

### 📚 文檔同步更新 ⚠️ 重要！
- [ ] 運行文檔同步檢查：`python3 scripts/doc_sync_checker.py`
- [ ] 根據檢查報告更新相關文檔：
  - [ ] INITIAL.md (如果涉及架構或已知問題)
  - [ ] README.md (如果影響用戶使用)
  - [ ] 功能相關的技術文檔
- [ ] 如果解決了已知問題，標記為✅已解決
- [ ] 如果添加了新功能，更新功能清單

### 🔄 品質確保
- [ ] 檢查變更是否影響其他功能
- [ ] 如果是重大變更，通知相關人員
- [ ] 考慮是否需要更新部署文檔

## 💡 使用說明

1. **每次完成重要功能後**，對照此清單執行
2. **特別注意文檔同步**，這是最容易被忽略的環節
3. **運行自動檢查工具**，不要依賴記憶

## 🤖 自動化工具

- 文檔同步檢查：`python3 scripts/doc_sync_checker.py`
- Git Hook會在提交關鍵文件後自動提醒
- 詳細報告會生成在 `DOC_SYNC_REPORT.md`

---
**版本：** 1.0  
**創建時間：** 自動生成  
**目的：** 避免文檔與代碼不同步的問題
'''
    
    checklist_file = project_root / "TASK_COMPLETION_CHECKLIST.md"
    
    try:
        with open(checklist_file, "w", encoding="utf-8") as f:
            f.write(checklist_content)
        print(f"✅ 檢查清單已創建：{checklist_file}")
        return True
    except Exception as e:
        print(f"❌ 創建檢查清單失敗：{e}")
        return False

def setup_alias():
    """設置便捷命令別名"""
    print("💡 建議設置以下別名到你的 ~/.bashrc 或 ~/.zshrc：")
    print()
    print("# 文檔同步相關別名")
    print("alias doc-check='python3 scripts/doc_sync_checker.py'")
    print("alias doc-report='cat DOC_SYNC_REPORT.md'")
    print()
    print("使用方式：")
    print("  doc-check    # 運行文檔同步檢查")
    print("  doc-report   # 查看最新檢查報告")

def main():
    print("🚀 設置文檔同步自動化...")
    print("="*50)
    
    success_count = 0
    
    # 1. 設置Git Hook
    if setup_git_hook():
        success_count += 1
    
    print()
    
    # 2. 創建檢查清單
    if create_doc_update_checklist():
        success_count += 1
    
    print()
    
    # 3. 設置別名建議
    setup_alias()
    
    print()
    print("="*50)
    
    if success_count == 2:
        print("🎉 自動化設置完成！")
        print()
        print("📋 現在當你提交關鍵文件時，Git會自動提醒你檢查文檔")
        print("💡 使用 TASK_COMPLETION_CHECKLIST.md 確保不遺漏任何步驟")
        print()
        print("🧪 測試方式：")
        print("1. 修改任意 modules/handlers/ 下的文件")
        print("2. 提交變更")
        print("3. 應該會看到自動提醒")
    else:
        print("⚠️ 部分設置可能失敗，請檢查錯誤信息")

if __name__ == "__main__":
    main()