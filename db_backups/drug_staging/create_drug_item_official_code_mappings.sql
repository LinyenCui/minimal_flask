-- Draft only. Do not execute without explicit approval.
-- Purpose: approved mapping between drug_items and official code systems.

CREATE TABLE IF NOT EXISTS drug_item_official_code_mappings (
    id BIGSERIAL PRIMARY KEY,
    drug_item_id BIGINT NOT NULL REFERENCES drug_items(id),
    code_type TEXT NOT NULL,
    code_value TEXT NOT NULL,
    official_source_table TEXT NOT NULL,
    official_source_id BIGINT,
    match_method TEXT NOT NULL,
    confidence TEXT NOT NULL DEFAULT 'medium',
    review_status TEXT NOT NULL DEFAULT 'approved',
    review_decision TEXT NOT NULL DEFAULT 'approve',
    note_text TEXT,
    source_candidate_table TEXT,
    source_candidate_id BIGINT,
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT drug_item_official_code_mappings_code_type_chk
        CHECK (code_type IN ('NHI', 'TFDA_LICENSE', 'ATC')),
    CONSTRAINT drug_item_official_code_mappings_confidence_chk
        CHECK (confidence IN ('high', 'medium', 'low')),
    CONSTRAINT drug_item_official_code_mappings_review_status_chk
        CHECK (review_status IN ('pending', 'approved', 'rejected', 'needs_more_source')),
    CONSTRAINT drug_item_official_code_mappings_review_decision_chk
        CHECK (review_decision IN ('approve', 'reject', 'needs_more_source')),
    CONSTRAINT drug_item_official_code_mappings_uniq
        UNIQUE (drug_item_id, code_type, code_value, official_source_table, COALESCE(official_source_id, 0))
);

CREATE INDEX IF NOT EXISTS idx_drug_item_official_code_mappings_drug
    ON drug_item_official_code_mappings (drug_item_id);

CREATE INDEX IF NOT EXISTS idx_drug_item_official_code_mappings_code
    ON drug_item_official_code_mappings (code_type, code_value);

CREATE INDEX IF NOT EXISTS idx_drug_item_official_code_mappings_review
    ON drug_item_official_code_mappings (review_status, review_decision);
