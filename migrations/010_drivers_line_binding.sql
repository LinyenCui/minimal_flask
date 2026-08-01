-- 010: drivers 加 LINE 綁定 + 啟用旗標（司機自助回報車資）
--
-- 用途
--   line_user_id : 司機在 LIFF 表單「請問你是哪一位？」點自己的名字後寫入，
--                  之後開表單就直接認人，不用每次選。
--   is_active    : 停用 = 不出現在選單／司機列表標記停用，但**不真刪**，
--                  歷史班次的 driver_id 才不會變孤兒。
--
-- 冪等（IF NOT EXISTS），本地與 Render 都可重複執行。
-- ⚠️ 部署順序：先在 Render 跑完這段 DDL，再 push 程式碼。

ALTER TABLE drivers ADD COLUMN IF NOT EXISTS line_user_id VARCHAR(64);
ALTER TABLE drivers ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;

-- 既有司機補 TRUE（PG 11+ 的 ADD COLUMN DEFAULT 會回填，這行是保險：
-- 若欄位早已存在且有 NULL，一併補齊）
UPDATE drivers SET is_active = TRUE WHERE is_active IS NULL;

-- 一個 LINE 帳號只能綁一位司機（partial index：未綁定的 NULL 不受限，
-- 所以可以有很多位司機都還沒綁）
CREATE UNIQUE INDEX IF NOT EXISTS ux_drivers_line_user_id
    ON drivers(line_user_id) WHERE line_user_id IS NOT NULL;
