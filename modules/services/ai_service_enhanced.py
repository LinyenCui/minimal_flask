import os
import logging
import json
import re
import base64
from io import BytesIO
from PIL import Image
import vertexai
from vertexai.generative_models import GenerativeModel, GenerationConfig, Part
from google.oauth2 import service_account
from google.auth import exceptions as auth_exceptions

logger = logging.getLogger(__name__)

# Path configurations
SERVICE_ACCOUNT_KEY_FILE = 'chrome-flight-458709-d1-cc3bdb1f0846.json' 
_SERVICE_DIR = os.path.dirname(__file__)
_ROOT_DIR = os.path.abspath(os.path.join(_SERVICE_DIR, '..', '..'))
_KEY_FILE_PATH = os.path.join(_ROOT_DIR, SERVICE_ACCOUNT_KEY_FILE)

# Prompt paths
_PROMPT_DIR = os.path.join(_SERVICE_DIR, '..', 'prompts')
_MULTILINGUAL_PROMPT_PATH = os.path.join(_PROMPT_DIR, 'booking_extraction_prompt_multilingual.txt')
_IMAGE_PROMPT_PATH = os.path.join(_PROMPT_DIR, 'booking_extraction_prompt_image.txt')

# API configurations
PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "chrome-flight-458709-d1")
LOCATION = os.environ.get("GCP_LOCATION", "us-central1")
MODEL_ID = "gemini-2.0-flash-001"

def load_prompt_from_file(file_path):
    """從指定路徑加載 Prompt 文本"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        logger.error(f"Prompt 文件未找到: {file_path}")
        # Fallback to a multilingual prompt if file is missing
        return '''分析以下文字（中文或日文）提取預約信息，以 JSON 格式回傳： "{user_text}"
支援語言：中文、日文
JSON輸出:'''
    except Exception as e:
        logger.error(f"讀取 Prompt 文件時出錯: {e}")
        return '''分析以下文字（中文或日文）提取預約信息，以 JSON 格式回傳： "{user_text}"
JSON輸出:'''

def init_vertexai():
    """Initialize Vertex AI client with explicit credentials."""
    credentials = None
    try:
        if os.path.exists(_KEY_FILE_PATH):
            credentials = service_account.Credentials.from_service_account_file(_KEY_FILE_PATH)
            logger.info(f"Loaded credentials from: {_KEY_FILE_PATH}")
        else:
            logger.error(f"Service account key file not found at: {_KEY_FILE_PATH}")

        vertexai.init(project=PROJECT_ID, location=LOCATION, credentials=credentials)
        logger.info(f"Vertex AI initialized for project: {PROJECT_ID}, location: {LOCATION}")

    except auth_exceptions.DefaultCredentialsError as e:
         logger.error(f"Failed to find default credentials: {e}")
    except Exception as e:
        logger.error(f"Failed to initialize Vertex AI: {e}", exc_info=True)

def detect_language(text: str) -> str:
    """簡單的語言檢測，檢查是否包含日文字符"""
    # 日文字符範圍：ひらがな、カタカナ、漢字
    japanese_chars = re.search(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FAF]', text)
    chinese_chars = re.search(r'[\u4E00-\u9FFF]', text)
    
    if japanese_chars:
        return "japanese"
    elif chinese_chars:
        return "chinese"
    else:
        return "chinese"  # Default to Chinese

def extract_booking_info_with_gemini(user_text: str) -> dict | None:
    """Extract booking info from text using enhanced multilingual Gemini API."""
    try:
        init_vertexai()
        
        # 檢測語言並選擇合適的 prompt
        language = detect_language(user_text)
        logger.info(f"Detected language: {language} for text: {user_text[:50]}...")
        
        # 載入多語言 prompt 模板並格式化
        base_prompt = load_prompt_from_file(_MULTILINGUAL_PROMPT_PATH)
        prompt = base_prompt.format(user_text=user_text)

        model = GenerativeModel(MODEL_ID)
        
        generation_config = GenerationConfig(
            temperature=0.2,
            top_p=0.8,
            top_k=40,
            max_output_tokens=1024,
        )

        logger.info(f"Calling enhanced Gemini API model: {MODEL_ID} with language: {language}...")
        response = model.generate_content(
            prompt,
            generation_config=generation_config,
        )
        logger.info("Enhanced Gemini API response received.")

        # Extract and parse the JSON response
        if response.candidates and response.text:
            content = response.text
            json_match = re.search(r"```json\s*({.*?})\s*```", content, re.DOTALL)
            if json_match:
                 json_str = json_match.group(1).strip()
            else:
                 json_match_no_fences = re.search(r"^\s*({.*?})\s*$", content.strip(), re.DOTALL | re.MULTILINE)
                 if json_match_no_fences:
                      json_str = json_match_no_fences.group(1).strip()
                 else:
                      logger.warning("Could not find JSON block in response content.")
                      json_str = content.strip().lstrip('```json').rstrip('```').strip()

            logger.info(f"Raw prediction content: {content}")
            logger.info(f"Extracted JSON string: {json_str}")

            try:
                if not json_str:
                    logger.error("Extracted JSON string is empty.")
                    return None
                extracted_info = json.loads(json_str)
                logger.info(f"Successfully parsed multilingual JSON: {extracted_info}")
                if isinstance(extracted_info, dict):
                    return extracted_info
                else:
                    logger.error(f"Parsed JSON is not a dictionary: {extracted_info}")
                    return None
            except json.JSONDecodeError as json_e:
                logger.error(f"Failed to parse JSON response: {json_e}")
                logger.error(f"Problematic JSON string: {json_str}")
                return None
        else:
            logger.warning("Gemini API returned no candidates or empty text.")
            return None

    except Exception as e:
        logger.error(f"Error calling enhanced Gemini API: {e}", exc_info=True)
        return None

def extract_booking_info_from_image(image_data: bytes, image_format: str = "jpeg") -> dict | None:
    """Extract booking info from image using Gemini Vision API."""
    try:
        init_vertexai()
        
        # 創建圖片 prompt
        image_prompt = load_prompt_from_file(_IMAGE_PROMPT_PATH)
        
        # 處理圖片數據
        try:
            # 驗證和處理圖片
            image = Image.open(BytesIO(image_data))
            # 轉換為 RGB 如果需要
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # 調整圖片大小以符合 API 限制（最大 20MB，建議小於 4MB）
            max_size = (1024, 1024)
            image.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            # 將處理後的圖片轉換為字節
            img_buffer = BytesIO()
            image.save(img_buffer, format='JPEG', quality=85)
            processed_image_data = img_buffer.getvalue()
            
            logger.info(f"Processed image size: {len(processed_image_data)} bytes")
            
        except Exception as img_error:
            logger.error(f"Image processing error: {img_error}")
            return None

        # 創建圖片部分
        image_part = Part.from_data(processed_image_data, mime_type="image/jpeg")
        
        model = GenerativeModel(MODEL_ID)
        
        generation_config = GenerationConfig(
            temperature=0.2,
            top_p=0.8,
            top_k=40,
            max_output_tokens=1024,
        )

        logger.info(f"Calling Gemini Vision API model: {MODEL_ID}...")
        response = model.generate_content(
            [image_prompt, image_part],
            generation_config=generation_config,
        )
        logger.info("Gemini Vision API response received.")

        # Extract and parse the JSON response
        if response.candidates and response.text:
            content = response.text
            json_match = re.search(r"```json\s*({.*?})\s*```", content, re.DOTALL)
            if json_match:
                 json_str = json_match.group(1).strip()
            else:
                 json_match_no_fences = re.search(r"^\s*({.*?})\s*$", content.strip(), re.DOTALL | re.MULTILINE)
                 if json_match_no_fences:
                      json_str = json_match_no_fences.group(1).strip()
                 else:
                      logger.warning("Could not find JSON block in image response content.")
                      json_str = content.strip().lstrip('```json').rstrip('```').strip()

            logger.info(f"Raw image prediction content: {content}")
            logger.info(f"Extracted JSON from image: {json_str}")

            try:
                if not json_str:
                    logger.error("Extracted JSON string from image is empty.")
                    return None
                extracted_info = json.loads(json_str)
                logger.info(f"Successfully parsed image JSON: {extracted_info}")
                if isinstance(extracted_info, dict):
                    return extracted_info
                else:
                    logger.error(f"Parsed image JSON is not a dictionary: {extracted_info}")
                    return None
            except json.JSONDecodeError as json_e:
                logger.error(f"Failed to parse JSON response from image: {json_e}")
                logger.error(f"Problematic JSON string: {json_str}")
                return None
        else:
            logger.warning("Gemini Vision API returned no candidates or empty text.")
            return None

    except Exception as e:
        logger.error(f"Error calling Gemini Vision API: {e}", exc_info=True)
        return None

def test_multilingual_extraction():
    """Test function for multilingual booking extraction"""
    init_vertexai()

    test_cases = [
        # Chinese cases
        "明天下午三點半從火車站送到成大醫院，東洋的",
        "幫我預約今天早上9:00醫院的車",
        "我要訂後天早上，從安平到高鐵站",
        
        # Japanese cases  
        "明日午後3時半に駅から病院まで送ってください",
        "今日朝9時に病院の車を予約したいです",
        "あさって朝、安平から新幹線駅まで予約お願いします",
        "田中さんを東洋まで送る、料金400円",
        "佐藤様のお迎え、明日午後2時に会社の前から"
    ]

    for i, text in enumerate(test_cases):
        print(f"--- Test Case {i+1} ---")
        print(f"Input: {text}")
        info = extract_booking_info_with_gemini(text)
        print(f"Output: {info}")
        print("-" * 20)

if __name__ == '__main__':
    test_multilingual_extraction()