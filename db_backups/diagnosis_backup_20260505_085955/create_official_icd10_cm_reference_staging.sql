-- create_official_icd10_cm_reference_staging.sql
--
-- Purpose:
--   Staging table for the full official NHI 2023 ICD-10-CM diagnosis reference.
--   This table is separate from diagnosis_icd10_reference_staging, which is used
--   for OCR/prescription-derived small candidate batches.
--
-- Safety:
--   This script only defines the official_icd10_cm_reference_staging table.
--   It does not modify diagnosis_codes, diagnosis_icd10_reference_staging,
--   diagnosis_icd_mappings_staging, drug tables, OCR tables, or prescription tables.

CREATE TABLE IF NOT EXISTS official_icd10_cm_reference_staging (
    id BIGSERIAL PRIMARY KEY,
    icd10_code TEXT NOT NULL,
    normalized_code TEXT NOT NULL,
    use_flag TEXT,
    official_name_en TEXT NOT NULL,
    official_name_zh TEXT NOT NULL,
    status TEXT,
    revision_date TEXT,
    source_file TEXT NOT NULL,
    source_sheet TEXT NOT NULL,
    source_row_number INTEGER NOT NULL,
    source_version TEXT NOT NULL,
    import_batch_id TEXT NOT NULL,
    imported_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    source_checksum TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    is_billable BOOLEAN NOT NULL DEFAULT FALSE,
    notes TEXT,
    CONSTRAINT official_icd10_cm_reference_staging_source_code_uniq
        UNIQUE (source_version, icd10_code)
);

CREATE INDEX IF NOT EXISTS idx_official_icd10_cm_ref_norm_code
    ON official_icd10_cm_reference_staging (normalized_code);

CREATE INDEX IF NOT EXISTS idx_official_icd10_cm_ref_import_batch
    ON official_icd10_cm_reference_staging (import_batch_id);

CREATE INDEX IF NOT EXISTS idx_official_icd10_cm_ref_billable
    ON official_icd10_cm_reference_staging (is_billable);
