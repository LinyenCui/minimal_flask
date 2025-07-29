"""
AI路由器
負責判斷用戶請求是否應該使用AI Agent處理，或者回退到傳統處理方式
"""

import logging
import re
from typing import Optional, Tuple, Dict, Any
from dataclasses import dataclass

from modules.ai_agent.agent_core import dispatch_agent
from modules.utils.line_bot import reply_text, reply_flex
from modules.utils.taiwan_time import get_taiwan_time, get_taiwan_date

logger = logging.getLogger(__name__)

@dataclass
class RoutingDecision:
    """路由決策"""
    use_ai_agent: bool
    confidence: float
    reasoning: str
    fallback_handler: Optional[str] = None

class AIRouter:
    """AI路由器"""
    
    def __init__(self):
        # AI Agent觸發關鍵字（自然語言模式）
        self.ai_triggers = [
            # 自然語言查詢
            "今天有什麼班次",
            "明天東洋班次",
            "有沒有診所班次",
            "班次狀況",
            "司機安排",
            
            # 複合請求
            "幫我查一下",
            "幫我看看",
            "請問",
            "想知道",
            "需要",
            
            # 問題形式
            "什麼時候",
            "誰負責",
            "如何",
            "為什麼",
            "哪裡",
            "怎麼",
            
            # 情境描述
            "我要",
            "我想",
            "可以",
            "能不能",
            "是否",
            
            # 時間表達
            "等等",
            "稍後",
            "一會兒",
            "下午",
            "晚上",
            "週末"
        ]
        
        # 傳統命令（精確匹配）
        self.traditional_commands = [
            "東洋班次",
            "診所班次",
            "查已完成",
            "班次詳情",
            "指派司機",
            "指派",
            "記錄車資",
            "修改類別",
            "生成周報表",
            "生成週報表",
            "匯入固定班次",
            "清理trips",
            "批量加成",
            "幫助",
            "幫助文字",
            "固定班次請假",
            "固定班次恢復",
            "固定班表"
        ]
        
        # 複雜場景（一定使用AI）
        self.complex_scenarios = [
            "但是",
            "不過",
            "然而",
            "另外",
            "同時",
            "除了",
            "而且",
            "或者",
            "如果",
            "假如",
            "萬一",
            "既然",
            "因為",
            "由於"
        ]
    
    def should_use_ai_agent(self, message_text: str, user_id: str = None) -> RoutingDecision:
        """判斷是否應該使用AI Agent"""
        
        # 1. 檢查是否是精確的傳統命令
        if self._is_traditional_command(message_text):
            return RoutingDecision(
                use_ai_agent=False,
                confidence=0.9,
                reasoning="精確匹配傳統命令格式",
                fallback_handler="traditional"
            )
        
        # 2. 檢查是否包含過去時間表達（優先處理）
        text_lower = message_text.lower()
        past_time_keywords = ["昨天", "前天", "上週", "上個月", "已完成", "完成的"]
        has_past_time = any(keyword in text_lower for keyword in past_time_keywords)
        
        if has_past_time and "班次" in text_lower:
            return RoutingDecision(
                use_ai_agent=True,
                confidence=0.9,
                reasoning="過去時間查詢，需要AI處理已完成班次",
                fallback_handler="ai_agent"
            )
        
        # 3. 檢查是否包含複雜場景關鍵字
        if self._has_complex_scenario(message_text):
            return RoutingDecision(
                use_ai_agent=True,
                confidence=0.95,
                reasoning="檢測到複雜場景，需要AI推理",
                fallback_handler="ai_agent"
            )
        
        # 4. 檢查是否包含自然語言觸發詞
        ai_score = self._calculate_ai_score(message_text)
        if ai_score > 0.6:
            return RoutingDecision(
                use_ai_agent=True,
                confidence=ai_score,
                reasoning="自然語言表達，適合AI處理",
                fallback_handler="ai_agent"
            )
        
        # 5. 檢查是否是多步驟請求
        if self._is_multi_step_request(message_text):
            return RoutingDecision(
                use_ai_agent=True,
                confidence=0.8,
                reasoning="多步驟請求，需要AI規劃",
                fallback_handler="ai_agent"
            )
        
        # 6. 檢查是否包含時間和條件邏輯
        if self._has_temporal_logic(message_text):
            return RoutingDecision(
                use_ai_agent=True,
                confidence=0.75,
                reasoning="包含時間邏輯，需要AI理解",
                fallback_handler="ai_agent"
            )
        
        # 7. 默認情況：如果不確定，使用傳統處理
        return RoutingDecision(
            use_ai_agent=False,
            confidence=0.3,
            reasoning="無明確AI觸發條件，使用傳統處理",
            fallback_handler="traditional"
        )
    
    def route_message(self, message_text: str, reply_token: str, user_id: str = None) -> bool:
        """路由消息到適當的處理器"""
        
        decision = self.should_use_ai_agent(message_text, user_id)
        
        logger.info(f"路由決策: {decision.reasoning} (信心度: {decision.confidence})")
        
        if decision.use_ai_agent:
            try:
                # 使用AI Agent處理
                logger.info(f"使用AI Agent處理: {message_text}")
                
                response = dispatch_agent.process_request(message_text, user_id)
                
                if response.success:
                    # 成功處理，回復用戶
                    self._send_ai_response(reply_token, response)
                    return True
                else:
                    # AI處理失敗，回退到傳統處理
                    logger.warning(f"AI Agent處理失敗，回退到傳統處理: {response.text}")
                    return False
                    
            except Exception as e:
                logger.error(f"AI Agent處理出錯: {str(e)}")
                # 發送錯誤回復
                reply_text(reply_token, f"AI處理出現問題，請稍後再試或使用具體命令。")
                return True
        
        else:
            # 不使用AI Agent，讓傳統處理器處理
            return False
    
    def _is_traditional_command(self, message_text: str) -> bool:
        """檢查是否是傳統命令"""
        text_stripped = message_text.strip()
        
        # 精確匹配
        if text_stripped in self.traditional_commands:
            return True
        
        # 帶參數的命令匹配
        traditional_patterns = [
            r'^東洋班次\s*\d*\s*$',  # 東洋班次 [日期]
            r'^診所班次\s*\d*\s*$',  # 診所班次 [日期]
            r'^班次詳情\s+\d+$',     # 班次詳情 ID
            r'^指派司機\s+\d+\s+\d+$',  # 指派司機 ID ID
            r'^指派\s+\d+$',         # 指派 ID
            r'^記錄車資\s+\d+\s+\d+',  # 記錄車資 ID 金額
            r'^修改類別\s+\d+\s+\w+$',  # 修改類別 ID 類別
            r'^匯入固定班次\s+\w+',    # 匯入固定班次 週次
            r'^清理trips\s+\w+$',     # 清理trips 選項
            r'^固定班次請假\s+\d+',    # 固定班次請假 ID
            r'^固定班次恢復\s+\d+$',   # 固定班次恢復 ID
            r'^固定班表\s+\w+$',      # 固定班表 客戶
        ]
        
        for pattern in traditional_patterns:
            if re.match(pattern, text_stripped):
                return True
        
        return False
    
    def _has_complex_scenario(self, message_text: str) -> bool:
        """檢查是否包含複雜場景"""
        text_lower = message_text.lower()
        
        # 檢查複雜場景關鍵字
        for keyword in self.complex_scenarios:
            if keyword in text_lower:
                return True
        
        # 檢查多個實體
        entity_count = 0
        entities = ["班次", "司機", "時間", "日期", "地點", "客戶"]
        for entity in entities:
            if entity in text_lower:
                entity_count += 1
        
        return entity_count >= 2
    
    def _calculate_ai_score(self, message_text: str) -> float:
        """計算AI處理分數"""
        text_lower = message_text.lower()
        score = 0.0
        
        # 自然語言觸發詞匹配
        for trigger in self.ai_triggers:
            if trigger in text_lower:
                score += 0.3
        
        # 問句特徵
        question_indicators = ["？", "?", "嗎", "呢", "吧", "什麼", "哪", "怎麼", "如何"]
        for indicator in question_indicators:
            if indicator in text_lower:
                score += 0.2
        
        # 自然語言特徵
        natural_features = ["請", "幫", "能", "可以", "想", "要", "希望", "需要"]
        for feature in natural_features:
            if feature in text_lower:
                score += 0.15
        
        # 時間表達（增強版）
        time_expressions = ["今天", "明天", "昨天", "後天", "前天", "現在", "等等", "稍後"]
        past_time_expressions = ["昨天", "前天", "上週", "上個月", "之前"]  # 過去時間強烈觸發AI
        
        for expr in time_expressions:
            if expr in text_lower:
                score += 0.1
        
        # 過去時間表達額外加分（因為需要查詢已完成班次）
        for expr in past_time_expressions:
            if expr in text_lower:
                score += 0.3
        
        # 長度獎勵（較長的句子更可能是自然語言）
        if len(message_text) > 15:
            score += 0.1
        if len(message_text) > 25:
            score += 0.1
        
        return min(score, 1.0)  # 限制在1.0以內
    
    def _is_multi_step_request(self, message_text: str) -> bool:
        """檢查是否是多步驟請求"""
        text_lower = message_text.lower()
        
        # 連接詞
        connectors = ["然後", "接著", "之後", "再", "還", "另外", "同時", "並且"]
        for connector in connectors:
            if connector in text_lower:
                return True
        
        # 多個動詞
        verbs = ["查", "看", "指派", "修改", "記錄", "生成", "匯入", "清理"]
        verb_count = sum(1 for verb in verbs if verb in text_lower)
        
        return verb_count >= 2
    
    def _has_temporal_logic(self, message_text: str) -> bool:
        """檢查是否包含時間邏輯"""
        text_lower = message_text.lower()
        
        # 時間條件
        temporal_conditions = [
            "如果.*時間", "當.*時候", "在.*之前", "在.*之後", 
            "等到", "直到", "從.*到", "期間", "之間"
        ]
        
        for condition in temporal_conditions:
            if re.search(condition, text_lower):
                return True
        
        # 時間比較
        time_comparisons = ["早於", "晚於", "之前", "之後", "比較"]
        for comparison in time_comparisons:
            if comparison in text_lower:
                return True
        
        return False
    
    def _send_ai_response(self, reply_token: str, response) -> None:
        """發送AI回應"""
        
        # 優先發送主要回應
        if response.text:
            reply_text(reply_token, response.text)
        
        # 如果有執行結果且是Flex消息，嘗試發送
        for result in response.execution_results:
            if result.success and result.result:
                # 檢查是否是Flex消息格式
                if isinstance(result.result, tuple) and len(result.result) == 2:
                    flex_content, alt_text = result.result
                    if flex_content:
                        try:
                            reply_flex(reply_token, alt_text or "查詢結果", flex_content)
                        except Exception as e:
                            logger.error(f"發送Flex消息失敗: {str(e)}")
                
                # 檢查是否是純文本結果
                elif isinstance(result.result, str):
                    # 如果主要回應已經包含了這個信息，就不重複發送
                    if result.result not in response.text:
                        reply_text(reply_token, result.result)
        
        # 如果需要澄清，發送澄清問題
        if response.needs_clarification and response.clarification_question:
            reply_text(reply_token, response.clarification_question)

# 全局AI路由器實例
ai_router = AIRouter() 