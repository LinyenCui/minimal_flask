"""
過去態（completed_trips）Flex Message 渲染器

提供：
  render_completed_trip_detail(ct)             — 單筆詳情 bubble
  render_completed_trip_list_carousel(cts)     — 多筆 carousel（按日分組）
  render_aggregate_card(data, *, filters)      — 統計卡（金額醒目）

主題色：橘色（ACCENT）— 三時間態 doc 規定「查已完成」用橘色表頭。
"""

import json
from collections import defaultdict
from typing import List, Optional
from rewrite.tools.completed_trip import CompletedTripView


# 主題色
ACCENT = "#FF6D00"          # 過去態主色（橘）
ACCENT_DARK = "#E65100"
PRIMARY = "#1565C0"
SUCCESS = "#2E7D32"
DANGER = "#D32F2F"
LEAVE = "#7B1FA2"
LEAVE_TINT = "#F3E5F5"      # 請假列在列表 row 的淡紫底色標記（比照現在態 temp 列
                            # 的 TEMP_TINT 做法；紫系呼應 LEAVE 主色、避開 temp 的暖色）
MUTED = "#999999"
BLACK = "#333333"

WEEKDAY_TC = ['一', '二', '三', '四', '五', '六', '日']

PER_BUBBLE = 10
MAX_BUBBLES = 10
# LINE Flex 單一 message size 上限 50KB；保留 envelope（altText/quickReply）緩衝
SIZE_BUDGET_BYTES = 45_000


# ============================================================
# 共用元件
# ============================================================

def _row(label: str, value: str, *, value_color: str = BLACK,
         value_weight: str = "regular", label_color: str = "#666666") -> dict:
    return {
        "type": "box",
        "layout": "horizontal",
        "spacing": "sm",
        "contents": [
            {"type": "text", "text": label, "size": "sm",
             "color": label_color, "flex": 2},
            {"type": "text", "text": value, "size": "sm",
             "color": value_color, "weight": value_weight,
             "flex": 5, "wrap": True},
        ]
    }


def _separator(margin: str = "md"):
    return {"type": "separator", "margin": margin}


def _format_date_with_weekday(d):
    if not d:
        return '—'
    return f"{d.month}/{d.day} (星期{WEEKDAY_TC[d.weekday()]})"


def _format_money(v: Optional[int]) -> str:
    if v is None:
        return '—'
    return f"{v:+d} 元" if v < 0 else f"{v} 元"


def _short_route(ct: CompletedTripView) -> str:
    parts = [ct.start_point or '?']
    if ct.via_point:
        parts.append(f"經{ct.via_point}")
    parts.append(ct.end_point or '?')
    return '→'.join(p for p in parts if p)


# ============================================================
# 1. 詳情卡（單筆）
# ============================================================

def render_completed_trip_detail(ct: CompletedTripView) -> dict:
    """單筆已完成班次詳情 → Flex Bubble"""
    body = []

    body.append(_row("日期", _format_date_with_weekday(ct.date)))

    # 路線（completed_trips scheduler 已經 swap 過 custom_*，直接用 standard 欄位）
    body.append(_row("起點", ct.start_point or '—'))
    if ct.via_point:
        body.append(_row("途經", ct.via_point))
    body.append(_row("終點", ct.end_point or '—'))

    body.append(_separator())

    body.append(_row("司機", f"#{ct.driver_id}" if ct.driver_id else '—'))
    body.append(_row("類別", ct.category or '—'))

    # 車資（醒目）
    body.append(_separator())
    body.append(_row("基本車資",
                     f"{ct.meter_fare} 元" if ct.meter_fare is not None else '—'))
    body.append(_row("加成", _format_money(ct.extra_fare)))
    if ct.computed_total is not None:
        body.append(_row("合計", f"{ct.computed_total} 元",
                         value_color=ACCENT_DARK, value_weight="bold"))
    if ct.actual_fare is not None and ct.actual_fare != ct.computed_total:
        # 跟 computed 不一致時才另顯示（金額不一致 bug 的可視化線索）
        body.append(_row("actual_fare", f"{ct.actual_fare} 元",
                         value_color=MUTED))

    # 請假原因
    if ct.passenger_leave_reason:
        body.append(_separator())
        body.append(_row("📝 請假原因", ct.passenger_leave_reason,
                         value_color=LEAVE))

    # 乘客
    if ct.passenger_name:
        body.append(_row("乘客", ct.passenger_name))

    # 修改原因（已記錄車資、改類別等）
    if ct.modification_reason:
        body.append(_separator())
        body.append(_row("修改紀錄", ct.modification_reason,
                         value_color=MUTED, label_color=MUTED))

    # 識別碼
    if ct.unique_code:
        body.append(_row("識別碼", ct.unique_code,
                         value_color=MUTED, label_color=MUTED))

    bubble: dict = {
        "type": "bubble",
        "size": "mega",
        "header": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": ACCENT,
            "paddingAll": "md",
            "contents": [{
                "type": "text",
                "text": f"📦 已完成 #{ct.id}",
                "weight": "bold", "size": "lg", "color": "#ffffff",
            }]
        },
        "body": {
            "type": "box", "layout": "vertical", "spacing": "sm",
            "contents": body,
        }
    }
    return bubble


# ============================================================
# 2. 列表 carousel（按日分組）
# ============================================================

def render_completed_trip_list_carousel(
    cts: List[CompletedTripView],
    *,
    header_title: Optional[str] = None,
    truncated: bool = False,
) -> dict:
    """
    多筆已完成班次 → carousel

    分頁規則：
      1 筆           → 詳情卡
      同日 ≤ 10 筆   → 1 張 bubble
      同日 > 10 筆   → 拆多張，header 標 「第 X/Y 頁」
      跨日           → 每日依上述展開
      > 10 張 bubble → 截 9 + 「還 N 頁」提示
      JSON > 45KB   → 切回單張「過多筆數」提示 bubble

    Args:
        truncated: query 結果是否撞到 LIMIT（meta.truncated=True）
    """
    if not cts:
        return _empty_bubble(header_title or "已完成班次")

    if len(cts) == 1:
        return render_completed_trip_detail(cts[0])

    # 按日期分組（保持原順序）
    groups = defaultdict(list)
    order = []
    for ct in cts:
        if ct.date not in groups:
            order.append(ct.date)
        groups[ct.date].append(ct)

    bubbles = []
    for d in order:
        day_cts = groups[d]
        n_pages = (len(day_cts) + PER_BUBBLE - 1) // PER_BUBBLE
        for i in range(n_pages):
            page = day_cts[i * PER_BUBBLE:(i + 1) * PER_BUBBLE]
            page_info = (i + 1, n_pages, len(day_cts)) if n_pages > 1 else None
            bubbles.append(_render_day_bubble(d, page, page_info=page_info))

    if len(bubbles) > MAX_BUBBLES:
        bubbles = bubbles[:MAX_BUBBLES - 1] + [
            _render_more_indicator(len(bubbles) - (MAX_BUBBLES - 1),
                                   total_trips=len(cts))
        ]

    # 真實 size 檢查：LINE Flex 單訊息 50KB 上限
    if len(bubbles) == 1:
        result = bubbles[0]
    else:
        result = {"type": "carousel", "contents": bubbles}

    size = len(json.dumps(result, ensure_ascii=False).encode('utf-8'))
    if size > SIZE_BUDGET_BYTES:
        return _render_overflow_bubble(
            count=len(cts), truncated=truncated, size_kb=size // 1024,
        )

    # 撞到上限 → 在 carousel 末尾追加提示 bubble（如還有空間）
    if truncated and len(bubbles) < MAX_BUBBLES and isinstance(result, dict) \
            and result.get('type') == 'carousel':
        result['contents'].append(_render_truncated_bubble(len(cts)))
    return result


def _empty_bubble(title: str) -> dict:
    return {
        "type": "bubble",
        "size": "kilo",
        "body": {
            "type": "box", "layout": "vertical",
            "contents": [
                {"type": "text", "text": title, "weight": "bold", "size": "lg"},
                {"type": "text", "text": "無資料", "color": MUTED, "margin": "md"},
            ]
        }
    }


def _render_day_bubble(d, cts_of_day: List[CompletedTripView], *,
                       page_info: Optional[tuple] = None) -> dict:
    """一天的已完成班次 bubble（每筆可 tap 至詳情）"""
    rows = [_ct_row(ct) for ct in cts_of_day]

    sub_text = f"{len(cts_of_day)} 筆"
    if page_info:
        page_no, total_pages, total_count = page_info
        sub_text = f"第 {page_no}/{total_pages} 頁（共 {total_count} 筆）"

    return {
        "type": "bubble",
        "size": "kilo",
        "header": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": ACCENT,
            "paddingAll": "sm",
            "contents": [{
                "type": "text",
                "text": f"📦 {_format_date_with_weekday(d)}",
                "weight": "bold", "size": "sm", "color": "#ffffff",
            }, {
                "type": "text",
                "text": sub_text,
                "size": "xxs", "color": "#FFE0B2",
            }]
        },
        "body": {
            "type": "box", "layout": "vertical", "spacing": "xs",
            "contents": rows,
        }
    }


def _ct_row(ct: CompletedTripView) -> dict:
    """Carousel 內一行已完成班次（可 tap 至詳情）"""
    driver_text = f"🚗{ct.driver_id}" if ct.driver_id else "🚗?"
    route_text = _short_route(ct)
    # 金額恆顯示（請假列可能是負數加成，如 -30，照顯示）；None/0 才顯佔位
    if ct.computed_total:
        # 列表不帶「元」——carousel 一行要塞 編號/路線/司機/金額 四欄，
        # 路線常被截成「土城→經湖美街46巷…」，省下的字寬還給路線。
        # （詳情卡與統計卡仍保留「元」，那邊空間夠。）
        fare_text = f"{ct.computed_total}"
        fare_color = LEAVE if ct.is_leave else ACCENT_DARK
    else:
        fare_text = "—" if ct.is_leave else "未記錄"
        fare_color = MUTED

    row = {
        "type": "box",
        "layout": "horizontal",
        "spacing": "xs",
        "paddingTop": "xs",
        "paddingBottom": "xs",
        "action": {
            "type": "message",
            "label": f"#{ct.id} 詳情",
            "text": f"查看 {ct.id}",
        },
        "contents": [
            {"type": "text", "text": f"#{ct.id}", "flex": 2, "size": "xxs",
             "color": ACCENT_DARK, "weight": "bold"},
            {"type": "text", "text": route_text, "flex": 6, "size": "xxs",
             "color": BLACK, "wrap": False},
            {"type": "text", "text": driver_text, "flex": 2, "size": "xxs",
             "color": MUTED, "align": "end"},
            {"type": "text", "text": fare_text, "flex": 2, "size": "xxs",
             "color": fare_color, "align": "end", "weight": "bold"},
        ]
    }
    # 請假列：整列淡紫底色標記（比照現在態 temp 列 TEMP_TINT 做法，
    # 不加 padding 免得欄位跟其他 row 對不齊），「請假」字樣移除 — 底色已表達
    if ct.is_leave:
        row["backgroundColor"] = LEAVE_TINT
        row["cornerRadius"] = "sm"
    return row


def _render_more_indicator(remaining_bubbles: int, total_trips: int) -> dict:
    return {
        "type": "bubble",
        "size": "kilo",
        "body": {
            "type": "box", "layout": "vertical",
            "alignItems": "center", "justifyContent": "center",
            "contents": [
                {"type": "text", "text": f"還有 {remaining_bubbles} 頁",
                 "weight": "bold", "size": "lg", "color": ACCENT},
                {"type": "text",
                 "text": f"（共 {total_trips} 筆，請縮小範圍）",
                 "size": "xs", "color": MUTED, "margin": "md", "wrap": True},
            ]
        }
    }


def _render_truncated_bubble(count: int) -> dict:
    """query 結果撞 LIMIT 時，carousel 末加這張提示"""
    return {
        "type": "bubble",
        "size": "kilo",
        "body": {
            "type": "box", "layout": "vertical",
            "alignItems": "center", "justifyContent": "center",
            "spacing": "sm",
            "contents": [
                {"type": "text", "text": f"⚠️ 已截至 {count} 筆",
                 "weight": "bold", "size": "md", "color": DANGER, "wrap": True},
                {"type": "text", "text": "可能還有更多",
                 "size": "xs", "color": MUTED, "wrap": True},
                {"type": "text",
                 "text": "建議：\n・縮小日期範圍\n・加類別/司機 filter\n・改用「加總」",
                 "size": "xs", "color": BLACK, "wrap": True, "margin": "md"},
            ]
        }
    }


def _render_overflow_bubble(*, count: int, truncated: bool,
                            size_kb: int) -> dict:
    """JSON 超過 LINE 50KB 上限時整個訊息退化為這張單張警示 bubble"""
    note = "結果太多 LINE 顯示不下"
    if truncated:
        note = f"結果太多 LINE 顯示不下（已截至 {count} 筆）"
    return {
        "type": "bubble",
        "size": "mega",
        "header": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": DANGER,
            "paddingAll": "md",
            "contents": [{
                "type": "text",
                "text": "⚠️ 範圍過大",
                "weight": "bold", "size": "lg", "color": "#ffffff",
            }]
        },
        "body": {
            "type": "box", "layout": "vertical", "spacing": "md",
            "contents": [
                {"type": "text", "text": note,
                 "weight": "bold", "color": BLACK, "wrap": True},
                {"type": "text", "text": f"訊息大小：{size_kb} KB（上限 50 KB）",
                 "size": "xs", "color": MUTED},
                {"type": "separator"},
                {"type": "text", "text": "💡 建議：",
                 "weight": "bold", "color": ACCENT_DARK},
                {"type": "text",
                 "text": "・改用「加總」或「統計金額」拿合計\n"
                         "・加 filter（類別 / 司機 / 客戶）\n"
                         "・縮小日期範圍",
                 "size": "sm", "color": BLACK, "wrap": True},
            ]
        }
    }


# ============================================================
# 3. 統計卡（aggregate）
# ============================================================

def render_aggregate_card(
    data: dict,
    *,
    filters_text: Optional[str] = None,
    title: str = "📊 已完成統計",
) -> dict:
    """
    過去態車資統計卡（金額醒目）

    Args:
        data: aggregate_completed_trips 的 ToolResult.data
              {total_count, filled_count, unfilled_count, sum_amount}
        filters_text: 套用的條件描述（例：「4/26-5/2 東洋」），顯示在 header 副標
        title: header 標題
    """
    total = data.get('total_count', 0)
    filled = data.get('filled_count', 0)
    unfilled = data.get('unfilled_count', 0)
    sum_amount = data.get('sum_amount', 0)

    # 大字金額區
    money_box = {
        "type": "box",
        "layout": "vertical",
        "alignItems": "center",
        "paddingTop": "lg", "paddingBottom": "lg",
        "contents": [
            {"type": "text", "text": "合計金額", "size": "sm", "color": MUTED},
            {"type": "text", "text": f"{sum_amount:,} 元",
             "size": "3xl", "weight": "bold", "color": ACCENT_DARK,
             "margin": "sm"},
        ]
    }

    breakdown = [
        _row("總筆數", f"{total} 筆", value_weight="bold"),
        _row("已記錄車資",
             f"{filled} 筆",
             value_color=SUCCESS if filled == total else BLACK),
    ]
    if unfilled > 0:
        breakdown.append(_row("未記錄車資", f"{unfilled} 筆",
                              value_color=DANGER, value_weight="bold"))

    # header 副標
    header_contents = [{
        "type": "text", "text": title,
        "weight": "bold", "size": "lg", "color": "#ffffff",
    }]
    if filters_text:
        header_contents.append({
            "type": "text", "text": filters_text,
            "size": "xs", "color": "#FFE0B2",
        })

    return {
        "type": "bubble",
        "size": "mega",
        "header": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": ACCENT,
            "paddingAll": "md",
            "contents": header_contents,
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": [
                money_box,
                _separator(),
                *breakdown,
            ]
        }
    }


# ============================================================
# 4. 分組統計卡（受護欄查詢層 grouped 結果）
# ============================================================

def render_grouped_stat_card(view, *, title: str = "📊 分組統計") -> dict:
    """受護欄查詢層 grouped 結果卡：每組一列（組鍵 → 聚合值）。

    Args:
        view: GroupedStatView（group_cols / agg_cols / rows / subtitle）
    """
    rows = view.rows or []
    group_cols = view.group_cols or []
    agg_cols = view.agg_cols or []
    agg_kinds = getattr(view, 'agg_kinds', None) or {}

    def _group_label(r: dict) -> str:
        parts = []
        for gc in group_cols:
            v = r.get(gc)
            if gc == 'driver_id':
                parts.append(f"🚗{v}" if v is not None else "🚗?")
            elif gc == 'has_fare':
                parts.append("已記錄" if v else "未記錄")
            elif gc == 'is_leave':
                parts.append("請假" if v else "正常")
            else:
                parts.append(str(v) if v not in (None, '') else "—")
        return ' / '.join(parts) if parts else "合計"

    def _fmt_agg(ac, v):
        # 用編譯期帶來的 kind 決定 筆/元；缺 kind 才退回別名子字串 heuristic
        kind = agg_kinds.get(ac) or ('count' if (ac == 'count' or '筆' in ac) else 'money')
        if kind == 'count':
            return f"{int(v)} 筆"
        try:
            return f"{int(v):,} 元"
        except (TypeError, ValueError):
            return str(v)

    def _agg_label(r: dict) -> str:
        return '　'.join(_fmt_agg(ac, r.get(ac)) for ac in agg_cols if r.get(ac) is not None)

    MAX_ROWS = 40
    body_rows = []
    for r in rows[:MAX_ROWS]:
        body_rows.append({
            "type": "box", "layout": "horizontal",
            "paddingTop": "xs", "paddingBottom": "xs",
            "contents": [
                {"type": "text", "text": _group_label(r), "size": "sm",
                 "weight": "bold", "color": BLACK, "flex": 4},
                {"type": "text", "text": _agg_label(r), "size": "sm",
                 "color": ACCENT_DARK, "align": "end", "flex": 6, "wrap": True},
            ],
        })
    if len(rows) > MAX_ROWS:
        body_rows.append({"type": "text", "text": f"… 還有 {len(rows) - MAX_ROWS} 組",
                          "size": "xs", "color": MUTED, "margin": "sm"})

    header_contents = [{"type": "text", "text": title, "weight": "bold",
                        "size": "lg", "color": "#ffffff"}]
    sub = getattr(view, 'subtitle', None)
    if sub:
        header_contents.append({"type": "text", "text": sub, "size": "xs", "color": "#FFE0B2"})
    header_contents.append({"type": "text", "text": f"{len(rows)} 組", "size": "xs", "color": "#FFE0B2"})

    return {
        "type": "bubble", "size": "mega",
        "header": {"type": "box", "layout": "vertical", "backgroundColor": ACCENT,
                   "paddingAll": "md", "contents": header_contents},
        "body": {"type": "box", "layout": "vertical", "spacing": "sm",
                 "contents": body_rows or [{"type": "text", "text": "（無資料）", "color": MUTED}]},
    }
