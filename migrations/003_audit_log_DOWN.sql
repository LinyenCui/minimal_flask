-- ============================================================
-- Migration 003 ROLLBACK
-- ============================================================
BEGIN;
DROP INDEX IF EXISTS idx_audit_log_action;
DROP INDEX IF EXISTS idx_audit_log_user_time;
DROP INDEX IF EXISTS idx_audit_log_target;
DROP TABLE IF EXISTS audit_log;
COMMIT;
