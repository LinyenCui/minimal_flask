

import json
import logging
from modules.ai_agent.router import classify_and_route

# 配置日誌
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

if __name__ == '__main__':
    # 測試前，請確保您的 GOOGLE_APPLICATION_CREDENTIALS 環境變數已設定
    # test_query = "幫我查一下昨天司機5386的診所班次"
    # test_query = "明天早上8點從公司到機場，乘客是王先生"
    test_query = "今天有哪些待派班次？"
    
    print(f"\n--- 正在測試查詢: '{test_query}' ---")
    classification_result = classify_and_route(test_query)
    
    print("\n--- 測試結果 ---")
    # 使用 pretty print 格式化輸出 JSON
    print(json.dumps(classification_result, indent=2, ensure_ascii=False))
    print("--- 測試結束 ---\n")

