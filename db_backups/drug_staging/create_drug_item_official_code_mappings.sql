-- Draft only. Do not execute without explicit approval.
-- Purpose: approved mapping between drug_items and official code systems.
-- This table is separate from drug_items so a clinic drug item can map to
-- multiple official codes and official source versions over time.

CREATE TABLE IF NOT EXISTS drug_item_official_code_mappings (
    id BIGSERIAL PRIMARY KEY,
    drug_item_id BIGINT NOT NULL REFERENCES drug_items(id),
    code_type TEXT NOT NULL,
    code_value TEXT NOT NULL,
    official_source_table TEXT NOT NULL,
    official_source_id BIGINT,
    official_source_version TEXT NOT NULL,
    match_method TEXT NOT NULL,
    confidence TEXT NOT NULL DEFAULT 'medium',
    review_status TEXT NOT NULL DEFAULT 'needs_review',
    review_decision TEXT,
    source_candidate_id BIGINT,
    note_text TEXT,
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT drug_item_official_code_mappings_code_type_chk
        CHECK (code_type IN ('NHI', 'TFDA_LICENSE', 'ATC')),
    CONSTRAINT drug_item_official_code_mappings_match_method_chk
        CHECK (match_method IN ('prescription_nhi_code', 'official_name_exact', 'official_name_contains', 'ingredient_match', 'manual')),
    CONSTRAINT drug_item_official_code_mappings_confidence_chk
        CHECK (confidence IN ('high', 'medium', 'low')),
    CONSTRAINT drug_item_official_code_mappings_review_status_chk
        CHECK (review_status IN ('auto_accepted', 'needs_review', 'approved', 'rejected')),
    CONSTRAINT drug_item_official_code_mappings_review_decision_chk
        CHECK (review_decision IS NULL OR review_decision IN ('approve', 'reject', 'needs_more_source', 'keep_for_reference')),
    CONSTRAINT drug_item_official_code_mappings_uniq
        UNIQUE (drug_item_id, code_type, code_value, official_source_version)
);

CREATE INDEX IF NOT EXISTS idx_drug_item_official_code_mappings_drug
    ON drug_item_official_code_mappings (drug_item_id);

CREATE INDEX IF NOT EXISTS idx_drug_item_official_code_mappings_code
    ON drug_item_official_code_mappings (code_type, code_value);

CREATE INDEX IF NOT EXISTS idx_drug_item_official_code_mappings_source
    ON drug_item_official_code_mappings (official_source_table, official_source_id);

CREATE INDEX IF NOT EXISTS idx_drug_item_official_code_mappings_candidate
    ON drug_item_official_code_mappings (source_candidate_id);

CREATE INDEX IF NOT EXISTS idx_drug_item_official_code_mappings_review
    ON drug_item_official_code_mappings (review_status, review_decision);
