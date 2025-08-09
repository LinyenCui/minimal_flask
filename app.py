# app.py
import os
from dotenv import load_dotenv
import time
from datetime import datetime, timezone, timedelta, date

# 設置時區為台灣時間（UTC+8）
os.environ['TZ'] = 'Asia/Taipei'
try:
    time.tzset()  # 這個只能在Unix/Linux/MacOS上使用
except AttributeError:
    pass  # Windows不支持這個函數

# 檢查是否在本地運行
is_local = os.environ.get('FLASK_ENV') == 'development'

# 環境變量加載邏輯
if is_local:
    print("本地開發環境：加載 .env.dev")
    load_dotenv('.env.dev', override=True)
elif not os.environ.get('RENDER'):  # 如果不是在 Render 上運行
    print("非 Render 環境：加載 .env")
    load_dotenv('.env', override=True)
else:
    print("Render 環境：使用 Render 環境變量")

# 驗證配置
from modules.utils.security import mask_value  # for early masking in startup prints
secret = os.environ.get('LINE_CHANNEL_SECRET')
token = os.environ.get('LINE_CHANNEL_TOKEN')
print(f"使用的 Channel Secret: {mask_value(secret)}" if secret else "未设置")
print(f"使用的 Channel Token: {mask_value(token)}" if token else "未设置")

# 其他的 import
import logging
from modules.utils.security import mask_value, mask_db_url, MaskSecretsFilter
from modules import create_app
from flask import request, abort
from flask_apscheduler import APScheduler
import flask
import sqlalchemy

# 版本檢查
flask_version = flask.__version__
sqlalchemy_version = sqlalchemy.__version__
print(f"Flask version: {flask_version}")
print(f"SQLAlchemy version: {sqlalchemy_version}")
if flask_version.startswith("3."):
    print("使用 Flask 3.x 兼容模式")
else:
    print("使用 Flask 2.x 或更早版本兼容模式")

# 創建應用實例
app = create_app()

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Attach global secrets masking filter to all handlers (root and current)
_mask_filter = MaskSecretsFilter()
root_logger = logging.getLogger()
for handler in root_logger.handlers or []:
    handler.addFilter(_mask_filter)
if not root_logger.handlers:
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.INFO)
    stream_handler.addFilter(_mask_filter)
    root_logger.addHandler(stream_handler)

for handler in logger.handlers or []:
    handler.addFilter(_mask_filter)

# 顯示配置信息
def show_config():
    token = app.config.get('LINE_CHANNEL_TOKEN')
    secret = app.config.get('LINE_CHANNEL_SECRET')
    db_url = app.config.get('SQLALCHEMY_DATABASE_URI')

    logger.info("Channel token: %s", mask_value(token))
    logger.info("Database URL: %s", mask_db_url(db_url))
    logger.info("Channel Secret: %s", mask_value(secret))

# 在應用啟動前執行配置顯示
with app.app_context():
    show_config()

# 在創建 app 時
app.config['LINE_CHANNEL_SECRET'] = os.environ.get('LINE_CHANNEL_SECRET')

# 主路由（健康檢查）
@app.route("/")
def hello():
    return "派班系統已啟動！"

# 設置排程器
scheduler = APScheduler()
app.scheduler = scheduler  # 將排程器附加到應用程序實例

# 在應用程序啟動時初始化
with app.app_context():
    # 初始化排程器
    scheduler.init_app(app)
    
    # 使用scheduler_service中的init_scheduler函數初始化排程任務
    from modules.services.scheduler_service import init_scheduler
    init_scheduler(app)
    
    # 啟動排程器
    scheduler.start()
    
    # 應用啟動時，處理所有已過期的班次
    from modules.services.scheduler_service import update_completed_trips
    update_completed_trips()
    
    # 應用啟動時，初始化所有沒有唯一識別碼的班次
    from modules.services.scheduler_service import initialize_unique_codes
    initialize_unique_codes()
    
    # 應用啟動時，安排所有未來班次的自動更新任務
    from modules.services.scheduler_service import schedule_all_trip_updates
    schedule_all_trip_updates(app)

# 在app.py中，添加在其他路由定义之后
@app.route('/test_env')
def test_env():
    import os
    import sys
    import platform
    import time
    
    return {
        'python_version': sys.version,
        'platform': platform.platform(),
        'env_vars': {k: v for k, v in os.environ.items() if not k.startswith('LINE') and not k.startswith('DATABASE')},  # 过滤敏感信息
        'tz': time.tzname,
        'current_time': str(datetime.now()),
        'app_config': {k: str(v) for k, v in app.config.items() if not k.startswith('LINE') and not k.startswith('DATABASE')}  # 过滤敏感信息
    }

# 在文件末尾添加診斷端點
@app.route('/render_diagnosis')
def render_diagnosis():
    """Render端診斷頁面"""
    from flask import jsonify
    import traceback
    from datetime import datetime, date, timedelta
    
    results = {}
    
    try:
        # 1. 測試系統時間
        results['system_time'] = {
            'utc_now': datetime.utcnow().isoformat(),
            'local_now': datetime.now().isoformat(),
            'date_today': date.today().isoformat()
        }
        
        # 2. 測試環境變數
        import os
        results['environment'] = {
            'TZ': os.environ.get('TZ', 'Not Set'),
            'PYTHONPATH': os.environ.get('PYTHONPATH', 'Not Set')
        }
        
        # 3. 測試台灣時間函數
        try:
            from modules.utils.helpers import get_taiwan_date, get_taiwan_time
            taiwan_time = get_taiwan_time()
            taiwan_date = get_taiwan_date()
            
            results['taiwan_time'] = {
                'taiwan_datetime': taiwan_time.isoformat(),
                'taiwan_date': taiwan_date.isoformat(),
                'timezone': str(taiwan_time.tzinfo),
                'offset': str(taiwan_time.utcoffset())
            }
        except Exception as e:
            results['taiwan_time'] = {'error': str(e), 'traceback': traceback.format_exc()}
        
        # 4. 測試日期解析函數
        try:
            from modules.utils.unified_date_parser import UnifiedDateParser
            
            test_dates = ['昨天', '前天', '今天', '明天', '7/25', '7/24']
            parsed_dates = {}
            
            for date_str in test_dates:
                try:
                    parsed = UnifiedDateParser.parse(date_str)
                    parsed_dates[date_str] = parsed.isoformat() if parsed else None
                except Exception as e:
                    parsed_dates[date_str] = f"Error: {str(e)}"
            
            results['date_parsing'] = parsed_dates
        except Exception as e:
            results['date_parsing'] = {'error': str(e), 'traceback': traceback.format_exc()}
        
        # 5. 測試AI車資服務解析
        try:
            from modules.services.ai_fare_service import CompletedTripMatcher
            
            matcher = CompletedTripMatcher()
            
            test_queries = [
                '查已完成 昨天 診所',
                '查已完成 7/25 診所',
                '查已完成 前天 診所',
                '查已完成 7/24 診所'
            ]
            
            query_results = {}
            for query in test_queries:
                try:
                    criteria = matcher.parse_natural_query(query)
                    # 將日期轉換為字符串以便JSON序列化
                    criteria_serializable = {}
                    for key, value in criteria.items():
                        if isinstance(value, date):
                            criteria_serializable[key] = value.isoformat()
                        else:
                            criteria_serializable[key] = value
                    query_results[query] = criteria_serializable
                except Exception as e:
                    query_results[query] = {'error': str(e)}
            
            results['query_parsing'] = query_results
        except Exception as e:
            results['query_parsing'] = {'error': str(e), 'traceback': traceback.format_exc()}
        
        # 6. 測試數據庫查詢（簡化版）
        try:
            from modules import db
            from sqlalchemy import text
            
            # 查詢7/25的診所班次數量
            sql_725 = """
                SELECT COUNT(*) as count 
                FROM completed_trips 
                WHERE date = '2025-07-25' AND category = '診所'
            """
            
            # 查詢7/24的診所班次數量  
            sql_724 = """
                SELECT COUNT(*) as count 
                FROM completed_trips 
                WHERE date = '2025-07-24' AND category = '診所'
            """
            
            # 查詢最近3天的診所班次數量
            sql_recent = """
                SELECT COUNT(*) as count 
                FROM completed_trips 
                WHERE date >= '2025-07-24' AND category = '診所'
            """
            
            count_725 = db.session.execute(text(sql_725)).scalar()
            count_724 = db.session.execute(text(sql_724)).scalar()
            count_recent = db.session.execute(text(sql_recent)).scalar()
            
            results['database_counts'] = {
                '2025-07-25_clinic': count_725,
                '2025-07-24_clinic': count_724,
                'recent_3days_clinic': count_recent
            }
        except Exception as e:
            results['database_counts'] = {'error': str(e), 'traceback': traceback.format_exc()}
        
        # 7. 關鍵分析
        analysis = []
        
        # 分析日期解析結果
        if 'date_parsing' in results and isinstance(results['date_parsing'], dict):
            yesterday_parsed = results['date_parsing'].get('昨天')
            absolute_725 = results['date_parsing'].get('7/25')
            
            if yesterday_parsed and absolute_725:
                if yesterday_parsed == absolute_725:
                    analysis.append("✅ '昨天'和'7/25'解析為相同日期")
                else:
                    analysis.append(f"❌ '昨天'解析為{yesterday_parsed}，'7/25'解析為{absolute_725}")
            else:
                analysis.append(f"⚠️ 日期解析有問題：昨天={yesterday_parsed}, 7/25={absolute_725}")
        
        # 分析數據庫計數
        if 'database_counts' in results and isinstance(results['database_counts'], dict):
            count_725 = results['database_counts'].get('2025-07-25_clinic')
            count_724 = results['database_counts'].get('2025-07-24_clinic')
            count_recent = results['database_counts'].get('recent_3days_clinic')
            
            if count_725 == 21:
                analysis.append(f"✅ 7/25診所班次：{count_725}筆（正確）")
            else:
                analysis.append(f"⚠️ 7/25診所班次：{count_725}筆（預期21筆）")
            
            if count_recent == 54:
                analysis.append(f"❌ 最近3天診所班次：{count_recent}筆（這可能是'昨天'查詢錯誤的原因）")
            
        results['analysis'] = analysis
        
    except Exception as e:
        results['global_error'] = {
            'error': str(e),
            'traceback': traceback.format_exc()
        }
    
    # 返回JSON結果
    return jsonify(results)

# 啟動應用
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    app.run(host="0.0.0.0", port=port)
