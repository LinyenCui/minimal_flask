#!/usr/bin/env python3
"""
真正的AI增強車資查詢服務
使用Gemini API進行自然語言理解和SQL生成
"""
import logging
import json
import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from modules.models.base import db
from modules.utils.taiwan_time import get_taiwan_time, get_taiwan_date
from modules.services.ai_service import init_vertexai, MODEL_ID
from vertexai.generative_models import GenerativeModel, GenerationConfig
from sqlalchemy import text
import traceback

logger = logging.getLogger(__name__)

class TrueAIFareService:
    """真正使用AI的車資查詢服務"""
    
    def __init__(self):
        """初始化AI服務"""
        self.model = None
        self._initialize_ai()
    
    def _initialize_ai(self):
        """初始化AI模型"""
        try:
            init_vertexai()
            self.model = GenerativeModel(MODEL_ID)
            logger.info("真正的AI車資服務已初始化")
        except Exception as e:
            logger.error(f"AI初始化失敗: {e}")
            raise RuntimeError(f"無法初始化AI服務: {e}")
    
    def _build_fare_query_prompt(self, user_query: str) -> str:
        """構建車資查詢的AI提示"""
        return f"""
你是派班系統的AI助手，專門處理車資查詢和修改請求。

資料庫結構：
- completed_trips表：已完成班次記錄
  - id: 班次ID  
  - date: 日期 (YYYY-MM-DD)
  - start_point: 起點
  - end_point: 終點
  - meter_fare: 錶價
  - extra_fare: 加成
  - driver_id: 司機ID
  - category: 類別 (診所/東洋/臨時)

常見查詢格式示例：
1. "7/5司機533診所班次" → 查詢7月5日司機533的診所類別班次
2. "7/12司機5386診所班次" → 查詢7月12日司機5386的診所類別班次  
3. "昨天司機123東洋班次" → 查詢昨天司機123的東洋類別班次
4. "今天診所班次" → 查詢今天所有診所類別班次
5. "司機456的車資" → 查詢司機456的車資記錄
6. "修改班次#789車資400" → 修改班次789的車資為400

用戶查詢："{user_query}"

請分析用戶意圖並返回JSON格式：
{{
    "intent": "query",
    "confidence": 0.95,
    "entities": {{
        "date": "2024-07-05",
        "driver_id": "533", 
        "category": "診所"
    }},
    "sql_conditions": [
        "date = '2024-07-05'",
        "driver_id = 533",
        "category = '診所'"
    ],
    "natural_response": "查詢7月5日司機533的診所班次",
    "needs_clarification": false
}}

關鍵解析規則：
1. 日期格式：
   - "M/D" → "2024-0M-0D" (當年度)
   - "MM/DD" → "2024-MM-DD"  
   - "今天"、"昨天"、"明天" → 相對日期
2. 司機ID：緊跟在"司機"後的數字
3. 類別：診所、東洋、臨時
4. 意圖：包含"修改"、"改"為modify，其他為query
5. 信心度：有明確日期+司機+類別 = 0.95以上
"""

    def analyze_fare_query_with_ai(self, user_query: str) -> Dict:
        """使用AI分析車資查詢"""
        try:
            prompt = self._build_fare_query_prompt(user_query)
            
            generation_config = GenerationConfig(
                temperature=0.3,
                top_p=0.8,
                top_k=40,
                max_output_tokens=1024,
            )
            
            logger.info(f"🤖 調用Gemini API分析查詢: {user_query}")
            start_time = datetime.now()
            
            response = self.model.generate_content(
                prompt,
                generation_config=generation_config
            )
            
            end_time = datetime.now()
            logger.info(f"✅ AI分析完成，耗時: {(end_time - start_time).total_seconds():.2f}秒")
            
            # 解析AI回應
            if response.candidates and response.candidates[0].content.parts:
                text_response = response.candidates[0].content.parts[0].text
                
                # 清理JSON
                json_match = re.search(r'\{.*\}', text_response, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                    return json.loads(json_str)
            
            return self._create_fallback_analysis(user_query)
            
        except Exception as e:
            logger.error(f"AI分析失敗: {e}")
            return self._create_fallback_analysis(user_query)
    
    def _create_fallback_analysis(self, user_query: str) -> Dict:
        """AI失敗時的智能降級分析"""
        import re
        from datetime import datetime
        
        entities = {}
        sql_conditions = []
        confidence = 0.3
        
        # 🔥 智能解析常見格式：M/D司機ID診所班次
        pattern = r'(\d{1,2}/\d{1,2})司機(\d+)(診所|東洋|臨時)班次'
        match = re.search(pattern, user_query)
        
        if match:
            date_str, driver_id, category = match.groups()
            
            # 解析日期
            try:
                month, day = date_str.split('/')
                current_year = datetime.now().year
                formatted_date = f"{current_year}-{int(month):02d}-{int(day):02d}"
                entities['date'] = formatted_date
                sql_conditions.append(f"date = '{formatted_date}'")
            except:
                pass
            
            # 司機ID
            entities['driver_id'] = driver_id
            sql_conditions.append(f"driver_id = {driver_id}")
            
            # 類別
            entities['category'] = category
            sql_conditions.append(f"category = '{category}'")
            
            confidence = 0.95  # 高信心度，因為格式完全匹配
            
            return {
                "intent": "query",
                "confidence": confidence,
                "entities": entities,
                "sql_conditions": sql_conditions,
                "natural_response": f"查詢{date_str}司機{driver_id}的{category}班次",
                "needs_clarification": False
            }
        
        # 其他格式的基本解析
        # 司機ID
        driver_match = re.search(r'司機(\d+)', user_query)
        if driver_match:
            entities['driver_id'] = driver_match.group(1)
            sql_conditions.append(f"driver_id = {driver_match.group(1)}")
            confidence += 0.2
        
        # 類別
        for category in ['診所', '東洋', '臨時']:
            if category in user_query:
                entities['category'] = category
                sql_conditions.append(f"category = '{category}'")
                confidence += 0.2
                break
        
        # 日期關鍵詞
        if '今天' in user_query:
            today = datetime.now().strftime('%Y-%m-%d')
            entities['date'] = today
            sql_conditions.append(f"date = '{today}'")
            confidence += 0.2
        
        if confidence > 0.3:
            return {
                "intent": "query", 
                "confidence": min(confidence, 0.95),
                "entities": entities,
                "sql_conditions": sql_conditions,
                "natural_response": f"查詢班次記錄",
                "needs_clarification": False
            }
        
        # 完全無法解析時的回應
        return {
            "intent": "query",
            "confidence": 0.3,
            "entities": {},
            "sql_conditions": [],
            "natural_response": f"抱歉，無法理解查詢「{user_query}」。",
            "needs_clarification": True,
            "clarification_question": "請提供更具體的查詢條件，例如：日期、司機ID、或班次ID。"
        }
    
    def execute_ai_fare_query(self, user_query: str, user_id: str) -> str:
        """執行真正的AI車資查詢"""
        try:
            logger.info(f"🚀 開始真正的AI車資查詢: {user_query}")
            
            # 1. AI分析用戶意圖
            ai_analysis = self.analyze_fare_query_with_ai(user_query)
            confidence = ai_analysis.get('confidence', 0.0)
            
            logger.info(f"🧠 AI分析結果: 信心度={confidence}, 意圖={ai_analysis.get('intent')}")
            
            # 2. 檢查信心度
            if confidence < 0.5:
                return f"""🤖 AI無法理解您的查詢

💬 「{user_query}」
🔍 信心度：{confidence:.1%}

{ai_analysis.get('clarification_question', '請提供更具體的查詢條件。')}

💡 建議格式：
• 查詢今天司機123的車資
• 修改班次#456的錶價為400
• 昨天診所班次的費用"""
            
            # 3. 需要澄清
            if ai_analysis.get('needs_clarification'):
                return f"""🤖 AI需要更多信息

💬 「{user_query}」
❓ {ai_analysis.get('clarification_question')}

{ai_analysis.get('natural_response')}"""
            
            # 4. 構建SQL查詢
            sql_query, params = self._build_sql_from_ai_analysis(ai_analysis)
            
            # 5. 執行查詢
            results = db.session.execute(text(sql_query), params).fetchall()
            
            # 6. 格式化結果
            if ai_analysis.get('intent') == 'modify':
                return self._handle_ai_modification(ai_analysis, results, user_id)
            else:
                return self._format_ai_query_results(user_query, ai_analysis, results)
            
        except Exception as e:
            logger.error(f"AI車資查詢執行失敗: {e}")
            traceback.print_exc()
            return f"❌ AI查詢執行失敗: {str(e)}"
    
    def _build_sql_from_ai_analysis(self, ai_analysis: Dict) -> Tuple[str, Dict]:
        """根據AI分析結果構建SQL查詢"""
        base_query = """
        SELECT 
            id, date, start_point, end_point, 
            meter_fare, extra_fare, driver_id, category
        FROM completed_trips
        WHERE 1=1
        """
        
        conditions = []
        params = {}
        
        entities = ai_analysis.get('entities', {})
        
        # 日期條件
        if entities.get('date'):
            date_value = self._parse_ai_date(entities['date'])
            if date_value:
                conditions.append("AND date = :date")
                params['date'] = date_value
        
        # 司機ID條件
        if entities.get('driver_id'):
            conditions.append("AND driver_id = :driver_id")
            params['driver_id'] = str(entities['driver_id'])
        
        # 班次ID條件
        if entities.get('trip_id'):
            conditions.append("AND id = :trip_id")
            params['trip_id'] = entities['trip_id']
        
        # 類別條件
        if entities.get('category'):
            conditions.append("AND category = :category")
            params['category'] = entities['category']
        
        # 地點條件
        if entities.get('location'):
            conditions.append("AND (start_point LIKE :location OR end_point LIKE :location)")
            params['location'] = f"%{entities['location']}%"
        
        # AI提供的額外條件
        for condition in ai_analysis.get('sql_conditions', []):
            if condition.strip():
                conditions.append(f"AND {condition}")
        
        final_query = base_query + " ".join(conditions) + " ORDER BY date DESC, id DESC LIMIT 20"
        
        logger.info(f"🔍 AI生成的SQL: {final_query}")
        logger.info(f"📋 參數: {params}")
        
        return final_query, params
    
    def _parse_ai_date(self, date_str: str) -> str:
        """解析AI識別的日期"""
        today = get_taiwan_date()
        
        if date_str in ['今天', 'today']:
            return today.strftime('%Y-%m-%d')
        elif date_str in ['昨天', 'yesterday']:
            return (today - timedelta(days=1)).strftime('%Y-%m-%d')
        elif date_str in ['明天', 'tomorrow']:
            return (today + timedelta(days=1)).strftime('%Y-%m-%d')
        elif date_str in ['前天']:
            return (today - timedelta(days=2)).strftime('%Y-%m-%d')
        elif date_str in ['後天']:
            return (today + timedelta(days=2)).strftime('%Y-%m-%d')
        else:
            # 嘗試解析具體日期
            try:
                if re.match(r'\d{4}-\d{2}-\d{2}', date_str):
                    return date_str
                
                # 🔥 新增：處理M/D格式（如"7/5" → "2024-07-05"）
                if re.match(r'^\d{1,2}/\d{1,2}$', date_str):
                    month, day = date_str.split('/')
                    current_year = today.year
                    formatted_date = f"{current_year}-{int(month):02d}-{int(day):02d}"
                    logger.info(f"🗓️ 解析M/D格式: '{date_str}' → '{formatted_date}'")
                    return formatted_date
                
                # 其他日期格式處理
                return date_str
            except Exception as e:
                logger.warning(f"日期解析失敗: {date_str}, 錯誤: {e}")
                return today.strftime('%Y-%m-%d')
                return None
    
    def _format_ai_query_results(self, user_query: str, ai_analysis: Dict, results: List) -> str:
        """格式化AI查詢結果"""
        confidence = ai_analysis.get('confidence', 0.0)
        entities = ai_analysis.get('entities', {})
        
        header = f"""🤖 真正的AI智能搜索

💬 用戶查詢：{user_query}
🧠 AI理解：{ai_analysis.get('natural_response', '分析中...')}
📊 信心度：{confidence:.1%}
🔍 識別實體：{', '.join([f"{k}={v}" for k, v in entities.items() if v])}

"""
        
        if not results:
            return header + """❌ 未找到符合條件的班次記錄

💡 AI建議：
• 嘗試擴大日期範圍
• 檢查司機ID是否正確
• 確認類別名稱（診所/東洋/臨時）"""
        
        # 格式化結果
        results_text = f"✅ AI找到 {len(results)} 筆記錄：\n\n"
        
        for i, row in enumerate(results, 1):
            total_fare = (row.meter_fare or 0) + (row.extra_fare or 0)
            results_text += f"""📋 #{row.id} | {row.date} | {row.category}
📍 {row.start_point} → {row.end_point}
🚕 司機{row.driver_id} | 💰 錶價{row.meter_fare}+加成{row.extra_fare}={total_fare}元

"""
            
            if i >= 10:  # 限制顯示數量
                results_text += f"... 還有 {len(results) - 10} 筆記錄\n"
                break
        
        return header + results_text + "\n💡 要修改費用請說：「修改班次#XXX的錶價為XXX」"
    
    def _handle_ai_modification(self, ai_analysis: Dict, results: List, user_id: str) -> str:
        """處理AI修改請求"""
        entities = ai_analysis.get('entities', {})
        
        if not results:
            return "❌ 找不到要修改的班次記錄"
        
        if len(results) > 1:
            return f"⚠️ 找到 {len(results)} 筆記錄，請指定具體的班次ID"
        
        # 構建修改信息
        trip = results[0]
        modification_info = {
            'trip_id': trip.id,
            'current_meter': trip.meter_fare or 0,
            'current_extra': trip.extra_fare or 0,
            'new_meter': entities.get('meter_fare', trip.meter_fare or 0),
            'new_extra': entities.get('extra_fare', trip.extra_fare or 0),
            'reason': entities.get('reason', 'AI智能修改'),
            'category': trip.category,
            'route': f"{trip.start_point} → {trip.end_point}",
            'driver_id': trip.driver_id
        }
        
        return f"""🤖 AI準備修改班次

📋 班次：#{modification_info['trip_id']} ({modification_info['category']})
📍 路線：{modification_info['route']}
🚕 司機：{modification_info['driver_id']}
💰 費用變更：{modification_info['current_meter']}+{modification_info['current_extra']} → {modification_info['new_meter']}+{modification_info['new_extra']}
📝 修改原因：{modification_info['reason']}

⚠️ 請確認是否執行此修改？
回覆「確認AI修改」執行，「取消AI修改」取消"""

# 創建全局實例
_true_ai_fare_service = None

def get_true_ai_fare_service() -> TrueAIFareService:
    """獲取真正的AI車資服務實例"""
    global _true_ai_fare_service
    if _true_ai_fare_service is None:
        _true_ai_fare_service = TrueAIFareService()
    return _true_ai_fare_service

def handle_true_ai_fare_query(user_query: str, user_id: str) -> str:
    """處理真正的AI車資查詢入口函數"""
    try:
        service = get_true_ai_fare_service()
        return service.execute_ai_fare_query(user_query, user_id)
    except Exception as e:
        logger.error(f"真正的AI車資查詢失敗: {e}")
        return f"❌ AI服務暫時不可用: {str(e)}" 