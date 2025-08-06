"""
LINE Bot 序列修復處理模塊
提供遠程序列檢查和修復功能
"""

import logging
from sqlalchemy import text
from modules.models.base import db
from modules.utils.quick_reply_manager import QuickReplyManager

logger = logging.getLogger(__name__)

# 序列修復狀態管理（類似於 temp_booking_states）
sequence_fix_states = {}

def check_all_sequences():
    """檢查所有序列狀態，返回詳細報告"""
    try:
        # 定義需要檢查的表和序列
        tables_with_sequences = [
            ('completed_trips', 'completed_trips_id_seq', 'id'),
            ('trips', 'trips_trip_id_seq', 'trip_id'),
            # 可以添加更多表...
        ]
        
        results = []
        need_fix = []
        
        for table_name, seq_name, id_column in tables_with_sequences:
            try:
                # 獲取最大ID
                max_id_query = f"SELECT COALESCE(MAX({id_column}), 0) FROM {table_name};"
                max_result = db.session.execute(text(max_id_query)).fetchone()
                max_id = max_result[0] if max_result else 0
                
                # 獲取序列值
                seq_query = f"SELECT last_value FROM {seq_name};"
                seq_result = db.session.execute(text(seq_query)).fetchone()
                current_seq = seq_result[0] if seq_result else 0
                
                # 修正邏輯：只有當序列值 < 最大ID 時才需要修復
                # 序列值 = 最大ID 是正常的（下次會使用 max_id + 1）
                # 序列值 > 最大ID 也是正常的
                is_normal = current_seq >= max_id
                
                status = "✅ 正常" if is_normal else "❌ 需修復"
                
                result_info = {
                    'table': table_name,
                    'max_id': max_id,
                    'current_seq': current_seq,
                    'status': status,
                    'need_fix': not is_normal
                }
                
                results.append(result_info)
                
                if current_seq < max_id:
                    need_fix.append(result_info)
                    
            except Exception as e:
                logger.error(f"檢查表 {table_name} 時出錯: {e}")
                results.append({
                    'table': table_name,
                    'max_id': '錯誤',
                    'current_seq': '錯誤', 
                    'status': f'❌ 檢查失敗: {str(e)}',
                    'need_fix': False
                })
        
        return results, need_fix
        
    except Exception as e:
        logger.error(f"檢查序列時出錯: {e}")
        return [], []

def format_sequence_report(results, need_fix):
    """格式化序列檢查報告"""
    if not results:
        return "❌ 無法獲取序列狀態"

    report_lines = ["🔍 資料庫序列檢查報告", "=" * 25]
    
    for result in results:
        table = result['table']
        max_id = result['max_id']
        seq = result['current_seq']
        status = result['status']
        
        report_lines.append(f"\n📊 {table}:")
        report_lines.append(f"   最大ID: {max_id}")
        report_lines.append(f"   序列值: {seq}")
        report_lines.append(f"   狀態: {status}")
    
    report_lines.append("\n" + "=" * 25)
    
    # 生成網頁版工具連結
    import os
    domain = os.getenv('APP_DOMAIN', 'localhost:3000')  # 修正為實際運行的端口
    protocol = 'https' if 'render.com' in domain or 'herokuapp.com' in domain else 'http'
    admin_url = f"{protocol}://{domain}/admin/database-tools"
    
    if need_fix:
        report_lines.append(f"⚠️ 發現 {len(need_fix)} 個表需要修復")
        report_lines.append("\n回覆「確認修復」來執行修復")
        report_lines.append("回覆「取消」來取消操作")
        report_lines.append(f"\n💡 網頁版工具: {admin_url}")
    else:
        report_lines.append("✅ 所有序列狀態正常")
        report_lines.append(f"\n💡 網頁版工具: {admin_url}")
    
    return "\n".join(report_lines)

def fix_sequences(need_fix_list):
    """執行序列修復"""
    try:
        fixed_count = 0
        errors = []
        
        for fix_info in need_fix_list:
            table_name = fix_info['table'] 
            max_id = fix_info['max_id']
            
            try:
                # 確定序列名稱和ID列名
                if table_name == 'completed_trips':
                    seq_name = 'completed_trips_id_seq'
                elif table_name == 'trips':
                    seq_name = 'trips_trip_id_seq'
                else:
                    continue
                
                next_val = max_id + 1 if max_id > 0 else 1
                
                # 修復序列
                fix_query = f"SELECT setval('{seq_name}', {next_val}, false);"
                db.session.execute(text(fix_query))
                
                logger.info(f"已修復 {table_name} 序列，設為: {next_val}")
                fixed_count += 1
                
            except Exception as e:
                error_msg = f"{table_name}: {str(e)}"
                errors.append(error_msg)
                logger.error(f"修復 {table_name} 序列時出錯: {e}")
        
        # 提交變更
        db.session.commit()
        
        # 生成結果報告
        result_lines = [f"🔧 序列修復完成"]
        result_lines.append(f"✅ 成功修復: {fixed_count} 個表")
        
        if errors:
            result_lines.append(f"❌ 修復失敗: {len(errors)} 個表")
            for error in errors:
                result_lines.append(f"   - {error}")
        
        return "\n".join(result_lines)
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"修復序列時出錯: {e}")
        return f"❌ 修復失敗: {str(e)}"

def handle_sequence_fix_start(user_id):
    """開始序列修復流程"""
    logger.info(f"用戶 {user_id} 開始序列修復流程")
    
    try:
        # 檢查序列狀態
        results, need_fix = check_all_sequences()
        
        if not results:
            return {"type": "text", "text": "❌ 無法檢查序列狀態，請稍後再試"}
        
        # 生成報告
        report = format_sequence_report(results, need_fix)
        
        # 如果需要修復，保存狀態並添加 Quick Reply 按鈕
        if need_fix:
            # 保存狀態
            sequence_fix_states[user_id] = {
                "state": "waiting_confirm",
                "results": results,
                "need_fix": need_fix
            }
            
            # 使用標準化的按鈕
            buttons = [
                {"label": "✅ 確認修復", "text": "確認修復", "type": "message"},
                {"label": "❌ 取消", "text": "取消", "type": "message"}
            ]
            
            return QuickReplyManager.create_text_response(report, buttons)
        else:
            return QuickReplyManager.create_text_response(report)
        
    except Exception as e:
        logger.error(f"序列修復流程啟動失敗: {e}")
        return {"type": "text", "text": f"❌ 檢查序列時出錯: {str(e)}"}

def handle_sequence_fix_message(user_id, message_text):
    """處理序列修復流程中的消息"""
    if user_id not in sequence_fix_states:
        logger.info(f"用戶 {user_id} 不在序列修復流程中")
        return None
    
    # 處理取消指令
    if message_text.lower() in ["取消", "cancel", "退出", "exit"]:
        logger.info(f"用戶 {user_id} 取消序列修復流程")
        del sequence_fix_states[user_id]
        return {"type": "text", "text": "已取消序列修復操作"}
    
    current_state = sequence_fix_states[user_id]["state"]
    
    if current_state == "waiting_confirm":
        if message_text.lower() in ["確認修復", "確認", "yes", "y"]:
            need_fix = sequence_fix_states[user_id]["need_fix"]
            
            if not need_fix:
                del sequence_fix_states[user_id]
                return {"type": "text", "text": "✅ 所有序列都正常，無需修復"}
            
            # 執行修復
            logger.info(f"用戶 {user_id} 確認執行序列修復")
            result = fix_sequences(need_fix)
            
            # 清除狀態
            del sequence_fix_states[user_id]
            
            return {"type": "text", "text": result}
        else:
            return {"type": "text", "text": "請回覆「確認修復」來執行修復，或「取消」來取消操作"}
    
    return {"type": "text", "text": "未知操作，請回覆「確認修復」或「取消」"} 