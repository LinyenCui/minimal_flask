-- Draft only. Do not execute without explicit approval.
-- Purpose: staging candidates extracted from prescription photos/OCR text.

CREATE TABLE IF NOT EXISTS prescription_nhi_drug_code_candidates (
    id BIGSERIAL PRIMARY KEY,
    source_photo TEXT NOT NULL,
    source_photo_page_or_index TEXT,
    source_row_number INTEGER,
    raw_nhi_drug_code TEXT NOT NULL,
    normalized_nhi_drug_code TEXT NOT NULL,
    raw_drug_name_text TEXT,
    raw_dosage_text TEXT,
    raw_frequency_text TEXT,
    raw_days_text TEXT,
    ocr_method TEXT NOT NULL DEFAULT 'existing_ocr_text_extraction',
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
    CONSTRAINT prescription_nhi_drug_code_candidates_confidence_chk
        CHECK (confidence IN ('high', 'medium', 'low')),
    CONSTRAINT prescription_nhi_drug_code_candidates_review_status_chk
        CHECK (review_status IN ('pending', 'approved', 'rejected', 'needs_more_source')),
    CONSTRAINT prescription_nhi_drug_code_candidates_review_decision_chk
        CHECK (review_decision IS NULL OR review_decision IN ('approve', 'reject', 'needs_more_source', 'keep_for_reference'))
);

CREATE INDEX IF NOT EXISTS idx_prescription_nhi_candidates_code
    ON prescription_nhi_drug_code_candidates (normalized_nhi_drug_code);

CREATE INDEX IF NOT EXISTS idx_prescription_nhi_candidates_photo
    ON prescription_nhi_drug_code_candidates (source_photo, source_row_number);

CREATE INDEX IF NOT EXISTS idx_prescription_nhi_candidates_batch
    ON prescription_nhi_drug_code_candidates (import_batch_id);

CREATE INDEX IF NOT EXISTS idx_prescription_nhi_candidates_review
    ON prescription_nhi_drug_code_candidates (review_status, review_decision);
