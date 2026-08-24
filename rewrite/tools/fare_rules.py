"""
「這筆車資算不算填過」— 單一判定來源（Python 與 SQL 兩種形式）

為什麼需要單一來源：
    這條規則同時出現在五個地方，而且各寫各的，於是同一筆資料在不同畫面
    講不同的話：
      · CompletedTripView.has_fare（已完成列表顯示 + 統計卡的「未記錄 N 筆」）
      · completed_trip._build_filters 的 has_fare 過濾
      · query_spec.py 的 has_fare 欄（AI 受護欄查詢）
      · aggregate_completed_trips 的「已記錄／未記錄 N 筆」（統計卡）
      · driver._MISSING_FARE（司機待補車資清單）
    只有最後一個是對的 —— 其他四個都用「總額 > 0」，於是把
    **沖帳**（人工把金額抵成 0）判成「未記錄」。

判定：
    填過 = 錶價 ≠ 0  或  加成 ≠ 0  或  備註有「改車資」

    第三個條件是關鍵：沖帳的班次錶價 140、加成 −140，淨額 0，
    但它確實填過（備註寫著「改車資: 加成 0→−140 (遲到自己騎車回)」）。
    用戶的原話：「車資雖然是零，但是他是經過修改有修改理由的，
    不應該被歸為未紀錄」。
    PROD 實測有 64 筆屬於這種情況。

    ⚠️ 2026-08-21 補記：第一次修的時候漏掉統計卡那份（aggregate 自己寫了
    一套 SQL），於是同一週的班次在列表顯示 0 元、在統計卡卻算「未記錄 1 筆」。
    要加第六個使用者的話**引用這裡**，不要自己寫 —— test_driver_fare_rules.py
    有一條全 repo 掃描會抓到新長出來的自訂判定。

    反過來「真的沒填」是三個條件都不成立 —— 錶價加成都 0/空、也沒動過。

⚠️ SQL 片段裡的 % 一律寫成 %% ：
    這些字串會被塞進 sqlalchemy.text() 且該查詢有帶參數，psycopg2 會把
    單一個 % 當成參數佔位符而炸掉。
"""

# 「填過」的 SQL 述詞（欄名固定為 meter_fare / extra_fare / modification_reason，
# trips 與 completed_trips 兩張表都有這三欄）
FILLED_SQL = (
    "(COALESCE(meter_fare, 0) <> 0"
    " OR COALESCE(extra_fare, 0) <> 0"
    " OR COALESCE(modification_reason, '') LIKE '%%改車資%%')"
)

# 「沒填」＝ 填過的反面。刻意用 NOT(...) 表示，兩者永遠不可能各自漂移。
MISSING_SQL = f"NOT {FILLED_SQL}"


def is_fare_filled(meter, extra, mod_reason=None) -> bool:
    """Python 版判定，語意必須與 FILLED_SQL 完全一致。

    沖帳（錶價被人工改成 0、或錶價加成互相抵成 0）算「已填」——
    它有修改理由，是有人決定過的結果，不是漏填。
    """
    if (meter or 0) != 0:
        return True
    if (extra or 0) != 0:
        return True
    return '改車資' in (mod_reason or '')
