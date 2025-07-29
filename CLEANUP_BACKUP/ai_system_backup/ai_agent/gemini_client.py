
import os
import logging
import vertexai
from vertexai.generative_models import GenerativeModel, GenerationConfig
from google.oauth2 import service_account
from google.auth import exceptions as auth_exceptions

# 配置日誌
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- 全局變數 ---
MODEL = None
PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "chrome-flight-458709-d1") # 從 ai_service.py 獲取
LOCATION = os.environ.get("GCP_LOCATION", "us-central1") # 從 ai_service.py 獲取
MODEL_ID = "gemini-2.0-flash-001" # 使用您文件中提到的模型

# 服務帳號金鑰檔案路徑 (位於 temp_files 目錄)
TEMP_FILES_KEY_FILE = os.path.join(
    os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'temp_files')),
    'chrome-flight-458709-d1-cc3bdb1f0846.json'
)

def configure_gemini():
    """
    配置 Gemini 模型，使用 Vertex AI 進行認證。
    優先使用 GOOGLE_APPLICATION_CREDENTIALS 環境變數，
    其次嘗試從 temp_files 目錄載入，
    最後回退到 Vertex AI 的預設憑證機制。
    """
    global MODEL
    
    # 只在第一次呼叫時配置
    if MODEL:
        return

    credentials = None
    try:
        # 1. 嘗試從 GOOGLE_APPLICATION_CREDENTIALS 環境變數中獲取憑證
        env_key_file_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if env_key_file_path and os.path.exists(env_key_file_path):
            credentials = service_account.Credentials.from_service_account_file(env_key_file_path)
            logging.info(f"Loaded credentials from GOOGLE_APPLICATION_CREDENTIALS: {env_key_file_path}")
        # 2. 如果環境變數未設定或檔案不存在，嘗試從 temp_files 目錄載入
        elif os.path.exists(TEMP_FILES_KEY_FILE):
            credentials = service_account.Credentials.from_service_account_file(TEMP_FILES_KEY_FILE)
            logging.info(f"Loaded credentials from temp_files: {TEMP_FILES_KEY_FILE}")
        else:
            logging.warning("服務帳號金鑰檔案未找到。Vertex AI 將嘗試使用預設憑證 (例如：gcloud 認證或 Compute Engine 服務帳號)。")

        vertexai.init(project=PROJECT_ID, location=LOCATION, credentials=credentials)
        
        # 建立模型實例
        MODEL = GenerativeModel(MODEL_ID)
        logging.info(f"Gemini API 已成功配置。模型: {MODEL_ID}")
    except auth_exceptions.DefaultCredentialsError as e:
        logging.error(f"無法找到預設憑證，請確保服務帳號金鑰檔案存在或 gcloud 已認證: {e}")
        raise RuntimeError("無法配置 Gemini API，請檢查憑證和網路連線。")
    except Exception as e:
        logging.error(f"配置 Gemini API 時發生錯誤: {e}", exc_info=True)
        raise RuntimeError("無法配置 Gemini API，請檢查憑證和網路連線。")

def call_gemini_api(prompt: str) -> str | None:
    """
    呼叫 Gemini API 並回傳純文字回應。

    Args:
        prompt: 要發送到 API 的完整 Prompt。

    Returns:
        API 回應的純文字內容，或在發生錯誤時回傳 None。
    """
    try:
        # 確保 API 已配置
        configure_gemini()
        
        logging.info("正在向 Gemini API 發送請求...")
        
        # 呼叫 API
        response = MODEL.generate_content(prompt)
        
        # 檢查並提取回應文字
        if response.candidates and response.candidates[0].content.parts:
            text_response = response.candidates[0].content.parts[0].text
            logging.info("成功從 Gemini API 收到回應。")
            return text_response.strip()
        else:
            logging.warning("Gemini API 回應中沒有有效的內容。")
            return None

    except Exception as e:
        logging.error(f"呼叫 Gemini API 時發生錯誤: {e}", exc_info=True)
        return None

# --- 測試程式碼 ---
if __name__ == '__main__':
    # 測試前，請確保您的服務帳號金鑰檔案 'chrome-flight-458709-d1-cc3bdb1f0846.json' 位於專案根目錄的 temp_files/ 中，
    # 或者設定 GOOGLE_APPLICATION_CREDENTIALS 環境變數。
    print("--- 測試 Gemini API 客戶端 ---")
    test_prompt = "天空是什麼顏色的？請用中文簡短回答。"
    api_response = call_gemini_api(test_prompt)
    
    if api_response:
        print(f"測試查詢: {test_prompt}")
        print(f"API 回應: {api_response}")
    else:
        print("API 呼叫失敗。請檢查憑證設定和網路連線。")
    print("--- 測試結束 ---")

