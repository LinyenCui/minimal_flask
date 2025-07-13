#!/usr/bin/env python3
"""
一鍵部署和測試班次執行前30分鐘修改限制功能
執行命令：python deploy_30min_restriction.py
"""

import os
import sys
import subprocess
from datetime import datetime

def print_banner():
    """顯示部署橫幅"""
    print("=" * 60)
    print("🚀 班次執行前30分鐘修改限制功能 - 部署腳本")
    print("=" * 60)
    print(f"📅 部署時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

def check_dependencies():
    """檢查依賴"""
    print("🔍 檢查依賴...")
    
    try:
        import pytz
        print("✅ pytz 時區庫已安裝")
    except ImportError:
        print("❌ pytz 時區庫未安裝，正在安裝...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pytz"], check=True)
        print("✅ pytz 安裝完成")
    
    try:
        from dotenv import load_dotenv
        print("✅ python-dotenv 已安裝")
    except ImportError:
        print("❌ python-dotenv 未安裝，請先安裝：pip install python-dotenv")
        return False
    
    print()
    return True

def run_tests():
    """運行測試"""
    print("🧪 運行功能測試...")
    
    try:
        # 檢查測試腳本是否存在
        if not os.path.exists("test_30min_restriction.py"):
            print("❌ 測試腳本不存在")
            return False
        
        # 運行測試
        result = subprocess.run([sys.executable, "test_30min_restriction.py"], 
                              capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ 功能測試通過")
            print(result.stdout)
        else:
            print("❌ 功能測試失敗")
            print(result.stderr)
            return False
    except Exception as e:
        print(f"❌ 測試執行出錯: {e}")
        return False
    
    print()
    return True

def check_git_status():
    """檢查Git狀態"""
    print("📝 檢查Git狀態...")
    
    try:
        # 檢查是否有未提交的變更
        result = subprocess.run(["git", "status", "--porcelain"], 
                              capture_output=True, text=True)
        
        if result.stdout.strip():
            print("⚠️  發現未提交的變更:")
            print(result.stdout)
            
            choice = input("是否要提交這些變更？(y/n): ").lower()
            if choice == 'y':
                # 添加所有變更
                subprocess.run(["git", "add", "."], check=True)
                
                # 提交變更
                commit_message = "實現班次執行前30分鐘修改限制功能"
                subprocess.run(["git", "commit", "-m", commit_message], check=True)
                print("✅ 變更已提交")
            else:
                print("⚠️  變更未提交，請手動處理")
        else:
            print("✅ 沒有未提交的變更")
    except subprocess.CalledProcessError:
        print("⚠️  無法檢查Git狀態（可能不在Git倉庫中）")
    except FileNotFoundError:
        print("⚠️  Git未安裝或不在PATH中")
    
    print()

def show_deployment_summary():
    """顯示部署摘要"""
    print("📋 部署摘要")
    print("-" * 40)
    print("✅ 已修改的文件:")
    print("   • modules/models/trip.py - 添加時間檢查方法")
    print("   • modules/services/postback_service.py - 添加限制邏輯")
    print("   • modules/flex_designs/trip_details_flex.py - UI適配")
    print("   • test_30min_restriction.py - 測試腳本")
    print("   • 30分鐘修改限制功能說明.md - 文檔")
    print()
    
    print("🎯 核心功能:")
    print("   • 班次執行前30分鐘內不可修改狀態")
    print("   • 班次執行後不可修改狀態（原有功能）")
    print("   • 指派司機功能不受限制")
    print("   • 智能時區處理（台灣時區）")
    print()

def show_next_steps():
    """顯示後續步驟"""
    print("🚀 後續步驟")
    print("-" * 40)
    print("1. 如果在本地測試:")
    print("   python test_30min_restriction.py")
    print()
    print("2. 如果要部署到生產環境:")
    print("   • Docker: docker-compose restart")
    print("   • Render: git push origin main")
    print()
    print("3. 監控建議:")
    print("   • 觀察用戶反饋")
    print("   • 檢查錯誤日誌")
    print("   • 驗證時間邏輯正確性")
    print()

def main():
    """主函數"""
    print_banner()
    
    # 檢查依賴
    if not check_dependencies():
        print("❌ 依賴檢查失敗，請手動安裝所需依賴")
        return
    
    # 運行測試
    if not run_tests():
        print("❌ 測試失敗，請檢查配置")
        choice = input("是否要忽略測試錯誤繼續部署？(y/n): ").lower()
        if choice != 'y':
            return
    
    # 檢查Git狀態
    check_git_status()
    
    # 顯示摘要
    show_deployment_summary()
    show_next_steps()
    
    print("🎉 班次執行前30分鐘修改限制功能部署完成！")
    print("=" * 60)

if __name__ == "__main__":
    main() 