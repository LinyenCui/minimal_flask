-- 011: drivers 加「管理司機」旗標（司機自助回報車資 — 代填／代查）
--
-- 用途
--   is_manager : TRUE 的司機在 LIFF 回報車資表單可以
--                  (a) 切換檢視任何一位司機（含已停用的 9999「其他」）
--                  (b) 代任何司機填車資（audit 會記成「{管理員}代{司機}」）
--                一般司機維持現狀：只看得到、只改得到自己的。
--
-- 目前的管理司機
--   5386 崔林彥（老闆本人）        → 本檔直接設定
--   1117 春妃（尚未建檔）          → 用戶自行在 Adminer 新增該列時要一併帶 is_manager = TRUE
--                                    範例見檔尾註解
--
-- 冪等（IF NOT EXISTS），本地與 Render 都可重複執行。
-- ⚠️ 部署順序：先在 Render 跑完這段 DDL，再 push 程式碼
--    （程式的 SELECT 會讀 is_manager 欄位，欄位不在會整個表單掛掉）。

ALTER TABLE drivers ADD COLUMN IF NOT EXISTS is_manager BOOLEAN DEFAULT FALSE;

-- 既有司機補 FALSE（欄位若早已存在且有 NULL，一併補齊）
UPDATE drivers SET is_manager = FALSE WHERE is_manager IS NULL;

-- 老闆本人
UPDATE drivers SET is_manager = TRUE WHERE id = 5386;

-- ------------------------------------------------------------------
-- 春妃（1117）建檔範例 —— 用戶在 Adminer 新增時整段貼上即可：
--
--   INSERT INTO drivers (id, name, plate_number, is_active, is_manager)
--   VALUES (1117, '春妃', NULL, TRUE, TRUE)
--   ON CONFLICT (id) DO UPDATE SET is_manager = TRUE, is_active = TRUE;
--
--   -- 手動指定 id 不會推進序列 → 補推，之後沒指定 id 的新增才不會撞號
--   SELECT setval(pg_get_serial_sequence('drivers', 'id'),
--                 GREATEST((SELECT MAX(id) FROM drivers), 1));
-- ------------------------------------------------------------------
