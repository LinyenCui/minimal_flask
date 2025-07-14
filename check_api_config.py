#!/usr/bin/env python3
"""
Gemini API 配置檢查腳本
幫助診斷為什麼50調用額度沒有使用到
"""
import os
import json
from pathlib import Path
from dotenv import load_dotenv

def check_environment_variables():
    """檢查環境變數配置"""
    print("🔍 檢查環境變數配置...")
    
    # 載入環境變數
    load_dotenv()
    
    required_vars = [
        'GCP_PROJECT_ID',
        'GOOGLE_APPLICATION_CREDENTIALS',
        'GCP_LOCATION'
    ]
    
    missing_vars = []
    for var in required_vars:
        value = os.getenv(var)
        if value:
            print(f"  ✅ {var}: {value}")
        else:
            print(f"  ❌ {var}: 未設置")
            missing_vars.append(var)
    
    return len(missing_vars) == 0

def check_credentials_file():
    """檢查憑證文件是否存在"""
    print("\n🔍 檢查憑證文件...")
    
    credential_file = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
    if not credential_file:
        print("  ❌ 環境變數 GOOGLE_APPLICATION_CREDENTIALS 未設置")
        return False
    
    file_path = Path(credential_file)
    if not file_path.exists():
        print(f"  ❌ 憑證文件不存在: {credential_file}")
        return False
    
    try:
        with open(file_path, 'r') as f:
            creds = json.load(f)
        
        required_keys = ['type', 'project_id', 'private_key_id', 'private_key', 'client_email']
        missing_keys = [key for key in required_keys if key not in creds]
        
        if missing_keys:
            print(f"  ❌ 憑證文件缺少必要字段: {missing_keys}")
            return False
        
        print(f"  ✅ 憑證文件正常: {credential_file}")
        print(f"  ✅ 項目ID: {creds.get('project_id')}")
        print(f"  ✅ 服務帳戶: {creds.get('client_email')}")
        return True
        
    except json.JSONDecodeError:
        print(f"  ❌ 憑證文件格式錯誤: {credential_file}")
        return False
    except Exception as e:
        print(f"  ❌ 讀取憑證文件失敗: {e}")
        return False

def test_gemini_initialization():
    """測試Gemini API初始化"""
    print("\n🔍 測試Gemini API初始化...")
    
    try:
        from modules.services.ai_service import init_vertexai, GenerativeModel, MODEL_ID
        
        # 嘗試初始化
        init_vertexai()
        print("  ✅ Vertex AI 初始化成功")
        
        # 嘗試創建模型
        model = GenerativeModel(MODEL_ID)
        print(f"  ✅ 模型創建成功: {MODEL_ID}")
        
        return True
        
    except ImportError as e:
        print(f"  ❌ 導入模組失敗: {e}")
        return False
    except Exception as e:
        print(f"  ❌ 初始化失敗: {e}")
        return False

def test_ai_router():
    """測試AI路由器"""
    print("\n🔍 測試AI路由器...")
    
    try:
        from modules.services.ai_router import get_ai_router
        
        router = get_ai_router()
        print("  ✅ AI路由器創建成功")
        
        # 測試簡單路由判斷
        test_message = "我要查詢今天的班次"
        should_use_ai = router.should_use_ai_router(test_message)
        print(f"  ✅ 路由判斷測試: '{test_message}' → {should_use_ai}")
        
        return True
        
    except Exception as e:
        print(f"  ❌ AI路由器測試失敗: {e}")
        return False

def provide_setup_instructions():
    """提供設置說明"""
    print("\n📋 設置說明:")
    print("1. 在 .env 文件中添加以下配置:")
    print("   GCP_PROJECT_ID=chrome-flight-458709-d1")
    print("   GCP_LOCATION=us-central1")
    print("   GOOGLE_APPLICATION_CREDENTIALS=chrome-flight-458709-d1-cc3bdb1f0846.json")
    print()
    print("2. 從 Google Cloud Console 下載服務帳戶憑證文件")
    print("3. 將憑證文件重命名為 chrome-flight-458709-d1-cc3bdb1f0846.json")
    print("4. 將憑證文件放在項目根目錄")
    print()
    print("5. 啟用 Vertex AI API:")
    print("   https://console.cloud.google.com/apis/library/aiplatform.googleapis.com")

def main():
    """主要檢查流程"""
    print("🚀 Gemini API 配置檢查")
    print("=" * 50)
    
    env_ok = check_environment_variables()
    creds_ok = check_credentials_file()
    
    if env_ok and creds_ok:
        gemini_ok = test_gemini_initialization()
        ai_router_ok = test_ai_router()
        
        if gemini_ok and ai_router_ok:
            print("\n🎉 配置檢查完成!")
            print("✅ 所有配置正確，AI系統已就緒")
            print("✅ 現在您的自然語言命令會開始使用 Gemini API")
            print("✅ Usage-Based Spending 將開始計算實際使用量")
        else:
            print("\n⚠️ 配置檢查完成，但有問題")
            print("❌ API初始化失敗，請檢查憑證和網路連接")
    else:
        print("\n❌ 配置檢查失敗")
        print("這就是為什麼您的50調用額度沒有使用到的原因!")
        provide_setup_instructions()

if __name__ == "__main__":
    main() 