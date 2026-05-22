-- Draft only. Do not run directly without review.
-- Official TFDA drug license raw staging schema.
-- Source: reference_data/drug/raw/tfda_drug_license_20260522.zip / 36_2.csv

CREATE TABLE IF NOT EXISTS official_tfda_drug_license_staging (
    id BIGSERIAL PRIMARY KEY,

    -- Raw official columns, renamed to stable snake_case names.
    raw_license_no TEXT NOT NULL,
    raw_cancel_status TEXT,
    raw_cancel_date TEXT,
    raw_cancel_reason TEXT,
    raw_valid_until TEXT,
    raw_issue_date TEXT,
    raw_license_type TEXT,
    raw_old_license_no TEXT,
    raw_import_clearance_no TEXT,
    raw_product_name_zh TEXT,
    raw_product_name_en TEXT,
    raw_indication TEXT,
    raw_dosage_form TEXT,
    raw_package TEXT,
    raw_drug_category TEXT,
    raw_controlled_drug_level TEXT,
    raw_main_ingredient_summary TEXT,
    raw_applicant_name TEXT,
    raw_applicant_address TEXT,
    raw_applicant_tax_id TEXT,
    raw_manufacturer_name TEXT,
    raw_manufacturer_address TEXT,
    raw_manufacturer_company_address TEXT,
    raw_manufacturer_country TEXT,
    raw_manufacturing_process TEXT,
    raw_changed_at TEXT,
    raw_usage_dosage TEXT,
    raw_package_and_barcode TEXT,

    -- Normalized helper columns for future matching and review.
    normalized_license_no TEXT NOT NULL,
    normalized_old_license_no TEXT,
    normalized_product_name_zh TEXT,
    normalized_product_name_en TEXT,
    normalized_dosage_form TEXT,
    normalized_main_ingredient_summary TEXT,
    normalized_applicant_name TEXT,
    normalized_manufacturer_name TEXT,
    normalized_manufacturer_country TEXT,
    license_valid_until DATE,
    license_issue_date DATE,
    cancel_date DATE,
    changed_at DATE,
    is_cancelled BOOLEAN,
    is_active_license BOOLEAN,

    -- Source metadata.
    source_file TEXT NOT NULL,
    source_inner_file TEXT NOT NULL,
    source_url TEXT,
    source_version TEXT NOT NULL,
    import_batch_id TEXT NOT NULL,
    source_checksum TEXT NOT NULL,
    source_row_number INTEGER NOT NULL,
    imported_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    notes TEXT,

    CONSTRAINT official_tfda_drug_license_staging_source_row_uniq
        UNIQUE (source_version, source_checksum, source_inner_file, source_row_number),
    CONSTRAINT official_tfda_drug_license_staging_business_uniq
        UNIQUE (source_version, normalized_license_no, source_row_number)
);

CREATE INDEX IF NOT EXISTS idx_official_tfda_drug_license_staging_batch
    ON official_tfda_drug_license_staging (import_batch_id);
CREATE INDEX IF NOT EXISTS idx_official_tfda_drug_license_staging_license
    ON official_tfda_drug_license_staging (normalized_license_no);
CREATE INDEX IF NOT EXISTS idx_official_tfda_drug_license_staging_names
    ON official_tfda_drug_license_staging (normalized_product_name_zh, normalized_product_name_en);
CREATE INDEX IF NOT EXISTS idx_official_tfda_drug_license_staging_applicant
    ON official_tfda_drug_license_staging (normalized_applicant_name);
CREATE INDEX IF NOT EXISTS idx_official_tfda_drug_license_staging_manufacturer
    ON official_tfda_drug_license_staging (normalized_manufacturer_name);
