"""
測試 customer CRUD：create / update / delete

測試結束會自動清理建立的測試客戶（不留垃圾）。
"""
import sys
from datetime import date
from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, '/Users/linyancui/minimal_flask')
from database import Session
from sqlalchemy import text
from rewrite.tools.customer import (
    create_customer,
    update_customer,
    delete_customer,
    get_customer_by_id,
    query_customer,
)


def banner(label: str):
    print(f'\n{"="*60}\n# {label}\n{"="*60}')


session = Session()
created_ids = []  # 追蹤建立的 ID 以便清理

try:
    # ============================================================
    # T1: create - 完整資料
    # ============================================================
    banner('T1: create_customer - 完整資料')
    r = create_customer(
        session=session,
        name='測試客戶A',
        short_name='測試A',
        address='測試地址1',
        category='診所',
        birthday=date(1980, 5, 15),
        gender='F',
        national_id='X123456789',
        medical_record_no='999001',
        insurance_type='健保',
    )
    assert r.ok, f'expected ok, got {r.error}'
    c = r.data
    created_ids.append(c.id)
    print(f'  ✅ 建立 #{c.id} {c.name} (生日層 {c.birthday_day} 日)')
    print(f'     身分證(遮罩): {c.national_id}')

    # ============================================================
    # T2: create - 短名重複（應被拒絕）
    # ============================================================
    banner('T2: create_customer - 短名重複')
    r = create_customer(
        session=session,
        name='測試客戶B',
        short_name='測試A',  # 重複
        address='地址',
    )
    assert not r.ok, '應該拒絕'
    print(f'  ✅ 正確拒絕: {r.error}')

    # ============================================================
    # T3: create - 身分證重複（應被拒絕）
    # ============================================================
    banner('T3: create_customer - 身分證重複')
    r = create_customer(
        session=session,
        name='測試客戶C',
        short_name='測試C',
        address='地址',
        national_id='X123456789',  # 與 T1 重複
    )
    assert not r.ok
    print(f'  ✅ 正確拒絕: {r.error}')

    # ============================================================
    # T4: create - gender 不合法（應被拒絕）
    # ============================================================
    banner('T4: create_customer - gender 不合法')
    r = create_customer(
        session=session,
        name='測試客戶D',
        short_name='測試D',
        address='地址',
        gender='X',  # 不合法
    )
    assert not r.ok
    print(f'  ✅ 正確拒絕: {r.error}')

    # ============================================================
    # T5: create - 必填空（應被拒絕）
    # ============================================================
    banner('T5: create_customer - name 為空')
    r = create_customer(
        session=session,
        name='   ',
        short_name='測試E',
        address='地址',
    )
    assert not r.ok
    print(f'  ✅ 正確拒絕: {r.error}')

    # ============================================================
    # T6: update - 部分欄位
    # ============================================================
    banner('T6: update_customer - 改 contact_phone + remarks')
    test_id = created_ids[0]
    r = update_customer(
        session=session,
        customer_id=test_id,
        contact_phone='0912345678',
        remarks='更新後備註',
    )
    assert r.ok
    c = r.data
    print(f'  ✅ 更新 #{c.id}')
    print(f'     contact_phone: {c.contact_phone}')
    print(f'     remarks: {c.remarks}')

    # ============================================================
    # T7: update - 不允許的欄位（應被拒絕）
    # ============================================================
    banner('T7: update_customer - 嘗試改 id（白名單擋下）')
    r = update_customer(
        session=session,
        customer_id=test_id,
        id=99999,  # 不在白名單
    )
    assert not r.ok
    print(f'  ✅ 正確拒絕: {r.error}')

    # ============================================================
    # T8: update - 改 short_name 撞既有
    # ============================================================
    banner('T8: update_customer - short_name 撞既有「龍埔街」')
    r = update_customer(
        session=session,
        customer_id=test_id,
        short_name='龍埔街',  # #29 已用
    )
    assert not r.ok
    print(f'  ✅ 正確拒絕: {r.error}')

    # ============================================================
    # T9: update_at trigger 自動更新（驗證 m001 trigger）
    # ============================================================
    banner('T9: 驗證 updated_at trigger 自動更新')
    import time
    before = session.execute(
        text("SELECT created_at, updated_at FROM customers WHERE id = :id"),
        {'id': test_id}
    ).fetchone()
    print(f'  before  created_at = {before[0]}')
    print(f'  before  updated_at = {before[1]}')
    time.sleep(1.1)
    update_customer(session=session, customer_id=test_id, remarks='trigger 測試')
    after = session.execute(
        text("SELECT created_at, updated_at FROM customers WHERE id = :id"),
        {'id': test_id}
    ).fetchone()
    print(f'  after   created_at = {after[0]}')
    print(f'  after   updated_at = {after[1]}')
    assert before[0] == after[0], 'created_at 不該變'
    assert after[1] > before[1], 'updated_at 應自動刷新'
    print(f'  ✅ trigger 正確（created_at 不變、updated_at 自動 +1.1s）')

    # ============================================================
    # T10: delete - 拒絕（被 trips 引用的不可刪）
    # ============================================================
    banner('T10: delete_customer - 嘗試刪 #29 龍埔街（應被擋下）')
    r = delete_customer(session=session, customer_id=29)
    assert not r.ok
    print(f'  ✅ 正確拒絕: {r.error}')

    # ============================================================
    # T11: delete - 沒被引用的可刪（清理測試客戶 A）
    # ============================================================
    banner(f'T11: delete_customer #{test_id}（測試客戶 A，未被 trips 引用）')
    r = delete_customer(session=session, customer_id=test_id)
    assert r.ok, f'expected ok, got {r.error}'
    print(f'  ✅ 已刪除: {r.data}')
    created_ids.remove(test_id)

    # 確認已刪
    r2 = get_customer_by_id(test_id, session=session)
    assert not r2.ok
    print(f'  ✅ get_customer_by_id 也找不到: {r2.error}')

    print('\n' + '='*60)
    print('✅ 全部 11 個 CRUD 測試通過')
    print('='*60)
finally:
    # 清理任何殘留的測試客戶
    if created_ids:
        print(f'\n🧹 清理殘留: {created_ids}')
        for cid in created_ids:
            try:
                delete_customer(session=session, customer_id=cid)
                print(f'  - 清掉 #{cid}')
            except Exception as e:
                print(f'  - #{cid} 清理失敗: {e}')
    session.close()
