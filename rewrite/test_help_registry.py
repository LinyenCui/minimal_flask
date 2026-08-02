"""
測試 rewrite/help_registry.py — 幫助系統單一來源

重點：
  T1  render_overview / render_category / render_full 不炸、每分類非空
  T2  覆蓋率斷言：全指令清查的每個 cmd 都在 render_full() 裡（防漏 —
      清單在下方 hardcode，故意不從 CATEGORIES 讀，刪掉指令會被抓到）
  T3  長度上限：每則 < 4900（LINE 單則 5000 保險）、overview < 1200（一屏可讀）
  T4  try_handle_help dispatch：幫助→總覽+按鈕、幫助 分類→分類清單、
      幫助 全部→全清單、不認得→None（不劫持 AI 請求）

純函數測試，不碰 DB、不需 LINE credentials。
"""
import sys

sys.path.insert(0, '/Users/linyancui/minimal_flask')

from rewrite.help_registry import (
    CATEGORIES,
    HELP_TRIGGERS,
    overview_message,
    render_category,
    render_full,
    render_overview,
    resolve_category,
    try_handle_help,
)


def banner(label: str):
    print(f'\n{"=" * 60}\n# {label}\n{"=" * 60}')


# ============================================================
# 全指令清查（hardcode 對照組 — 新指令上線請同步加到 registry 與這裡）
# ============================================================
ALL_COMMANDS = [
    # 查詢
    '查客戶 <關鍵字>',
    '客戶詳情 <ID>',
    '病歷層 <日>',
    '病歷層分布',
    '查班次 [日期] [司機X]',
    '診所班次 [日期] / 東洋班次 [日期]',
    '班次詳情 <trip_id>',
    '待派班次',
    '司機列表',
    '車資試算 <公里> [停等分鐘] [日間|夜間]',
    '查 太子龍 / 太子龍住哪（AI）',
    '今天司機533九點之後的診所班次（AI）',
    '查已完成 昨天 司機5386（AI）',
    '查看 820 / #820',
    '本週東洋加總 / 統計 / 賺多少（AI）',
    '各司機各加總多少 / 金額最高5筆（AI）',
    '載高橋的班次（AI）',
    '上週司機28530東洋班次對帳（AI）',
    '本週是哪一週 / W17 是哪幾天（AI）',
    '查太子龍的固定班次（AI）',
    '固定班次 #21（AI）',
    # 狀態·修改
    '今天X的狀態 / 5/9馬鎮宮的狀態',
    '全部請假 / 全部註銷 / 全部衝突 / 全部改回準備',
    '化療 -30（批量請假輸入模式）',
    '1234 化療 -30（AI）',
    '明天龍埔街都請假（AI）',
    '1234 註銷 / 1234 衝突（AI）',
    '指派司機 1190 28530',
    '記錄車資 1234 380',
    '修改#2674$700（記賬）（AI）',
    '行程ID3723金額改成445（AI）',
    '#N 改成 11:45（AI）',
    '#N 終點改南紡 / 清空途經（AI）',
    '1077 改成診所類別（AI）',
    '#N 司機改成 M（AI）',
    '刪除 #N（AI）',
    '固定班次 21 請假（AI）',
    '固定班次14恢復 / 不請假了（AI）',
    '刪除固定班次 N（AI）',
    '新增客戶 太子龍 龍哥 龍埔街123 諮所（AI）',
    '太子龍改名為龍哥 / 太子龍地址改成X（AI）',
    '刪除太子龍（AI）',
    '班次註銷 N / 班次衝突 N / 班次請假 N / 班次恢復 N / 班次撤銷指派 N',
    '出國 -50（請假輸入模式）',
    '確認執行 / 取消操作',
    # LIFF 表單
    '新增客戶 / 加客戶 / 建檔',
    '預約叫車 / 預約 / 新增班次 / 預約班次 / 叫車',
    '匯入固定班次 / 匯入 / import / 匯入班次 / 匯入班表',
    '新增固定班次 / 新增模板 / 加固定班次 / 新增班表 / 建班表',
    '批量加成 / 批次加成 / 批量改加成',
    '回報車資（司機用，走群組置頂連結）',
    # 帳務·報表
    '報表 / 產報表 / 生成報表 / 生成日報表 / 生成週報表 / 生成月報表 / 日報表 / 週報表 / 月報表',
    '帳務處理 / 帳務 / 餘額 / 查餘額 / 帳戶餘額',
    '帳務明細 / 查看明細 / 明細',
    '2026-04-01 2026-04-30（篩選區間輸入模式）',
    '分錄 83（AI）',
    '沖正 83（AI）',
    # 地點·到院通知
    '設定地點（= 設定診所）',
    '設定地點名稱 <名稱>',
    '查看地點名稱',
    '查看地點座標（= 查看診所座標）',
    '清除地點座標（= 清除診所座標）',
    '設定平均車速 <km/h>',
    '查看平均車速',
    '設定到院轉發',
    '綁定到院通知 <配對碼>',
    '查看到院轉發',
    '取消到院轉發',
    '收到',
    '（傳 LINE 位置訊息）',
    # 藥·診斷·日期
    '/dx <關鍵字|ICD碼> 或 /碼 <關鍵字>',
    '/dx 章節（目錄 / chapters）',
    '/dx help（幫助 / 說明）',
    '/藥名 X 或 /drug X（也收 drug X、!drug X、！drug X）',
    '/drug help（幫助 / 說明）',
    '!日期（!5/14、!05-20、!2026-5-14、!五月二十日）',
    '藥診關聯 / 新增藥診關聯',
    # 系統
    '幫助 / help / Help / 指令 / 說明',
    '資料庫同步',
    '確認同步 / 確認序號覆蓋',
    '取消同步 / 放棄同步',
    '同步結果',
    '歸檔檢查',
    '歸檔清理 [日期]',
    '重置班次序號',
    '新增司機 <編號> <姓名> [車號]',
    '停用司機 <編號> / 啟用司機 <編號>',
    '解綁司機 <編號>',
    '結束對話 / 結束 / 退出 / 退出對話 / exit / quit / bye',
    '（群組前綴規則）/<指令>',
]


# ============================================================
# T1: render 不炸、每分類非空
# ============================================================
banner('T1: render_overview / render_category / render_full 不炸、每分類非空')
overview = render_overview()
full = render_full()
assert overview.strip(), 'render_overview 空的'
assert full.strip(), 'render_full 空的'
assert len(CATEGORIES) == 7, f'分類數應為 7，實際 {len(CATEGORIES)}'
for c in CATEGORIES:
    assert c['entries'], f"分類 {c['key']} 沒有任何指令"
    cat_text = render_category(c['key'])
    assert cat_text.strip(), f"render_category({c['key']!r}) 空的"
    assert c['title'] in cat_text, f"render_category({c['key']!r}) 缺分類標題"
    assert c['title'] in overview, f"overview 缺分類 {c['title']}"
    print(f"  {c['emoji']} {c['title']}: {len(c['entries'])} 條, "
          f"render_category {len(cat_text)} 字")
print(f'  overview {len(overview)} 字 / full {len(full)} 字')

# ============================================================
# T2: 覆蓋率 — 清查裡每個 cmd 都要在 render_full()
# ============================================================
banner(f'T2: 覆蓋率斷言 — {len(ALL_COMMANDS)} 個指令都在 render_full()')
missing = [cmd for cmd in ALL_COMMANDS if cmd not in full]
assert not missing, f'render_full() 漏了 {len(missing)} 個指令: {missing}'
# 反向：registry 的每條 entry 也要在對照清單裡（防止只加 registry 忘了加測試）
registry_cmds = [cmd for c in CATEGORIES for cmd, _ in c['entries']]
extra = [cmd for cmd in registry_cmds if cmd not in ALL_COMMANDS]
assert not extra, f'registry 有指令不在測試對照清單（請同步）: {extra}'
assert len(registry_cmds) == len(ALL_COMMANDS), (
    f'數量不符: registry {len(registry_cmds)} vs 清查 {len(ALL_COMMANDS)}'
)
print(f'  ✓ {len(ALL_COMMANDS)} 個指令雙向對齊')

# ============================================================
# T3: 長度上限
# ============================================================
banner('T3: 長度上限 — 每則 < 4900、overview < 1200')
assert len(overview) < 1200, f'overview {len(overview)} 字 ≥ 1200（手機一屏爆版）'
for c in CATEGORIES:
    n = len(render_category(c['key']))
    assert n < 4900, f"render_category({c['key']!r}) {n} 字 ≥ 4900"
assert len(full) < 4900, f'render_full {len(full)} 字 ≥ 4900（LINE 單則上限風險）'
print('  ✓ 全部通過')

# ============================================================
# T4: try_handle_help dispatch（sandbox「幫助 分類」的純函數層）
# ============================================================
banner('T4: try_handle_help dispatch')
# 4a. 幫助觸發詞 → 總覽 + Quick Reply 分類按鈕
for trig in sorted(HELP_TRIGGERS):
    msg = try_handle_help(trig)
    assert msg is not None, f'{trig!r} 應觸發幫助'
    assert msg['type'] == 'quick_reply', f'{trig!r} 應回 quick_reply 訊息'
    assert msg['text'] == overview
items = try_handle_help('幫助')['quick_reply']['items']
assert len(items) == 8, f'分類按鈕應 8 顆（7 分類 + 全部），實際 {len(items)}'
btn_texts = [it['action']['text'] for it in items]
assert all(t.startswith('幫助 ') for t in btn_texts), f'按鈕 text 應為「幫助 X」: {btn_texts}'
assert '幫助 全部' in btn_texts
print(f'  ✓ 觸發詞 {sorted(HELP_TRIGGERS)} → 總覽 + {len(items)} 顆按鈕')

# 4b. 每顆分類按鈕的 text 都 dispatch 得到（按鈕送出的字不能變孤兒）
for t in btn_texts:
    msg = try_handle_help(t)
    assert msg is not None and msg['type'] == 'text', f'按鈕文字 {t!r} dispatch 失敗'
assert try_handle_help('幫助 全部')['text'] == full
assert try_handle_help('幫助 查詢')['text'] == render_category('query')
print(f'  ✓ {len(btn_texts)} 顆按鈕文字全部 dispatch 成功')

# 4c. 別名
for alias, key in [('狀態·修改', 'status'), ('狀態', 'status'), ('表單', 'form'),
                   ('帳務', 'accounting'), ('報表', 'accounting'),
                   ('地點', 'location'), ('藥', 'drug'), ('日期', 'drug'),
                   ('系統', 'system'), ('全部', 'full'), ('all', 'full')]:
    assert resolve_category(alias) == key, f'別名 {alias!r} 應解析為 {key!r}'
print('  ✓ 分類別名解析正確')

# 4d. 不認得的 → None（不劫持 AI 請求 / 一般訊息）
for t in ['幫助我查太子龍', '幫助 不存在的分類', '查客戶 龍埔街', 'helpme', '', '   ']:
    assert try_handle_help(t) is None, f'{t!r} 不該被幫助系統劫持'
print('  ✓ 不認得的訊息回 None（留給既有路徑）')

print('\n' + '=' * 60)
print('✅ 全部測試通過 — help_registry 純函數、無 DB / LINE 依賴')
print('=' * 60)
