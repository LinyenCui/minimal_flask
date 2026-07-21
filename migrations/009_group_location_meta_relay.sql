-- 009: group_location_meta 加 relay_chat_id（到院通知接送群綁定）
--
-- 背景：接送群 = 接送人員+司機+bot 的專用群。工作群（group_location_meta.chat_id）
-- 可綁定一個接送群（relay_chat_id）：
--   ・司機在接送群傳位置 → bot reply 到院通知（免費）
--   ・司機忘記、跑回工作群傳 → 工作群照常回 ETA 卡，另 push 一則到綁定的接送群（fallback，吃額度）
--
-- 可重跑（IF NOT EXISTS）。Render Adminer 執行同一句即可。

ALTER TABLE group_location_meta ADD COLUMN IF NOT EXISTS relay_chat_id VARCHAR(128);
