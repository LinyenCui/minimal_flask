
"""
資料庫同步處理器 - 透過 LINE Bot 控制 Render 資料同步
(現代化版本，呼叫外部腳本)
"""
import os
import subprocess
import logging
from modules.utils.line_bot import get_user_display_name, get_line_bot_api

logger = logging.getLogger(__name__)

class DatabaseSyncHandler:
    """
    資料庫同步處理器。
    這個類別現在作為一個包裝器，主要負責檢查設定和呼叫外部的、
    功能更強大的 sync_from_render.py 腳本。
    """
    
    def __init__(self):
        self.render_host = os.getenv('RENDER_DB_HOST')
        self.render_user = os.getenv('RENDER_DB_USER') 
        self.render_db = os.getenv('RENDER_DB_NAME')
        self.render_password = os.getenv('RENDER_DB_PASSWORD')
        self.local_db = os.getenv('LOCAL_DB_NAME', 'dispatch_db')
        
    def check_render_connection(self):
        """檢查執行同步所需的核心環境變數"""
        missing = []
        if not self.render_host:
            missing.append("RENDER_DB_HOST")
        if not self.render_user:
            missing.append("RENDER_DB_USER")
        if not self.render_db:
            missing.append("RENDER_DB_NAME")
        if not self.render_password:
            missing.append("RENDER_DB_PASSWORD")
        return missing

    def get_database_stats(self, is_render=False):
        """獲取資料庫統計資訊，用於在確認前顯示給使用者"""
        try:
            env = os.environ.copy()
            command_args = ['psql', '-t']

            if is_render:
                env['PGPASSWORD'] = self.render_password
                command_args.extend(['-h', self.render_host, '-U', self.render_user, '-d', self.render_db])
            else:
                command_args.extend(['-d', self.local_db])

            sql = """
            SELECT 'trips: ' || COUNT(*) FROM trips UNION ALL
            SELECT 'completed_trips: ' || COUNT(*) FROM completed_trips UNION ALL
            SELECT 'customers: ' || COUNT(*) FROM customers UNION ALL
            SELECT 'drivers: ' || COUNT(*) FROM drivers UNION ALL
            SELECT 'account_ledger: ' || COUNT(*) FROM account_ledger UNION ALL
            SELECT 'payments: ' || COUNT(*) FROM payments;
            """
            command_args.extend(['-c', sql])
            
            result = subprocess.run(command_args, capture_output=True, text=True, env=env, timeout=30)
            
            if result.returncode == 0:
                return result.stdout.strip()
            else:
                # 截斷錯誤訊息以保持回應簡潔
                error_msg = result.stderr.split('\n')[0]
                return f"查詢失敗: {error_msg}"
                    
        except subprocess.TimeoutExpired:
            return "連線超時"
        except Exception as e:
            return f"錯誤: {str(e)}"

def check_sequence_conflicts():
    """檢查序號衝突"""
    try:
        import sys
        python_executable = sys.executable
        script_path = "scripts/sync_from_render.py"
        
        result = subprocess.run(
            [python_executable, script_path, "--check-only"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        # 返回碼 1 表示有衝突，0 表示無衝突
        if result.returncode == 1:
            return {"has_conflicts": True, "output": result.stdout}
        elif result.returncode == 0:
            return {"has_conflicts": False, "output": result.stdout}
        else:
            return {"has_conflicts": False, "error": result.stderr}
            
    except Exception as e:
        logger.error(f"檢查序號衝突時發生錯誤: {e}")
        return {"has_conflicts": False, "error": str(e)}

def handle_database_sync_request(event, line_bot_api):
    """處理資料庫同步請求，顯示狀態並提供確認按鈕"""
    user_id = event.source.user_id
    user_name = get_user_display_name(user_id)
    
    logger.info(f"用戶 {user_name} 請求資料庫同步檢查")
    
    sync_handler = DatabaseSyncHandler()
    
    missing_config = sync_handler.check_render_connection()
    if missing_config:
        response_text = "❌ Render 資料庫連線設定不完整\n缺少：\n" + "\n".join([f"• {c}" for c in missing_config])
        return {"type": "text", "text": response_text}
    
    # 檢查序號衝突
    conflict_result = check_sequence_conflicts()
    
    response_text = "📊 資料庫同步狀態檢查\n"
    response_text += "=" * 20 + "\n"
    response_text += "🏠 本地資料庫：\n" + sync_handler.get_database_stats(is_render=False) + "\n\n"
    response_text += "☁️ Render 資料庫：\n" + sync_handler.get_database_stats(is_render=True) + "\n\n"
    
    # 顯示序號衝突檢查結果
    if conflict_result.get("has_conflicts"):
        response_text += "⚠️ 序號衝突檢測：\n"
        # 從輸出中提取關鍵信息
        if "發現" in conflict_result.get("output", ""):
            conflict_lines = [line for line in conflict_result["output"].split('\n') 
                            if '發現' in line or '表名:' in line or '本地序號:' in line or '遠端序號:' in line]
            response_text += "\n".join(conflict_lines[:10])  # 限制顯示行數
        else:
            response_text += "發現序號衝突，詳情請查看日誌"
        response_text += "\n\n"
    else:
        response_text += "✅ 序號衝突檢測：未發現衝突\n\n"
    
    response_text += "⚠️ 同步將使用混合模式進行：\n"
    response_text += "• `completed_trips` 將只增不減。\n"
    response_text += "• 其他資料表將被完全覆蓋。\n"
    
    # 如果有序號衝突，增加警告信息
    if conflict_result.get("has_conflicts"):
        response_text += "• ⚠️ 檢測到序號衝突，將以遠端序號為主覆蓋本地\n"
    
    response_text += "\n確定要執行同步嗎？"
    
    from modules.utils.quick_reply_manager import QuickReplyManager
    
    # 使用新的 Quick Reply 標準格式
    if conflict_result.get("has_conflicts"):
        confirm_buttons = [
            {"label": "⚡ 強制同步", "text": "確認序號覆蓋", "type": "message"},
            {"label": "❌ 放棄操作", "text": "放棄", "type": "message"}
        ]
    else:
        confirm_buttons = [
            {"label": "✅ 確認同步", "text": "確認同步", "type": "message"},
            {"label": "❌ 放棄操作", "text": "放棄", "type": "message"}
        ]
    
    return QuickReplyManager.create_text_response(response_text, confirm_buttons)

def handle_database_sync_confirm(event, line_bot_api_passed=None):
    """處理資料庫同步確認，執行新的 sync_from_render.py 腳本"""
    import sys
    import traceback
    import datetime

    user_id = event.source.user_id
    user_name = get_user_display_name(user_id)
    
    # 檢測是否是強制同步模式
    force_sync = False
    if hasattr(event, 'message') and hasattr(event.message, 'text'):
        message_text = event.message.text.strip()
        if message_text == "確認序號覆蓋":
            force_sync = True
    
    from linebot.v3.messaging import (
        ReplyMessageRequest,
        TextMessage
    )

    line_bot_api = line_bot_api_passed or get_line_bot_api()
    
    # 立即回覆開始訊息，包含查詢提示
    if force_sync:
        start_message = f"⚡ {user_name} 開始執行強制同步 (序號覆蓋模式)...\n"
    else:
        start_message = f"🚀 {user_name} 開始執行資料庫同步...\n"
    start_message += "⏱️ 預計需要 30-60 秒\n"
    start_message += "💡 完成後輸入「同步結果」查看結果"
    
    try:
        reply_request = ReplyMessageRequest(
            reply_token=event.reply_token,
            messages=[TextMessage(text=start_message)]
        )
        line_bot_api.reply_message(reply_request)
        logger.info(f"已回覆用戶 {user_id} 同步開始訊息")
    except Exception as reply_error:
        logger.error(f"回覆同步開始訊息失敗: {reply_error}")
        return start_message

    if force_sync:
        logger.info(f"用戶 {user_name} 確認執行強制資料庫同步 (序號覆蓋模式)...")
    else:
        logger.info(f"用戶 {user_name} 確認執行資料庫同步...")

    # 使用 sys.executable 確保使用正確的 Python 解釋器
    python_executable = sys.executable
    script_path = "scripts/sync_from_render.py"
    
    # 構建命令參數
    command_args = [python_executable, script_path]
    if force_sync:
        command_args.append("--force")
    
    logger.info(f"將要執行的命令: {' '.join(command_args)}")

    try:
        process = subprocess.run(
            command_args,
            capture_output=True,
            text=True,
            timeout=50,  # 縮短到50秒
            check=False
        )

        # 同步成功後，自動補本地測試 seed（不影響 Render）
        # 詳見 scripts/post_sync_seed.py
        seed_msg = ""
        if process.returncode == 0:
            try:
                seed_process = subprocess.run(
                    [python_executable, "scripts/post_sync_seed.py"],
                    capture_output=True, text=True, timeout=15, check=False,
                )
                if seed_process.returncode == 0:
                    # 從 seed stdout 抓「範例患者: 新增 X 筆、更新 Y 筆」
                    seed_msg = "\n🌱 補種子完成"
                    for line in seed_process.stdout.splitlines():
                        if '範例患者' in line:
                            seed_msg = f"\n🌱 {line.strip()}"
                            break
                    logger.info(f"post_sync_seed 完成: {seed_msg}")
                else:
                    seed_msg = f"\n⚠️ 補種子失敗 (exit {seed_process.returncode})"
                    logger.warning(f"post_sync_seed stderr: {seed_process.stderr[:300]}")
            except subprocess.TimeoutExpired:
                seed_msg = "\n⚠️ 補種子超時 (>15s)"
                logger.error("post_sync_seed 超時")
            except Exception as seed_err:
                seed_msg = f"\n⚠️ 補種子異常: {str(seed_err)[:100]}"
                logger.error(f"post_sync_seed 異常: {seed_err}")

        # 準備結果訊息
        if process.returncode == 0:
            final_response_text = "🎉 資料庫同步完成！\n\n"
        else:
            final_response_text = "❌ 同步過程中發生錯誤！\n\n"

        # 簡化輸出，避免訊息過長
        if process.stdout:
            stdout_lines = process.stdout.strip().split('\n')
            important_lines = [line for line in stdout_lines[-10:] if '成功' in line or '完成' in line or '錯誤' in line or '失敗' in line]
            if important_lines:
                final_response_text += "📋 重要結果:\n" + '\n'.join(important_lines[-5:])
        
        if process.stderr:
            final_response_text += f"\n⚠️ 警告: {process.stderr[:500]}"

        # 把 post_sync_seed 結果附加到回覆
        if seed_msg:
            final_response_text += seed_msg

    except subprocess.TimeoutExpired:
        logger.error("同步腳本執行超時")
        final_response_text = "⏰ 同步超時！\n腳本執行超過50秒。可能需要手動檢查同步狀態。"
    except Exception as e:
        logger.error(f"執行同步腳本時發生未知錯誤: {e}")
        logger.error(traceback.format_exc())
        final_response_text = f"❌ 執行失敗: {str(e)[:200]}"

    # 儲存同步結果到文件，供後續查詢
    try:
        result_file = "last_sync_result.txt"
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(result_file, 'w', encoding='utf-8') as f:
            f.write(f"同步時間: {timestamp}\n")
            f.write(f"執行用戶: {user_name}\n")
            f.write("=" * 40 + "\n")
            f.write(final_response_text)
        
        logger.info(f"✅ 同步結果已儲存到 {result_file}")
        logger.info(f"同步完成，結果: {final_response_text}")
        
    except Exception as save_error:
        logger.error(f"❌ 儲存同步結果失敗: {save_error}")
    
    return None


def handle_sync_result_query(event, line_bot_api_passed=None):
    """處理同步結果查詢，提供詳細的錯誤信息"""
    import os
    
    line_bot_api = line_bot_api_passed or get_line_bot_api()
    
    try:
        result_file = "last_sync_result.txt"
        if os.path.exists(result_file):
            with open(result_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 分析內容，提供結構化顯示
            lines = content.split('\n')
            
            # 提取基本信息
            basic_info = []
            error_info = []
            full_logs = []
            solutions = []
            
            current_section = "basic"
            
            for line in lines:
                if line.startswith('同步時間:') or line.startswith('執行用戶:') or line.startswith('返回碼:') or line.startswith('錯誤概要:'):
                    basic_info.append(line)
                elif '錯誤輸出日誌:' in line:
                    current_section = "error"
                elif '完整輸出日誌:' in line:
                    current_section = "full"
                elif '常見問題解決方案:' in line:
                    current_section = "solutions"
                elif current_section == "error" and line.strip() and not line.startswith('-'):
                    error_info.append(line)
                elif current_section == "solutions" and line.strip() and line.startswith('•'):
                    solutions.append(line)
                elif current_section == "full" and line.strip() and not line.startswith('-'):
                    full_logs.append(line)
            
            # 構建回覆訊息
            response_parts = []
            
            # 基本信息
            response_parts.append("📊 同步結果摘要")
            response_parts.append("=" * 20)
            response_parts.extend(basic_info)
            response_parts.append("")
            
            # 如果有錯誤，優先顯示錯誤
            if error_info:
                response_parts.append("⚠️ 錯誤詳情")
                response_parts.append("-" * 15)
                # 只顯示前5行最重要的錯誤
                for error in error_info[:5]:
                    if any(keyword in error for keyword in ['total_fare', 'users', 'sequence', 'connection', 'ERROR', 'FATAL']):
                        response_parts.append(f"🔍 {error.strip()}")
                
                if len(error_info) > 5:
                    response_parts.append(f"... 還有 {len(error_info) - 5} 行錯誤")
                response_parts.append("")
            
            # 解決方案
            if solutions:
                response_parts.append("💡 解決建議")
                response_parts.append("-" * 15)
                response_parts.extend(solutions[:4])  # 最多顯示4個建議
                response_parts.append("")
            
            # 組合回覆，控制長度
            response_text = '\n'.join(response_parts)
            
            # 如果訊息太長，分段顯示
            if len(response_text) > 1500:
                # 先顯示摘要和錯誤
                summary_parts = []
                summary_parts.extend(basic_info)
                
                if error_info:
                    summary_parts.append("\n⚠️ 主要錯誤:")
                    for error in error_info[:3]:
                        if 'total_fare' in error:
                            summary_parts.append("🔧 生成欄位錯誤")
                        elif 'users' in error:
                            summary_parts.append("📋 資料表缺失")
                        elif 'sequence' in error:
                            summary_parts.append("🔢 序列問題")
                        else:
                            summary_parts.append(f"❌ {error[:50]}...")
                
                summary_parts.append("\n💡 完整日誌已儲存")
                summary_parts.append("如需查看更多詳情，請聯繫管理員")
                
                response_text = '\n'.join(summary_parts)
            
        else:
            response_text = "📝 尚無同步記錄\n\n"
            response_text += "請先執行以下步驟：\n"
            response_text += "1. 輸入「資料庫同步」\n"
            response_text += "2. 點擊「確認同步」\n"
            response_text += "3. 等待完成後再查詢結果"
    
    except Exception as e:
        logger.error(f"讀取同步結果失敗: {e}")
        response_text = f"❌ 讀取同步結果失敗\n\n"
        response_text += f"錯誤: {e}\n\n"
        response_text += "💡 請檢查：\n"
        response_text += "• 是否已執行過同步\n"
        response_text += "• 檔案權限是否正確\n"
        response_text += "• 磁碟空間是否足夠"
    
    from linebot.v3.messaging import ReplyMessageRequest, TextMessage
    
    reply_request = ReplyMessageRequest(
        reply_token=event.reply_token,
        messages=[TextMessage(text=response_text)]
    )
    line_bot_api.reply_message(reply_request)
    
    return response_text

def handle_database_sync_confirm_free(event, line_bot_api_passed=None):
    """處理資料庫同步確認，執行快速同步並立即回覆結果（免費版兼容）"""
    import sys
    import traceback
    import datetime

    user_id = event.source.user_id
    user_name = get_user_display_name(user_id)
    
    from linebot.v3.messaging import (
        ReplyMessageRequest,
        TextMessage
    )

    line_bot_api = line_bot_api_passed or get_line_bot_api()
    
    logger.info(f"用戶 {user_name} 確認執行快速資料庫同步...")

    # 使用 sys.executable 確保使用正確的 Python 解釋器
    python_executable = sys.executable
    script_path = "scripts/sync_from_render.py"
    
    logger.info(f"將要執行的命令: {python_executable} {script_path}")

    try:
        # 立即開始同步，設定較短的超時
        process = subprocess.run(
            [python_executable, script_path],
            capture_output=True,
            text=True,
            timeout=45,  # 45秒超時，確保能在reply_token有效期內完成
            check=False
        )

        # 準備結果訊息
        if process.returncode == 0:
            final_response_text = f"✅ {user_name} 資料庫同步完成！\n\n"
            error_summary = ""
        else:
            final_response_text = f"❌ {user_name} 同步過程有錯誤！\n\n"
            error_summary = "有錯誤發生"

        # 提取重要資訊，包括錯誤
        if process.stdout:
            stdout_lines = process.stdout.strip().split('\n')
            # 顯示成功和錯誤信息
            success_lines = [line for line in stdout_lines if '✅' in line or '完全同步成功' in line]
            error_lines = [line for line in stdout_lines if '❌' in line or 'ERROR' in line or 'FATAL' in line]
            
            if success_lines:
                final_response_text += "📋 同步結果:\n" + '\n'.join(success_lines[-3:]) + "\n\n"
            
            if error_lines:
                final_response_text += "⚠️ 發現錯誤:\n" + '\n'.join(error_lines[-2:]) + "\n\n"
                error_summary = f"發現 {len(error_lines)} 個錯誤"
        
        # 處理stderr錯誤
        if process.stderr:
            error_lines = process.stderr.strip().split('\n')
            # 顯示關鍵錯誤類型
            critical_errors = []
            
            for line in error_lines:
                if 'total_fare' in line:
                    critical_errors.append("🔧 生成欄位插入錯誤")
                elif 'users' in line and '不存在' in line:
                    critical_errors.append("📋 缺少資料表")
                elif 'completed_trips' in line:
                    if 'actual_fare' in line or 'total_fare' in line:
                        critical_errors.append("💾 completed_trips生成欄位錯誤")
                    else:
                        critical_errors.append("💾 completed_trips問題")
                elif 'sequence' in line:
                    critical_errors.append("🔢 序列錯誤")
                elif 'connection' in line.lower():
                    critical_errors.append("🔌 連線問題")
                elif 'timeout' in line.lower():
                    critical_errors.append("⏰ 超時錯誤")
            
            if critical_errors:
                final_response_text += "🔍 錯誤類型:\n" + '\n'.join(set(critical_errors)) + "\n\n"
                error_summary = f"{len(set(critical_errors))} 種錯誤類型"
        
        # 添加查看詳細錯誤的指引
        if process.returncode != 0:
            final_response_text += "💡 查看完整錯誤：輸入「同步結果」\n"
            final_response_text += "📞 如需協助請提供完整錯誤日誌"

    except subprocess.TimeoutExpired:
        logger.error("快速同步超時")
        final_response_text = f"⏰ {user_name} 同步超時\n"
        final_response_text += "可能原因：\n• 網路連線緩慢\n• 資料量過大\n• 伺服器負載高\n\n"
        final_response_text += "💡 輸入「同步結果」查看詳細狀態"
        error_summary = "超時錯誤"
    except Exception as e:
        logger.error(f"執行同步時發生錯誤: {e}")
        final_response_text = f"❌ {user_name} 同步執行失敗\n\n"
        final_response_text += f"錯誤類型: {type(e).__name__}\n"
        final_response_text += f"錯誤描述: {str(e)[:200]}\n\n"
        final_response_text += "💡 輸入「同步結果」查看完整錯誤"
        error_summary = f"執行失敗: {type(e).__name__}"

    # 不再截斷訊息，讓完整錯誤顯示在群組中
    # if len(final_response_text) > 1000:
    #     final_response_text = final_response_text[:1000] + "\n\n...(使用「同步結果」查看完整)"
        
    # 儲存詳細結果供後續查詢
    try:
        result_file = "last_sync_result.txt"
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(result_file, 'w', encoding='utf-8') as f:
            f.write(f"同步時間: {timestamp}\n")
            f.write(f"執行用戶: {user_name}\n")
            f.write(f"返回碼: {getattr(process, 'returncode', 'N/A')}\n")
            f.write(f"錯誤概要: {error_summary}\n")
            f.write("=" * 50 + "\n\n")
            
            if hasattr(process, 'returncode'):
                if process.returncode == 0:
                    f.write("🎉 同步成功完成！\n\n")
                else:
                    f.write("❌ 同步過程中發生錯誤！\n\n")
            
            if hasattr(process, 'stdout') and process.stdout:
                f.write("📋 完整輸出日誌:\n")
                f.write("-" * 30 + "\n")
                f.write(process.stdout)
                f.write("\n" + "-" * 30 + "\n\n")
            
            if hasattr(process, 'stderr') and process.stderr:
                f.write("⚠️ 錯誤輸出日誌:\n")
                f.write("-" * 30 + "\n")
                f.write(process.stderr)
                f.write("\n" + "-" * 30 + "\n\n")
            
            f.write("💡 常見問題解決方案:\n")
            f.write("• total_fare錯誤 → 生成欄位問題，腳本需更新\n")
            f.write("• users表錯誤 → 移除不存在的表\n")
            f.write("• completed_trips錯誤 → 增量同步生成欄位過濾問題\n")
            f.write("• 序列錯誤 → 執行序列校準\n")
            f.write("• 連線錯誤 → 檢查網路和資料庫狀態\n")
        
        logger.info(f"✅ 同步結果已儲存（{error_summary}），立即回覆用戶")
        
    except Exception as save_error:
        logger.error(f"❌ 儲存同步結果失敗: {save_error}")
        final_response_text += f"\n\n⚠️ 無法儲存結果日誌: {save_error}"

    # 立即回覆結果（免費版兼容）
    try:
        reply_request = ReplyMessageRequest(
            reply_token=event.reply_token,
            messages=[TextMessage(text=final_response_text)]
        )
        line_bot_api.reply_message(reply_request)
        logger.info(f"✅ 已立即回覆同步結果給用戶 {user_id}")
        
    except Exception as reply_error:
        logger.error(f"❌ 回覆同步結果失敗: {reply_error}")
        return final_response_text
    
    return None
