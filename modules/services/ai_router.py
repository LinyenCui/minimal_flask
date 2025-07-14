"""
AI智能路由器 - 三時間態意圖分析與路由系統
整合現有的Gemini API配置，實現自然語言理解和智能路由
"""
import os
import logging
import json
import re
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

# 重用現有的Gemini API配置
import vertexai
from vertexai.generative_models import GenerativeModel, GenerationConfig
from google.oauth2 import service_account
from google.auth import exceptions as auth_exceptions

# 導入現有的初始化函數
from modules.services.ai_service import init_vertexai, PROJECT_ID, LOCATION, MODEL_ID, _KEY_FILE_PATH

logger = logging.getLogger(__name__)

class TimePerspective(Enum):
    """時間態度枚舉"""
    PAST = "past"
    PRESENT = "present"
    FUTURE = "future"

class OperationType(Enum):
    """操作類型枚舉"""
    QUERY = "query"
    MODIFY = "modify"
    CREATE = "create"
    DELETE = "delete"

@dataclass
class IntentResult:
    """意圖分析結果"""
    time_perspective: TimePerspective
    operation_type: OperationType
    entities: Dict[str, Any]
    target_function: str
    confidence: float
    reasoning: str
    raw_response: str

@dataclass
class RouteResult:
    """路由結果"""
    success: bool
    response_text: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    execution_time: float = 0.0

class AIRouter:
    """AI智能路由器核心類"""
    
    def __init__(self):
        """初始化AI路由器"""
        self.model = None
        self.confidence_threshold = 0.6
        self.max_retries = 3
        self.system_knowledge = self._load_system_knowledge()
        self._initialize_gemini()
    
    def _initialize_gemini(self):
        """初始化Gemini API"""
        try:
            # 使用現有的初始化函數
            init_vertexai()
            
            # 創建模型實例
            self.model = GenerativeModel(MODEL_ID)
            logger.info(f"AI路由器已成功初始化，模型: {MODEL_ID}")
            
        except Exception as e:
            logger.error(f"初始化Gemini API失敗: {e}")
            raise RuntimeError(f"無法初始化AI路由器: {e}")
    
    def _load_system_knowledge(self) -> Dict[str, Any]:
        """載入系統知識庫"""
        return {
            "database_tables": {
                "trips": {
                    "description": "當前進行中的班次",
                    "time_perspective": "present",
                    "main_columns": ["id", "date", "driver_id", "category", "status", "start_point", "end_point"]
                },
                "completed_trips": {
                    "description": "已完成的歷史班次",
                    "time_perspective": "past", 
                    "main_columns": ["id", "trip_id", "completed_at", "duration", "fare", "driver_id"]
                },
                "fixed_schedules": {
                    "description": "固定班次模板",
                    "time_perspective": "future",
                    "main_columns": ["id", "date", "time", "category", "driver_id", "status"]
                }
            },
            "time_keywords": {
                "past": ["昨天", "昨日", "前天", "上週", "上個月", "已完成", "歷史", "過去", "之前"],
                "present": ["今天", "今日", "現在", "當前", "目前", "這個", "正在", "待派"],
                "future": ["明天", "明日", "後天", "下週", "下個月", "未來", "即將", "安排", "匯入", "預定"]
            },
            "operation_keywords": {
                "query": ["查詢", "查", "看", "顯示", "搜尋", "找", "列出", "檢視"],
                "modify": ["修改", "改", "更新", "調整", "設定", "變更", "編輯"],
                "create": ["創建", "新增", "建立", "匯入", "添加", "預約", "安排"],
                "delete": ["刪除", "移除", "清除", "取消", "廢棄"]
            },
            "available_functions": {
                "query_trips": "查詢當前班次",
                "query_completed_trips": "查詢已完成班次",
                "query_fixed_schedules": "查詢固定班次",
                "assign_driver": "指派司機",
                "modify_trip": "修改班次",
                "import_schedules": "匯入固定班次",
                "generate_report": "生成報表"
            }
        }
    
    def analyze_intent(self, user_message: str) -> IntentResult:
        """分析用戶意圖"""
        try:
            # 構建意圖分析prompt
            prompt = self._build_intent_prompt(user_message)
            
            # 配置生成參數
            generation_config = GenerationConfig(
                temperature=0.2,
                top_p=0.8,
                top_k=40,
                max_output_tokens=2048,
            )
            
            # 調用Gemini API
            response = self.model.generate_content(
                prompt,
                generation_config=generation_config
            )
            
            # 解析回應
            return self._parse_intent_response(response, user_message)
            
        except Exception as e:
            logger.error(f"意圖分析失敗: {e}")
            return self._create_fallback_intent(user_message)
    
    def _build_intent_prompt(self, user_message: str) -> str:
        """構建意圖分析prompt - 使用專用的prompt模板"""
        try:
            # 載入專用的prompt模板
            prompt_file = os.path.join(os.path.dirname(__file__), '..', 'prompts', 'intent_analysis_prompt.txt')
            with open(prompt_file, 'r', encoding='utf-8') as f:
                prompt_template = f.read()
            
            # 用用戶輸入替換佔位符
            prompt = prompt_template.format(user_input=user_message)
            return prompt
            
        except FileNotFoundError:
            # 如果prompt文件不存在，使用備用的簡化prompt
            logger.warning("專用prompt文件未找到，使用備用prompt")
            return self._build_fallback_prompt(user_message)
        except Exception as e:
            logger.error(f"載入prompt文件失敗: {e}")
            return self._build_fallback_prompt(user_message)
    
    def _build_fallback_prompt(self, user_message: str) -> str:
        """備用的簡化prompt"""
        return f"""
你是派班系統AI助手。分析以下用戶輸入並返回JSON格式結果：

用戶輸入："{user_message}"

返回格式：
{{
    "time_perspective": "past|present|future",
    "operation_type": "query|modify|create|delete", 
    "entities": {{}},
    "target_function": "query_trips",
    "confidence": 0.5,
    "reasoning": "簡化分析"
}}
"""
    
    def _parse_intent_response(self, response, user_message: str) -> IntentResult:
        """解析意圖分析回應"""
        try:
            # 提取文本內容
            if response.candidates and response.candidates[0].content.parts:
                text_response = response.candidates[0].content.parts[0].text
                
                # 清理JSON字符串
                json_str = self._clean_json_response(text_response)
                
                # 解析JSON
                result_data = json.loads(json_str)
                
                # 創建IntentResult對象
                return IntentResult(
                    time_perspective=TimePerspective(result_data.get("time_perspective", "present")),
                    operation_type=OperationType(result_data.get("operation_type", "query")),
                    entities=result_data.get("entities", {}),
                    target_function=result_data.get("target_function", "query_trips"),
                    confidence=float(result_data.get("confidence", 0.5)),
                    reasoning=result_data.get("reasoning", ""),
                    raw_response=text_response
                )
                
        except Exception as e:
            logger.error(f"解析意圖回應失敗: {e}")
            return self._create_fallback_intent(user_message)
    
    def _clean_json_response(self, text: str) -> str:
        """清理JSON回應文本"""
        # 移除代碼塊標記
        text = re.sub(r'```json\s*', '', text)
        text = re.sub(r'```\s*', '', text)
        
        # 尋找JSON對象
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            return json_match.group(0)
        
        return text.strip()
    
    def _create_fallback_intent(self, user_message: str) -> IntentResult:
        """創建備用意圖結果"""
        # 使用基本的關鍵詞匹配作為備用
        time_perspective = self._detect_time_perspective(user_message)
        operation_type = self._detect_operation_type(user_message)
        
        return IntentResult(
            time_perspective=time_perspective,
            operation_type=operation_type,
            entities={},
            target_function="query_trips",
            confidence=0.3,
            reasoning="使用備用關鍵詞匹配",
            raw_response=f"備用分析: {user_message}"
        )
    
    def _detect_time_perspective(self, message: str) -> TimePerspective:
        """檢測時間態度"""
        message_lower = message.lower()
        
        for time_key, keywords in self.system_knowledge["time_keywords"].items():
            if any(keyword in message_lower for keyword in keywords):
                return TimePerspective(time_key)
        
        return TimePerspective.PRESENT
    
    def _detect_operation_type(self, message: str) -> OperationType:
        """檢測操作類型"""
        message_lower = message.lower()
        
        for op_key, keywords in self.system_knowledge["operation_keywords"].items():
            if any(keyword in message_lower for keyword in keywords):
                return OperationType(op_key)
        
        return OperationType.QUERY
    
    def route_to_service(self, intent: IntentResult) -> RouteResult:
        """根據意圖路由到對應服務"""
        start_time = datetime.now()
        
        try:
            # 檢查信心度
            if intent.confidence < self.confidence_threshold:
                return RouteResult(
                    success=False,
                    response_text="抱歉，我無法理解您的請求。請提供更具體的信息。",
                    error=f"信心度過低: {intent.confidence}"
                )
            
            # 根據時間態度路由
            if intent.time_perspective == TimePerspective.PAST:
                return self._route_to_past_service(intent)
            elif intent.time_perspective == TimePerspective.PRESENT:
                return self._route_to_present_service(intent)
            elif intent.time_perspective == TimePerspective.FUTURE:
                return self._route_to_future_service(intent)
            else:
                return RouteResult(
                    success=False,
                    response_text="無法確定時間範圍，請重新描述您的需求。",
                    error="未知時間態度"
                )
                
        except Exception as e:
            logger.error(f"路由失敗: {e}")
            return RouteResult(
                success=False,
                response_text="處理請求時發生錯誤，請稍後再試。",
                error=str(e)
            )
        finally:
            execution_time = (datetime.now() - start_time).total_seconds()
            logger.info(f"路由執行時間: {execution_time:.2f}秒")
    
    def _route_to_past_service(self, intent: IntentResult) -> RouteResult:
        """路由到過去時間態服務（已完成班次）"""
        try:
            # 這裡將整合現有的 ai_fare_service.py 功能
            from modules.services.ai_fare_service import handle_smart_fare_query
            
            # 構建查詢參數
            query_params = {
                "operation": intent.operation_type.value,
                "entities": intent.entities,
                "confidence": intent.confidence
            }
            
            # TODO: 調用現有的智能車資查詢服務
            # result = handle_smart_fare_query(intent.raw_response, "ai_router", use_flex=True)
            
            return RouteResult(
                success=True,
                response_text="已完成班次查詢功能將在下階段整合",
                data=query_params
            )
            
        except Exception as e:
            logger.error(f"過去時間態路由失敗: {e}")
            return RouteResult(
                success=False,
                response_text="查詢已完成班次時發生錯誤",
                error=str(e)
            )
    
    def _route_to_present_service(self, intent: IntentResult) -> RouteResult:
        """路由到現在時間態服務（當前班次）"""
        try:
            # 構建查詢參數
            query_params = {
                "operation": intent.operation_type.value,
                "entities": intent.entities,
                "target_table": "trips"
            }
            
            # TODO: 整合現有的班次查詢功能
            # 例如：東洋班次、診所班次等
            
            return RouteResult(
                success=True,
                response_text="當前班次管理功能將在下階段整合",
                data=query_params
            )
            
        except Exception as e:
            logger.error(f"現在時間態路由失敗: {e}")
            return RouteResult(
                success=False,
                response_text="查詢當前班次時發生錯誤",
                error=str(e)
            )
    
    def _route_to_future_service(self, intent: IntentResult) -> RouteResult:
        """路由到未來時間態服務（固定班次）"""
        try:
            # 構建查詢參數
            query_params = {
                "operation": intent.operation_type.value,
                "entities": intent.entities,
                "target_table": "fixed_schedules"
            }
            
            # TODO: 整合現有的固定班次功能
            # 例如：匯入固定班次、查詢固定班次等
            
            return RouteResult(
                success=True,
                response_text="固定班次管理功能將在下階段整合",
                data=query_params
            )
            
        except Exception as e:
            logger.error(f"未來時間態路由失敗: {e}")
            return RouteResult(
                success=False,
                response_text="處理固定班次時發生錯誤",
                error=str(e)
            )
    
    def process_message(self, user_message: str) -> RouteResult:
        """處理用戶消息的主要入口"""
        try:
            logger.info(f"處理用戶消息: {user_message}")
            
            # 1. 分析意圖
            intent = self.analyze_intent(user_message)
            logger.info(f"意圖分析結果: {intent.time_perspective.value}, {intent.operation_type.value}, 信心度: {intent.confidence}")
            
            # 2. 路由到對應服務
            result = self.route_to_service(intent)
            
            # 3. 記錄結果
            logger.info(f"路由結果: 成功={result.success}, 回應={result.response_text[:100]}...")
            
            return result
            
        except Exception as e:
            logger.error(f"處理消息失敗: {e}")
            return RouteResult(
                success=False,
                response_text="系統處理請求時發生錯誤，請稍後再試。",
                error=str(e)
            )
    
    def should_use_ai_router(self, message: str) -> bool:
        """判斷是否應該使用AI路由器"""
        # 如果是精確的命令，使用傳統處理
        exact_commands = [
            "東洋班次", "診所班次", "匯入固定班次", "幫助", "資料庫同步"
        ]
        
        if message.strip() in exact_commands:
            return False
        
        # 如果包含自然語言特徵，使用AI路由器
        natural_patterns = [
            r'我要.*', r'幫我.*', r'請.*', r'可以.*', r'如何.*', r'怎麼.*',
            r'.*的.*', r'.*有.*', r'.*是.*', r'.*嗎.*'
        ]
        
        for pattern in natural_patterns:
            if re.search(pattern, message):
                return True
        
        # 如果包含複雜查詢關鍵詞，使用AI路由器
        complex_keywords = [
            "查詢", "修改", "調整", "分析", "統計", "報表", "效率"
        ]
        
        if any(keyword in message for keyword in complex_keywords):
            return True
        
        return False

# 創建全局實例
ai_router = None

def get_ai_router() -> AIRouter:
    """獲取AI路由器實例（單例模式）"""
    global ai_router
    if ai_router is None:
        ai_router = AIRouter()
    return ai_router

def test_ai_router():
    """測試AI路由器功能"""
    router = get_ai_router()
    
    test_messages = [
        "我要查詢今天的東洋班次",
        "昨天司機123的車資是多少？",
        "明天要匯入固定班次",
        "幫我修改班次#456的車資",
        "可以分析一下本週的班次效率嗎？"
    ]
    
    for message in test_messages:
        print(f"\n測試: {message}")
        try:
            result = router.process_message(message)
            print(f"結果: {result.success}, {result.response_text}")
        except Exception as e:
            print(f"錯誤: {e}")

if __name__ == "__main__":
    test_ai_router() 