#!/usr/bin/env python3
"""
智能助手系統 - 真正的AI版本
使用Gemini API進行自然語言理解，提供完整的智能用戶體驗
"""
import logging
import json
import os
from typing import Dict, Optional
from modules.services.intelligent_command_parser import parse_user_command
from modules.services.contextual_guidance_system import provide_smart_guidance

# Gemini API imports
try:
    import vertexai
    from vertexai.generative_models import GenerativeModel, GenerationConfig
    GEMINI_AVAILABLE = True
    logger = logging.getLogger(__name__)
    logger.info("✅ Gemini API 可用")
except ImportError as e:
    GEMINI_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning(f"❌ Gemini API 不可用: {e}")

class SmartAssistant:
    """真正的AI智能助手 - 使用Gemini進行自然語言理解"""
    
    def __init__(self):
        self.model = None
        self.ai_enabled = self._initialize_ai()
        
    def _initialize_ai(self) -> bool:
        """初始化AI模型"""
        if not GEMINI_AVAILABLE:
            logger.warning("Gemini API 不可用，使用傳統解析")
            return False
            
        try:
            # 從環境變數獲取配置
            project_id = os.getenv('GCP_PROJECT_ID', 'chrome-flight-458709-d1')
            location = os.getenv('GCP_LOCATION', 'us-central1')
            model_name = os.getenv('GEMINI_MODEL', 'gemini-2.0-flash-001')
            
            # 初始化 Vertex AI
            vertexai.init(project=project_id, location=location)
            
            # 初始化 Gemini 模型
            self.model = GenerativeModel(model_name)
            
            logger.info(f"✅ Gemini AI 初始化成功: {model_name}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Gemini AI 初始化失敗: {e}")
            return False
    
    def _build_ai_prompt(self, user_input: str) -> str:
        """構建AI分析prompt - 整合完整系統知識庫與生產線思維"""
        # 導入系統知識庫
        from modules.services.system_knowledge_base import (
            DATABASE_SCHEMA, TIME_PERSPECTIVES, AVAILABLE_FUNCTIONS, 
            CONDITION_PARSING_RULES, QUERY_EXAMPLES
        )
        
        return f"""你是一個專業的派班系統AI專家。你擁有完整的系統知識，能夠理解複雜的自然語言查詢並生成準確的系統命令。

## 🏭 系統核心概念：生產線思維

**將班次管理系統理解為一條日夜不停的生產線：**

### 🔄 生產線流程架構
- **產品 = 班次記錄**：每個班次都是生產線上的一個產品
- **生產線 = trips表**：所有匯入的班次在這裡"流動執行"  
- **自動化機制**：執行時間到達時，班次會自動從trips"掉入"completed_trips
- **品質控制**：工作人員(用戶)可在產品掉入已完成前進行干預

### 🎯 三時間態 = 生產線的三個區域

**🏗️ 未來態 (整備區域)**
- **資料表**: fixed_schedules, customers 等
- **本質**: 為生產線準備"原料"和"模板"
- **功能**: 客戶資料、固定班次模板、基礎設定
- **比喻**: 工廠的原料倉庫和生產模板區
- **關鍵字**: 匯入、安排、固定班次、模板、準備

**⚡ 現在態 (生產線區域)** 
- **資料表**: trips (生產線主體)
- **本質**: 產品正在生產線上"流動執行"
- **狀態流**: 待派 → 準備 → (執行時間到達) → 自動掉入過去態
- **工作人員干預**:
  * 請假：標記瑕疵但讓產品繼續跑完流程(狀態還是準備)
  * 取消/衝突：直接從生產線拿掉，防止掉入已完成
  * 30分鐘前修改：最後調整機會
- **關鍵字**: 今天、當前、狀態、待派、準備、正在進行

**📦 過去態 (成品倉庫)**
- **資料表**: completed_trips
- **本質**: 已完成的"產品"，存放在成品倉庫
- **特點**: 記錄車資、收入、統計資料
- **用途**: 歷史查詢、收入分析、績效統計
- **關鍵字**: 昨天、已完成、車資、收入、歷史、統計

## 📊 資料庫結構知識

### trips表 (現在時間態 - 生產線主體)
- trip_id: 班次編號 (主鍵，注意不是id)
- date: 班次日期  
- category: 班次類別 (東洋、診所、臨時)
- driver_id: 司機編號
- status: 班次狀態 (待派、準備、已完成、取消)
- start_point, end_point: 起點終點
- passenger_leave_reason: 請假原因(障眼法機制)

### completed_trips表 (過去時間態 - 成品倉庫)  
- id: 記錄編號
- date: 完成日期
- category: 班次類別 (東洋、診所、臨時)
- driver_id: 司機編號
- meter_fare: 錶價金額
- extra_fare: 加成金額
- total_amount: 總金額 = meter_fare + extra_fare
- start_point, end_point: 起點終點

### fixed_schedules表 (未來時間態 - 整備區域)
- id: 模板編號
- category: 班次類別
- driver_id: 預設司機編號  
- status: 模板狀態 (準備、請假)

## 🎯 生產線流程智能路由

**🔍 現在態查詢** (關鍵字: 今天、司機5386所有班次、狀態查詢)
→ 查詢生產線上正在流動的產品
→ 主要查詢 trips 表
→ 支援司機篩選、狀態篩選、當日班次查看
→ **重要**: "明天司機5386所有班次" = 查詢明天已匯入的班次(在生產線上的)

**📈 過去態查詢** (關鍵字: 昨天、已完成、車資、收入、歷史)
→ 查詢成品倉庫中的完成記錄
→ 主要查詢 completed_trips 表
→ 支援複雜條件：金額篩選、司機績效、收入統計

**🏗️ 未來態操作** (關鍵字: 匯入、安排、固定班次模板)
→ 操作整備區域的原料和模板
→ 主要操作 fixed_schedules 表
→ 支援班次匯入、模板管理

## 🧠 複雜條件解析能力

### 金額條件 (適用於 completed_trips - 成品倉庫)
- "金額大於200" → WHERE (meter_fare + extra_fare) > 200
- "錶價小於300" → WHERE meter_fare < 300  
- "加成等於80" → WHERE extra_fare = 80

### 狀態條件 (適用於 trips - 生產線)
- "狀態為待派" → WHERE status = '待派'
- "找待派的班次" → WHERE status = '待派'
- "未完成的班次" → WHERE status IN ('待派', '準備')

⚠️ **重要：生產線品質控制原則**
- 系統有5種狀態：待派、準備、已完成、取消、衝突
- 直接生成標準命令，讓查詢處理器正常處理
- 例如："查狀態為衝突的班次" → 直接生成 "查詢班次 狀態=衝突"

### 司機條件 (跨所有區域)
- "司機533" → WHERE driver_id = 533
- "司機5386的班次" → WHERE driver_id = 5386
- **重要**: "明天司機5386所有班次" → 查詢trips表中明天日期的該司機班次

### 類別條件  
- "診所班次" → WHERE category = '診所'
- "東洋班次" → WHERE category IN ('東洋', '臨時')

### 日期條件
- "今天" → WHERE date = CURRENT_DATE
- "昨天" → WHERE date = CURRENT_DATE - INTERVAL '1 day'
- "明天" → WHERE date = CURRENT_DATE + INTERVAL '1 day'

## 📝 標準命令格式

### 生產線查詢命令
- "東洋班次 [日期]" - 查詢生產線上的東洋/臨時班次
- "診所班次 [日期]" - 查詢生產線上的診所班次
- "班次詳情 [ID]" - 查詢特定產品詳情

### 複雜生產線查詢 (重要!)
- "查已完成 [條件]" - 查詢成品倉庫，支援所有複雜條件
- "查詢班次 [條件]" - 查詢生產線狀態，支援狀態篩選

### 生產線管理命令
- "指派司機 [班次ID] [司機編號]" - 分配工作人員
- "記錄車資 [班次ID] [錶價] [加成]" - 記錄成品價值
- "匯入固定班次 [週次]" - 從整備區投入新產品

## 🔍 查詢範例學習

範例1: "明天司機5386所有班次"
生產線分析: 查詢明天已匯入到生產線上的該司機所有產品
時間態: 現在 (生產線上的產品，無論是今天還是明天)
目標表: trips
命令: "查詢班次 明天 司機5386"

範例2: "今天金額大於200的診所班次"  
生產線分析: 查詢成品倉庫中今天完成的高價值診所產品
時間態: 過去 (金額查詢屬於已完成產品)
目標表: completed_trips
命令: "查已完成 今天 診所 金額>200"

範例3: "找狀態為待派的班次"
生產線分析: 查詢生產線上等待工作人員分配的產品
時間態: 現在 (生產線狀態管理)
目標表: trips
命令: "查詢班次 狀態=待派"

範例4: "司機5386昨天東洋班次的金額總和" ⭐ 重要聚合查詢
生產線分析: 查詢成品倉庫中該司機昨天東洋班次的金額統計
時間態: 過去 (金額統計屬於已完成產品)
目標表: completed_trips  
命令: "統計金額 昨天 司機5386 東洋"
特殊處理: 需要聚合計算(SUM)，返回總和數字而非班次列表

範例5: "7/14司機5386班次" ⭐ 關鍵：過去具體日期查詢
生產線分析: 查詢7/14(過去日期)該司機的班次，這些班次應該已執行完畢
時間態: 過去 (過去日期的班次已掉入成品倉庫)
目標表: completed_trips
命令: "查已完成 7/14 司機5386"
重要提醒: 過去的具體日期(非今天)都查completed_trips，不管有無金額關鍵字

範例6: "今天診所班次總收入"
生產線分析: 統計今天診所班次的總金額收入
時間態: 過去 (收入統計)
目標表: completed_trips
命令: "統計金額 今天 診所"

範例7: "昨天司機123的車資總和是多少"
生產線分析: 查詢成品倉庫中該司機昨天的總金額
時間態: 過去 (金額統計)
目標表: completed_trips
命令: "統計金額 昨天 司機123"

範例8: "昨天司機533診所班次" ⭐ 重要：過去相對日期查詢  
生產線分析: 查詢昨天該司機診所班次，無金額關鍵字但是過去日期
時間態: 過去 (昨天的班次已執行完畢)
目標表: completed_trips
命令: "查已完成 昨天 司機533 診所"

範例9: "我想修改班次2014的車資" ⭐ 重要：自然語言車資修改
生產線分析: 用戶希望修改成品倉庫中班次2014的車資金額
時間態: 過去 (車資修改針對已完成班次)
目標表: completed_trips
命令: "記錄車資 2014"
說明: 先顯示當前車資，然後引導用戶輸入新的錶價和加成

範例10: "修改班次2014錶價280加成-50" ⭐ 具體車資修改
生產線分析: 修改成品倉庫中班次2014的具體車資數值
時間態: 過去 (車資記錄屬於已完成產品)
目標表: completed_trips
命令: "記錄車資 2014 280 -50"

範例11: "班次1990的車資改成錶價350" ⭐ 自然語言車資修改
生產線分析: 修改已完成班次的錶價，加成保持原值或設為0
時間態: 過去 (車資記錄)
目標表: completed_trips
命令: "記錄車資 1990 350 0"

範例12: "幫我調整#2015的費用，錶價400，減免100" ⭐ 自然對話式修改
生產線分析: 調整已完成班次的車資，減免表示負加成
時間態: 過去 (費用調整針對已完成班次)
目標表: completed_trips
命令: "記錄車資 2015 400 -100"

⭐ **關鍵時間態判斷規則**：
1. **明天/未來日期** → 查生產線(trips) → "查詢班次"命令
2. **今天** → 看是否有金額/統計關鍵字決定
3. **昨天/過去日期** → 查成品倉庫(completed_trips) → "查已完成"命令  
4. **具體過去日期(7/14, 6/20等)** → 查成品倉庫(completed_trips) → "查已完成"命令

⭐ 關鍵提示：當用戶詢問「總和」、「總計」、「收入」、「總金額」時，必須生成「統計金額」命令，而不是「查已完成」命令！

## ⚡ 分析任務

🎯 **生產線管理決策原則**
1. **流程優先**: 理解生產線的自動化流程和工作人員干預機制
2. **直接執行**: 能生成標準命令的都直接執行，不要過度謹慎
3. **錯誤後處理**: 遇到無效參數直接生成命令，讓查詢處理器報錯
4. **只在真正模糊時才澄清**: 只有完全無法判斷意圖時才設 needs_clarification=true
5. **容錯處理**: "查狀態為X" 和 "狀態為X" 應該有相同的處理結果

用戶輸入: "{user_input}"

請仔細分析並回應JSON格式結果：

{{
    "intent_type": "query|modify|create|help|unknown",
    "confidence": 0.95,
    "time_perspective": "past|present|future",
    "production_line_area": "整備區域|生產線|成品倉庫",
    "target_table": "trips|completed_trips|fixed_schedules",
    "target_function": "具體功能名稱",
    "standard_command": "完全符合系統格式的標準命令",
    "extracted_conditions": {{
        "date": "提取的日期條件",
        "driver_id": "司機編號",
        "category": "班次類別", 
        "status": "班次狀態",
        "amount_condition": "金額條件",
        "other_conditions": "其他條件"
    }},
    "sql_logic": "對應的SQL邏輯說明",
    "needs_clarification": false,
    "clarification_question": "需要澄清的問題",
    "suggested_actions": ["建議的操作1", "建議的操作2"],
    "reasoning": "詳細的分析推理過程，說明如何用生產線思維理解用戶意圖並選擇命令"
}}"""
    
    def _analyze_with_ai(self, user_input: str) -> Dict:
        """使用Gemini AI分析用戶輸入"""
        try:
            logger.info(f"🤖 使用Gemini分析: {user_input}")
            
            prompt = self._build_ai_prompt(user_input)
            
            generation_config = GenerationConfig(
                temperature=0.2,
                top_p=0.8,
                top_k=40,
                max_output_tokens=1024,
            )
            
            response = self.model.generate_content(
                prompt,
                generation_config=generation_config
            )
            
            if response.candidates and response.candidates[0].content.parts:
                text_response = response.candidates[0].content.parts[0].text
                
                # 提取JSON
                import re
                json_match = re.search(r'\{.*\}', text_response, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                    ai_result = json.loads(json_str)
                    logger.info(f"✅ AI分析成功: 信心度={ai_result.get('confidence', 0)}")
                    return ai_result
            
            logger.warning("AI回應格式異常，使用傳統解析")
            return None
            
        except Exception as e:
            logger.error(f"❌ AI分析失敗: {e}")
            return None
    
    def process_user_message(self, user_input: str, user_id: str) -> Dict:
        """智能處理用戶消息 - AI增強版"""
        logger.info(f"🤖 智能助手處理: {user_input}")
        
        # 步驟1: 嘗試AI分析（如果可用）
        ai_result = None
        if self.ai_enabled:
            ai_result = self._analyze_with_ai(user_input)
        
        if ai_result and ai_result.get('confidence', 0) > 0.3:  # 🔥 降低門檻從0.6到0.3
            logger.info(f"✅ AI分析成功，信心度: {ai_result['confidence']}")
            
            # 🔥 移除澄清邏輯，直接執行！
            # AI理解成功，執行標準命令
            if ai_result.get('standard_command'):
                return {
                    "type": "execute_command",
                    "command": ai_result['standard_command'],
                    "original_input": user_input,
                    "confidence": ai_result['confidence'],
                    "ai_reasoning": ai_result.get('reasoning', ''),
                    "entities": ai_result.get('entities', {})
                }
        
        # 步驟2: AI失敗時，回退到傳統智能解析
        logger.info("回退到傳統智能解析")
        parse_result = parse_user_command(user_input)
        
        if parse_result["success"]:
            logger.info(f"✅ 傳統解析成功: {parse_result['standard_command']}")
            
            # 檢查是否需要上下文引導
            guidance = provide_smart_guidance(user_input, user_id)
            
            if guidance["should_guide"]:
                return {
                    "type": "smart_guidance",
                    "guidance": guidance,
                    "parsed_command": parse_result,
                    "should_execute_command": False
                }
            else:
                return {
                    "type": "execute_command", 
                    "command": parse_result["standard_command"],
                    "original_input": user_input,
                    "confidence": parse_result["confidence"]
                }
        else:
            # 完全無法理解，提供一般性建議
            logger.info(f"❓ 無法理解，提供一般性建議")
            guidance = provide_smart_guidance(user_input, user_id)
            
            if guidance["should_guide"]:
                return {
                    "type": "smart_guidance",
                    "guidance": guidance,
                    "should_execute_command": False
                }
            else:
                return {
                    "type": "general_suggestion",
                    "suggestions": self._get_intelligent_suggestions(user_input),
                    "original_input": user_input
                }
    
    def _get_intelligent_suggestions(self, user_input: str) -> list:
        """根據用戶輸入提供智能建議"""
        suggestions = [
            "💡 嘗試說「東洋班次」查看班次",
            "💡 嘗試說「今天診所班次」查看診所安排", 
            "💡 嘗試說「匯入固定班次 本週」匯入班次",
            "💡 輸入「幫助」查看完整功能列表"
        ]
        
        # 根據關鍵詞提供相關建議
        if any(word in user_input for word in ['查', '看', '查詢']):
            suggestions.insert(0, "💡 嘗試更具體：「今天東洋班次」或「司機123今天班次」")
        elif any(word in user_input for word in ['匯入', '導入', '固定']):
            suggestions.insert(0, "💡 嘗試：「匯入固定班次 本週」或「匯入固定班次 下週」")
        elif any(word in user_input for word in ['司機', '指派']):
            suggestions.insert(0, "💡 嘗試：「指派司機 [班次ID] [司機編號]」")
            
        return suggestions[:3]
    
    def format_smart_response(self, process_result: Dict) -> str:
        """格式化智能回應"""
        response_type = process_result["type"]
        
        if response_type == "ai_clarification":
            return f"""🤖 AI需要澄清

💬 「{process_result['original_input']}」
❓ {process_result['question']}

💡 建議：
{chr(10).join(f"• {action}" for action in process_result.get('suggestions', []))}

信心度：{process_result.get('confidence', 0):.1%}"""
            
        elif response_type == "smart_guidance":
            return self._format_guidance_response(process_result["guidance"])
            
        elif response_type == "general_suggestion":
            suggestions = process_result.get("suggestions", [])
            return f"""🤔 我無法理解您的請求

💬 「{process_result['original_input']}」

{chr(10).join(suggestions)}"""
            
        elif response_type == "execute_command":
            ai_info = ""
            if "ai_reasoning" in process_result:
                ai_info = f"\n🧠 AI理解：{process_result['ai_reasoning']}"
            
            return f"✅ 理解您的請求{ai_info}\n正在執行：{process_result['command']}"
            
        else:
            return "❓ 抱歉，我無法理解您的請求。"
    
    def _format_guidance_response(self, guidance: Dict) -> str:
        """格式化引導回應"""
        guidance_text = guidance.get("message", "")
        if guidance.get("options"):
            guidance_text += "\n\n" + "\n".join(f"• {option}" for option in guidance["options"])
        return guidance_text

# 全域實例
smart_assistant = SmartAssistant()

def process_with_smart_assistant(user_input: str, user_id: str) -> Dict:
    """使用真正的AI智能助手處理用戶消息"""
    return smart_assistant.process_user_message(user_input, user_id)

def format_smart_response(process_result: Dict) -> str:
    """格式化智能回應的便捷函數"""
    return smart_assistant.format_smart_response(process_result) 