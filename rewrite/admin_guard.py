"""破壞性指令的管理員閘門（2026-08-01）

背景：司機自助回報車資讓司機第一次接觸 bot。私聊 1:1 是全收指令的，
司機一旦加 bot 好友，就能打「歸檔清理」（刪 Render 生產班次）、
「資料庫同步」、「解綁司機 N」等破壞性指令。

設計（安全的漸進式導入）：
  - 未設定 ADMIN_USER_IDS → 全部放行（維持現行行為，不會因為忘了設定而鎖死自己）
  - 設定後 → 只有名單內的 LINE user_id 能用破壞性指令，其餘回友善拒絕
  - 查詢類、司機回報車資、幫助等一律不受限
"""
import logging
import os

logger = logging.getLogger(__name__)

# 破壞性 / 管理類指令（前綴比對，涵蓋帶參數的形式）
GUARDED_PREFIXES = (
    '資料庫同步', '確認同步', '確認序號覆蓋', '取消同步', '放棄同步',
    '歸檔清理', '確認清理', '取消清理',
    '重置班次序號',
    '新增司機', '停用司機', '啟用司機', '解綁司機',
)

_DENY_TEXT = (
    '🔒 這是管理指令，只有管理員可以使用。\n'
    '如需協助請聯繫公司。'
)


def _admin_ids() -> set:
    raw = os.environ.get('ADMIN_USER_IDS', '')
    return {x.strip() for x in raw.replace('\n', ',').split(',') if x.strip()}


def is_guarded(text: str) -> bool:
    """這則訊息是否為受管制的破壞性指令"""
    t = (text or '').strip().lstrip('/').lstrip('!').lstrip('！').strip()
    return t.startswith(GUARDED_PREFIXES)


def is_admin(user_id) -> bool:
    """未設定名單 → 一律視為管理員（向後相容）"""
    ids = _admin_ids()
    if not ids:
        return True
    return bool(user_id) and user_id in ids


def check(text: str, user_id) -> str | None:
    """回拒絕訊息（str）表示要擋；None 表示放行。"""
    if not is_guarded(text):
        return None
    if is_admin(user_id):
        return None
    logger.warning(
        f"[admin_guard] 擋下非管理員的破壞性指令: user={str(user_id)[:10]}… text={text[:20]!r}")
    return _DENY_TEXT
