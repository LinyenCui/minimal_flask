-- Draft only. Do not run directly without review.
-- Official NHI drug payment raw staging schema.
-- Source: reference_data/drug/raw/nhi_drug_payment_20260522.csv

CREATE TABLE IF NOT EXISTS official_nhi_drug_payment_staging (
    id BIGSERIAL PRIMARY KEY,

    -- Raw official columns, renamed to stable snake_case names.
    raw_change_flag TEXT,
    raw_drug_code TEXT NOT NULL,
    raw_drug_name_en TEXT,
    raw_drug_name_zh TEXT,
    raw_ingredient TEXT,
    raw_spec_amount TEXT,
    raw_spec_unit TEXT,
    raw_single_or_compound TEXT,
    raw_payment_price TEXT,
    raw_effective_start_date TEXT,
    raw_effective_end_date TEXT,
    raw_supplier TEXT,
    raw_manufacturer_name TEXT,
    raw_dosage_form TEXT,
    raw_drug_category TEXT,
    raw_category_group_name TEXT,
    raw_atc_code TEXT,
    raw_reimbursement_rule_chapter TEXT,
    raw_drug_code_url TEXT,
    raw_reimbursement_rule_url TEXT,

    -- Normalized helper columns for future matching and review.
    normalized_drug_code TEXT,
    normalized_drug_name_en TEXT,
    normalized_drug_name_zh TEXT,
    normalized_ingredient TEXT,
    normalized_spec_amount NUMERIC,
    normalized_spec_unit TEXT,
    normalized_payment_price NUMERIC,
    effective_start_date DATE,
    effective_end_date DATE,
    normalized_supplier TEXT,
    normalized_manufacturer_name TEXT,
    normalized_dosage_form TEXT,
    normalized_atc_code TEXT,
    parsed_tfda_license_id TEXT,
    normalized_license_no TEXT,

    -- Source metadata.
    source_file TEXT NOT NULL,
    source_url TEXT,
    source_version TEXT NOT NULL,
    import_batch_id TEXT NOT NULL,
    source_checksum TEXT NOT NULL,
    source_row_number INTEGER NOT NULL,
    imported_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    notes TEXT,

    CONSTRAINT official_nhi_drug_payment_staging_source_row_uniq
        UNIQUE (source_version, source_checksum, source_row_number),
    CONSTRAINT official_nhi_drug_payment_staging_business_uniq
        UNIQUE (source_version, normalized_drug_code, raw_effective_start_date, raw_effective_end_date, raw_payment_price)
);

CREATE INDEX IF NOT EXISTS idx_official_nhi_drug_payment_staging_batch
    ON official_nhi_drug_payment_staging (import_batch_id);
CREATE INDEX IF NOT EXISTS idx_official_nhi_drug_payment_staging_drug_code
    ON official_nhi_drug_payment_staging (normalized_drug_code);
CREATE INDEX IF NOT EXISTS idx_official_nhi_drug_payment_staging_license
    ON official_nhi_drug_payment_staging (normalized_license_no);
CREATE INDEX IF NOT EXISTS idx_official_nhi_drug_payment_staging_atc
    ON official_nhi_drug_payment_staging (normalized_atc_code);
CREATE INDEX IF NOT EXISTS idx_official_nhi_drug_payment_staging_names
    ON official_nhi_drug_payment_staging (normalized_drug_name_zh, normalized_drug_name_en);
