-- Draft only. Do not execute without explicit approval.
-- Purpose: staging candidates extracted from prescription photos / existing OCR text.
-- This table keeps raw OCR values, normalized values, correction results,
-- official NHI join snapshots, and review state.

CREATE TABLE IF NOT EXISTS prescription_nhi_drug_code_candidates (
    id BIGSERIAL PRIMARY KEY,

    -- Source occurrence. A repeated OCR code may appear in multiple columns for the same row.
    source_photo TEXT NOT NULL,
    source_csv TEXT NOT NULL,
    source_photo_page_or_index TEXT,
    source_row_number INTEGER NOT NULL,
    source_column TEXT NOT NULL,
    source_match_index INTEGER NOT NULL,
    source_match_start INTEGER,
    source_match_end INTEGER,

    -- OCR code values. raw is never overwritten.
    raw_nhi_drug_code TEXT NOT NULL,
    normalized_nhi_drug_code TEXT NOT NULL,
    corrected_nhi_drug_code TEXT,
    effective_nhi_drug_code TEXT,
    correction_method TEXT NOT NULL DEFAULT 'none',

    -- Official NHI join snapshot. These values do not replace the official table.
    official_join_status TEXT NOT NULL DEFAULT 'no_match',
    official_match_count INTEGER NOT NULL DEFAULT 0,
    official_source_table TEXT,
    official_normalized_drug_code TEXT,
    official_drug_name_zh TEXT,
    official_drug_name_en TEXT,
    official_ingredient TEXT,
    official_atc_code TEXT,

    -- Nearby OCR text for review.
    nearby_text TEXT,
    raw_drug_name_text TEXT,
    raw_dosage_text TEXT,
    raw_frequency_text TEXT,
    raw_days_text TEXT,

    -- Extraction and review metadata.
    extraction_method TEXT NOT NULL DEFAULT 'regex_existing_ocr_csv',
    confidence TEXT NOT NULL DEFAULT 'low',
    review_status TEXT NOT NULL DEFAULT 'pending',
    review_decision TEXT,
    reviewer TEXT,
    reviewed_at TIMESTAMPTZ,
    review_note TEXT,
    import_batch_id TEXT NOT NULL,
    imported_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT prescription_nhi_candidates_correction_method_chk
        CHECK (correction_method IN ('none', 'ocr_confusion_rule', 'manual', 'not_applicable')),
    CONSTRAINT prescription_nhi_candidates_join_status_chk
        CHECK (official_join_status IN ('matched', 'corrected_matched', 'no_match', 'false_positive')),
    CONSTRAINT prescription_nhi_candidates_match_count_chk
        CHECK (official_match_count >= 0),
    CONSTRAINT prescription_nhi_candidates_confidence_chk
        CHECK (confidence IN ('high', 'medium', 'low')),
    CONSTRAINT prescription_nhi_candidates_review_status_chk
        CHECK (review_status IN ('auto_accepted', 'needs_review', 'rejected', 'pending')),
    CONSTRAINT prescription_nhi_candidates_review_decision_chk
        CHECK (review_decision IS NULL OR review_decision IN ('approve', 'reject', 'needs_more_source', 'keep_for_reference')),
    CONSTRAINT prescription_nhi_candidates_source_occurrence_uniq
        UNIQUE (source_csv, source_row_number, source_column, raw_nhi_drug_code, source_match_index, import_batch_id)
);

CREATE INDEX IF NOT EXISTS idx_prescription_nhi_candidates_effective_code
    ON prescription_nhi_drug_code_candidates (effective_nhi_drug_code);

CREATE INDEX IF NOT EXISTS idx_prescription_nhi_candidates_normalized_code
    ON prescription_nhi_drug_code_candidates (normalized_nhi_drug_code);

CREATE INDEX IF NOT EXISTS idx_prescription_nhi_candidates_official_code
    ON prescription_nhi_drug_code_candidates (official_normalized_drug_code);

CREATE INDEX IF NOT EXISTS idx_prescription_nhi_candidates_photo
    ON prescription_nhi_drug_code_candidates (source_photo, source_row_number);

CREATE INDEX IF NOT EXISTS idx_prescription_nhi_candidates_match_position
    ON prescription_nhi_drug_code_candidates (source_csv, source_row_number, source_column, source_match_start, source_match_end);

CREATE INDEX IF NOT EXISTS idx_prescription_nhi_candidates_batch
    ON prescription_nhi_drug_code_candidates (import_batch_id);

CREATE INDEX IF NOT EXISTS idx_prescription_nhi_candidates_review
    ON prescription_nhi_drug_code_candidates (review_status, review_decision);
