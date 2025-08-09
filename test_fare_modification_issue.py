#!/usr/bin/env python3
"""
測試AI修改車資的原因疊加問題
確認問題後再實施正確的傳統命令修復
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_current_ai_modification_mechanism():
    """測試當前AI修改車資機制，確認原因疊加問題"""
    print("=" * 70)
    print("🔍 測試AI修改車資機制 - 原因疊加問題分析")
    print("=" * 70)
    
    print("📋 測試目標:")
    print("1. 確認AI修改車資時原因是如何記錄的")
    print("2. 驗證是否存在原因疊加問題")
    print("3. 找到原因記錄的具體實現位置")
    print("4. 為傳統命令設計正確的原因處理機制")

def analyze_trip_handler_record_fare():
    """分析 trip_handler.py 中的 handle_record_fare 函數"""
    print("\n" + "=" * 50)
    print("📄 分析 handle_record_fare 函數")
    print("=" * 50)
    
    try:
        with open('/Users/linyancui/ai_experiments/minimal_flask/modules/handlers/trip_handler.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 查找 handle_record_fare 函數
        lines = content.split('\n')
        in_function = False
        function_lines = []
        
        for i, line in enumerate(lines):
            if 'def handle_record_fare(' in line:
                in_function = True
                function_lines.append(f"{i+1}: {line}")
                continue
                
            if in_function:
                # 如果遇到下一個函數定義，結束
                if line.startswith('def ') and not line.startswith('    '):
                    break
                function_lines.append(f"{i+1}: {line}")
        
        print("🔍 handle_record_fare 函數內容：")
        for line in function_lines[:50]:  # 只顯示前50行
            print(line)
            
        # 查找原因處理邏輯
        print("\n🔍 查找原因處理相關邏輯：")
        for line in function_lines:
            if 'reason' in line.lower() or 'modification_reason' in line.lower():
                print(f"  → {line}")
                
    except Exception as e:
        print(f"❌ 讀取 trip_handler.py 失敗: {e}")

def analyze_ai_fare_service():
    """分析 AI 車資服務中的修改機制"""
    print("\n" + "=" * 50)
    print("📄 分析 ai_fare_service.py 中的修改機制")
    print("=" * 50)
    
    try:
        with open('/Users/linyancui/ai_experiments/minimal_flask/modules/services/ai_fare_service.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 查找修改車資相關的函數
        lines = content.split('\n')
        
        print("🔍 查找修改車資相關函數...")
        for i, line in enumerate(lines):
            if ('def ' in line and ('modify' in line.lower() or 'update' in line.lower())) or \
               ('record_fare' in line.lower() and 'def' in line):
                print(f"第{i+1}行: {line.strip()}")
                # 顯示函數的前幾行
                for j in range(i+1, min(i+10, len(lines))):
                    if lines[j].strip() and not lines[j].startswith('    ') and not lines[j].startswith('\t'):
                        break
                    print(f"  {j+1}: {lines[j]}")
                print()
        
        # 查找原因處理
        print("🔍 查找原因處理邏輯...")
        for i, line in enumerate(lines):
            if 'modification_reason' in line or '修改原因' in line:
                print(f"第{i+1}行: {line.strip()}")
                # 顯示上下文
                start = max(0, i-2)
                end = min(len(lines), i+3)
                for j in range(start, end):
                    marker = " -> " if j == i else "    "
                    print(f"   {marker}{j+1}: {lines[j]}")
                print()
                
    except Exception as e:
        print(f"❌ 讀取 ai_fare_service.py 失敗: {e}")

def analyze_database_update_logic():
    """分析資料庫更新邏輯"""
    print("\n" + "=" * 50)
    print("🗄️ 分析資料庫更新邏輯")
    print("=" * 50)
    
    try:
        with open('/Users/linyancui/ai_experiments/minimal_flask/modules/handlers/trip_handler.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 查找UPDATE語句
        lines = content.split('\n')
        print("🔍 查找UPDATE SQL語句...")
        
        for i, line in enumerate(lines):
            if 'UPDATE' in line.upper() and 'completed_trips' in line:
                print(f"第{i+1}行: {line.strip()}")
                # 顯示UPDATE語句的完整內容
                j = i
                update_lines = []
                while j < len(lines):
                    update_lines.append(f"  {j+1}: {lines[j]}")
                    if ')' in lines[j] or ';' in lines[j]:
                        break
                    j += 1
                
                for update_line in update_lines:
                    print(update_line)
                print()
                
        # 查找原因相關的資料庫操作
        print("🔍 查找原因相關的資料庫操作...")
        for i, line in enumerate(lines):
            if ('modification_reason' in line and ('SET' in line.upper() or '=' in line)) or \
               ('remarks' in line and ('SET' in line.upper() or '=' in line)):
                print(f"第{i+1}行: {line.strip()}")
                # 顯示上下文
                start = max(0, i-3)
                end = min(len(lines), i+4)
                for j in range(start, end):
                    marker = " -> " if j == i else "    "
                    print(f"   {marker}{j+1}: {lines[j]}")
                print()
                
    except Exception as e:
        print(f"❌ 分析資料庫更新邏輯失敗: {e}")

def identify_reason_stacking_issue():
    """識別原因疊加問題的根本原因"""
    print("\n" + "=" * 50)
    print("🎯 識別原因疊加問題")
    print("=" * 50)
    
    issue_analysis = {
        "問題現象": [
            "每次AI修改車資後，新的原因會疊加到舊原因上",
            "而不是替換舊的修改原因",
            "導致modification_reason欄位越來越長"
        ],
        
        "可能原因": [
            "UPDATE語句使用了字串拼接而不是直接替換",
            "可能是 modification_reason = CONCAT(old_reason, new_reason)",
            "或者是應用程式層的字串處理問題"
        ],
        
        "正確行為": [
            "每次修改都應該替換舊的修改原因",
            "modification_reason = new_reason (直接替換)",
            "如果需要保留歷史，應該使用專門的歷史表"
        ],
        
        "修復策略": [
            "1. 找到原因疊加的具體位置",
            "2. 修改為直接替換而不是拼接",
            "3. 確保傳統命令也使用相同的正確邏輯",
            "4. 測試驗證修復效果"
        ]
    }
    
    for category, points in issue_analysis.items():
        print(f"\n🔸 {category}:")
        for point in points:
            print(f"   • {point}")

def design_correct_traditional_command():
    """設計正確的傳統命令實現"""
    print("\n" + "=" * 50)
    print("🛠️ 設計正確的傳統記錄車資命令")
    print("=" * 50)
    
    design_plan = {
        "命令格式": {
            "完整格式": "記錄車資 2014 280 50 客戶要求調整",
            "缺少原因": "記錄車資 2014 280 50",
            "最小格式": "記錄車資 2014 280"
        },
        
        "處理邏輯": {
            "參數檢查": [
                "檢查參數數量 (至少3個：命令、ID、錶價)",
                "驗證ID是數字且存在於completed_trips表",
                "驗證錶價和加成是有效數字"
            ],
            "原因處理": [
                "如果提供了原因，直接使用",
                "如果沒有原因，啟動interactive對話",
                "用戶輸入原因後，直接替換而不是疊加"
            ]
        },
        
        "資料庫更新": {
            "正確方式": "UPDATE completed_trips SET modification_reason = %s WHERE id = %s",
            "錯誤方式": "UPDATE completed_trips SET modification_reason = CONCAT(modification_reason, %s)",
            "重點": "直接替換，不要拼接"
        },
        
        "用戶體驗": {
            "Quick Reply": "只提供「❌ 取消修改」按鈕",
            "輸入方式": "用戶自由輸入修改原因",
            "確認機制": "顯示修改前後對比，用戶確認"
        }
    }
    
    for category, details in design_plan.items():
        print(f"\n🔸 {category}:")
        if isinstance(details, dict):
            for key, value in details.items():
                print(f"   📌 {key}:")
                if isinstance(value, list):
                    for item in value:
                        print(f"      • {item}")
                else:
                    print(f"      {value}")
        else:
            for item in details:
                print(f"   • {item}")

def run_modification_analysis():
    """執行完整的修改機制分析"""
    print("🚀 開始分析AI修改車資機制...")
    
    test_current_ai_modification_mechanism()
    analyze_trip_handler_record_fare()
    analyze_ai_fare_service()
    analyze_database_update_logic()
    identify_reason_stacking_issue()
    design_correct_traditional_command()
    
    print("\n" + "=" * 70)
    print("📝 分析總結")
    print("=" * 70)
    
    summary = """
🎯 關鍵發現:
1. 需要找到AI修改中原因疊加的具體位置
2. 確認是資料庫層面的CONCAT操作還是應用層面的字串處理
3. 設計傳統命令時避免重複同樣的錯誤

💡 修復計劃:
1. 分析handle_record_fare函數的原因處理邏輯
2. 確認UPDATE語句是否使用了字串拼接
3. 修復原因疊加問題（直接替換而不是拼接）
4. 實施傳統記錄車資命令，使用正確的原因處理

🏗️ 實施順序:
1. 先修復現有的原因疊加問題
2. 再添加傳統命令的支援
3. 確保兩種方式都使用相同的正確邏輯
4. 測試驗證修復效果
    """
    
    print(summary)

if __name__ == "__main__":
    run_modification_analysis()
    
    print("\n✅ 分析完成！")
    print("💡 接下來需要實際查看程式碼來確認原因疊加問題的具體位置。")