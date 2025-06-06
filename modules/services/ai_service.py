import os
import logging
import json
import re
# Use the high-level Vertex AI SDK for Gemini
import vertexai
from vertexai.generative_models import GenerativeModel, GenerationConfig
# --- ADDED: Imports for explicit credential loading ---
from google.oauth2 import service_account
from google.auth import exceptions as auth_exceptions
# --- END ADDED ---

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
MODEL_ID = "gemini-2.0-flash-001" # Use latest stable model according to docs

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

def init_vertexai():
    """Initialize Vertex AI client with explicit credentials.""" # Modified docstring
    credentials = None
    try:
        # --- MODIFIED: Load credentials explicitly --- 
        if os.path.exists(_KEY_FILE_PATH):
            credentials = service_account.Credentials.from_service_account_file(_KEY_FILE_PATH)
            logger.info(f"Loaded credentials from: {_KEY_FILE_PATH}")
        else:
            logger.error(f"Service account key file not found at: {_KEY_FILE_PATH}. Vertex AI will use default credentials if available, which might fail.")
            # Fallback to default - might still cause issues
            # credentials = None 
        # --- END MODIFIED ---

        # --- MODIFIED: Pass credentials to init --- 
        vertexai.init(project=PROJECT_ID, location=LOCATION, credentials=credentials)
        logger.info(f"Vertex AI initialized for project: {PROJECT_ID}, location: {LOCATION}")
        # --- END MODIFIED ---

    # --- ADDED: Specific auth error handling ---
    except auth_exceptions.DefaultCredentialsError as e:
         logger.error(f"Failed to find default credentials and key file was not found or invalid: {e}")
    # --- END ADDED ---
    except Exception as e:
        logger.error(f"Failed to initialize Vertex AI: {e}", exc_info=True)

def extract_booking_info_with_gemini(user_text: str) -> dict | None:
    """Extract booking info from text using Gemini API."""
    try:
        # --- REMOVED: Explicit initialize Vertex AI before calling --- 
        # init_vertexai()
        # --- END REMOVED ---
        
        # --- MODIFIED: Load prompt from file and format --- 
        # model = GenerativeModel(MODEL_ID)
        # Construct the prompt
        # prompt = f"""... (Old prompt string removed) ..."""
        base_prompt = load_prompt_from_file(_PROMPT_FILE_PATH)
        prompt = base_prompt.format(user_text=user_text) # Format the prompt with user input
        # --- END MODIFIED ---

        # --- ADDED: Initialize model after getting prompt content (optional, but can be here) ---
        model = GenerativeModel(MODEL_ID)
        # --- END ADDED ---
        
        # Configure generation parameters
        generation_config = GenerationConfig(
            temperature=0.2,
            top_p=0.8,
            top_k=40,
            max_output_tokens=1024,
            # Specify JSON output format if model supports it (check documentation)
            # response_mime_type="application/json", # Uncomment if using a model/version that supports direct JSON output
        )

        logger.info(f"Calling Gemini API model: {MODEL_ID}...")
        # Call the Gemini API
        response = model.generate_content(
            prompt, # Send prompt as string directly
            generation_config=generation_config,
        )
        logger.info("Gemini API response received.")

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