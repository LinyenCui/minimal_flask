"""
Rewrite v0.1 LINE 路由 — 整合測試用入口

接收 LINE event，攔截 rewrite 命令並呼叫新 tools + views 回應。
不匹配 → 回 False，讓既有 process_text_message 繼續處理。

支援命令（自然語法，無前綴）：

  客戶領域：
    查客戶 <term>          — 模糊查詢（cascade fallback）
    客戶詳情 <id>          — 單筆 ID 查詢
    病歷層 <day>           — 列出某層所有客戶（1-31）
    病歷層分布             — 各層分布總覽

  班次領域：
    查班次 [日期]          — 班次列表（預設今天）
    診所班次 [日期]        — 同上 + category=診所
    東洋班次 [日期]        — 同上 + category=東洋
    班次詳情 <trip_id>     — 單筆班次詳情
    待派班次               — 沒指派司機的班次
"""
import logging
import re
from datetime import date

from database import Session
from modules.utils.line_bot import reply_message
from modules.utils.unified_date_parser import UnifiedDateParser
from rewrite.tools.customer import (
    query_customer_by_term,
    get_customer_by_id,
    query_customers_by_birthday_day,
    query_birthday_day_summary,
)
from rewrite.tools.trip import (
    query_trips,
    query_trip_by_id,
    query_today_trips,
    query_pending_dispatch,
)
from rewrite.views.customer_flex import (
    render_customer_detail,
    render_birthday_layer_carousel,
)
from rewrite.views.trip_flex import (
    render_trip_detail,
    render_trip_list_carousel,
)

logger = logging.getLogger(__name__)


# 客戶命令 regex
_RE_QUERY = re.compile(r'^查客戶(?:\s+(.+))?$')
_RE_DETAIL = re.compile(r'^客戶詳情\s+(\d+)$')
_RE_LAYER = re.compile(r'^病歷層\s+(\d+)$')
_RE_LAYER_SUMMARY = re.compile(r'^病歷層分布$')

# 班次命令 regex
_RE_TRIP_DETAIL = re.compile(r'^班次詳情\s+(\d+)$')
_RE_TRIP_LIST = re.compile(r'^(查|診所|東洋)班次(?:\s+(.+))?$')
_RE_PENDING = re.compile(r'^待派班次$')


def try_route(event) -> bool:
    """
    嘗試處理 event。回 True 表示已處理（不要走主流程）。
    """
    text = (event.message.text or '').strip()

    # 處理群組 prefix：剝掉 / 或 # （但保留 ! ！ — 那是 sandbox 的）
    for p in ('/', '#'):
        if text.startswith(p):
            text = text[len(p):].lstrip()
            break

    # 提早退出：不像我們的命令
    rewrite_prefixes = ('查客戶', '客戶詳情', '病歷層',
                        '查班次', '診所班次', '東洋班次',
                        '班次詳情', '待派班次')
    if not text.startswith(rewrite_prefixes):
        return False

    reply_token = event.reply_token
    session = Session()

    try:
        # ===== 客戶命令 =====
        m = _RE_DETAIL.match(text)
        if m:
            return _handle_customer_detail(reply_token, session, int(m.group(1)))

        m = _RE_QUERY.match(text)
        if m:
            term = (m.group(1) or '').strip()
            if not term:
                _send_help(reply_token)
                return True
            return _handle_customer_query(reply_token, session, term)

        m = _RE_LAYER.match(text)
        if m:
            return _handle_birthday_layer(reply_token, session, int(m.group(1)))

        if _RE_LAYER_SUMMARY.match(text):
            return _handle_layer_summary(reply_token, session)

        # ===== 班次命令 =====
        m = _RE_TRIP_DETAIL.match(text)
        if m:
            return _handle_trip_detail(reply_token, session, int(m.group(1)))

        if _RE_PENDING.match(text):
            return _handle_pending_dispatch(reply_token, session)

        m = _RE_TRIP_LIST.match(text)
        if m:
            kind = m.group(1)  # 查 / 診所 / 東洋
            arg = (m.group(2) or '').strip()
            return _handle_trip_list(reply_token, session, kind, arg)

        # 開頭看似但格式不對 → 提示
        _send_help(reply_token)
        return True

    except Exception as e:
        logger.error(f"rewrite router 異常: {e}", exc_info=True)
        try:
            reply_message(reply_token, {
                "type": "text",
                "text": f"⚠️ rewrite 處理錯誤：{str(e)[:200]}"
            })
        except Exception:
            pass
        return True
    finally:
        session.close()


# ============================================================
# Handlers
# ============================================================

def _handle_customer_detail(reply_token, session, customer_id: int) -> bool:
    r = get_customer_by_id(customer_id, session=session, mask_id=True)
    if not r.ok:
        reply_message(reply_token, {"type": "text", "text": f"❌ {r.error}"})
        return True

    bubble = render_customer_detail(r.data)
    reply_message(reply_token, {
        "type": "flex",
        "altText": f"客戶詳情 #{customer_id}",
        "contents": bubble,
    })
    return True


def _handle_customer_query(reply_token, session, term: str) -> bool:
    r = query_customer_by_term(term, session=session, mask_id=True)
    if not r.ok:
        reply_message(reply_token, {"type": "text", "text": f"❌ {r.error}"})
        return True

    customers = r.data
    matched_by = r.meta.get('matched_by', '?')

    if len(customers) == 1:
        # 1 筆 → 直接詳情卡
        bubble = render_customer_detail(customers[0])
        reply_message(reply_token, {
            "type": "flex",
            "altText": f"找到客戶：{customers[0].name}",
            "contents": bubble,
        })
    else:
        # 多筆 → 文字列表 + 使用提示
        lines = [f"找到 {len(customers)} 筆（命中欄位：{matched_by}）："]
        for c in customers[:20]:
            lines.append(f"  #{c.id} {c.name} (簡稱:{c.short_name or '—'})")
        if len(customers) > 20:
            lines.append(f"  ⋯ 還有 {len(customers) - 20} 筆")
        lines.append("\n💡 用「客戶詳情 <ID>」看單筆詳情")
        reply_message(reply_token, {"type": "text", "text": "\n".join(lines)})
    return True


def _handle_birthday_layer(reply_token, session, day: int) -> bool:
    r = query_customers_by_birthday_day(day=day, session=session, mask_id=True)
    if not r.ok:
        # 空層也用 view 渲染（產生空層 bubble）
        flex = render_birthday_layer_carousel(day, [])
        reply_message(reply_token, {
            "type": "flex",
            "altText": f"病歷層 {day} 日（空）",
            "contents": flex,
        })
        return True

    flex = render_birthday_layer_carousel(day, r.data)
    reply_message(reply_token, {
        "type": "flex",
        "altText": f"病歷層 {day} 日（{len(r.data)} 人）",
        "contents": flex,
    })
    return True


def _handle_layer_summary(reply_token, session) -> bool:
    r = query_birthday_day_summary(session=session)
    if not r.ok or not r.data:
        reply_message(reply_token, {"type": "text", "text": "目前無客戶有生日資料"})
        return True

    lines = ["📋 病歷層分布"]
    for day, cnt in r.data:
        bar = '█' * min(cnt, 20)
        lines.append(f"  {day:2d} 日: {bar} ({cnt})")
    total_layers = r.meta.get('total_layers', len(r.data))
    total_customers = r.meta.get('total_customers_with_birthday', sum(c for _, c in r.data))
    lines.append(f"\n共 {total_layers} 層、{total_customers} 個客戶有生日資料")

    reply_message(reply_token, {"type": "text", "text": "\n".join(lines)})
    return True


# ============================================================
# 班次 handlers
# ============================================================

def _handle_trip_detail(reply_token, session, trip_id: int) -> bool:
    r = query_trip_by_id(trip_id, session=session)
    if not r.ok:
        reply_message(reply_token, {"type": "text", "text": f"❌ {r.error}"})
        return True
    bubble = render_trip_detail(r.data)
    reply_message(reply_token, {
        "type": "flex",
        "altText": f"班次 #{trip_id} 詳情",
        "contents": bubble,
    })
    return True


def _handle_pending_dispatch(reply_token, session) -> bool:
    r = query_pending_dispatch(session=session)
    if not r.ok:
        reply_message(reply_token, {"type": "text", "text": r.error})
        return True
    flex = render_trip_list_carousel(r.data, header_title="🔴 待派班次")
    reply_message(reply_token, {
        "type": "flex",
        "altText": f"待派班次（{len(r.data)} 筆）",
        "contents": flex,
    })
    return True


def _parse_trip_args(arg: str) -> tuple:
    """
    解析 「查/診所/東洋班次 <args>」 的 arg 部分

    支援格式：
        ""              → today
        "今天"          → today
        "5/2"           → 2026-05-02
        "4/26-5/2"      → 範圍
        "5/2 司機533"   → date + driver

    回傳 (date_from, date_to, driver_id, error_msg)
    error_msg != None 表示解析失敗
    """
    arg = arg.strip()

    # 空 → 今天
    if not arg:
        td = date.today()
        return td, td, None, None

    # 拆 token：先看有無 「司機」
    parts = arg.split()
    date_part = None
    driver_id = None

    for p in parts:
        if p.startswith('司機') and p[2:].isdigit():
            driver_id = int(p[2:])
        elif p.replace('司機', '').isdigit() and len(p) > 2:
            # 容錯：純數字當 driver
            try:
                driver_id = int(p)
            except ValueError:
                pass
        else:
            date_part = p if date_part is None else f"{date_part} {p}"

    # 解析日期（可能是「5/2」或「4/26-5/2」）
    date_from, date_to = None, None
    if date_part:
        try:
            if '-' in date_part and date_part.count('-') == 1 and '/' in date_part:
                # 「4/26-5/2」 範圍
                a, b = date_part.split('-')
                date_from = UnifiedDateParser.parse(a.strip())
                date_to = UnifiedDateParser.parse(b.strip())
            else:
                date_from = date_to = UnifiedDateParser.parse(date_part)
        except Exception as e:
            return None, None, None, f"日期解析失敗：{date_part!r} ({e})"
    else:
        td = date.today()
        date_from = date_to = td

    return date_from, date_to, driver_id, None


def _handle_trip_list(reply_token, session, kind: str, arg: str) -> bool:
    """
    處理 「查/診所/東洋班次 [args]」

    kind: '查' / '診所' / '東洋'
    """
    date_from, date_to, driver_id, err = _parse_trip_args(arg)
    if err:
        reply_message(reply_token, {"type": "text", "text": f"❌ {err}\n用例：查班次 今天 / 診所班次 5/2 / 查班次 5/2 司機533"})
        return True

    category = None
    if kind == '診所':
        category = '診所'
    elif kind == '東洋':
        category = '東洋'

    r = query_trips(
        session=session,
        date_from=date_from,
        date_to=date_to,
        driver_id=driver_id,
        category=category,
    )
    if not r.ok:
        # 空也用 carousel 顯示（產生 empty bubble）
        flex = render_trip_list_carousel([])
        reply_message(reply_token, {
            "type": "flex",
            "altText": "查無班次",
            "contents": flex,
        })
        return True

    flex = render_trip_list_carousel(r.data)
    label_parts = [str(date_from)]
    if date_to and date_to != date_from:
        label_parts.append(f'~{date_to}')
    if driver_id:
        label_parts.append(f' 司機{driver_id}')
    if category:
        label_parts.append(f' {category}')
    label = ''.join(label_parts)

    reply_message(reply_token, {
        "type": "flex",
        "altText": f"班次 {label}（{len(r.data)} 筆）",
        "contents": flex,
    })
    return True


def _send_help(reply_token):
    help_text = """🛠️ Rewrite v0.1 測試命令

🔍 客戶查詢
  查客戶 <關鍵字>
    例：查客戶 龍埔街
    例：查客戶 D200615801（自動辨識身分證）
    例：查客戶 001026（自動辨識病歷號）
  客戶詳情 <ID>
    例：客戶詳情 54

📋 病歷層
  病歷層 <日>
    例：病歷層 23
  病歷層分布

🚖 班次查詢
  查班次 [日期] [司機X]
    例：查班次（= 今天）
    例：查班次 5/2
    例：查班次 4/27 司機533
  診所班次 [日期]
  東洋班次 [日期]
  班次詳情 <trip_id>
    例：班次詳情 1043
  待派班次"""
    reply_message(reply_token, {"type": "text", "text": help_text})
