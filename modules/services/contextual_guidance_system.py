#!/usr/bin/env python3
"""
上下文智能引導系統
理解用戶的真實意圖，提供主動幫助和引導
"""
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from modules.models.base import db
from modules.utils.taiwan_time import get_taiwan_time, get_taiwan_date
from sqlalchemy import text

logger = logging.getLogger(__name__)

class ContextualGuidanceSystem:
    """上下文智能引導系統 - 像人一樣理解用戶的真實需求"""
    
    def __init__(self):
        self.guidance_patterns = self._build_guidance_patterns()
    
    def _build_guidance_patterns(self) -> List[Dict]:
        """建立引導模式"""
        return [
            {
                "trigger_keywords": ["匯入", "固定班次", "班次"],
                "context_analyzer": self._analyze_import_context,
                "guidance_generator": self._generate_import_guidance
            },
            {
                "trigger_keywords": ["請假", "不搭車", "取消"],
                "context_analyzer": self._analyze_leave_context, 
                "guidance_generator": self._generate_leave_guidance
            },
            {
                "trigger_keywords": ["查詢", "班次", "明天", "今天"],
                "context_analyzer": self._analyze_query_context,
                "guidance_generator": self._generate_query_guidance
            }
        ]
    
    def provide_contextual_guidance(self, user_input: str, user_id: str) -> Dict:
        """提供上下文智能引導"""
        logger.info(f"🎯 分析用戶上下文: {user_input}")
        
        # 檢查是否觸發任何引導模式
        for pattern in self.guidance_patterns:
            if any(keyword in user_input for keyword in pattern["trigger_keywords"]):
                logger.info(f"✅ 觸發引導模式: {pattern['trigger_keywords']}")
                
                # 分析上下文
                context = pattern["context_analyzer"](user_input, user_id)
                
                # 生成引導回應
                guidance = pattern["guidance_generator"](context, user_input)
                
                if guidance["should_guide"]:
                    return guidance
        
        # 無需特殊引導
        return {"should_guide": False}
    
    def _analyze_import_context(self, user_input: str, user_id: str) -> Dict:
        """分析匯入相關的上下文"""
        context = {
            "wants_import": True,
            "time_period": self._extract_time_period(user_input),
            "already_imported": False,
            "import_count": 0
        }
        
        # 檢查該時間段是否已經匯入過
        if context["time_period"]:
            start_date, end_date = self._get_date_range(context["time_period"])
            if start_date and end_date:
                # 查詢該時間段的班次數量
                query = """
                SELECT COUNT(*) as count
                FROM trips 
                WHERE date BETWEEN :start_date AND :end_date
                AND source = 'fixed_schedule'
                """
                
                try:
                    result = db.session.execute(
                        text(query), 
                        {"start_date": start_date, "end_date": end_date}
                    ).fetchone()
                    
                    if result and result.count > 0:
                        context["already_imported"] = True
                        context["import_count"] = result.count
                        
                except Exception as e:
                    logger.error(f"檢查匯入狀態失敗: {e}")
        
        return context
    
    def _analyze_leave_context(self, user_input: str, user_id: str) -> Dict:
        """分析請假相關的上下文"""
        return {
            "wants_leave": True,
            "trip_id": self._extract_trip_id_from_text(user_input),
            "reason_mentioned": any(keyword in user_input for keyword in ["不搭車", "有事", "請假"])
        }
    
    def _analyze_query_context(self, user_input: str, user_id: str) -> Dict:
        """分析查詢相關的上下文"""
        return {
            "wants_query": True,
            "date": self._extract_date_from_text(user_input),
            "trip_type": self._extract_trip_type(user_input)
        }
    
    def _generate_import_guidance(self, context: Dict, user_input: str) -> Dict:
        """生成匯入相關的智能引導"""
        if not context["already_imported"]:
            # 班次還沒匯入，正常處理
            return {"should_guide": False}
        
        # 班次已經匯入過了，提供智能引導
        time_period = context["time_period"] or "該時間段"
        count = context["import_count"]
        
        guidance_text = f"""📅 {time_period}的固定班次已經匯入過了（共 {count} 筆）

🤔 您可能想要：
1️⃣ 查看班次進行請假操作
2️⃣ 查看班次詳情進行修改
3️⃣ 重新匯入並覆蓋現有班次

❓ **請告訴我您想要做什麼？**
• 如果要查看班次：請說「明天診所班次」或「今天東洋班次」
• 如果要請假：請說「班次請假」，我會幫您找到相關班次
• 如果要覆蓋：請說「匯入固定班次 {time_period} 覆蓋」

💡 **或者直接告訴我：**
「我要幫某乘客請假」或「我要查看明天的班次」"""
        
        return {
            "should_guide": True,
            "guidance_type": "import_already_exists",
            "text": guidance_text,
            "suggested_actions": [
                f"明天診所班次",
                f"今天東洋班次", 
                f"匯入固定班次 {time_period} 覆蓋"
            ]
        }
    
    def _generate_leave_guidance(self, context: Dict, user_input: str) -> Dict:
        """生成請假相關的智能引導"""
        if context["trip_id"]:
            # 已經有班次ID，直接引導
            return {"should_guide": False}
        
        # 沒有具體班次ID，幫助找到班次
        guidance_text = """🎯 我來幫您找到要請假的班次

❓ **請告訴我更具體的信息：**
• 哪一天的班次？（明天、後天、7/15等）
• 什麼類型的班次？（診所、東洋、臨時）
• 或者如果您知道班次編號，直接說「班次1800請假」

💡 **例如：**
「明天診所班次」→ 我會列出所有班次讓您選擇
「7/15東洋班次」→ 顯示該日東洋班次
「班次1800請假」→ 直接處理請假"""
        
        return {
            "should_guide": True,
            "guidance_type": "help_find_trip_for_leave",
            "text": guidance_text,
            "suggested_actions": [
                "明天診所班次",
                "今天東洋班次",
                "後天診所班次"
            ]
        }
    
    def _generate_query_guidance(self, context: Dict, user_input: str) -> Dict:
        """生成查詢相關的智能引導"""
        # 查詢類通常不需要特殊引導，讓正常流程處理
        return {"should_guide": False}
    
    def _extract_time_period(self, text: str) -> Optional[str]:
        """從文本中提取時間週期"""
        if "本週" in text or "這週" in text:
            return "本週"
        elif "下週" in text:
            return "下週"
        elif "本星期" in text or "這星期" in text:
            return "本週"
        elif "下星期" in text:
            return "下週"
        return None
    
    def _extract_trip_id_from_text(self, text: str) -> Optional[str]:
        """從文本中提取班次ID"""
        import re
        match = re.search(r'班次\s*(\d+)', text)
        if match:
            return match.group(1)
        return None
    
    def _extract_date_from_text(self, text: str) -> Optional[str]:
        """從文本中提取日期"""
        if "明天" in text:
            return "明天"
        elif "今天" in text:
            return "今天"
        elif "後天" in text:
            return "後天"
        return None
    
    def _extract_trip_type(self, text: str) -> Optional[str]:
        """從文本中提取班次類型"""
        if "診所" in text:
            return "診所"
        elif "東洋" in text:
            return "東洋"
        elif "臨時" in text:
            return "臨時"
        return None
    
    def _get_date_range(self, time_period: str) -> tuple:
        """根據時間週期獲取日期範圍"""
        today = get_taiwan_date()
        
        if time_period == "本週":
            # 計算本週的週日到週六
            days_since_sunday = today.weekday() + 1  # Monday=0 -> 1, Sunday=6 -> 7 -> 0
            if days_since_sunday == 7:
                days_since_sunday = 0
            
            start_date = today - timedelta(days=days_since_sunday)
            end_date = start_date + timedelta(days=6)
            
        elif time_period == "下週":
            # 計算下週的週日到週六
            days_since_sunday = today.weekday() + 1
            if days_since_sunday == 7:
                days_since_sunday = 0
                
            start_date = today - timedelta(days=days_since_sunday) + timedelta(weeks=1)
            end_date = start_date + timedelta(days=6)
            
        else:
            return None, None
            
        return start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')

# 全域實例
guidance_system = ContextualGuidanceSystem()

def provide_smart_guidance(user_input: str, user_id: str) -> Dict:
    """提供智能引導的便捷函數"""
    return guidance_system.provide_contextual_guidance(user_input, user_id) 