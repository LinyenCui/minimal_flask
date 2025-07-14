

import os
import json
import logging
import re
from datetime import datetime, timedelta, date

# 引入真實的 Gemini 客戶端和知識庫
from .gemini_client import call_gemini_api
from .knowledge_base import load_db_schema
from .utils import NaturalQueryParser # New import

# 配置日誌
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_classification_prompt(user_query: str, db_schema: dict, extracted_entities: dict) -> str:
    """
    生成用於三時間態分類的 Prompt。
    """
    today_str = datetime.now().strftime('%Y-%m-%d')
    schema_str = json.dumps(db_schema, indent=2, ensure_ascii=False)
    # 處理 extracted_entities 中的日期物件，將其轉換為字串
    serializable_entities = extracted_entities.copy()
    if 'date' in serializable_entities and isinstance(serializable_entities['date'], date):
        serializable_entities['date'] = serializable_entities['date'].strftime('%Y-%m-%d')
    
    extracted_entities_str = json.dumps(serializable_entities, indent=2, ensure_ascii=False) # New

    prompt = f"""
# 指令:
你是一個專業的派班系統 AI 助理。你的任務是根據用戶的查詢，將其分類到三種時間態之一：「Past」、「Present」、「Future」，並根據已提取的實體，輸出最終的實體資訊。

# 背景知識:
- 今天日期: {today_str}
- 資料庫結構:
```json
{schema_str}
```
- 已從用戶查詢中初步提取的實體:
```json
{extracted_entities_str}
```

# 分類規則:
1.  **Past**: 查詢已經完成的歷史數據。關鍵字包括「昨天」、「上週」、「已完成」、「查帳」等。
2.  **Present**: 管理和查詢當天的班次。關鍵字包括「今天」、「現在」、「待派」、「準備中」等。
3.  **Future**: 預約或規劃未來的班次。關鍵字包括「明天」、「下週」、「預約」、「安排」等。
4.  **Unknown**: 如果查詢與派班無關，或意圖不明確，則分類為 "Unknown"。

# 輸出格式:
你必須嚴格按照以下 JSON 格式回傳，不要有任何額外的解釋或文字。
請根據用戶查詢和已提取的實體，判斷正確的 time_perspective，並填寫或修正 entities 欄位。

```json
{{
  "time_perspective": "Past" | "Present" | "Future" | "Unknown",
  "entities": {{
    "date": "YYYY-MM-DD" | null,
    "time": "HH:MM" | null,
    "driver_id": "司機編號" | null,
    "customer_name": "客戶姓名" | null,
    "category": "班次類型" | null,
    "start_point": "起點" | null,
    "end_point": "終點" | null
  }}
}}
```

# 範例:
- 查詢: "幫我查一下昨天司機5386的診所班次"
- 已提取實體:
```json
{{
  "date": "{(datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')}",
  "time": null,
  "driver_id": "5386",
  "customer_name": null,
  "category": "診所",
  "start_point": null,
  "end_point": null
}}
```
- 回傳:
```json
{{
  "time_perspective": "Past",
  "entities": {{
    "date": "{(datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')}",
    "time": null,
    "driver_id": "5386",
    "customer_name": null,
    "category": "診所",
    "start_point": null,
    "end_point": null
  }}
}}
```
- 查詢: "明天早上8點從公司到機場"
- 已提取實體:
```json
{{
  "date": "{(datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')}",
  "time": "08:00",
  "driver_id": null,
  "customer_name": null,
  "category": null,
  "start_point": "公司",
  "end_point": "機場"
}}
```
- 回傳:
```json
{{
  "time_perspective": "Future",
  "entities": {{
    "date": "{(datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')}",
    "time": "08:00",
    "driver_id": null,
    "customer_name": null,
    "category": null,
    "start_point": "公司",
    "end_point": "機場"
  }}
}}
```

# 用戶查詢:
"{user_query}"

# 你的 JSON 回傳:
"""
    return prompt.strip()

def clean_json_response(raw_response: str) -> str:
    """清理 Gemini API 可能回傳的非標準 JSON 字串。"""
    # 移除常見的 markdown 標記
    match = re.search(r'```(json)?(.*)```', raw_response, re.DOTALL)
    if match:
        return match.group(2).strip()
    return raw_response.strip()

def classify_and_route(user_query: str) -> dict:
    """
    使用真實的 Gemini API 分類用戶查詢並提取實體。
    """
    logging.info(f"收到查詢，開始進行時間態分類: '{user_query}'")

    # 1. 載入知識庫
    db_schema = load_db_schema()
    if not db_schema:
        return {"error": "無法載入資料庫知識庫"}

    # 2. 使用 NaturalQueryParser 提取實體
    parser = NaturalQueryParser() # Instantiate the parser
    extracted_entities = parser.parse_natural_query(user_query) # Extract entities
    logging.info(f"初步提取的實體: {extracted_entities}")

    # 3. 生成 Prompt (現在包含初步提取的實體)
    prompt = get_classification_prompt(user_query, db_schema, extracted_entities) # Pass extracted_entities
    logging.info("分類 Prompt 已生成。")

    # 4. 呼叫真實的 Gemini API
    raw_response = call_gemini_api(prompt)
    if not raw_response:
        return {"error": "AI API 呼叫失敗或沒有回應"}

    # 5. 清理並解析回應
    cleaned_response = clean_json_response(raw_response)
    try:
        result = json.loads(cleaned_response)
        logging.info(f"成功解析 AI 回應: {result}")
        return result
    except json.JSONDecodeError:
        logging.error(f"無法解析來自 AI 的 JSON 回應。清理後的回應: '{cleaned_response}'")
        return {"error": "AI 回應格式錯誤"}

