#!/usr/bin/env python3
"""
分析現在態互動機制
研究班次詳情的請假按鈕如何處理缺少參數的情況
為過去態記錄車資設計類似的互動機制
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def analyze_trip_details_interactive():
    """分析班次詳情的互動機制"""
    print("=" * 70)
    print("🔍 現在態互動機制分析 - 班次詳情請假按鈕")
    print("=" * 70)
    
    print("\n📋 分析目標:")
    print("• 班次詳情頁面的請假按鈕如何處理")
    print("• 缺少參數時的追問機制")
    print("• Quick Reply 和對話狀態管理")
    print("• 如何應用到過去態記錄車資")

def analyze_trip_details_flex_design():
    """分析 trip_details_flex.py 的設計"""
    print("\n" + "=" * 50)
    print("📄 分析 trip_details_flex.py")
    print("=" * 50)
    
    try:
        with open('/Users/linyancui/ai_experiments/minimal_flask/modules/flex_designs/trip_details_flex.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        print("🔍 查找請假相關的按鈕設計...")
        
        # 查找請假按鈕
        if '請假' in content:
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if '請假' in line:
                    print(f"第{i+1}行: {line.strip()}")
                    # 顯示上下文
                    start = max(0, i-3)
                    end = min(len(lines), i+4)
                    print("   上下文:")
                    for j in range(start, end):
                        marker = " -> " if j == i else "    "
                        print(f"   {marker}{j+1}: {lines[j]}")
                    print()
        
        # 查找 postback action
        print("🔍 查找 postback action 設計...")
        if 'postback' in content.lower():
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if 'postback' in line.lower():
                    print(f"第{i+1}行: {line.strip()}")
        
    except Exception as e:
        print(f"❌ 讀取 trip_details_flex.py 失敗: {e}")

def analyze_postback_handling():
    """分析 postback 處理機制"""
    print("\n" + "=" * 50)
    print("📡 分析 postback 處理機制")
    print("=" * 50)
    
    try:
        # 查找 postback 服務
        with open('/Users/linyancui/ai_experiments/minimal_flask/modules/services/postback_service.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        print("🔍 查找請假相關的 postback 處理...")
        
        if '請假' in content:
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if '請假' in line and ('def' in line or 'elif' in line or 'if' in line):
                    print(f"第{i+1}行: {line.strip()}")
                    # 顯示函數內容
                    start = i
                    end = min(len(lines), i+20)
                    print("   函數內容:")
                    for j in range(start, end):
                        if j > start and lines[j].strip() and not lines[j].startswith('    ') and not lines[j].startswith('\t'):
                            break
                        print(f"   {j+1}: {lines[j]}")
                    print()
                    
    except Exception as e:
        print(f"❌ 讀取 postback_service.py 失敗: {e}")

def analyze_conversation_context_usage():
    """分析對話上下文的使用"""
    print("\n" + "=" * 50)
    print("💬 分析對話上下文管理")
    print("=" * 50)
    
    try:
        # 查找對話上下文的使用
        with open('/Users/linyancui/ai_experiments/minimal_flask/modules/utils/conversation_context.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        print("🔍 查找活躍對話管理...")
        
        # 查找 ActiveConversation 類
        if 'class ActiveConversation' in content:
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if 'class ActiveConversation' in line:
                    start = i
                    end = min(len(lines), i+30)
                    print("ActiveConversation 類定義:")
                    for j in range(start, end):
                        if j > start and lines[j].strip() and not lines[j].startswith(' ') and not lines[j].startswith('\t') and 'class' in lines[j]:
                            break
                        print(f"   {j+1}: {lines[j]}")
                    break
                    
        # 查找 start_conversation 方法
        print("\n🔍 查找 start_conversation 方法...")
        if 'def start_conversation' in content:
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if 'def start_conversation' in line:
                    start = i
                    end = min(len(lines), i+25)
                    print("start_conversation 方法:")
                    for j in range(start, end):
                        if j > start and lines[j].strip() and not lines[j].startswith('    ') and not lines[j].startswith('\t') and 'def' in lines[j]:
                            break
                        print(f"   {j+1}: {lines[j]}")
                    break
                    
    except Exception as e:
        print(f"❌ 讀取 conversation_context.py 失敗: {e}")

def analyze_text_handler_conversation_check():
    """分析 text_handler 中的對話狀態檢查"""
    print("\n" + "=" * 50)
    print("🎯 分析 text_handler 對話狀態檢查")
    print("=" * 50)
    
    try:
        with open('/Users/linyancui/ai_experiments/minimal_flask/modules/handlers/text_message_handler.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        print("🔍 查找活躍對話檢查邏輯...")
        
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if 'get_active_conversation' in line:
                print(f"第{i+1}行: {line.strip()}")
                # 顯示上下文
                start = max(0, i-5)
                end = min(len(lines), i+15)
                print("   上下文:")
                for j in range(start, end):
                    marker = " -> " if j == i else "    "
                    print(f"   {marker}{j+1}: {lines[j]}")
                print()
                
        # 查找對話類型處理
        print("🔍 查找對話類型處理...")
        for i, line in enumerate(lines):
            if "conversation_type ==" in line and "'fare_modification'" in line:
                print(f"第{i+1}行: {line.strip()}")
                # 顯示處理邏輯
                start = i
                end = min(len(lines), i+10)
                for j in range(start, end):
                    print(f"   {j+1}: {lines[j]}")
                print()
                
    except Exception as e:
        print(f"❌ 讀取 text_message_handler.py 失敗: {e}")

def design_fare_recording_interaction():
    """設計記錄車資的互動機制"""
    print("\n" + "=" * 50)
    print("🎨 設計過去態記錄車資互動機制")
    print("=" * 50)
    
    interaction_design = {
        "參考模式": {
            "現在態請假": [
                "1. 用戶點擊班次詳情的請假按鈕",
                "2. 系統檢查是否有必要參數（原因、金額）",
                "3. 如果缺少，啟動對話模式要求用戶輸入",
                "4. 用戶輸入後，系統執行操作"
            ]
        },
        
        "記錄車資應用": {
            "完整命令": "記錄車資 2014 280 50 客戶要求調整",
            "缺少原因": "記錄車資 2014 280 50",
            "處理流程": [
                "1. 檢測到記錄車資命令",
                "2. 解析參數：ID=2014, 錶價=280, 加成=50",
                "3. 發現缺少修改原因",
                "4. 啟動 fare_modification 對話",
                "5. 提示用戶輸入原因",
                "6. 用戶回覆原因後執行記錄"
            ]
        },
        
        "實現要點": {
            "命令檢查": "elif message_text.startswith('記錄車資'):",
            "參數解析": "parts = message_text.split()",
            "缺少原因判斷": "if len(parts) < 5:",
            "啟動對話": "conversation_manager.start_conversation(...)",
            "對話處理": "handle_fare_modification_conversation(...)"
        },
        
        "Quick Reply設計": {
            "提示訊息": "✅ 車資資料已準備：\\n班次 #{trip_id}\\n錶價：{meter}元\\n加成：{extra}元\\n\\n❓ 請提供修改原因：",
            "按鈕選項": [
                "客戶要求調整",
                "計費錯誤修正", 
                "特殊情況處理",
                "❌ 取消修改"
            ]
        }
    }
    
    for category, details in interaction_design.items():
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
    
    return interaction_design

def compare_mechanisms():
    """比較現在態和過去態的互動機制"""
    print("\n" + "=" * 50)
    print("🔄 機制比較與建議")
    print("=" * 50)
    
    comparison = {
        "現在態請假機制": {
            "觸發方式": "Flex Message 中的 postback 按鈕",
            "參數檢查": "在 postback_service.py 中檢查",
            "對話管理": "使用 conversation_manager",
            "用戶體驗": "直觀的按鈕操作"
        },
        
        "過去態記錄車資機制（建議）": {
            "觸發方式": "傳統命令文字輸入",
            "參數檢查": "在 text_message_handler.py 中檢查",
            "對話管理": "使用相同的 conversation_manager",
            "用戶體驗": "命令式操作 + 互動追問"
        },
        
        "共同點": [
            "都使用 conversation_manager 管理對話狀態",
            "都有參數缺失的檢查機制",
            "都提供 Quick Reply 按鈕選項",
            "都有取消操作的機制"
        ],
        
        "實現建議": [
            "複用現有的對話管理框架",
            "設計類似的 Quick Reply 選項",
            "保持一致的用戶體驗",
            "添加適當的錯誤處理"
        ]
    }
    
    for category, details in comparison.items():
        print(f"\n🔸 {category}:")
        if isinstance(details, dict):
            for key, value in details.items():
                print(f"   📌 {key}: {value}")
        else:
            for item in details:
                print(f"   • {item}")

def run_interactive_analysis():
    """執行完整的互動機制分析"""
    print("🚀 開始互動機制分析...")
    
    analyze_trip_details_interactive()
    analyze_trip_details_flex_design()
    analyze_postback_handling()
    analyze_conversation_context_usage()
    analyze_text_handler_conversation_check()
    design_result = design_fare_recording_interaction()
    compare_mechanisms()
    
    print("\n" + "=" * 70)
    print("📝 分析總結")
    print("=" * 70)
    
    summary = """
🎯 關鍵發現:
1. 現在態使用 conversation_manager 來管理互動對話
2. postback 按鈕觸發對話，text_handler 處理對話中的回覆
3. 對話狀態通過 ActiveConversation 類管理
4. Quick Reply 提供預設選項，提升用戶體驗

💡 過去態記錄車資設計:
1. 檢測 '記錄車資' 命令並解析參數
2. 如果缺少原因，啟動 fare_modification 對話
3. 提供 Quick Reply 按鈕供用戶選擇常用原因
4. 用戶回覆後完成記錄車資操作

🏗️ 實現策略:
1. 在 text_handler 中添加記錄車資命令檢查
2. 使用現有的 conversation_manager 框架
3. 設計類似現在態的互動流程
4. 保持與現有機制的一致性
    """
    
    print(summary)
    
    return design_result

if __name__ == "__main__":
    analysis_result = run_interactive_analysis()
    
    print("\n✅ 互動機制分析完成！")
    print("💡 現在可以設計一個與現在態請假機制類似的記錄車資互動系統。")