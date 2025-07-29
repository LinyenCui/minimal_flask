"""
AI Agent 核心
實現思考->檢索->規劃->執行->回應的完整工作流程
"""

import json
import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
import traceback

from modules.ai_agent.tool_registry import tool_registry, ToolDefinition
from modules.ai_agent.knowledge_base import knowledge_base
# from modules.services.ai_service import get_gemini_response  # 不再需要Google API
from modules.utils.taiwan_time import get_taiwan_date, get_taiwan_time

logger = logging.getLogger(__name__)

@dataclass
class AgentThought:
    """AI代理的思考過程"""
    step: str
    content: str
    confidence: float
    timestamp: str

@dataclass
class ExecutionPlan:
    """執行計劃"""
    tools: List[str]
    parameters: List[Dict[str, Any]]
    reasoning: str
    estimated_complexity: str  # "simple", "medium", "complex"

@dataclass
class ExecutionResult:
    """執行結果"""
    tool_name: str
    parameters: Dict[str, Any]
    result: Any
    success: bool
    error_message: Optional[str] = None

@dataclass
class AgentResponse:
    """AI代理回應"""
    text: str
    execution_results: List[ExecutionResult]
    thoughts: List[AgentThought]
    success: bool
    needs_clarification: bool = False
    clarification_question: Optional[str] = None

class DispatchAgent:
    """派班AI代理"""
    
    def __init__(self):
        self.tool_registry = tool_registry
        self.knowledge_base = knowledge_base
        self.conversation_context = {}  # 對話上下文
    
    def process_request(self, user_input: str, user_id: str = None) -> AgentResponse:
        """處理用戶請求的主要入口"""
        logger.info(f"AI Agent處理請求: {user_input}")
        
        try:
            # 第一步：思考（理解用戶意圖）
            thoughts = []
            thought = self._think_about_request(user_input)
            thoughts.append(thought)
            
            # 第二步：檢索（查找相關知識）
            relevant_info = self._retrieve_relevant_info(user_input, thought)
            
            # 第三步：規劃（制定執行計劃）
            plan = self._plan_execution(user_input, thought, relevant_info)
            thoughts.append(AgentThought(
                step="planning",
                content=plan.reasoning,
                confidence=0.8,
                timestamp=datetime.now().isoformat()
            ))
            
            # 第四步：執行（使用工具完成任務）
            execution_results = self._execute_plan(plan)
            
            # 第五步：回應（生成自然語言回答）
            response_text = self._generate_response(user_input, execution_results, thoughts)
            
            # 檢查是否需要進一步澄清
            needs_clarification, clarification_question = self._check_need_clarification(
                user_input, execution_results
            )
            
            return AgentResponse(
                text=response_text,
                execution_results=execution_results,
                thoughts=thoughts,
                success=all(result.success for result in execution_results),
                needs_clarification=needs_clarification,
                clarification_question=clarification_question
            )
            
        except Exception as e:
            logger.error(f"AI Agent處理請求失敗: {str(e)}")
            traceback.print_exc()
            
            return AgentResponse(
                text=f"抱歉，處理您的請求時遇到了問題：{str(e)}",
                execution_results=[],
                thoughts=[],
                success=False
            )
    
    def _think_about_request(self, user_input: str) -> AgentThought:
        """思考用戶請求的意圖（使用回退機制）"""
        # 直接使用關鍵字分析，不依賴Google API
        keywords = self._extract_keywords(user_input)
        
        # 基於關鍵字的簡單意圖分析
        if any(keyword in user_input.lower() for keyword in ["昨天", "前天", "上週", "已完成", "完成"]):
            content = f"分析用戶請求：'{user_input}' - 這是過去時間查詢，需要查詢已完成班次記錄"
        elif "班次" in user_input:
            content = f"分析用戶請求：'{user_input}' - 這是班次查詢，提取到關鍵字：{keywords}"
        else:
            content = f"分析用戶請求：'{user_input}' - 一般查詢，關鍵字：{keywords}"
        
        return AgentThought(
            step="thinking",
            content=content,
            confidence=0.8,
            timestamp=datetime.now().isoformat()
        )
    
    def _retrieve_relevant_info(self, user_input: str, thought: AgentThought) -> Dict[str, Any]:
        """檢索相關的背景知識"""
        relevant_info = {
            "current_date": get_taiwan_date(),
            "current_time": get_taiwan_time(),
            "database_schemas": {},
            "business_rules": [],
            "examples": [],
            "available_tools": []
        }
        
        # 根據用戶輸入關鍵字檢索相關信息
        keywords = self._extract_keywords(user_input)
        
        # 檢索相關的資料庫結構
        for keyword in keywords:
            if keyword in ["班次", "trip"]:
                relevant_info["database_schemas"]["trips"] = asdict(
                    self.knowledge_base.get_schema("trips")
                )
            elif keyword in ["司機", "driver"]:
                relevant_info["database_schemas"]["drivers"] = asdict(
                    self.knowledge_base.get_schema("drivers")
                )
            elif keyword in ["固定", "schedule"]:
                relevant_info["database_schemas"]["fixed_schedules"] = asdict(
                    self.knowledge_base.get_schema("fixed_schedules")
                )
        
        # 檢索相關的業務規則
        for keyword in keywords:
            rules = self.knowledge_base.get_business_rules(keyword)
            relevant_info["business_rules"].extend([asdict(rule) for rule in rules])
        
        # 檢索相關的使用範例
        examples = self.knowledge_base.get_examples()
        relevant_info["examples"] = [asdict(example) for example in examples[:3]]  # 限制數量
        
        # 檢索可用的工具
        all_tools = self.tool_registry.get_all_tools()
        for tool_name, tool_def in all_tools.items():
            if any(keyword in tool_def.description.lower() for keyword in keywords):
                relevant_info["available_tools"].append({
                    "name": tool_name,
                    "description": tool_def.description,
                    "parameters": [asdict(param) for param in tool_def.parameters],
                    "examples": tool_def.examples
                })
        
        return relevant_info
    
    def _plan_execution(self, user_input: str, thought: AgentThought, relevant_info: Dict[str, Any]) -> ExecutionPlan:
        """制定執行計劃（使用回退機制）"""
        # 直接使用回退規劃，不依賴Google API
        return self._fallback_planning(user_input)
    
    def _execute_plan(self, plan: ExecutionPlan) -> List[ExecutionResult]:
        """執行計劃"""
        results = []
        
        for i, tool_name in enumerate(plan.tools):
            tool_def = self.tool_registry.get_tool(tool_name)
            if not tool_def:
                results.append(ExecutionResult(
                    tool_name=tool_name,
                    parameters={},
                    result=None,
                    success=False,
                    error_message=f"找不到工具: {tool_name}"
                ))
                continue
            
            parameters = plan.parameters[i] if i < len(plan.parameters) else {}
            
            try:
                # 動態調用工具
                result = self._invoke_tool(tool_def, parameters)
                
                results.append(ExecutionResult(
                    tool_name=tool_name,
                    parameters=parameters,
                    result=result,
                    success=True
                ))
                
            except Exception as e:
                logger.error(f"執行工具 {tool_name} 失敗: {str(e)}")
                results.append(ExecutionResult(
                    tool_name=tool_name,
                    parameters=parameters,
                    result=None,
                    success=False,
                    error_message=str(e)
                ))
        
        return results
    
    def _generate_response(self, user_input: str, execution_results: List[ExecutionResult], thoughts: List[AgentThought]) -> str:
        """生成自然語言回應（使用回退機制）"""
        # 直接使用回退回應，不依賴Google API
        return self._fallback_response(execution_results)
    
    def _build_thinking_prompt(self) -> str:
        """構建思考階段的系統提示"""
        return f"""你是一個專業的派班系統AI助手。你的任務是理解用戶的派班相關需求。

當前時間：{get_taiwan_time()}
當前日期：{get_taiwan_date()}

你的能力包括：
1. 查詢班次信息（東洋班次、診所班次）
2. 管理司機指派
3. 處理班次狀態
4. 記錄車資信息
5. 生成報表
6. 清理資料

請分析用戶請求，識別：
1. 用戶的具體意圖
2. 需要的信息（日期、班次ID、司機ID等）
3. 可能需要使用的工具
4. 任何不明確的地方

保持專業、準確、有幫助。"""
    
    def _build_planning_prompt(self, user_input: str, thought: AgentThought, relevant_info: Dict[str, Any]) -> str:
        """構建規劃階段的提示"""
        return f"""基於用戶請求和思考結果，制定具體的執行計劃。

用戶請求：{user_input}

思考結果：{thought.content}

可用工具：
{json.dumps(relevant_info.get('available_tools', []), ensure_ascii=False, indent=2)}

相關業務規則：
{json.dumps(relevant_info.get('business_rules', []), ensure_ascii=False, indent=2)}

請提供執行計劃，格式如下：
TOOLS: [工具名稱列表]
PARAMETERS: [對應參數列表]
REASONING: 選擇這些工具的原因

確保：
1. 選擇最合適的工具
2. 提供正確的參數
3. 考慮工具的執行順序
4. 處理可能的錯誤情況"""
    
    def _build_response_prompt(self, user_input: str, execution_results: List[ExecutionResult], thoughts: List[AgentThought]) -> str:
        """構建回應生成提示"""
        results_summary = []
        for result in execution_results:
            if result.success:
                results_summary.append(f"✅ {result.tool_name}: 成功")
            else:
                results_summary.append(f"❌ {result.tool_name}: {result.error_message}")
        
        return f"""根據執行結果，為用戶生成自然、友好的回應。

用戶原始請求：{user_input}

執行結果：
{chr(10).join(results_summary)}

詳細結果：
{json.dumps([asdict(result) for result in execution_results], ensure_ascii=False, indent=2)}

請生成：
1. 自然語言回應
2. 總結執行結果
3. 如有錯誤，提供解決建議
4. 保持專業和有幫助的語氣

不要包含技術細節，專注於用戶關心的信息。"""
    
    def _extract_keywords(self, text: str) -> List[str]:
        """提取關鍵字"""
        keywords = []
        keyword_mapping = {
            "班次": ["班次", "行程", "trip"],
            "東洋": ["東洋", "dongyang"],
            "診所": ["診所", "clinic"],
            "司機": ["司機", "driver"],
            "指派": ["指派", "assign"],
            "查詢": ["查詢", "查看", "query"],
            "匯入": ["匯入", "import"],
            "固定": ["固定", "schedule"],
            "車資": ["車資", "費用", "fare"],
            "清理": ["清理", "cleanup"]
        }
        
        text_lower = text.lower()
        for category, words in keyword_mapping.items():
            if any(word in text_lower for word in words):
                keywords.append(category)
        
        return keywords
    
    def _parse_planning_response(self, response: str) -> Tuple[List[str], List[Dict[str, Any]], str]:
        """解析規劃回應"""
        tools = []
        parameters = []
        reasoning = ""
        
        try:
            lines = response.split('\n')
            current_section = None
            
            for line in lines:
                line = line.strip()
                
                if line.startswith("TOOLS:"):
                    current_section = "tools"
                    tools_str = line.replace("TOOLS:", "").strip()
                    if tools_str.startswith("[") and tools_str.endswith("]"):
                        tools = json.loads(tools_str)
                    
                elif line.startswith("PARAMETERS:"):
                    current_section = "parameters"
                    params_str = line.replace("PARAMETERS:", "").strip()
                    if params_str.startswith("[") and params_str.endswith("]"):
                        parameters = json.loads(params_str)
                
                elif line.startswith("REASONING:"):
                    current_section = "reasoning"
                    reasoning = line.replace("REASONING:", "").strip()
                
                elif current_section == "reasoning" and line:
                    reasoning += " " + line
            
        except Exception as e:
            logger.error(f"解析規劃回應失敗: {str(e)}")
            # 回退到簡單解析
            if "query" in response.lower():
                tools = ["query_dongyang_trips"]
                parameters = [{"date": "today"}]
                reasoning = "基於關鍵字匹配的回退規劃"
        
        return tools, parameters, reasoning
    
    def _fallback_planning(self, user_input: str) -> ExecutionPlan:
        """回退規劃（關鍵字匹配）"""
        text_lower = user_input.lower()
        
        # 首先檢測時間態
        past_time_keywords = ["昨天", "前天", "上週", "上個月", "已完成", "完成的"]
        is_past_time = any(keyword in text_lower for keyword in past_time_keywords)
        
        # 如果是過去時間，優先選擇已完成班次查詢
        if is_past_time and "班次" in text_lower:
            return ExecutionPlan(
                tools=["query_completed_trips"],
                parameters=[{"message_text": user_input}],
                reasoning="關鍵字匹配：過去時間班次查詢",
                estimated_complexity="simple"
            )
        
        # 其他情況按原邏輯
        if "東洋" in text_lower and "班次" in text_lower:
            return ExecutionPlan(
                tools=["query_dongyang_trips"],
                parameters=[{"date": "today"}],
                reasoning="關鍵字匹配：東洋班次查詢",
                estimated_complexity="simple"
            )
        elif "診所" in text_lower and "班次" in text_lower:
            return ExecutionPlan(
                tools=["query_clinic_trips"],
                parameters=[{"date": "today"}],
                reasoning="關鍵字匹配：診所班次查詢",
                estimated_complexity="simple"
            )
        else:
            return ExecutionPlan(
                tools=[],
                parameters=[],
                reasoning="無法識別具體需求",
                estimated_complexity="simple"
            )
    
    def _invoke_tool(self, tool_def: ToolDefinition, parameters: Dict[str, Any]) -> Any:
        """動態調用工具"""
        try:
            # 導入模組
            module_parts = tool_def.handler_module.split('.')
            module = __import__(tool_def.handler_module, fromlist=[module_parts[-1]])
            
            # 獲取函數
            handler_func = getattr(module, tool_def.handler_function)
            
            # 調用函數
            if parameters:
                # 構建調用參數
                call_params = self._build_call_parameters(tool_def, parameters)
                return handler_func(**call_params)
            else:
                return handler_func()
                
        except Exception as e:
            logger.error(f"調用工具 {tool_def.name} 失敗: {str(e)}")
            raise
    
    def _build_call_parameters(self, tool_def: ToolDefinition, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """構建函數調用參數"""
        call_params = {}
        
        # 根據工具類型處理參數
        if tool_def.name in ["query_dongyang_trips", "query_clinic_trips"]:
            # 查詢類工具，需要構建message_text
            date_param = parameters.get("date", "today")
            if date_param == "today":
                call_params["message_text"] = "東洋班次" if "dongyang" in tool_def.name else "診所班次"
            else:
                call_params["message_text"] = f"{'東洋班次' if 'dongyang' in tool_def.name else '診所班次'} {date_param}"
        
        elif tool_def.name == "get_trip_details":
            trip_id = parameters.get("trip_id")
            call_params["message_text"] = f"班次詳情 {trip_id}"
        
        elif tool_def.name == "assign_driver":
            trip_id = parameters.get("trip_id")
            driver_id = parameters.get("driver_id")
            if driver_id:
                call_params["message_text"] = f"指派司機 {trip_id} {driver_id}"
            else:
                call_params["message_text"] = f"指派司機 {trip_id}"
        
        elif tool_def.name == "query_completed_trips":
            # 增強版查詢已完成班次工具，支援直接參數傳遞
            date_param = parameters.get("date")
            driver_id = parameters.get("driver_id")
            category = parameters.get("category")
            
            # 處理自然語言日期轉換
            from modules.utils.taiwan_time import get_taiwan_date
            from datetime import timedelta
            
            actual_date = None
            if date_param:
                if date_param.lower() in ["today", "今天"]:
                    actual_date = get_taiwan_date()
                elif date_param.lower() in ["yesterday", "昨天"]:
                    actual_date = get_taiwan_date() - timedelta(days=1)
                elif date_param.lower() in ["前天"]:
                    actual_date = get_taiwan_date() - timedelta(days=2)
                elif date_param.lower() in ["tomorrow", "明天"]:
                    actual_date = get_taiwan_date() + timedelta(days=1)
                else:
                    # 嘗試解析其他日期格式
                    try:
                        from modules.utils.unified_date_parser import parse_date_input
                        actual_date = parse_date_input(date_param)
                    except:
                        actual_date = get_taiwan_date()  # 回退到今天
            
            # 構建message_text用於舊版兼容
            message_parts = ["查已完成"]
            if date_param and date_param not in ["today", "今天"]:
                message_parts.append(date_param)
            if category:
                message_parts.append(category)
            
            call_params["message_text"] = " ".join(message_parts)
            
            # 同時傳遞直接參數給增強版函數
            if actual_date:
                call_params["date"] = actual_date
            if driver_id:
                call_params["driver_id"] = driver_id
            if category:
                call_params["category"] = category
        
        else:
            # 其他工具，直接傳遞參數
            call_params = parameters
        
        return call_params
    
    def _check_need_clarification(self, user_input: str, execution_results: List[ExecutionResult]) -> Tuple[bool, Optional[str]]:
        """檢查是否需要進一步澄清"""
        # 如果所有工具都執行失敗，可能需要澄清
        if all(not result.success for result in execution_results):
            return True, "我沒有完全理解您的需求，能否請您提供更多詳細信息？"
        
        # 如果沒有執行任何工具，可能需要澄清
        if not execution_results:
            return True, "我不確定如何幫助您，請描述您想要做什麼？"
        
        return False, None
    
    def _fallback_response(self, execution_results: List[ExecutionResult]) -> str:
        """回退回應生成"""
        if not execution_results:
            return "抱歉，我無法理解您的請求。請提供更多詳細信息。"
        
        success_count = sum(1 for result in execution_results if result.success)
        total_count = len(execution_results)
        
        if success_count == total_count:
            return f"已完成您的請求，執行了 {total_count} 個操作。"
        elif success_count > 0:
            return f"部分完成您的請求，{success_count}/{total_count} 個操作成功。"
        else:
            return "抱歉，無法完成您的請求，所有操作都失敗了。"

# 全局AI代理實例
dispatch_agent = DispatchAgent() 