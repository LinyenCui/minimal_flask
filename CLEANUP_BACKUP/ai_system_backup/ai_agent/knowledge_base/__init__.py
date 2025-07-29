
import os
import json
import logging

# 配置日誌
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- 常數定義 ---
DB_SCHEMA_PATH = os.path.join(os.path.dirname(__file__), 'db_schema.json')

# --- 核心函式 ---

def load_db_schema() -> dict:
    """載入資料庫結構的 JSON 檔案。"""
    try:
        with open(DB_SCHEMA_PATH, 'r', encoding='utf-8') as f:
            logging.info(f"成功從 {DB_SCHEMA_PATH} 載入資料庫結構。")
            return json.load(f)
    except FileNotFoundError:
        logging.error(f"資料庫結構檔案未找到於: {DB_SCHEMA_PATH}")
        return None
    except json.JSONDecodeError:
        logging.error(f"無法解析資料庫結構檔案: {DB_SCHEMA_PATH}")
        return None

# 為了讓 agent_core.py 能運作，我們先建立一個模擬的 knowledge_base 物件
# 在未來，這個物件可以被擴展，包含更多業務規則和範例
class KnowledgeBase:
    def __init__(self):
        self.schema = load_db_schema()

    def get_schema(self, table_name: str) -> dict | None:
        return self.schema.get(table_name)

    def get_business_rules(self, keyword: str) -> list:
        # 模擬的業務規則
        return []

    def get_examples(self) -> list:
        # 模擬的範例
        return []

# 建立一個全域實例，供其他模組導入
knowledge_base = KnowledgeBase()
