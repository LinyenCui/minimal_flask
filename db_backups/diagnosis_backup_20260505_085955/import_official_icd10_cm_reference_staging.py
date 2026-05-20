#!/usr/bin/env python3
"""Import official NHI ICD-10-CM reference into staging.

Default mode is dry-run: it reads the XLSX and prints a profile only.
Use --apply to create/import official_icd10_cm_reference_staging.

Safety:
- Does not touch diagnosis_codes.
- Does not touch diagnosis_icd10_reference_staging.
- Does not touch diagnosis_icd_mappings_staging.
- Does not touch drug tables.
- Does not import ICD-10-PCS.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

try:
    import openpyxl
except ImportError:  # pragma: no cover
    openpyxl = None

try:
    import psycopg2
    from psycopg2.extras import execute_values
except ImportError:  # pragma: no cover
    psycopg2 = None
    execute_values = None

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parents[1]
SOURCE_FILE = PROJECT_ROOT / "reference_data/icd/nhi_2023_icd10_cm_pcs.xlsx"
CREATE_SQL = BASE_DIR / "create_official_icd10_cm_reference_staging.sql"
SOURCE_SHEET = "ICD-10-CM"
SOURCE_VERSION = "nhi_2023_icd10_cm"
TABLE_NAME = "official_icd10_cm_reference_staging"

ICD10_RE = re.compile(r"^[A-Z][0-9][0-9A-Z](?:\.[0-9A-Z]{1,4})?$")


@dataclass(frozen=True)
class Icd10ReferenceRow:
    icd10_code: str
    normalized_code: str
    use_flag: str
    official_name_en: str
    official_name_zh: str
    status: str
    revision_date: str
    source_file: str
    source_sheet: str
    source_row_number: int
    source_version: str
    source_checksum: str
    is_active: bool
    is_billable: bool
    notes: str


def normalize_database_url(url: str) -> str:
    if url.startswith("postgresql+psycopg://"):
        return "postgresql://" + url[len("postgresql+psycopg://") :]
    if url.startswith("postgresql+psycopg2://"):
        return "postgresql://" + url[len("postgresql+psycopg2://") :]
    return url


def load_env() -> None:
    if load_dotenv is not None:
        load_dotenv(PROJECT_ROOT / ".env")
        load_dotenv(PROJECT_ROOT / ".env.dev")


def connect():
    if psycopg2 is None:
        raise RuntimeError("Missing psycopg2; cannot connect to database.")
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("Missing DATABASE_URL.")
    return psycopg2.connect(normalize_database_url(database_url))


def row_checksum(values: Iterable[str]) -> str:
    joined = "␟".join(values)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def load_rows() -> list[Icd10ReferenceRow]:
    if openpyxl is None:
        raise RuntimeError("Missing openpyxl; cannot read XLSX source.")
    if not SOURCE_FILE.exists():
        raise FileNotFoundError(SOURCE_FILE)

    workbook = openpyxl.load_workbook(SOURCE_FILE, read_only=True, data_only=True)
    try:
        worksheet = workbook[SOURCE_SHEET]
        iterator = worksheet.iter_rows(values_only=True)
        header = [str(value).replace("\n", " ").strip() if value is not None else "" for value in next(iterator)]
        expected = [
            "2023年版 ICD-10-CM",
            "USE",
            "2023 CM英文名稱",
            "2023 CM中文名稱",
            "狀態",
            "修訂日期",
        ]
        if header[:6] != expected:
            raise RuntimeError(f"Unexpected header: {header[:6]!r}")

        rows: list[Icd10ReferenceRow] = []
        for source_row_number, row in enumerate(iterator, start=2):
            values = list(row) + [None] * 6
            code = str(values[0]).strip() if values[0] is not None else ""
            use_flag = str(values[1]).strip() if values[1] is not None else ""
            name_en = str(values[2]).strip() if values[2] is not None else ""
            name_zh = str(values[3]).strip() if values[3] is not None else ""
            status = str(values[4]).strip() if values[4] is not None else ""
            revision_date = str(values[5]).strip() if values[5] is not None else ""
            if not code and not name_en and not name_zh:
                continue
            checksum = row_checksum([code, use_flag, name_en, name_zh, status, revision_date])
            rows.append(
                Icd10ReferenceRow(
                    icd10_code=code,
                    normalized_code=code.upper(),
                    use_flag=use_flag,
                    official_name_en=name_en,
                    official_name_zh=name_zh,
                    status=status,
                    revision_date=revision_date,
                    source_file=str(SOURCE_FILE),
                    source_sheet=SOURCE_SHEET,
                    source_row_number=source_row_number,
                    source_version=SOURCE_VERSION,
                    source_checksum=checksum,
                    is_active=status != "代碼刪除",
                    is_billable=use_flag == "1",
                    notes="",
                )
            )
        return rows
    finally:
        workbook.close()


def profile(rows: list[Icd10ReferenceRow]) -> dict:
    codes = Counter(row.icd10_code for row in rows if row.icd10_code)
    return {
        "total_rows": len(rows),
        "blank_code": sum(1 for row in rows if not row.icd10_code),
        "blank_zh": sum(1 for row in rows if not row.official_name_zh),
        "blank_en": sum(1 for row in rows if not row.official_name_en),
        "invalid_code": sum(1 for row in rows if row.icd10_code and not ICD10_RE.match(row.icd10_code)),
        "duplicate_code_count": sum(1 for count in codes.values() if count > 1),
        "duplicate_rows": sum(count for count in codes.values() if count > 1),
        "use_distribution": Counter(row.use_flag for row in rows),
        "status_distribution": Counter(row.status for row in rows),
    }


def print_profile(rows: list[Icd10ReferenceRow], import_batch_id: str) -> None:
    stats = profile(rows)
    print("ICD-REF-1 official ICD-10-CM reference staging dry-run")
    print(f"source_file: {SOURCE_FILE}")
    print(f"source_sheet: {SOURCE_SHEET}")
    print(f"source_version: {SOURCE_VERSION}")
    print(f"import_batch_id: {import_batch_id}")
    print(f"total_rows: {stats['total_rows']}")
    print(f"blank_code: {stats['blank_code']}")
    print(f"blank_zh: {stats['blank_zh']}")
    print(f"blank_en: {stats['blank_en']}")
    print(f"invalid_code: {stats['invalid_code']}")
    print(f"duplicate_code_count: {stats['duplicate_code_count']}")
    print("USE distribution:", dict(stats["use_distribution"]))
    print("status distribution:", dict(stats["status_distribution"]))
    print("first 5 rows:")
    for row in rows[:5]:
        print(f"  {row.source_row_number}: {row.icd10_code} use={row.use_flag} {row.official_name_zh} / {row.official_name_en}")


def ensure_table(cursor) -> None:
    sql = CREATE_SQL.read_text(encoding="utf-8")
    cursor.execute(sql)


def insert_rows(cursor, rows: list[Icd10ReferenceRow], import_batch_id: str) -> int:
    if execute_values is None:
        raise RuntimeError("Missing psycopg2.extras.execute_values.")
    values = [
        (
            row.icd10_code,
            row.normalized_code,
            row.use_flag,
            row.official_name_en,
            row.official_name_zh,
            row.status,
            row.revision_date,
            row.source_file,
            row.source_sheet,
            row.source_row_number,
            row.source_version,
            import_batch_id,
            row.source_checksum,
            row.is_active,
            row.is_billable,
            row.notes,
        )
        for row in rows
    ]
    execute_values(
        cursor,
        """
        INSERT INTO official_icd10_cm_reference_staging (
            icd10_code, normalized_code, use_flag, official_name_en, official_name_zh,
            status, revision_date, source_file, source_sheet, source_row_number,
            source_version, import_batch_id, source_checksum, is_active, is_billable, notes
        ) VALUES %s
        ON CONFLICT (source_version, icd10_code) DO NOTHING
        """,
        values,
        page_size=1000,
    )
    return cursor.rowcount


def main() -> int:
    parser = argparse.ArgumentParser(description="Import official NHI ICD-10-CM reference into staging")
    parser.add_argument("--apply", action="store_true", help="Create/import official_icd10_cm_reference_staging")
    args = parser.parse_args()

    rows = load_rows()
    import_batch_id = f"official_icd10_cm_{datetime.now():%Y%m%d_%H%M%S}"
    print_profile(rows, import_batch_id)

    if not args.apply:
        print("Dry-run only. No database connection and no database writes were performed.")
        return 0

    load_env()
    with connect() as conn, conn.cursor() as cursor:
        ensure_table(cursor)
        inserted = insert_rows(cursor, rows, import_batch_id)
    print(f"Applied import_batch_id: {import_batch_id}")
    print(f"Inserted rows: {inserted}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
