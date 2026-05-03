"""
產生 Customer Flex JSON（不發 LINE，輸出檔案讓你貼到 simulator 看）

產出位置：rewrite/views/output/*.json
LINE Flex Simulator: https://developers.line.biz/flex-simulator/
"""
import sys, json, os
from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, '/Users/linyancui/minimal_flask')
from database import Session
from rewrite.tools.customer import (
    get_customer_by_id,
    query_customers_by_birthday_day,
    create_customer,
    delete_customer,
)
from rewrite.views.customer_flex import (
    render_customer_detail,
    render_birthday_layer_carousel,
)


OUTPUT_DIR = '/Users/linyancui/minimal_flask/rewrite/views/output'
os.makedirs(OUTPUT_DIR, exist_ok=True)


def banner(label):
    print(f'\n{"="*60}\n# {label}\n{"="*60}')


def save_json(filename, data):
    path = os.path.join(OUTPUT_DIR, filename)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f'  💾 {path}')
    return path


def basic_check(bubble):
    assert bubble['type'] in ('bubble', 'carousel'), f'unexpected type: {bubble["type"]}'
    if bubble['type'] == 'bubble':
        assert 'body' in bubble


session = Session()
fake_ids = []  # 待清理的 fake customers
try:
    # ============================================================
    # T1：完整詳情卡 (#54 黃陳玉盆)
    # ============================================================
    banner('T1: 完整詳情卡 (#54 黃陳玉盆)')
    r = get_customer_by_id(54, session=session, mask_id=True)
    assert r.ok
    bubble = render_customer_detail(r.data)
    basic_check(bubble)
    print(f'  header: {bubble["header"]["contents"][0]["text"]}')
    print(f'  body 行數: {len(bubble["body"]["contents"])}')
    print(f'  footer 按鈕: {len(bubble["footer"]["contents"])} 個')
    save_json('01_customer_detail_54_masked.json', bubble)

    # ============================================================
    # T2：不遮罩版（看完整身分證）
    # ============================================================
    banner('T2: 不遮罩 (#54 mask_id=False)')
    r = get_customer_by_id(54, session=session, mask_id=False)
    bubble = render_customer_detail(r.data)
    save_json('02_customer_detail_54_unmasked.json', bubble)

    # ============================================================
    # T3：沒生日的客戶 (#29 陳昭月)
    # ============================================================
    banner('T3: 無生日客戶 (#29 陳昭月)')
    r = get_customer_by_id(29, session=session)
    bubble = render_customer_detail(r.data)
    save_json('03_customer_detail_29_no_birthday.json', bubble)

    # ============================================================
    # T4：純位置 placeholder (#1 萬年七街)
    # ============================================================
    banner('T4: 資料未完整 (#1 萬年七街)')
    r = get_customer_by_id(1, session=session)
    bubble = render_customer_detail(r.data)
    save_json('04_customer_detail_01_incomplete.json', bubble)

    # ============================================================
    # T5：病歷層 23 日 (應只有 1 人 → 直接 single bubble)
    # ============================================================
    banner('T5: 病歷層 23 日 (1 人 → single bubble)')
    r = query_customers_by_birthday_day(day=23, session=session)
    assert r.ok
    flex = render_birthday_layer_carousel(23, r.data)
    print(f'  type: {flex["type"]}')
    save_json('05_birthday_day_23.json', flex)

    # ============================================================
    # T6：病歷層 18 日 (空 → empty bubble)
    # ============================================================
    banner('T6: 病歷層 18 日 (空)')
    flex = render_birthday_layer_carousel(18, [])
    print(f'  type: {flex["type"]}')
    save_json('06_birthday_day_18_empty.json', flex)

    # ============================================================
    # T7：模擬多人病歷層（建 4 個假客戶後查詢）
    # ============================================================
    banner('T7: 病歷層 18 日 (建 4 個假人後 carousel)')
    fake_data = [
        ('測試甲', '測試甲', 'F', '1960-03-18'),
        ('測試乙', '測試乙', 'M', '1975-07-18'),
        ('測試丙', '測試丙', 'F', '1988-11-18'),
        ('測試丁', '測試丁', 'M', '1995-05-18'),
    ]
    for name, sn, g, bd in fake_data:
        from datetime import date
        y, m, d = bd.split('-')
        rc = create_customer(
            session=session, name=name, short_name=sn,
            address='(待補)', category='診所',
            gender=g, birthday=date(int(y), int(m), int(d)),
        )
        if rc.ok:
            fake_ids.append(rc.data.id)

    r = query_customers_by_birthday_day(day=18, session=session)
    assert r.ok, f'expected to find {len(fake_data)} fake customers'
    print(f'  找到 {len(r.data)} 人在病歷層 18 日')
    flex = render_birthday_layer_carousel(18, r.data)
    print(f'  type: {flex["type"]}')
    if flex['type'] == 'carousel':
        print(f'  bubbles: {len(flex["contents"])}')
    save_json('07_birthday_day_18_multi.json', flex)

    print('\n' + '='*60)
    print('✅ 全部 Flex JSON 已產出於：')
    print(f'   {OUTPUT_DIR}/')
    print()
    print('預覽方式：')
    print('  1. 開啟 https://developers.line.biz/flex-simulator/')
    print('  2. 把 .json 內容（注意只貼 bubble/carousel 那部分）貼進去')
    print('  3. 看實際視覺效果')
    print('='*60)
finally:
    # 清理測試用 fake 客戶
    if fake_ids:
        print(f'\n🧹 清理 {len(fake_ids)} 筆測試客戶: {fake_ids}')
        for fid in fake_ids:
            try:
                delete_customer(session=session, customer_id=fid)
            except Exception as e:
                print(f'  - #{fid} 清理失敗: {e}')
    session.close()
