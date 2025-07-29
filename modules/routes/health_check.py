"""
系統健康檢查路由
提供環境配置和AI服務狀態檢查端點
"""
from flask import Blueprint, jsonify
from modules.services.ai_environment_validator import AIEnvironmentValidator

health_bp = Blueprint('health', __name__)

@health_bp.route('/health/ai', methods=['GET'])
def check_ai_health():
    """
    檢查AI服務環境配置健康狀態
    用於Render環境調試和監控
    """
    try:
        health_report = AIEnvironmentValidator.check_ai_service_health()
        
        # 根據健康狀態決定HTTP狀態碼
        status_code = 200 if health_report['environment_valid'] else 500
        
        return jsonify({
            'status': 'healthy' if health_report['environment_valid'] else 'unhealthy',
            'details': health_report
        }), status_code
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@health_bp.route('/health/basic', methods=['GET'])
def basic_health():
    """基本健康檢查"""
    return jsonify({
        'status': 'ok',
        'message': 'Service is running'
    }), 200