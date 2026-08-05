"""
請假加成閘門 — 「請假但沒扣款」的單一判定來源

問題（用戶回報，連續發生數次）：
    人員操作請假，但加成沒填、或填 0 / -0（-0 在 Python 與 DB 都等於 0，
    而且是被允許的值），結果該扣的錢沒扣。事後從欄位上完全看不出
    「這筆 0 是確認過的」還是「漏填的」。

為什麼判定用 `>= 0` 而不是 `== 0`：
    PROD 實測 158 筆請假班次，extra_fare 範圍是 -220 ~ 0，**從來沒有正數**。
    請假的加成本質是扣款，正數不合理。用 >= 0 比 == 0 保險，
    而實務上兩者觸發次數相同（沒有正數可觸發）。
    這也跟 trip.restore_to_ready 只把負數歸零的設計假設一致。

為什麼是「警示可放行」而不是硬擋：
    PROD 實測 0 元請假佔比 2.1%（completed_trips 143 筆裡 3 筆），
    大約每 30~50 次請假才跳一次，不會變成沒人看的雜訊。
    而那 2~3% 是有正當情境的（乘客缺席但車照跑、客戶自行另叫車但本趟仍計費），
    硬擋會把它們逼成「隨便填 -1 再改回來」的繞道行為。

放行時一定留痕：
    確認放行的會在 modification_reason / note 尾巴補 CONFIRMED_SUFFIX，
    事後對帳才分得出「確認過的 0」與「漏填的 0」——
    這正是目前 DB 的困境（既有的 0 元請假從欄位上分不出哪筆是漏的）。
"""

# 放行時寫進 modification_reason / note 的標記
CONFIRMED_SUFFIX = '（0元-已確認）'

# ToolResult.fail 的 meta 裡帶這個 key（fail 的簽名是 fail(error, **meta)，
# 額外資訊走 meta 不走 data），讓各入口層認得「這不是錯誤，是要確認」
NEEDS_CONFIRM_KEY = 'needs_zero_surcharge_confirm'


def is_zero_surcharge(surcharge) -> bool:
    """加成是不是「沒扣到錢」——未填、0、-0、或任何 >= 0 的值。

    轉不動的型別回 False，交給呼叫端原本的型別檢查去擋
    （不要在這裡吃掉型別錯誤，否則錯誤訊息會變得莫名其妙）。
    """
    if surcharge is None:
        return True
    if isinstance(surcharge, bool):      # bool 是 int 的子類，別讓 True/False 混進來
        return False
    try:
        return int(surcharge) >= 0
    except (TypeError, ValueError):
        return False


def describe_surcharge(surcharge) -> str:
    """給人看的加成描述——「未填」和「0」要分得出來。"""
    if surcharge is None:
        return '未填（會記成 0 元）'
    try:
        v = int(surcharge)
    except (TypeError, ValueError):
        return str(surcharge)
    return '0 元（不扣款）' if v == 0 else f'{v:+d} 元'


def warning_text(*, target: str, reason: str, surcharge, how_to_confirm: str,
                 count: int = 1) -> str:
    """組警示文案。

    target        — 「班次 #1234」/「固定班次 #21」/「這 5 筆班次」
    how_to_confirm— 各入口自己的確認方式（打什麼字 / 按什麼鈕）
    count         — 批次時的筆數，用來讓「一次扣 0 元 × N 筆」更有感
    """
    lines = [
        '⚠️ 請假，但沒有扣款',
        '',
        f'　{target}',
        f'　原因：{reason}',
        f'　加成：{describe_surcharge(surcharge)}',
    ]
    if count > 1:
        lines.append(f'　筆數：{count} 筆都會是 0 元')
    lines += [
        '',
        '請假通常要扣款（例：-30、-220）。',
        f'確定不扣款 → {how_to_confirm}',
        '要改金額 → 重新操作一次',
    ]
    return '\n'.join(lines)


def mark_confirmed(text_value: str) -> str:
    """在請假原因/備註尾端補上「已確認」標記，事後對帳分得出來。"""
    t = (text_value or '').strip()
    if CONFIRMED_SUFFIX in t:
        return t
    return f'{t} {CONFIRMED_SUFFIX}'.strip()
