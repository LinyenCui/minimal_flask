-- Draft only. Do not run directly without review.
-- Official TFDA ATC raw staging schema.
-- Source: reference_data/drug/raw/tfda_atc_20260522.zip / 41_2.csv

CREATE TABLE IF NOT EXISTS official_tfda_atc_staging (
    id BIGSERIAL PRIMARY KEY,

    -- Raw official columns, renamed to stable snake_case names.
    raw_license_no TEXT NOT NULL,
    raw_primary_or_secondary TEXT,
    raw_atc_code TEXT NOT NULL,
    raw_atc_name_en TEXT,
    raw_atc_name_zh TEXT,

    -- Normalized helper columns for future matching and review.
    normalized_license_no TEXT NOT NULL,
    normalized_atc_code TEXT NOT NULL,
    normalized_atc_name_en TEXT,
    normalized_atc_name_zh TEXT,
    is_primary_atc BOOLEAN,

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

    CONSTRAINT official_tfda_atc_staging_source_row_uniq
        UNIQUE (source_version, source_checksum, source_inner_file, source_row_number),
    CONSTRAINT official_tfda_atc_staging_business_uniq
        UNIQUE (source_version, normalized_license_no, normalized_atc_code, raw_primary_or_secondary)
);

CREATE INDEX IF NOT EXISTS idx_official_tfda_atc_staging_batch
    ON official_tfda_atc_staging (import_batch_id);
CREATE INDEX IF NOT EXISTS idx_official_tfda_atc_staging_license
    ON official_tfda_atc_staging (normalized_license_no);
CREATE INDEX IF NOT EXISTS idx_official_tfda_atc_staging_atc
    ON official_tfda_atc_staging (normalized_atc_code);
