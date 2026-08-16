"""
LINE push 用量統計 — 回答「這個月的額度被什麼用完的」

背景（2026-08-17 用戶問到）：
    LINE 免費方案每月 200 則 push（reply 不計）。額度用完時，
    我們**查不出是被什麼吃掉的** —— 8 個 push 點的 log 格式各不相同，
    有些根本沒 log，而 LINE 官方 API 只給總數不給明細。

作法：每送出一則 push 就記一筆（來源 + 當月），存在既有的
    database_maintenance key-value 表（key 有唯一索引，可 UPSERT），
    不必開新表也不必 migration。免費額度上限 200 則/月，
    所以這個寫入量小到可以忽略。

    key   = push_count_{YYYYMM}_{source}
    value = 次數

刻意的取捨：
  · 絕不能影響推播本身 —— 全部包 try/except，統計壞掉就壞掉，
    不可以讓一則該送的通知因為記帳失敗而送不出去
  · 用 database.Session 直連，不依賴 Flask app context
    （排程器那條路沒有 request context）
  · 同時也 log 一行統一格式，Render log 也 grep 得到
"""
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

_KEY_PREFIX = 'push_count_'

# 來源代號 → 給人看的名字（新增 push 點時記得補一行，沒補也不會壞，只是顯示代號）
SOURCE_LABELS = {
    'booking': '預約叫車完成通知',
    'customer': '客戶新增/修改通知',
    'trip_status': '班次狀態變更通知',
    'batch_status': '批次狀態彙總通知',
    'import': '匯入固定班次廣播',
    'relay': '到院轉發',
    'scheduler': '排程異常告警',
    'liff': 'LIFF 其他通知',
}


def _month_key(source: str, when: datetime = None) -> str:
    ym = (when or datetime.now()).strftime('%Y%m')
    return f"{_KEY_PREFIX}{ym}_{source}"


def record_push(source: str, *, target_id: str = '') -> None:
    """記一則實際送出的 push。**絕不 raise**。

    只在「真的打了 LINE API」時呼叫 —— 走 chat_text 由前端 sendMessages
    的那些不算（那些不吃額度，記進來會讓數字失真）。
    """
    src = (source or 'unknown').strip() or 'unknown'
    # 統一格式的 log，Render log 直接 grep [PUSH-SENT] 就數得出來
    logger.info(f"[PUSH-SENT] source={src} to={(target_id or '')[:8]}…")
    try:
        from database import Session
        from sqlalchemy import text
        s = Session()
        try:
            s.execute(text("""
                INSERT INTO database_maintenance (key, value, timestamp, description)
                VALUES (:k, '1', :ts, :d)
                ON CONFLICT (key) DO UPDATE
                SET value = (COALESCE(database_maintenance.value, '0')::int + 1)::text,
                    timestamp = EXCLUDED.timestamp
            """), {'k': _month_key(src), 'ts': datetime.now(),
                   'd': f'push 用量統計：{SOURCE_LABELS.get(src, src)}'})
            s.commit()
        finally:
            s.close()
    except Exception as e:
        # 統計失敗絕不能影響推播本身
        logger.warning(f"[PUSH-SENT] 統計寫入失敗（不影響推播）: {e}")


def monthly_summary(when: datetime = None) -> dict:
    """本月各來源的 push 次數。

    Returns:
        {'month': '2026-08', 'total': 12, 'rows': [(source, label, count), ...]}
        讀失敗回 rows=[] 且帶 error（讓呼叫端顯示「查不到」而不是當機）
    """
    ym = (when or datetime.now()).strftime('%Y%m')
    out = {'month': f"{ym[:4]}-{ym[4:]}", 'total': 0, 'rows': [], 'error': None}
    try:
        from database import Session
        from sqlalchemy import text
        s = Session()
        try:
            rows = s.execute(text("""
                SELECT key, COALESCE(value, '0') FROM database_maintenance
                WHERE key LIKE :pat ORDER BY key
            """), {'pat': f"{_KEY_PREFIX}{ym}_%"}).fetchall()
        finally:
            s.close()
        parsed = []
        for k, v in rows:
            src = k[len(_KEY_PREFIX) + len(ym) + 1:]
            try:
                n = int(v)
            except (TypeError, ValueError):
                n = 0
            parsed.append((src, SOURCE_LABELS.get(src, src), n))
        parsed.sort(key=lambda x: -x[2])
        out['rows'] = parsed
        out['total'] = sum(n for _, _, n in parsed)
    except Exception as e:
        out['error'] = str(e)[:120]
    return out


def render_summary_text(when: datetime = None, quota: int = 200) -> str:
    """給 LINE 顯示的純文字（指令「推播用量」用）。"""
    d = monthly_summary(when)
    if d['error']:
        return f"❌ 查不到推播用量：{d['error']}"
    lines = [f"📊 {d['month']} 推播用量", ""]
    if not d['rows']:
        lines.append("本月還沒有送出任何 push。")
        lines.append("")
        lines.append("（LIFF 的通知現在都走 chat_text 由前端發送，不吃額度；")
        lines.append("　只有在 LINE 外面用瀏覽器開才會 fallback 成 push。）")
        return '\n'.join(lines)
    for _src, label, n in d['rows']:
        lines.append(f"　{label}　{n} 則")
    lines.append("")
    lines.append(f"合計 {d['total']} 則（免費額度 {quota} 則/月）")
    left = quota - d['total']
    if left <= 20:
        lines.append(f"⚠️ 只剩 {left} 則")
    else:
        lines.append(f"剩餘約 {left} 則")
    lines.append("")
    lines.append("※ 這是本系統自己記的，LINE 官方數字以 Developers Console 為準")
    return '\n'.join(lines)
