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
    cancel_trip,
    mark_conflict,
    passenger_leave,
    restore_to_ready,
    unassign_driver,
)
from rewrite.views.customer_flex import (
    render_customer_detail,
    render_birthday_layer_carousel,
)
from rewrite.views.trip_flex import (
    render_trip_detail,
    render_trip_list_carousel,
    build_trip_quick_reply,
)
from rewrite.conversation_state import (
    set_state as _state_set,
    get_state as _state_get,
    clear_state as _state_clear,
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

# 班次 mutation 命令 regex（footer button 發出來的）
_RE_TRIP_CANCEL = re.compile(r'^班次註銷\s+(\d+)$')
_RE_TRIP_CONFLICT = re.compile(r'^班次衝突\s+(\d+)$')
_RE_TRIP_LEAVE = re.compile(r'^班次請假\s+(\d+)$')   # 進入請假輸入模式
_RE_TRIP_RESTORE = re.compile(r'^班次恢復\s+(\d+)$')
_RE_TRIP_UNASSIGN = re.compile(r'^班次撤銷指派\s+(\d+)$')

# 請假輸入模式的退出命令（跟原系統一致）
_LEAVE_ABORT_TEXTS = {'放棄操作', '放棄', '取消'}

# Postback data regex
_RE_PB_TRIP_DETAIL = re.compile(r'^trip_detail:(\d+)$')
_RE_PB_CUSTOMER_EDIT = re.compile(r'^customer_edit:(\d+)$')


def try_route(event) -> bool:
    """
    嘗試處理 event。回 True 表示已處理（不要走主流程）。
    """
    text = (event.message.text or '').strip()
    user_id = getattr(event.source, 'user_id', None)

    # 處理群組 prefix：剝掉 / 或 # （但保留 ! ！ — 那是 sandbox 的）
    for p in ('/', '#'):
        if text.startswith(p):
            text = text[len(p):].lstrip()
            break

    # ===== 優先：檢查是否在 conversation state（請假輸入模式等）=====
    # 在 input mode 中，user 任何 message 都先給 state handler 處理
    if user_id:
        state = _state_get(user_id)
        if state and state.get('type') == 'leave_input':
            return _handle_leave_input(
                event.reply_token, user_id, text, state['payload']
            )

    # 提早退出：不像我們的命令
    rewrite_prefixes = ('查客戶', '客戶詳情', '病歷層',
                        '查班次', '診所班次', '東洋班次',
                        '班次詳情', '待派班次',
                        # mutation 命令（footer button 觸發）
                        '班次註銷', '班次衝突', '班次請假',
                        '班次恢復', '班次撤銷指派')
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

        # ===== 班次 mutation 命令（quick reply 觸發）=====
        m = _RE_TRIP_CANCEL.match(text)
        if m:
            return _handle_trip_cancel(reply_token, session, int(m.group(1)), user_id)

        m = _RE_TRIP_CONFLICT.match(text)
        if m:
            return _handle_trip_conflict(reply_token, session, int(m.group(1)), user_id)

        m = _RE_TRIP_LEAVE.match(text)
        if m:
            return _handle_trip_leave(
                reply_token, session, int(m.group(1)), user_id,
            )

        m = _RE_TRIP_RESTORE.match(text)
        if m:
            return _handle_trip_restore(reply_token, session, int(m.group(1)), user_id)

        m = _RE_TRIP_UNASSIGN.match(text)
        if m:
            return _handle_trip_unassign(reply_token, session, int(m.group(1)), user_id)

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


def try_route_postback(event) -> bool:
    """
    嘗試處理 postback event。回 True 表示已處理。

    支援格式：
      trip_detail:NNNN     — 班次詳情卡跳轉
    """
    data = (getattr(event.postback, 'data', None) or '').strip()
    if not data:
        return False

    m = _RE_PB_TRIP_DETAIL.match(data)
    if m:
        session = Session()
        try:
            return _handle_trip_detail(event.reply_token, session, int(m.group(1)))
        except Exception as e:
            logger.error(f"rewrite postback 異常 ({data!r}): {e}", exc_info=True)
            try:
                reply_message(event.reply_token, {
                    "type": "text",
                    "text": f"⚠️ postback 處理錯誤：{str(e)[:200]}"
                })
            except Exception:
                pass
            return True
        finally:
            session.close()

    # customer_edit:N — 客戶詳情卡的「編輯」按鈕
    # rewrite v0.1 暫不做 postback 編輯流程，提示用戶用自然語言走 sandbox
    m = _RE_PB_CUSTOMER_EDIT.match(data)
    if m:
        cid = int(m.group(1))
        session = Session()
        try:
            r = get_customer_by_id(cid, session=session, mask_id=True)
            name = r.data.short_name or r.data.name if r.ok else f'#{cid}'
            reply_message(event.reply_token, {
                "type": "text",
                "text": (
                    f"💡 編輯客戶 #{cid} {name}\n\n"
                    f"請用自然語言（沙盒）：\n"
                    f"  !{name}改地址 XXX\n"
                    f"  !{name}改名 XXX\n"
                    f"  !{name}改類別 XXX"
                ),
            })
            return True
        finally:
            session.close()

    return False


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
    _send_trip_card(reply_token, r.data, alt_prefix=f"班次 #{trip_id} 詳情")
    return True


def _send_trip_card(reply_token, trip, *, alt_prefix: str) -> None:
    """送詳情卡 + 動作 quickReply（attach 在 reply message，輸入框上方顯示）"""
    bubble = render_trip_detail(trip)
    qr = build_trip_quick_reply(trip)
    msg = {
        "type": "flex",
        "altText": alt_prefix,
        "contents": bubble,
    }
    if qr:
        msg["quickReply"] = qr
    reply_message(reply_token, msg)


def _reply_mutation_result(reply_token, session, trip_id: int, result,
                            action_label: str) -> bool:
    """統一 mutation reply：失敗回文字、成功回更新後的詳情卡（含新狀態的 footer button）"""
    if not result.ok:
        reply_message(reply_token, {
            "type": "text",
            "text": f"❌ 班次 #{trip_id} {action_label} 失敗：{result.error}",
        })
        return True
    _send_trip_card(reply_token, result.data,
                    alt_prefix=f"班次 #{trip_id} 已{action_label}")
    return True


def _handle_trip_cancel(reply_token, session, trip_id: int,
                         user_id) -> bool:
    r = cancel_trip(
        session=session, trip_id=trip_id,
        reason='LINE quick reply',
        user_id=user_id, via='quick_reply',
    )
    return _reply_mutation_result(reply_token, session, trip_id, r, '註銷')


def _handle_trip_conflict(reply_token, session, trip_id: int,
                           user_id) -> bool:
    r = mark_conflict(
        session=session, trip_id=trip_id,
        reason='LINE quick reply',
        user_id=user_id, via='quick_reply',
    )
    return _reply_mutation_result(reply_token, session, trip_id, r, '標記衝突')


def _handle_trip_leave(reply_token, session, trip_id: int, user_id) -> bool:
    """
    [請假] button → 進入請假輸入模式（conversation state）

    跟原系統一致：先預檢 trip 狀態 + 鎖，過了才設 state 跳輸入。
    """
    r = query_trip_by_id(trip_id, session=session)
    if not r.ok:
        reply_message(reply_token, {"type": "text", "text": f"❌ {r.error}"})
        return True

    t = r.data
    if t.is_locked:
        reply_message(reply_token, {
            "type": "text",
            "text": (f"⏰ 班次 #{trip_id} 距執行時間還有 {t.minutes_until_trip} 分鐘，"
                     f"30 分鐘鎖內無法請假"),
        })
        return True
    if t.display_status not in ('準備',):
        reply_message(reply_token, {
            "type": "text",
            "text": f"❌ 班次 #{trip_id} 狀態為「{t.display_status}」，無法請假",
        })
        return True

    if not user_id:
        reply_message(reply_token, {
            "type": "text", "text": "❌ 缺 user_id，無法進入請假模式"})
        return True

    # 進入 input mode
    _state_set(user_id, 'leave_input', {'trip_id': trip_id})

    reply_message(reply_token, {
        "type": "text",
        "text": (
            f"🏷️ 班次 #{trip_id} 乘客請假\n\n"
            f"請輸入：[原因] [負加成]\n\n"
            f"❌ 退出：點下方「放棄操作」"
        ),
        "quickReply": {
            "items": [{
                "type": "action",
                "action": {
                    "type": "message",
                    "label": "❌ 放棄操作",
                    "text": "放棄操作",
                },
            }]
        },
    })
    return True


def _handle_leave_input(reply_token, user_id, text: str, payload: dict) -> bool:
    """
    在 leave_input state 下解析用戶輸入

    解析規則：
      - 「放棄操作」/「放棄」/「取消」 → 清 state
      - 「[原因] [整數]」              → passenger_leave + 清 state
      - 其他（沒打整數加成）            → 提示失敗 + 清 state（用戶從按鈕重來）
    """
    text = text.strip()

    # 退出
    if text in _LEAVE_ABORT_TEXTS:
        _state_clear(user_id)
        reply_message(reply_token, {
            "type": "text",
            "text": "已放棄請假操作",
        })
        return True

    # 解析 [原因] [整數]
    parts = text.rsplit(maxsplit=1)
    surcharge = None
    reason = None
    if len(parts) == 2:
        try:
            surcharge = int(parts[1])
            reason = parts[0].strip()
        except ValueError:
            pass

    if surcharge is None or not reason:
        # 失敗 → 清 state，用戶重新按 [請假] 來
        _state_clear(user_id)
        reply_message(reply_token, {
            "type": "text",
            "text": (
                "❌ 操作失敗\n\n"
                "格式應為：[原因] [負加成]\n\n"
                "請從詳情卡重新點選「請假」按鈕再操作"
            ),
        })
        return True

    # 成功路徑
    trip_id = payload['trip_id']
    session = Session()
    try:
        r = passenger_leave(
            session=session, trip_id=trip_id,
            reason=reason, surcharge=surcharge,
            user_id=user_id, via='line_input_mode',
        )
        _state_clear(user_id)
        return _reply_mutation_result(
            reply_token, session, trip_id, r,
            f'請假（{reason}/{surcharge:+d}）',
        )
    finally:
        session.close()


def _handle_trip_restore(reply_token, session, trip_id: int,
                          user_id) -> bool:
    r = restore_to_ready(
        session=session, trip_id=trip_id,
        user_id=user_id, via='quick_reply',
    )
    return _reply_mutation_result(reply_token, session, trip_id, r, '恢復準備')


def _handle_trip_unassign(reply_token, session, trip_id: int,
                           user_id) -> bool:
    r = unassign_driver(
        session=session, trip_id=trip_id,
        user_id=user_id, via='quick_reply',
    )
    return _reply_mutation_result(reply_token, session, trip_id, r, '撤銷指派')


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
        exclude_status=['已完成'],  # 跟原系統一致：列表預設不顯示已完成（無意義資料）
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
