-- ============================================================
-- Migration 003: audit_log 表
-- ============================================================
-- 日期：2026-05-03
-- 用途：所有 mutation 操作（trips/customers/...）的稽核紀錄
-- 設計：R-6（所有 mutation 必須寫 audit log）
--
-- 用例：
--   - AI 操作可追溯（誰下指令、AI 計畫做什麼、實際改了什麼）
--   - 出包時可還原（before_state JSONB）
--   - 統計分析（最近 X 天某類動作頻次）
-- ============================================================

BEGIN;

CREATE TABLE IF NOT EXISTS audit_log (
    id BIGSERIAL PRIMARY KEY,

    -- WHO
    user_id VARCHAR(64),                    -- LINE userId（可 NULL：系統觸發）
    user_name VARCHAR(128),                 -- 顯示名（cache 用）

    -- WHAT
    action_type VARCHAR(64) NOT NULL,       -- 'passenger_leave' / 'cancel_trip' / ...
    target_table VARCHAR(64) NOT NULL,      -- 'trips' / 'customers' / 'fixed_schedules'
    target_id INTEGER NOT NULL,

    -- BEFORE / AFTER
    before_state JSONB,                     -- 操作前該 row 完整快照
    after_state JSONB,                      -- 操作後（同上）
    changed_fields TEXT[],                  -- 哪些欄位變了

    -- WHY / 額外
    reason TEXT,                            -- 操作原因（請假理由、修改理由等）
    extra JSONB,                            -- 其他結構化資料

    -- HOW
    via VARCHAR(32),                        -- 'sandbox' | 'quick_command' | 'button' | 'system'

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 常用查詢索引
CREATE INDEX idx_audit_log_target ON audit_log (target_table, target_id);
CREATE INDEX idx_audit_log_user_time ON audit_log (user_id, created_at DESC);
CREATE INDEX idx_audit_log_action ON audit_log (action_type, created_at DESC);

-- 註解
COMMENT ON TABLE audit_log IS '所有 mutation 的稽核紀錄（R-6）';
COMMENT ON COLUMN audit_log.via IS '操作來源：sandbox / quick_command / button / system';
COMMENT ON COLUMN audit_log.before_state IS '操作前完整 row 快照（JSONB），方便還原';
COMMENT ON COLUMN audit_log.changed_fields IS '變更欄位清單';

COMMIT;

-- 驗證查詢（可手動跑）
-- SELECT count(*) FROM audit_log;
-- SELECT action_type, target_table, count(*) FROM audit_log GROUP BY 1, 2;
