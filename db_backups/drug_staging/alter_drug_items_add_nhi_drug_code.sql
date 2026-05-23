-- Draft only. Do not execute without explicit approval.
-- Purpose: add primary NHI drug code fields to drug_items for pharmacy-facing identification.
-- This migration should not update existing rows.

ALTER TABLE drug_items
    ADD COLUMN IF NOT EXISTS nhi_drug_code VARCHAR(20),
    ADD COLUMN IF NOT EXISTS nhi_drug_code_source VARCHAR(50),
    ADD COLUMN IF NOT EXISTS nhi_drug_code_confidence VARCHAR(20),
    ADD COLUMN IF NOT EXISTS nhi_drug_code_verified_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS nhi_drug_code_note TEXT;

ALTER TABLE drug_items
    ADD CONSTRAINT drug_items_nhi_drug_code_source_chk
        CHECK (
            nhi_drug_code_source IS NULL
            OR nhi_drug_code_source IN ('prescription_ocr', 'official_nhi', 'manual', 'migrated')
        );

ALTER TABLE drug_items
    ADD CONSTRAINT drug_items_nhi_drug_code_confidence_chk
        CHECK (
            nhi_drug_code_confidence IS NULL
            OR nhi_drug_code_confidence IN ('high', 'medium', 'low')
        );

CREATE INDEX IF NOT EXISTS idx_drug_items_nhi_drug_code
    ON drug_items (nhi_drug_code);

CREATE INDEX IF NOT EXISTS idx_drug_items_nhi_drug_code_source
    ON drug_items (nhi_drug_code_source);

