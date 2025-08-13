"""
輕路由：幫助系統入口
行為維持不變，委派給既有 HelpHandler。
"""
import logging
from modules.utils.line_bot import reply_text
from modules.help_system.help_handler import HelpHandler

logger = logging.getLogger(__name__)

_help_handler = HelpHandler()

HELP_TRIGGERS = {"幫助", "幫助文字", "完整指令列表", "搜尋幫助", "help_system_check"}
CLINIC_SHORT_HELP = {"診所座標", "座標幫助", "到院提醒"}

def handle_help_commands(message_text: str, user_id: str, reply_token: str) -> bool:
    try:
        if message_text in HELP_TRIGGERS or message_text.startswith(("help_category_", "help_item_", "help_search_", "help_demo_")):
            handled = _help_handler.handle_help_request(message_text, user_id, reply_token)
            if not handled:
                reply_text(reply_token, "無可用的幫助項目")
            # 若是帳務處理分類，直接顯示餘額與Quick Reply（可操作）
            if message_text == "help_category_accounting":
                try:
                    from modules.handlers.accounting import show_accounting_menu
                    show_accounting_menu(reply_token)
                except Exception as e:
                    logger.error(f"[help_router] 帳務處理分類顯示失敗: {e}")
                    from modules.utils.line_bot import reply_text
                    reply_text(reply_token, "帳務處理暫時不可用")
                return True
            return True
        if message_text in CLINIC_SHORT_HELP:
            reply_text(reply_token, "🏥 到院提醒\n・設定診所 22.999 120.222（或：設定診所 → 傳一則位置）\n・設定平均車速 30\n・查看平均車速\n・在群組有人傳位置訊息時，系統會顯示距離與預估幾分鐘到，並提醒『請準備輪椅』。\n・（進階）若設 MAPS_PROVIDER=google 並提供 GOOGLE_MAPS_API_KEY，將改用 Google 路線距離與行車時間。\n\n🏷️ 群組地點名稱與到院訊息\n・設定地點名稱 診所\n・設定到院訊息 🧑‍🦽 請準備輪椅\\n距離：{distance_km} 公里，約 {eta_min} 分鐘（{provider}）\n・查看到院設定\n・恢復預設到院訊息")
            return True
        return False
    except Exception as e:
        logger.error(f"[help_router] 幫助命令處理失敗: {e}", exc_info=True)
        reply_text(reply_token, "幫助系統暫時不可用")
        return True
