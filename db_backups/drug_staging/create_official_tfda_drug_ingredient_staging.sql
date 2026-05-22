-- Draft only. Do not run directly without review.
-- Official TFDA drug ingredient raw staging schema.
-- Source: reference_data/drug/raw/tfda_drug_ingredient_20260522.zip / 43_2.csv

CREATE TABLE IF NOT EXISTS official_tfda_drug_ingredient_staging (
    id BIGSERIAL PRIMARY KEY,

    -- Raw official columns, renamed to stable snake_case names.
    raw_license_no TEXT NOT NULL,
    raw_prescription_label TEXT,
    raw_ingredient_name TEXT,
    raw_ingredient_code TEXT,
    raw_amount_description TEXT,
    raw_amount TEXT,
    raw_amount_unit TEXT,

    -- Normalized helper columns for future matching and review.
    normalized_license_no TEXT NOT NULL,
    normalized_ingredient_name TEXT,
    normalized_ingredient_code TEXT,
    normalized_amount NUMERIC,
    normalized_amount_unit TEXT,

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

    CONSTRAINT official_tfda_drug_ingredient_staging_source_row_uniq
        UNIQUE (source_version, source_checksum, source_inner_file, source_row_number),
    CONSTRAINT official_tfda_drug_ingredient_staging_business_uniq
        UNIQUE (source_version, normalized_license_no, normalized_ingredient_code, raw_amount_description, raw_amount, raw_amount_unit, source_row_number)
);

CREATE INDEX IF NOT EXISTS idx_official_tfda_drug_ingredient_staging_batch
    ON official_tfda_drug_ingredient_staging (import_batch_id);
CREATE INDEX IF NOT EXISTS idx_official_tfda_drug_ingredient_staging_license
    ON official_tfda_drug_ingredient_staging (normalized_license_no);
CREATE INDEX IF NOT EXISTS idx_official_tfda_drug_ingredient_staging_ingredient
    ON official_tfda_drug_ingredient_staging (normalized_ingredient_name, normalized_ingredient_code);
