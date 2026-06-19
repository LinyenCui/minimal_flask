import os
import logging
import json
import re
# google-genai SDK（取代已 deprecated 的 vertexai.generative_models，2026-06 移除）
from google import genai
from google.genai import types
# --- Imports for explicit credential loading ---
from google.oauth2 import service_account
from google.auth import exceptions as auth_exceptions
# --- END ADDED ---
from modules.services.ai_environment_validator import AIEnvironmentValidator

logger = logging.getLogger(__name__)

# --- ADDED: Define key file relative path --- 
# Assume the key file is in the root directory relative to app.py
# This needs to be consistent with where app.py sets the env var
SERVICE_ACCOUNT_KEY_FILE = 'chrome-flight-458709-d1-cc3bdb1f0846.json' 
# Construct absolute path based on this file's location
_SERVICE_DIR = os.path.dirname(__file__)
_ROOT_DIR = os.path.abspath(os.path.join(_SERVICE_DIR, '..', '..')) # Go up two levels
_KEY_FILE_PATH = os.path.join(_ROOT_DIR, SERVICE_ACCOUNT_KEY_FILE)
# --- END ADDED ---

# --- ADDED: Define prompt file path --- 
_PROMPT_DIR = os.path.join(_SERVICE_DIR, '..', 'prompts')
_PROMPT_FILE_PATH = os.path.join(_PROMPT_DIR, 'booking_extraction_prompt_enhanced.txt')
# --- END ADDED ---

# Correctly read project ID and location from environment or use defaults
# PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "plucky-mile-456412-p0") # Old project ID
PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "chrome-flight-458709-d1") # New project ID (Assuming this is the new ID based on SA email)
LOCATION = os.environ.get("GCP_LOCATION", "us-central1") # Try us-central1 again with latest model
# LOCATION = os.environ.get("GCP_LOCATION", "asia-east1") # Try asia-east1 again in the new project
# MODEL_ID = "gemini-1.0-pro" # Try the standard Pro model
# MODEL_ID = "gemini-pro" # Try short name variant
MODEL_ID = "gemini-2.5-flash" # Use latest stable model according to docs

# --- ADDED: Function to load prompt from file ---
def load_prompt_from_file(file_path):
    """從指定路徑加載 Prompt 文本"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        logger.error(f"Prompt 文件未找到: {file_path}")
        # Fallback to a very basic prompt if file is missing
        return '分析以下文字提取預約信息，以 JSON 格式回傳： "{user_text}"\nJSON輸出:' 
    except Exception as e:
        logger.error(f"讀取 Prompt 文件時出錯: {e}")
        return '分析以下文字提取預約信息，以 JSON 格式回傳： "{user_text}"\nJSON輸出:' 
# --- END ADDED ---

# Module-level singleton — 一個 process 只建一個 genai client 就夠
# （舊版每次 call 都 alloc 新 Credentials + vertexai.init()，物件 leak → Render 512MB 撐爆）
_GENAI_CLIENT = None


def get_genai_client(force: bool = False):
    """共用的 google-genai Client（Vertex 後端，explicit service-account 憑證）。

    取代舊的 vertexai.init() 全域初始化：google-genai 改用 client 物件，
    所有呼叫走 client.models.generate_content / client.chats.create。
    """
    global _GENAI_CLIENT
    if _GENAI_CLIENT is not None and not force:
        return _GENAI_CLIENT

    if not os.path.exists(_KEY_FILE_PATH):
        logger.error(f"❌ Service account key file not found at: {_KEY_FILE_PATH}")
        raise FileNotFoundError(f"Service account key file not found: {_KEY_FILE_PATH}")

    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = _KEY_FILE_PATH
    credentials = service_account.Credentials.from_service_account_file(
        _KEY_FILE_PATH,
        scopes=['https://www.googleapis.com/auth/cloud-platform'],
    )
    _GENAI_CLIENT = genai.Client(
        vertexai=True, project=PROJECT_ID, location=LOCATION, credentials=credentials,
    )
    logger.info(
        f"✅ google-genai client ready (project={PROJECT_ID}, "
        f"location={LOCATION}, model={MODEL_ID})"
    )
    return _GENAI_CLIENT


def init_vertexai(force: bool = False):
    """向後相容別名：舊 caller 仍呼叫此名，實際建/取共用 genai client。"""
    get_genai_client(force=force)

def extract_booking_info_with_gemini(user_text: str) -> dict | None:
    """Extract booking info from text using Gemini API."""
    try:
        # 驗證AI環境配置
        is_valid, errors = AIEnvironmentValidator.validate_environment()
        if not is_valid:
            logger.error("AI環境配置驗證失敗:")
            for error in errors:
                logger.error(f"  - {error}")
            return None
        
        # 取共用 genai client
        client = get_genai_client()

        # 載入 prompt 模板並格式化
        base_prompt = load_prompt_from_file(_PROMPT_FILE_PATH)
        prompt = base_prompt.format(user_text=user_text)

        logger.info(f"🚀 Calling Gemini API model: {MODEL_ID}...")
        logger.info(f"🚀 Prompt length: {len(prompt)} characters")

        # Call the Gemini API
        response = client.models.generate_content(
            model=MODEL_ID,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.2,
                top_p=0.8,
                top_k=40,
                max_output_tokens=1024,
            ),
        )
        logger.info("✅ Gemini API response received successfully")
        
        # Log response details for debugging
        if response.candidates:
            logger.info(f"✅ Response has {len(response.candidates)} candidates")
            if response.text:
                logger.info(f"✅ Response text length: {len(response.text)} characters")
                logger.info(f"✅ Response text preview: {response.text[:200]}...")
            else:
                logger.warning("⚠️ Response text is empty or None")
        else:
            logger.warning("⚠️ Response has no candidates")

        # Extract and parse the JSON response
        if response.candidates and response.text:
            content = response.text # Get text directly
            # Clean potential markdown code fences
            json_match = re.search(r"```json\s*({.*?})\s*```", content, re.DOTALL)
            if json_match:
                 json_str = json_match.group(1).strip()
            else:
                 # Fallback: try finding JSON without fences if regex fails
                 json_match_no_fences = re.search(r"^\s*({.*?})\s*$", content.strip(), re.DOTALL | re.MULTILINE)
                 if json_match_no_fences:
                      json_str = json_match_no_fences.group(1).strip()
                 else:
                      logger.warning("Could not find JSON block in response content using regex.")
                      # As a last resort, try stripping, but this might fail if extra text exists
                      json_str = content.strip().lstrip('```json').rstrip('```').strip()
            # --- END FIX ---

            logger.info(f"Raw prediction content: {content}")
            logger.info(f"Extracted JSON string: {json_str}") # Changed from Cleaned JSON string

            try:
                # Handle potential empty string after stripping
                if not json_str:
                    logger.error("Extracted JSON string is empty.")
                    return None
                extracted_info = json.loads(json_str)
                logger.info(f"Successfully parsed JSON: {extracted_info}")
                # Basic validation (optional but recommended)
                if isinstance(extracted_info, dict):
                    return extracted_info
                else:
                    logger.error(f"Parsed JSON is not a dictionary: {extracted_info}")
                    return None
            except json.JSONDecodeError as json_e:
                logger.error(f"Failed to parse JSON response from Gemini: {json_e}")
                logger.error(f"Problematic JSON string: {json_str}")
                return None
        else:
            logger.warning("Gemini API returned no candidates or empty text.")
            return None

    except Exception as e:
        logger.error(f"Error calling Gemini API: {e}", exc_info=True)
        return None

# Optional: Add a simple test function
def test_gemini_extraction():
    # Make sure GOOGLE_APPLICATION_CREDENTIALS is set for testing
    # You might need to set it explicitly if running this file directly
    key_path = os.path.join(os.path.dirname(__file__), '..', '..', 'chrome-flight-458709-d1-cc3bdb1f0846.json') # Adjust path if needed
    if os.path.exists(key_path):
         os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = key_path
         print(f"Test: Set GOOGLE_APPLICATION_CREDENTIALS to {key_path}")
    else:
         print(f"Test Warning: Key file not found at {key_path}")
         return

    init_vertexai() # Manual init for testing

    test_cases = [
        "明天下午三點半從火車站送到成大醫院，東洋的",
        "幫我預約今天早上9:00醫院的車",
        "我要訂後天早上，從安平到高鐵站",
        "預約 5/10 14:00 診所",
        "送到家" # Example of incomplete information
    ]

    for i, text in enumerate(test_cases):
        print(f"--- Test Case {i+1} ---")
        print(f"Input: {text}")
        info = extract_booking_info_with_gemini(text)
        print(f"Output: {info}")
        print("-" * 20)

# Uncomment the following line to run the test when executing this file directly
if __name__ == '__main__':
    test_gemini_extraction() 