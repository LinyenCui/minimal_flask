#!/usr/bin/env python3
"""
智能命令解析器
理解用戶的自然表達，轉換為系統可識別的標準命令
"""
import re
import logging
from typing import Optional, Dict, List, Tuple

logger = logging.getLogger(__name__)

class IntelligentCommandParser:
    """智能命令解析器 - 讓用戶不用死背命令格式"""
    
    def __init__(self):
        """初始化命令模式映射表"""
        self.command_patterns = self._build_command_patterns()
        
    def _build_command_patterns(self) -> List[Dict]:
        """建立命令模式映射表"""
        return [
            # 匯入固定班次相關
            {
                "patterns": [
                    r"匯入(.+?)固定班次",
                    r"(.+?)固定班次匯入", 
                    r"固定班次(.+?)匯入",
                    r"導入(.+?)固定班次",
                    r"載入(.+?)固定班次"
                ],
                "standard_command": "匯入固定班次",
                "extract_params": self._extract_time_period,
                "examples": [
                    "匯入本週固定班次 → 匯入固定班次 本週",
                    "本週固定班次匯入 → 匯入固定班次 本週",
                    "匯入下週固定班次 → 匯入固定班次 下週"
                ]
            },
            
            # 班次查詢相關
            {
                "patterns": [
                    r"(.+?)班次查詢",
                    r"查詢(.+?)班次",
                    r"查(.+?)班次",
                    r"看(.+?)班次",
                    r"(.+?)班次有哪些"
                ],
                "standard_command": "",  # 會根據類別動態決定
                "extract_params": self._extract_trip_query_params,
                "examples": [
                    "明天診所班次查詢 → 診所班次 明天",
                    "查詢今天東洋班次 → 東洋班次 今天"
                ]
            },
            
            # 班次詳情相關  
            {
                "patterns": [
                    r"班次(\d+)詳情",
                    r"查看班次(\d+)",
                    r"班次(\d+)資訊",
                    r"班次(\d+)信息",
                    r"(\d+)班次詳情"
                ],
                "standard_command": "班次詳情",
                "extract_params": self._extract_trip_id,
                "examples": [
                    "班次1800詳情 → 班次詳情 1800",
                    "查看班次1800 → 班次詳情 1800"
                ]
            },
            
            # 請假相關
            {
                "patterns": [
                    r"將班次\s*(\d+)\s*(.+?)為\s*請假",
                    r"班次\s*(\d+)\s*請假",
                    r"(\d+)\s*班次\s*請假",
                    r"把班次\s*(\d+)\s*改成請假"
                ],
                "standard_command": "乘客請假",
                "extract_params": self._extract_leave_params,
                "examples": [
                    "將班次1800狀態修改為請假 → 班次 #1800 乘客請假",
                    "班次1800請假 → 班次 #1800 乘客請假"
                ]
            },
            
            # 司機指派相關
            {
                "patterns": [
                    r"將司機(\d+)指派給班次(\d+)",
                    r"班次(\d+)指派司機(\d+)",
                    r"指派司機(\d+)到班次(\d+)",
                    r"班次(\d+)的司機是(\d+)"
                ],
                "standard_command": "指派司機",
                "extract_params": self._extract_assign_params,
                "examples": [
                    "將司機533指派給班次1800 → 指派司機 1800 533",
                    "班次1800指派司機533 → 指派司機 1800 533"
                ]
            }
        ]
    
    def parse_natural_command(self, user_input: str) -> Dict:
        """解析用戶的自然語言輸入"""
        user_input = user_input.strip()
        
        logger.info(f"🧠 智能解析用戶輸入: {user_input}")
        
        # 逐一檢查所有模式
        for command_group in self.command_patterns:
            for pattern in command_group["patterns"]:
                match = re.search(pattern, user_input)
                if match:
                    logger.info(f"✅ 匹配到模式: {pattern}")
                    
                    # 提取參數
                    params = command_group["extract_params"](match, user_input)
                    
                    # 生成標準命令
                    standard_cmd = self._generate_standard_command(
                        command_group["standard_command"], 
                        params,
                        command_group
                    )
                    
                    return {
                        "success": True,
                        "original_input": user_input,
                        "matched_pattern": pattern,
                        "extracted_params": params,
                        "standard_command": standard_cmd,
                        "confidence": 0.9,
                        "suggestions": command_group["examples"][:2]
                    }
        
        # 沒有找到匹配的模式
        logger.info(f"❌ 未找到匹配模式")
        return {
            "success": False,
            "original_input": user_input,
            "confidence": 0.0,
            "suggestions": self._get_general_suggestions(user_input)
        }
    
    def _extract_time_period(self, match, full_text: str) -> Dict:
        """提取時間週期參數"""
        time_part = match.group(1).strip()
        
        # 處理覆蓋選項
        override = "覆蓋" in full_text
        
        # 標準化時間表達
        time_mapping = {
            "本週": "本週",
            "這週": "本週", 
            "本星期": "本週",
            "這星期": "本週",
            "下週": "下週",
            "下星期": "下週",
            "下下週": "下下週",
            "下下星期": "下下週"
        }
        
        standard_time = time_mapping.get(time_part, time_part)
        
        return {
            "time_period": standard_time,
            "override": override
        }
    
    def _extract_trip_query_params(self, match, full_text: str) -> Dict:
        """提取班次查詢參數"""
        # 判斷是哪種班次類型
        if "診所" in full_text:
            trip_type = "診所"
        elif "東洋" in full_text:
            trip_type = "東洋"  
        elif "臨時" in full_text:
            trip_type = "臨時"
        else:
            trip_type = "診所"  # 默認
            
        # 提取時間 - 先從匹配群組取得，再從關鍵字中尋找
        time_part = ""
        if match.groups():
            time_part = match.group(1).strip()
            # 清理時間部分中的班次類型詞彙
            for trip_word in ["診所", "東洋", "臨時", "班次"]:
                time_part = time_part.replace(trip_word, "").strip()
        
        if not time_part:
            # 從整個文本中尋找時間關鍵字
            time_keywords = ["今天", "明天", "後天", "昨天"]
            for keyword in time_keywords:
                if keyword in full_text:
                    time_part = keyword
                    break
        
        return {
            "trip_type": trip_type,
            "time_period": time_part or "今天"
        }
    
    def _extract_trip_id(self, match, full_text: str) -> Dict:
        """提取班次ID"""
        trip_id = match.group(1)
        return {"trip_id": trip_id}
    
    def _extract_leave_params(self, match, full_text: str) -> Dict:
        """提取請假參數"""
        trip_id = match.group(1)
        return {"trip_id": trip_id}
    
    def _extract_assign_params(self, match, full_text: str) -> Dict:
        """提取司機指派參數"""
        if len(match.groups()) >= 2:
            return {
                "trip_id": match.group(2),
                "driver_id": match.group(1)
            }
        return {}
    
    def _generate_standard_command(self, base_command: str, params: Dict, command_group: Dict) -> str:
        """生成標準命令格式"""
        
        if base_command == "匯入固定班次":
            cmd = f"匯入固定班次 {params['time_period']}"
            if params.get("override"):
                cmd += " 覆蓋"
            return cmd
            
        elif base_command == "班次詳情":
            return f"班次詳情 {params['trip_id']}"
            
        elif base_command == "乘客請假":
            return f"班次 #{params['trip_id']} 乘客請假"
            
        elif base_command == "指派司機":
            return f"指派司機 {params['trip_id']} {params['driver_id']}"
            
        elif base_command == "":  # 班次查詢類
            trip_type = params['trip_type']
            time_period = params['time_period']
            return f"{trip_type}班次 {time_period}"
            
        return base_command
    
    def _get_general_suggestions(self, user_input: str) -> List[str]:
        """根據用戶輸入提供一般性建議"""
        suggestions = []
        
        if any(keyword in user_input for keyword in ["匯入", "固定", "班次"]):
            suggestions.extend([
                "匯入固定班次 本週",
                "匯入固定班次 下週", 
                "匯入固定班次 本週 覆蓋"
            ])
            
        if any(keyword in user_input for keyword in ["班次", "查詢", "查"]):
            suggestions.extend([
                "診所班次 明天",
                "東洋班次 今天",
                "班次詳情 1800"
            ])
            
        if any(keyword in user_input for keyword in ["請假", "修改"]):
            suggestions.extend([
                "班次 #1800 乘客請假",
                "班次詳情 1800"
            ])
            
        # 如果沒有特定建議，提供通用建議
        if not suggestions:
            suggestions = [
                "試試說：匯入本週固定班次",
                "試試說：明天診所班次",
                "試試說：班次1800詳情",
                "或者使用「幫助」查看所有命令"
            ]
            
        return suggestions[:3]  # 最多3個建議

# 全域實例
intelligent_parser = IntelligentCommandParser()

def parse_user_command(user_input: str) -> Dict:
    """解析用戶命令的便捷函數"""
    return intelligent_parser.parse_natural_command(user_input) 