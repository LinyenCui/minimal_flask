"""
處理固定班次請假功能的模組
參考 passenger_leave_handler.py 的設計，但操作對象是 fixed_schedules 表
"""
from datetime import datetime
from sqlalchemy.sql import text
import logging
from modules.models.base import db
from modules.utils.line_bot import get_user_display_name

# 建立日誌記錄器
logger = logging.getLogger(__name__)

def handle_fixed_schedule_leave_command(message_text, user_id):
    """處理固定班次請假命令"""
    try:
        logger.info(f"🎯 [fixed_schedule_leave_handler] 接收到命令: '{message_text}', 用戶: {user_id}")
        
        # 解析格式：固定班次請假 [固定班次ID] [加成] [原因]
        # 例如：固定班次請假 5 -50 診所乘客長期請假
        parts = message_text.split(maxsplit=3)  # 分割成4部分：命令 命令 ID 加成 原因
        logger.info(f"🎯 [fixed_schedule_leave_handler] 分割結果: {parts} (長度: {len(parts)})")
        
        if len(parts) < 4:
            error_msg = "請補充加成和原因資訊。\n\n📝 建議使用：/固定班表 [客戶簡稱] 查詢後點擊按鈕操作\n\n💡 完整格式：固定班次請假 [固定班次ID] [加成] [原因]\n範例：固定班次請假 5 -50 診所乘客長期請假"
            logger.warning(f"🎯 [fixed_schedule_leave_handler] 參數不足: {error_msg}")
            return error_msg
        
        try:
            fixed_schedule_id = int(parts[1])
            logger.info(f"🎯 [fixed_schedule_leave_handler] 解析固定班次ID: {fixed_schedule_id} (原始: '{parts[1]}')")
        except ValueError:
            error_msg = f"固定班次ID格式錯誤，請輸入數字，您輸入的是：{parts[1]}"
            logger.error(f"🎯 [fixed_schedule_leave_handler] ID格式錯誤: {error_msg}")
            return error_msg
        
        try:
            surcharge = int(parts[2])
            logger.info(f"🎯 [fixed_schedule_leave_handler] 解析加成: {surcharge} (原始: '{parts[2]}')")
        except ValueError:
            error_msg = f"加成格式錯誤，請輸入數字，您輸入的是：{parts[2]}"
            logger.error(f"🎯 [fixed_schedule_leave_handler] 加成格式錯誤: {error_msg}")
            return error_msg
        
        reason = parts[3].strip()
        if not reason:
            error_msg = "請提供請假原因說明"
            logger.warning(f"🎯 [fixed_schedule_leave_handler] 原因為空: {error_msg}")
            return error_msg
        
        logger.info(f"🎯 [fixed_schedule_leave_handler] 解析完成 - ID: {fixed_schedule_id}, 加成: {surcharge}, 原因: '{reason}'")
        logger.info(f"🎯 [fixed_schedule_leave_handler] 開始調用 process_fixed_schedule_leave...")
        
        return process_fixed_schedule_leave(fixed_schedule_id, surcharge, reason, user_id)
        
    except Exception as e:
        logger.error(f"處理固定班次請假命令時出錯: {e}")
        return f"處理固定班次請假命令時出錯: {e}"

def process_fixed_schedule_leave(fixed_schedule_id, surcharge, reason, user_id):
    """執行固定班次請假處理"""
    try:
        logger.info(f"🎯 [process_fixed_schedule_leave] 開始處理 - ID: {fixed_schedule_id}, 加成: {surcharge}, 原因: '{reason}', 用戶: {user_id}")
        
        # 查詢固定班次信息
        query = """
        SELECT 
            fs.id, 
            fs.route_number, 
            fs.departure_time, 
            fs.start_point,
            fs.end_point,
            fs.category,
            fs.status,
            fs.note,
            fs.base_fare,
            fs.surcharge,
            fs.total_fare
        FROM 
            fixed_schedules fs
        WHERE 
            fs.id = :fixed_schedule_id
        """
        
        logger.info(f"🎯 [process_fixed_schedule_leave] 執行查詢 - SQL: {query.strip()}")
        logger.info(f"🎯 [process_fixed_schedule_leave] 查詢參數: fixed_schedule_id = {fixed_schedule_id} (類型: {type(fixed_schedule_id)})")
        
        schedule = db.session.execute(text(query), {"fixed_schedule_id": fixed_schedule_id}).fetchone()
        
        logger.info(f"🎯 [process_fixed_schedule_leave] 查詢結果: {schedule}")
        
        if not schedule:
            error_msg = f"找不到ID為 {fixed_schedule_id} 的固定班次。"
            logger.error(f"🎯 [process_fixed_schedule_leave] {error_msg}")
            
            # 添加調試查詢：查看所有現有的固定班次ID
            debug_query = "SELECT id FROM fixed_schedules ORDER BY id LIMIT 20"
            try:
                all_ids = db.session.execute(text(debug_query)).fetchall()
                existing_ids = [row[0] for row in all_ids]
                logger.info(f"🎯 [process_fixed_schedule_leave] 調試 - 現有固定班次ID (前20個): {existing_ids}")
            except Exception as debug_e:
                logger.error(f"🎯 [process_fixed_schedule_leave] 調試查詢失敗: {debug_e}")
            
            return error_msg
        
        current_status = schedule[6] or '準備'
        current_note = schedule[7]
        original_surcharge = schedule[9] or 0
        
        # 檢查是否已經是請假狀態
        if current_status == '請假':
            return f"固定班次 #{fixed_schedule_id} 已經處於請假狀態。\n目前請假原因：{current_note or '無'}"
        
        # 更新固定班次為請假狀態，同時修改加成
        update_query = """
        UPDATE fixed_schedules
        SET status = '請假', 
            note = :leave_reason,
            surcharge = :new_surcharge,
            modified_by = :modified_by,
            modification_time = :modification_time
        WHERE id = :fixed_schedule_id
        RETURNING id
        """
        
        # 獲取用戶顯示名稱
        user_display_name = get_user_display_name(user_id) if user_id else "系統用戶"
        
        result = db.session.execute(text(update_query), {
            "fixed_schedule_id": fixed_schedule_id,
            "leave_reason": reason,
            "new_surcharge": surcharge,
            "modified_by": user_display_name,
            "modification_time": datetime.now()
        })
        
        # 提交事務
        db.session.commit()
        
        # 檢查更新結果
        updated_schedule = result.fetchone()
        if not updated_schedule:
            return f"更新固定班次 #{fixed_schedule_id} 請假狀態時出錯。"
        
        # 構建成功訊息
        success_message = f"✅ 固定班次 #{fixed_schedule_id} 請假設置完成\n\n"
        success_message += f"📝 請假原因：{reason}\n"
        success_message += f"💰 加成調整：{original_surcharge} → {surcharge} (變動{surcharge - original_surcharge})\n"
        success_message += f"🚌 路線：{schedule[1] or '未設定'}\n"
        success_message += f"🕐 時間：{schedule[2]}\n"
        success_message += f"📍 路線：{schedule[3]} → {schedule[4]}\n"
        success_message += f"📊 類別：{schedule[5] or '未分類'}\n\n"
        success_message += f"ℹ️ 下次匯入固定班次時，此班次將自動設為請假狀態"
        
        return success_message
        
    except Exception as e:
        logger.error(f"處理固定班次請假時出錯: {e}")
        db.session.rollback()
        return f"處理固定班次請假時出錯: {e}"

def handle_fixed_schedule_restore_command(message_text, user_id):
    """處理固定班次恢復命令"""
    try:
        # 解析格式：固定班次恢復 [固定班次ID]
        # 例如：固定班次恢復 5
        parts = message_text.split()
        
        if len(parts) < 2:
            return "格式不正確。請輸入：固定班次恢復 [固定班次ID]\n例如：固定班次恢復 5"
        
        try:
            fixed_schedule_id = int(parts[1])
        except ValueError:
            return f"固定班次ID格式錯誤，請輸入數字，您輸入的是：{parts[1]}"
        
        return process_fixed_schedule_restore(fixed_schedule_id, user_id)
        
    except Exception as e:
        logger.error(f"處理固定班次恢復命令時出錯: {e}")
        return f"處理固定班次恢復命令時出錯: {e}"

def process_fixed_schedule_restore(fixed_schedule_id, user_id):
    """執行固定班次恢復處理"""
    try:
        # 查詢固定班次信息
        query = """
        SELECT 
            fs.id, 
            fs.route_number, 
            fs.departure_time, 
            fs.start_point,
            fs.end_point,
            fs.category,
            fs.status,
            fs.note,
            fs.surcharge
        FROM 
            fixed_schedules fs
        WHERE 
            fs.id = :fixed_schedule_id
        """
        
        schedule = db.session.execute(text(query), {"fixed_schedule_id": fixed_schedule_id}).fetchone()
        
        if not schedule:
            return f"找不到ID為 {fixed_schedule_id} 的固定班次。"
        
        current_status = schedule[6] or '準備'
        current_note = schedule[7]
        current_surcharge = schedule[8] or 0
        
        # 檢查是否已經是準備狀態
        if current_status == '準備':
            return f"固定班次 #{fixed_schedule_id} 已經處於準備狀態，無需恢復。"
        
        # 更新固定班次為準備狀態，同時恢復加成為0（預設值）
        update_query = """
        UPDATE fixed_schedules
        SET status = '準備', 
            note = NULL,
            surcharge = 0,
            modified_by = :modified_by,
            modification_time = :modification_time
        WHERE id = :fixed_schedule_id
        RETURNING id
        """
        
        # 獲取用戶顯示名稱
        user_display_name = get_user_display_name(user_id) if user_id else "系統用戶"
        
        result = db.session.execute(text(update_query), {
            "fixed_schedule_id": fixed_schedule_id,
            "modified_by": user_display_name,
            "modification_time": datetime.now()
        })
        
        # 提交事務
        db.session.commit()
        
        # 檢查更新結果
        updated_schedule = result.fetchone()
        if not updated_schedule:
            return f"恢復固定班次 #{fixed_schedule_id} 狀態時出錯。"
        
        # 構建成功訊息
        success_message = f"✅ 固定班次 #{fixed_schedule_id} 已恢復為準備狀態\n\n"
        if current_note:
            success_message += f"📝 原請假原因：{current_note}\n"
        success_message += f"💰 加成調整：{current_surcharge} → 0 (變動{0 - current_surcharge})\n"
        success_message += f"🚌 路線：{schedule[1] or '未設定'}\n"
        success_message += f"🕐 時間：{schedule[2]}\n"
        success_message += f"📍 路線：{schedule[3]} → {schedule[4]}\n"
        success_message += f"📊 類別：{schedule[5] or '未分類'}\n\n"
        success_message += f"ℹ️ 下次匯入固定班次時，此班次將設為準備狀態"
        
        return success_message
        
    except Exception as e:
        logger.error(f"恢復固定班次時出錯: {e}")
        db.session.rollback()
        return f"恢復固定班次時出錯: {e}"

def get_fixed_schedule_status_display(schedule):
    """獲取固定班次的狀態顯示"""
    status = schedule.get('status', '準備')
    note = schedule.get('note')
    
    if status == '請假' and note:
        return f"請假 ({note})"
    elif status == '請假':
        return "請假"
    else:
        return status 