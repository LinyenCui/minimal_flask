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

# 環境變量加載邏輯（一勞永逸版，不再依賴 FLASK_ENV）
# - Render 平台會自動注入 RENDER=true（不可偽造）→ 跳過 .env，用 dashboard 環境變數
# - 本地有 .env.dev → 兩段載入：.env 當 base（sync 腳本要的 RENDER_DB_*）
#                              + .env.dev override（LIFF / dev channel / localhost DB）
# - 本地只有 .env → 載 .env（向後相容）
on_render = bool(os.environ.get('RENDER'))

if on_render:
    print("Render 環境：使用 Render dashboard 環境變數")
elif os.path.exists('.env.dev'):
    if os.path.exists('.env'):
        load_dotenv('.env', override=False)   # base：共用設定（如 RENDER_DB_* for sync）
    load_dotenv('.env.dev', override=True)    # 本地 override：LIFF / dev channel / DB
    print("本地開發環境：載 .env（base）+ .env.dev（override）")
elif os.path.exists('.env'):
    load_dotenv('.env', override=True)
    print("非 Render 環境：載入 .env（沒 .env.dev）")
else:
    print("⚠️ 無 .env 檔，僅用 OS 環境變數")

# 驗證配置
from modules.utils.security import mask_value  # for early masking in startup prints
secret = os.environ.get('LINE_CHANNEL_SECRET')
token = os.environ.get('LINE_CHANNEL_TOKEN')
liff_id = os.environ.get('LIFF_ID')
print(f"使用的 Channel Secret: {mask_value(secret)}" if secret else "未设置 LINE_CHANNEL_SECRET")
print(f"使用的 Channel Token: {mask_value(token)}" if token else "未设置 LINE_CHANNEL_TOKEN")
print(f"使用的 LIFF_ID: {liff_id[:8]}…" if liff_id else "⚠️ 未设置 LIFF_ID（!新增客戶 LIFF 表單會壞）")

# 其他的 import
import logging
from modules.utils.security import mask_value, mask_db_url, MaskSecretsFilter
from modules import create_app
from flask import request, abort
from flask_apscheduler import APScheduler
import flask
import sqlalchemy

# PATCH START: app.py logging & mem middleware
import os as _os
from time import perf_counter as _perf_counter
try:
    import psutil as _psutil
except Exception:
    _psutil = None
from flask import g as _g, request as _request
# PATCH END: app.py logging & mem middleware

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

# Also attach filter to the root logger itself (avoid duplicates)
if not any(isinstance(f, MaskSecretsFilter) for f in getattr(root_logger, "filters", [])):
    root_logger.addFilter(_mask_filter)

for handler in logger.handlers or []:
    handler.addFilter(_mask_filter)

# PATCH START: app.py logging & mem middleware
# tune noisy loggers
logging.getLogger("modules.utils.line_bot").setLevel(logging.WARNING)
logging.getLogger("modules.utils.response_handler").setLevel(logging.WARNING)

# lightweight memory/latency metrics (DEBUG only)
_proc = None
if _psutil:
    try:
        _proc = _psutil.Process(_os.getpid())
    except Exception:
        _proc = None
_memlog = logging.getLogger("mem")

@app.before_request
def _req_t0():
    _g._t0 = _perf_counter()

@app.after_request
def _req_metrics(resp):
    try:
        if _memlog.isEnabledFor(logging.DEBUG) and _proc is not None:
            rss_mb = _proc.memory_info().rss / (1024 * 1024)
            dt_ms = int((_perf_counter() - getattr(_g, "_t0", _perf_counter())) * 1000)
            _memlog.debug("RSS=%.1fMB %s %s %dms", rss_mb, _request.method, _request.path, dt_ms)
    except Exception:
        # Never fail the request on metrics errors
        pass
    return resp
# PATCH END: app.py logging & mem middleware

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

# 🔥 記憶體監控端點
@app.route('/memory_stats')
def memory_stats():
    """記憶體使用統計端點（用於監控和診斷）"""
    from flask import jsonify
    import sys
    
    stats = {
        'timestamp': datetime.now().isoformat(),
        'python_memory': {}
    }
    
    # 系統記憶體（如果 psutil 可用）
    if _proc is not None:
        try:
            mem_info = _proc.memory_info()
            stats['system_memory'] = {
                'rss_mb': round(mem_info.rss / (1024 * 1024), 2),
                'vms_mb': round(mem_info.vms / (1024 * 1024), 2)
            }
        except Exception as e:
            stats['system_memory'] = {'error': str(e)}
    
    # 對話狀態統計
    try:
        from modules.utils.conversation_context import (
            conversation_states, conversation_manager
        )
        stats['conversation_states'] = {
            'count': len(conversation_states),
            'keys_sample': list(conversation_states.keys())[:10]  # 只顯示前10個
        }
        
        if conversation_manager:
            stats['conversation_manager'] = conversation_manager.get_memory_stats()
    except Exception as e:
        stats['conversation_states'] = {'error': str(e)}
    
    # temp_booking_states 統計
    try:
        from modules.handlers.temp_booking_handler import temp_booking_states
        stats['temp_booking_states'] = {
            'count': len(temp_booking_states),
            'keys_sample': list(temp_booking_states.keys())[:10]
        }
    except Exception as e:
        stats['temp_booking_states'] = {'error': str(e)}
    
    # helpers.user_states 統計
    try:
        from modules.utils.helpers import user_states
        stats['user_states'] = {
            'count': len(user_states),
            'keys_sample': list(user_states.keys())[:10]
        }
    except Exception as e:
        stats['user_states'] = {'error': str(e)}
    
    # 其他狀態字典
    try:
        from modules.services.booking.booking_service import booking_states
        stats['booking_states'] = {'count': len(booking_states)}
    except:
        pass
    
    try:
        from modules.handlers.sequence_fix_handler import sequence_fix_states
        stats['sequence_fix_states'] = {'count': len(sequence_fix_states)}
    except:
        pass
    
    try:
        from modules.handlers.batch_allowance_handler import batch_allowance_states
        stats['batch_allowance_states'] = {'count': len(batch_allowance_states)}
    except:
        pass
    
    return jsonify(stats)


# 🔥 手動觸發記憶體清理端點
@app.route('/cleanup_memory')
def cleanup_memory():
    """手動觸發記憶體清理"""
    from flask import jsonify
    
    try:
        from modules.services.scheduler_service import cleanup_expired_conversation_states
        cleanup_expired_conversation_states()
        
        # 返回清理後的統計
        return jsonify({
            'status': 'success',
            'message': '記憶體清理完成',
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500


# 啟動應用
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    app.run(host="0.0.0.0", port=port)
