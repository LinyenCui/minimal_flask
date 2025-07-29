"""
AI環境配置驗證器
統一檢查AI服務所需環境變數和設定，確保本地和Render環境一致性
"""
import os
import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

class AIEnvironmentValidator:
    """AI環境配置驗證器"""
    
    @staticmethod
    def validate_environment() -> Tuple[bool, List[str]]:
        """
        驗證AI服務所需環境配置
        
        Returns:
            Tuple[bool, List[str]]: (是否有效, 錯誤消息列表)
        """
        errors = []
        is_valid = True
        
        # 檢查必須的環境變數
        required_env_vars = [
            'GCP_PROJECT_ID',
            'GCP_LOCATION', 
            'TZ'
        ]
        
        for var in required_env_vars:
            if not os.getenv(var):
                errors.append(f"缺少環境變數: {var}")
                is_valid = False
            else:
                logger.info(f"✅ 環境變數 {var}: {os.getenv(var)}")
        
        # 檢查Google認證
        credentials_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
        if not credentials_path:
            errors.append("缺少環境變數: GOOGLE_APPLICATION_CREDENTIALS")
            is_valid = False
        elif not os.path.exists(credentials_path):
            errors.append(f"Google認證檔案不存在: {credentials_path}")
            is_valid = False
        else:
            logger.info(f"✅ Google認證檔案: {credentials_path}")
        
        # 檢查時區設定
        tz = os.getenv('TZ')
        if tz != 'Asia/Taipei':
            errors.append(f"時區設定不正確，期望: Asia/Taipei，實際: {tz}")
            is_valid = False
        
        return is_valid, errors
    
    @staticmethod
    def get_ai_configuration() -> Dict[str, str]:
        """
        獲取當前AI配置信息
        
        Returns:
            Dict[str, str]: 配置信息字典
        """
        return {
            'project_id': os.getenv('GCP_PROJECT_ID', 'NOT_SET'),
            'location': os.getenv('GCP_LOCATION', 'NOT_SET'),
            'timezone': os.getenv('TZ', 'NOT_SET'),
            'credentials_path': os.getenv('GOOGLE_APPLICATION_CREDENTIALS', 'NOT_SET'),
            'credentials_exists': str(os.path.exists(os.getenv('GOOGLE_APPLICATION_CREDENTIALS', '')))
        }
    
    @staticmethod
    def check_ai_service_health() -> Dict[str, any]:
        """
        檢查AI服務健康狀態
        
        Returns:
            Dict[str, any]: 健康狀態報告
        """
        is_valid, errors = AIEnvironmentValidator.validate_environment()
        config = AIEnvironmentValidator.get_ai_configuration()
        
        # 嘗試進行簡單的AI調用測試
        ai_test_result = None
        try:
            from modules.services.ai_service import extract_booking_info_with_gemini
            # 進行一個簡單的測試調用
            test_result = extract_booking_info_with_gemini("測試連接")
            ai_test_result = "成功" if test_result is not None else "失敗"
        except Exception as e:
            ai_test_result = f"錯誤: {str(e)}"
        
        return {
            'environment_valid': is_valid,
            'errors': errors,
            'configuration': config,
            'ai_service_test': ai_test_result,
            'timestamp': __import__('datetime').datetime.now().isoformat()
        }
    
    @staticmethod 
    def get_confidence_threshold() -> float:
        """
        獲取AI信心度閾值
        根據環境配置返回適當的閾值
        
        Returns:
            float: 信心度閾值
        """
        is_valid, _ = AIEnvironmentValidator.validate_environment()
        
        # 如果環境配置完整，使用較高的閾值
        if is_valid:
            return 0.8
        else:
            # 環境有問題時，使用較低的閾值以避免過多確認請求
            logger.warning("AI環境配置不完整，使用較低的信心度閾值")
            return 0.6

def validate_ai_environment() -> bool:
    """向後兼容的驗證函數"""
    is_valid, errors = AIEnvironmentValidator.validate_environment()
    if not is_valid:
        for error in errors:
            logger.error(error)
    return is_valid