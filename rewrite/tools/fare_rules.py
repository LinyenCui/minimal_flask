"""
「這筆車資算不算填過」— 單一判定來源（Python 與 SQL 兩種形式）

判定（2026-09-30 定調）：
    填過 = 錶價 ≠ 0  或  加成 ≠ 0

    就這樣，**不看備註**。錶價和加成都是 0／空 → 沒填 → 進司機的待補清單。

為什麼需要單一來源：
    這條規則有五個使用者，以前各寫各的，同一筆資料在不同畫面講不同的話：
      · CompletedTripView.has_fare（已完成列表顯示 + 統計卡的「未記錄 N 筆」）
      · completed_trip._build_filters 的 has_fare 過濾
      · query_spec.py 的 has_fare 欄（AI 受護欄查詢）
      · aggregate_completed_trips 的「已記錄／未記錄 N 筆」（統計卡）
      · driver._MISSING_FARE（司機待補清單）＋ 司機週車資列表
    要加第六個使用者的話**引用這裡**，不要自己寫 ——
    test_driver_fare_rules.py 有一條全 repo 掃描會抓到新長出來的自訂判定。

沖帳照樣算「已填」：
    錶價 140、加成 −140，淨額 0 —— 但錶價 ≠ 0，所以是已填，列表顯示 0。
    用戶原話：「車資雖然是零，但是他是經過修改有修改理由的，不應該被歸為未紀錄」。
    PROD 有 64 筆這種情況，全部是錶價或加成非 0，不靠備註就判得出來。

⚠️ 以前多一個條件「或 備註有『改車資』」—— 2026-09-30 拿掉了：
    那一條本來要照顧「刻意填 0 的免費車」，但 PROD 上這種班次**一筆都沒有**。
    實際吃到這條的只有 #4344：先改路線（久保田家→南紡購物中心），再把錶價
    360 清成 0 —— 那是「新路線車資未知，清掉等司機重報」的意思，
    舊規則卻把它當「已填 0 元」，司機 28530 永遠不會被要求補，那趟就白跑。
    用戶選了「清成 0 = 要重報」。

    連帶：司機在 LIFF 送 0 會被擋（driver_fare._zero_fare_error），
    不然送出後又被判成「沒填」，跑回待補清單，變成無限迴圈。
    沒收錢的班次（沒搭到、取消）走請假或註銷，不是填 0。
"""

# 「填過」的 SQL 述詞（欄名固定為 meter_fare / extra_fare，
# trips 與 completed_trips 兩張表都有這兩欄）
FILLED_SQL = "(COALESCE(meter_fare, 0) <> 0 OR COALESCE(extra_fare, 0) <> 0)"

# 「沒填」＝ 填過的反面。刻意用 NOT(...) 表示，兩者永遠不可能各自漂移。
MISSING_SQL = f"NOT {FILLED_SQL}"


def is_fare_filled(meter, extra) -> bool:
    """Python 版判定，語意必須與 FILLED_SQL 完全一致。

    錶價或加成任一非 0 → 已填（沖帳 140/−140 也算）；兩個都 0／空 → 沒填。
    """
    return (meter or 0) != 0 or (extra or 0) != 0
