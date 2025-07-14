#!/usr/bin/env python3
"""
智能助手系統
整合命令解析和上下文引導，提供完整的智能用戶體驗
"""
import logging
from typing import Dict, Optional
from modules.services.intelligent_command_parser import parse_user_command
from modules.services.contextual_guidance_system import provide_smart_guidance

logger = logging.getLogger(__name__)

class SmartAssistant:
    """智能助手 - 像您一樣理解並引導用戶"""
    
    def __init__(self):
        pass
    
    def process_user_message(self, user_input: str, user_id: str) -> Dict:
        """智能處理用戶消息"""
        logger.info(f"🤖 智能助手處理: {user_input}")
        
        # 步驟1: 嘗試智能命令解析
        parse_result = parse_user_command(user_input)
        
        if parse_result["success"]:
            logger.info(f"✅ 成功解析命令: {parse_result['standard_command']}")
            
            # 步驟2: 提供上下文智能引導（檢查是否需要特殊引導）
            guidance = provide_smart_guidance(user_input, user_id)
            
            if guidance["should_guide"]:
                logger.info(f"🎯 提供智能引導: {guidance['guidance_type']}")
                return {
                    "type": "smart_guidance",
                    "guidance": guidance,
                    "parsed_command": parse_result,
                    "should_execute_command": False  # 先引導，暫不執行命令
                }
            else:
                # 無需引導，執行標準命令
                logger.info(f"➡️ 執行標準命令: {parse_result['standard_command']}")
                return {
                    "type": "execute_command", 
                    "command": parse_result["standard_command"],
                    "original_input": user_input,
                    "confidence": parse_result["confidence"]
                }
        else:
            # 步驟3: 解析失敗，提供智能引導
            logger.info(f"❌ 命令解析失敗，嘗試智能引導")
            guidance = provide_smart_guidance(user_input, user_id)
            
            if guidance["should_guide"]:
                logger.info(f"🎯 提供智能引導: {guidance['guidance_type']}")
                return {
                    "type": "smart_guidance",
                    "guidance": guidance,
                    "should_execute_command": False
                }
            else:
                # 完全無法理解，提供一般性建議
                logger.info(f"❓ 無法理解，提供一般性建議")
                return {
                    "type": "general_suggestion",
                    "suggestions": parse_result.get("suggestions", []),
                    "original_input": user_input
                }
    
    def format_smart_response(self, process_result: Dict) -> str:
        """格式化智能回應"""
        response_type = process_result["type"]
        
        if response_type == "smart_guidance":
            return self._format_guidance_response(process_result["guidance"])
            
        elif response_type == "general_suggestion":
            return self._format_suggestion_response(process_result)
            
        elif response_type == "execute_command":
            # 這種情況下，應該由調用方執行命令
            return f"✅ 執行命令: {process_result['command']}"
            
        else:
            return "❓ 抱歉，我無法理解您的請求。"
    
    def _format_guidance_response(self, guidance: Dict) -> str:
        """格式化引導回應"""
        response = guidance["text"]
        
        if guidance.get("suggested_actions"):
            response += "\n\n🎯 **快速操作：**\n"
            for i, action in enumerate(guidance["suggested_actions"], 1):
                response += f"{i}. {action}\n"
        
        return response
    
    def _format_suggestion_response(self, process_result: Dict) -> str:
        """格式化建議回應"""
        suggestions = process_result.get("suggestions", [])
        original_input = process_result.get("original_input", "")
        
        response = f"❓ 我不太理解「{original_input}」的意思\n\n"
        
        if suggestions:
            response += "💡 **您可以試試：**\n"
            for i, suggestion in enumerate(suggestions, 1):
                response += f"{i}. {suggestion}\n"
        
        response += "\n或者使用「幫助」查看所有可用命令。"
        
        return response

# 全域實例
smart_assistant = SmartAssistant()

def process_with_smart_assistant(user_input: str, user_id: str) -> Dict:
    """使用智能助手處理用戶消息的便捷函數"""
    return smart_assistant.process_user_message(user_input, user_id)

def format_smart_response(process_result: Dict) -> str:
    """格式化智能回應的便捷函數"""
    return smart_assistant.format_smart_response(process_result) 