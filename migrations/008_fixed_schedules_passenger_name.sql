-- 008: fixed_schedules 加乘客欄 + note 資料搬移
--
-- 背景：note 原設計是「請假原因」（apply_fixed_schedule_leave 寫入、restore 清空，
-- 匯入時請假列的 note → trips.passenger_leave_reason → 進請款報表說明欄）。
-- 用戶實際把接送順序/乘客名 key 進 note（原本沒有乘客欄），導致報表被污染。
--
-- 搬移規則：status ≠ '請假' 的 note 全部搬到 passenger_name（那些都是乘客資料）；
-- status='請假' 的 note 是真請假原因，留在 note。#4 是混合列（接送順序＋住院）手動拆。
--
-- ⚠️ prod（Render）執行順序：先跑【第 1 段】→ push main 部署 → 再跑【第 2 段】
--    （新代碼需要欄位先存在；資料搬移等新代碼上線後再做，避免空窗）

-- ── 第 1 段：加欄位（先跑，對舊代碼無害）──
ALTER TABLE fixed_schedules ADD COLUMN IF NOT EXISTS passenger_name TEXT;

-- ── 第 2 段：資料搬移（新代碼部署後跑；可重跑，已搬過的不會重複）──
-- 2a) 非請假列：note 整段搬到乘客欄
UPDATE fixed_schedules
SET passenger_name = note, note = NULL
WHERE note IS NOT NULL AND note <> ''
  AND status IS DISTINCT FROM '請假'
  AND passenger_name IS NULL;

-- 2b) 混合列 #4（請假中，note 前段是接送順序、末行是請假原因）：拆開
UPDATE fixed_schedules
SET passenger_name = '（廖貴7:30）→寶珠7:40 →診所7:45',
    note = '中華北路住院'
WHERE id = 4 AND status = '請假'
  AND passenger_name IS NULL
  AND note LIKE '（廖貴%';

-- （#13 note='中華北路住院' 為純請假原因，不動）
