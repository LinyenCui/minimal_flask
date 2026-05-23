#!/usr/bin/env python3
"""Build an occurrence-level dry-run preview for prescription NHI drug codes.

Default mode is read-only and does not connect to the database.
--apply is intentionally not implemented in this phase.
"""

from __future__ import annotations

import argparse
import csv
import os
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
DRUG_STAGING_DIR = ROOT / "db_backups" / "drug_staging"
REGEX_CSV = DRUG_STAGING_DIR / "prescription_nhi_drug_code_regex_candidates.csv"
CLEANING_CSV = DRUG_STAGING_DIR / "prescription_nhi_drug_code_cleaning_candidates.csv"
PREVIEW_CSV = DRUG_STAGING_DIR / "prescription_nhi_drug_code_candidates_import_preview.csv"
REPORT_MD = DRUG_STAGING_DIR / "00_prescription_nhi_drug_code_candidates_import_dry_run_report.md"
APPLY_REPORT_MD = DRUG_STAGING_DIR / "00_prescription_nhi_drug_code_candidates_import_apply_report.md"
CREATE_SQL = DRUG_STAGING_DIR / "create_prescription_nhi_drug_code_candidates.sql"
SOURCE_TABLE = "official_nhi_drug_payment_staging"
TARGET_TABLE = "prescription_nhi_drug_code_candidates"
EXPECTED_PREVIEW_ROWS = 235
VALID_REVIEW_STATUSES = {"auto_accepted", "rejected", "needs_review", "pending"}
VALID_JOIN_STATUSES = {"matched", "corrected_matched", "no_match", "false_positive"}

PREVIEW_FIELDS = [
    "source_photo",
    "source_csv",
    "source_photo_page_or_index",
    "source_row_number",
    "source_column",
    "source_match_index",
    "source_match_start",
    "source_match_end",
    "raw_nhi_drug_code",
    "normalized_nhi_drug_code",
    "corrected_nhi_drug_code",
    "effective_nhi_drug_code",
    "correction_method",
    "official_join_status",
    "official_match_count",
    "official_source_table",
    "official_normalized_drug_code",
    "official_drug_name_zh",
    "official_drug_name_en",
    "official_ingredient",
    "official_atc_code",
    "nearby_text",
    "raw_drug_name_text",
    "raw_dosage_text",
    "raw_frequency_text",
    "raw_days_text",
    "extraction_method",
    "confidence",
    "review_status",
    "review_decision",
    "reviewer",
    "reviewed_at",
    "review_note",
    "import_batch_id",
    "imported_at",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Input CSV not found: {path}")
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        os.environ.setdefault(key, value)


def normalize_database_url(url: str) -> str:
    if url.startswith("postgresql+psycopg://"):
        return "postgresql://" + url[len("postgresql+psycopg://"):]
    if url.startswith("postgresql+psycopg2://"):
        return "postgresql://" + url[len("postgresql+psycopg2://"):]
    return url


def database_url() -> str:
    load_env_file(ROOT / ".env")
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    normalized = normalize_database_url(url)
    parsed = urlparse(normalized)
    if not (
        parsed.scheme == "postgresql"
        and parsed.hostname in {"localhost", "127.0.0.1"}
        and parsed.port == 5432
        and parsed.path.lstrip("/") == "dispatch_db"
    ):
        raise RuntimeError("Refusing to apply: DATABASE_URL is not localhost:5432/dispatch_db")
    return normalized


def clean(value: Optional[str]) -> str:
    return (value or "").strip()


def split_first(value: str) -> str:
    return clean(value).split(";", 1)[0].strip()


def first_nonempty(*values: str) -> str:
    for value in values:
        if clean(value):
            return clean(value)
    return ""


def build_cleaning_lookup(cleaning_rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    lookup: dict[str, dict[str, str]] = {}
    for row in cleaning_rows:
        normalized = clean(row.get("normalized_nhi_drug_code"))
        raw = split_first(row.get("raw_nhi_drug_code", ""))
        if normalized:
            lookup[normalized] = row
        if raw:
            lookup.setdefault(raw, row)
    return lookup


def map_review(row: dict[str, str]) -> dict[str, str]:
    classification = clean(row.get("classification"))
    current_join_status = clean(row.get("current_join_status"))
    corrected_join_status = clean(row.get("corrected_join_status"))
    normalized = clean(row.get("normalized_nhi_drug_code"))
    corrected = clean(row.get("proposed_corrected_code"))

    if current_join_status in {"matched", "official_match"} or classification == "official_match":
        return {
            "effective_nhi_drug_code": normalized,
            "corrected_nhi_drug_code": "",
            "correction_method": "none",
            "official_join_status": "matched",
            "review_status": "auto_accepted",
            "review_decision": "approve",
            "confidence": "high",
        }
    if corrected_join_status == "matched":
        return {
            "effective_nhi_drug_code": corrected,
            "corrected_nhi_drug_code": corrected,
            "correction_method": "ocr_confusion_rule",
            "official_join_status": "corrected_matched",
            "review_status": "auto_accepted",
            "review_decision": "approve",
            "confidence": "medium",
        }
    if classification == "false_positive_word":
        return {
            "effective_nhi_drug_code": "",
            "corrected_nhi_drug_code": "",
            "correction_method": "not_applicable",
            "official_join_status": "false_positive",
            "review_status": "rejected",
            "review_decision": "reject",
            "confidence": "low",
        }
    return {
        "effective_nhi_drug_code": "",
        "corrected_nhi_drug_code": "",
        "correction_method": "none",
        "official_join_status": "no_match",
        "review_status": "needs_review",
        "review_decision": "needs_more_source",
        "confidence": "low",
    }


def build_preview(
    regex_rows: list[dict[str, str]],
    cleaning_rows: list[dict[str, str]],
    import_batch_id: str,
    imported_at: str,
) -> tuple[list[dict[str, str]], dict[str, int]]:
    cleaning_lookup = build_cleaning_lookup(cleaning_rows)
    preview: list[dict[str, str]] = []
    missing_cleaning = 0
    missing_source_photo = 0
    missing_source_row_number = 0
    missing_source_column = 0
    missing_match_start = 0
    missing_match_end = 0
    match_index_counts: Counter[tuple[str, str, str, str], int] = Counter()

    for occurrence in regex_rows:
        normalized = clean(occurrence.get("normalized_nhi_drug_code"))
        raw_code = clean(occurrence.get("raw_nhi_drug_code"))
        cleaning = first_nonempty(normalized, raw_code)
        cleaning_row = cleaning_lookup.get(cleaning)
        if cleaning_row is None and raw_code:
            cleaning_row = cleaning_lookup.get(raw_code)
        if cleaning_row is None:
            missing_cleaning += 1
            cleaning_row = {
                "normalized_nhi_drug_code": normalized,
                "raw_nhi_drug_code": raw_code,
                "classification": "needs_manual_review",
                "current_join_status": "unmatched",
                "corrected_join_status": "unmatched",
                "reason": "no matching cleaning candidate row found",
            }

        mapping = map_review(cleaning_row)
        official_status = mapping["official_join_status"]
        official_match_count = "1" if official_status in {"matched", "corrected_matched"} else "0"
        official_code = mapping["effective_nhi_drug_code"] if official_status in {"matched", "corrected_matched"} else ""
        source_photo = clean(occurrence.get("source_photo"))
        source_csv = clean(occurrence.get("source_csv"))
        source_row_number = clean(occurrence.get("source_row_number"))
        source_column = clean(occurrence.get("source_column"))
        match_key = (source_csv, source_row_number, source_column, raw_code)
        match_index_counts[match_key] += 1
        source_match_index = str(match_index_counts[match_key])
        source_match_start = clean(occurrence.get("source_match_start") or occurrence.get("match_start"))
        source_match_end = clean(occurrence.get("source_match_end") or occurrence.get("match_end"))
        if not source_photo:
            missing_source_photo += 1
        if not source_row_number:
            missing_source_row_number += 1
        if not source_column:
            missing_source_column += 1
        if not source_match_start:
            missing_match_start += 1
        if not source_match_end:
            missing_match_end += 1

        preview.append({
            "source_photo": source_photo,
            "source_csv": source_csv,
            "source_photo_page_or_index": "",
            "source_row_number": source_row_number,
            "source_column": source_column,
            "source_match_index": source_match_index,
            "source_match_start": source_match_start,
            "source_match_end": source_match_end,
            "raw_nhi_drug_code": raw_code,
            "normalized_nhi_drug_code": normalized,
            "corrected_nhi_drug_code": mapping["corrected_nhi_drug_code"],
            "effective_nhi_drug_code": mapping["effective_nhi_drug_code"],
            "correction_method": mapping["correction_method"],
            "official_join_status": official_status,
            "official_match_count": official_match_count,
            "official_source_table": SOURCE_TABLE if official_status in {"matched", "corrected_matched"} else "",
            "official_normalized_drug_code": official_code,
            "official_drug_name_zh": clean(cleaning_row.get("official_drug_name_zh")),
            "official_drug_name_en": clean(cleaning_row.get("official_drug_name_en")),
            "official_ingredient": clean(cleaning_row.get("official_ingredient")),
            "official_atc_code": "",
            "nearby_text": clean(occurrence.get("nearby_text")),
            "raw_drug_name_text": "",
            "raw_dosage_text": "",
            "raw_frequency_text": "",
            "raw_days_text": "",
            "extraction_method": clean(occurrence.get("extraction_method")) or "regex_existing_ocr_csv",
            "confidence": mapping["confidence"],
            "review_status": mapping["review_status"],
            "review_decision": mapping["review_decision"],
            "reviewer": "",
            "reviewed_at": "",
            "review_note": clean(cleaning_row.get("reason")),
            "import_batch_id": import_batch_id,
            "imported_at": imported_at,
        })

    diagnostics = {
        "missing_cleaning": missing_cleaning,
        "missing_source_photo": missing_source_photo,
        "missing_source_row_number": missing_source_row_number,
        "missing_source_column": missing_source_column,
        "missing_match_start": missing_match_start,
        "missing_match_end": missing_match_end,
    }
    return preview, diagnostics


def write_preview(preview: list[dict[str, str]]) -> None:
    with PREVIEW_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=PREVIEW_FIELDS)
        writer.writeheader()
        writer.writerows(preview)


def markdown_table_row(values: list[str]) -> str:
    cleaned = [str(value).replace("|", "/").replace("\n", " ") for value in values]
    return "| " + " | ".join(cleaned) + " |"


def duplicate_stats(rows: list[dict[str, str]], fields: list[str]) -> tuple[int, int]:
    counts = Counter(tuple(row.get(field, "") for field in fields) for row in rows)
    duplicate_groups = sum(1 for count in counts.values() if count > 1)
    duplicate_extra_rows = sum(count - 1 for count in counts.values() if count > 1)
    return duplicate_groups, duplicate_extra_rows


def validate_preview_rows(rows: list[dict[str, str]]) -> str:
    if len(rows) != EXPECTED_PREVIEW_ROWS:
        raise RuntimeError(f"Expected {EXPECTED_PREVIEW_ROWS} preview rows, got {len(rows)}")

    required = ["source_csv", "source_photo", "source_row_number", "source_column", "source_match_index"]
    for field in required:
        missing = sum(not clean(row.get(field)) for row in rows)
        if missing:
            raise RuntimeError(f"Preview has {missing} rows missing {field}")

    duplicate_groups, duplicate_extra_rows = duplicate_stats(rows, [
        "source_csv",
        "source_row_number",
        "source_column",
        "raw_nhi_drug_code",
        "source_match_index",
        "import_batch_id",
    ])
    if duplicate_groups:
        raise RuntimeError(
            "Preview source occurrence unique check failed: "
            f"{duplicate_groups} duplicate groups, {duplicate_extra_rows} extra rows"
        )

    invalid_review = sorted({row.get("review_status", "") for row in rows} - VALID_REVIEW_STATUSES)
    if invalid_review:
        raise RuntimeError(f"Invalid review_status values: {invalid_review}")
    invalid_join = sorted({row.get("official_join_status", "") for row in rows} - VALID_JOIN_STATUSES)
    if invalid_join:
        raise RuntimeError(f"Invalid official_join_status values: {invalid_join}")

    batch_ids = {clean(row.get("import_batch_id")) for row in rows if clean(row.get("import_batch_id"))}
    if len(batch_ids) != 1:
        raise RuntimeError(f"Expected exactly one import_batch_id, got {sorted(batch_ids)}")
    return next(iter(batch_ids))


def nullable_text(value: Optional[str]) -> Optional[str]:
    value = clean(value)
    return value or None


def nullable_int(value: Optional[str]) -> Optional[int]:
    value = clean(value)
    if not value:
        return None
    return int(value)


def row_to_insert_values(row: dict[str, str]) -> tuple[object, ...]:
    return (
        row["source_photo"],
        row["source_csv"],
        nullable_text(row.get("source_photo_page_or_index")),
        int(row["source_row_number"]),
        row["source_column"],
        int(row["source_match_index"]),
        nullable_int(row.get("source_match_start")),
        nullable_int(row.get("source_match_end")),
        row["raw_nhi_drug_code"],
        row["normalized_nhi_drug_code"],
        nullable_text(row.get("corrected_nhi_drug_code")),
        nullable_text(row.get("effective_nhi_drug_code")),
        row["correction_method"],
        row["official_join_status"],
        int(row["official_match_count"]),
        nullable_text(row.get("official_source_table")),
        nullable_text(row.get("official_normalized_drug_code")),
        nullable_text(row.get("official_drug_name_zh")),
        nullable_text(row.get("official_drug_name_en")),
        nullable_text(row.get("official_ingredient")),
        nullable_text(row.get("official_atc_code")),
        nullable_text(row.get("nearby_text")),
        nullable_text(row.get("raw_drug_name_text")),
        nullable_text(row.get("raw_dosage_text")),
        nullable_text(row.get("raw_frequency_text")),
        nullable_text(row.get("raw_days_text")),
        row["extraction_method"],
        row["confidence"],
        row["review_status"],
        nullable_text(row.get("review_decision")),
        nullable_text(row.get("reviewer")),
        nullable_text(row.get("reviewed_at")),
        nullable_text(row.get("review_note")),
        row["import_batch_id"],
        row["imported_at"],
    )


INSERT_COLUMNS = [
    "source_photo",
    "source_csv",
    "source_photo_page_or_index",
    "source_row_number",
    "source_column",
    "source_match_index",
    "source_match_start",
    "source_match_end",
    "raw_nhi_drug_code",
    "normalized_nhi_drug_code",
    "corrected_nhi_drug_code",
    "effective_nhi_drug_code",
    "correction_method",
    "official_join_status",
    "official_match_count",
    "official_source_table",
    "official_normalized_drug_code",
    "official_drug_name_zh",
    "official_drug_name_en",
    "official_ingredient",
    "official_atc_code",
    "nearby_text",
    "raw_drug_name_text",
    "raw_dosage_text",
    "raw_frequency_text",
    "raw_days_text",
    "extraction_method",
    "confidence",
    "review_status",
    "review_decision",
    "reviewer",
    "reviewed_at",
    "review_note",
    "import_batch_id",
    "imported_at",
]


def table_count(cursor, table_name: str) -> int:
    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
    return int(cursor.fetchone()[0])


def write_apply_report(
    import_batch_id: str,
    inserted_rows: int,
    final_table_count: int,
    preview_rows: list[dict[str, str]],
    drug_items_before: int,
    drug_items_after: int,
    links_before: int,
    links_after: int,
) -> None:
    review_counts = Counter(row["review_status"] for row in preview_rows)
    join_counts = Counter(row["official_join_status"] for row in preview_rows)
    photo_counts = Counter(row["source_photo"] for row in preview_rows)
    lines = [
        "# Prescription NHI Drug Code Candidates Import Apply Report",
        "",
        "## 結果",
        "",
        f"- import_batch_id: `{import_batch_id}`",
        f"- inserted rows: {inserted_rows}",
        f"- final table row count: {final_table_count}",
        "",
        "## Review Status",
        "",
        "| review_status | count |",
        "|---|---:|",
    ]
    for key in ["auto_accepted", "rejected", "needs_review", "pending"]:
        lines.append(f"| {key} | {review_counts.get(key, 0)} |")
    lines.extend([
        "",
        "## Official Join Status",
        "",
        "| official_join_status | count |",
        "|---|---:|",
    ])
    for key in ["matched", "corrected_matched", "false_positive", "no_match"]:
        lines.append(f"| {key} | {join_counts.get(key, 0)} |")
    lines.extend([
        "",
        "## Source Photo Count",
        "",
        "| source_photo | count |",
        "|---|---:|",
    ])
    for source_photo, count in sorted(photo_counts.items()):
        lines.append(f"| {source_photo} | {count} |")
    lines.extend([
        "",
        "## 正式表確認",
        "",
        f"- drug_items count before / after: {drug_items_before} / {drug_items_after}",
        f"- drug_diagnosis_links count before / after: {links_before} / {links_after}",
        "- 未修改 drug_items。",
        "- 未修改 drug_diagnosis_links。",
        "- 未修改 official staging、drug_item_official_code_mappings、diagnosis tables。",
    ])
    APPLY_REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_report(
    regex_rows: list[dict[str, str]],
    cleaning_rows: list[dict[str, str]],
    preview: list[dict[str, str]],
    diagnostics: dict[str, int],
    import_batch_id: str,
) -> None:
    review_counts = Counter(row["review_status"] for row in preview)
    join_counts = Counter(row["official_join_status"] for row in preview)
    photo_counts = Counter(row["source_photo"] or "(missing)" for row in preview)
    unique_codes = {clean(row.get("normalized_nhi_drug_code")) for row in cleaning_rows if clean(row.get("normalized_nhi_drug_code"))}
    occurrence_unique_codes = {clean(row.get("normalized_nhi_drug_code")) for row in regex_rows if clean(row.get("normalized_nhi_drug_code"))}
    old_duplicate_groups, old_duplicate_extra_rows = duplicate_stats(preview, [
        "source_csv",
        "source_row_number",
        "source_column",
        "raw_nhi_drug_code",
        "import_batch_id",
    ])
    new_duplicate_groups, new_duplicate_extra_rows = duplicate_stats(preview, [
        "source_csv",
        "source_row_number",
        "source_column",
        "raw_nhi_drug_code",
        "source_match_index",
        "import_batch_id",
    ])

    lines = [
        "# Prescription NHI Drug Code Candidates Import Dry-run Report",
        "",
        "## 本階段目的",
        "",
        "本報告把 regex occurrence-level candidates 合併 cleaning candidates，轉成 `prescription_nhi_drug_code_candidates` staging 欄位 preview。預設 dry-run 不連 DB、不建立 table、不寫 DB。",
        "",
        "## Input",
        "",
        f"- regex occurrence CSV: `{REGEX_CSV}`",
        f"- cleaning unique-code CSV: `{CLEANING_CSV}`",
        f"- regex occurrence rows: {len(regex_rows)}",
        f"- unique code rows: {len(cleaning_rows)}",
        f"- regex unique normalized codes: {len(occurrence_unique_codes)}",
        f"- cleaning unique normalized codes: {len(unique_codes)}",
        f"- preview occurrence rows: {len(preview)}",
        f"- import_batch_id: `{import_batch_id}`",
        "",
        "## Source Occurrence Unique 檢查",
        "",
        "| unique key | duplicate groups | extra duplicate rows |",
        "|---|---:|---:|",
        f"| 舊 key：source_csv + source_row_number + source_column + raw_nhi_drug_code + import_batch_id | {old_duplicate_groups} | {old_duplicate_extra_rows} |",
        f"| 新 key：source_csv + source_row_number + source_column + raw_nhi_drug_code + source_match_index + import_batch_id | {new_duplicate_groups} | {new_duplicate_extra_rows} |",
        "",
        "修正方式：原 regex candidates 沒有 match_start / match_end，因此 dry-run 在同一 source_csv + source_row_number + source_column + raw_nhi_drug_code 群組內依出現順序產生 `source_match_index`，從 1 開始。",
        "",
        "## Review Status 統計（occurrence-level）",
        "",
        "| review_status | occurrence_count |",
        "|---|---:|",
    ]
    for key in ["auto_accepted", "rejected", "needs_review", "pending"]:
        lines.append(f"| {key} | {review_counts.get(key, 0)} |")
    lines.extend([
        "",
        "## Official Join Status 統計（occurrence-level）",
        "",
        "| official_join_status | occurrence_count |",
        "|---|---:|",
    ])
    for key in ["matched", "corrected_matched", "false_positive", "no_match"]:
        lines.append(f"| {key} | {join_counts.get(key, 0)} |")
    lines.extend([
        "",
        "## 每張照片 occurrence count",
        "",
        "| source_photo | occurrence_count |",
        "|---|---:|",
    ])
    for source_photo, count in sorted(photo_counts.items()):
        lines.append(f"| {source_photo} | {count} |")
    lines.extend([
        "",
        "## 欄位完整性",
        "",
        f"- missing source_photo: {diagnostics['missing_source_photo']}",
        f"- missing source_row_number: {diagnostics['missing_source_row_number']}",
        f"- missing source_column: {diagnostics['missing_source_column']}",
        f"- missing source_match_start: {diagnostics['missing_match_start']}",
        f"- missing source_match_end: {diagnostics['missing_match_end']}",
        f"- missing cleaning lookup: {diagnostics['missing_cleaning']}",
        "- source_photo_page_or_index：原 OCR CSV 未提供，preview 先留空。",
        "- source_match_start / source_match_end：原 regex candidates 未保存文字位置，preview 先留空；目前以 source_match_index 解決同列同欄同碼重複問題。",
        "- raw_dosage_text / raw_frequency_text / raw_days_text：原 regex candidates 未拆出結構化欄位，preview 先留空。",
        "- official_atc_code：cleaning candidates 未輸出 ATC，preview 先留空。",
        "",
        "## 前 20 筆 Preview",
        "",
        "| photo | row | column | match_index | raw | normalized | corrected | effective | join_status | review_status | official zh | official en |",
        "|---|---:|---|---:|---|---|---|---|---|---|---|---|",
    ])
    for row in preview[:20]:
        lines.append(markdown_table_row([
            row["source_photo"],
            row["source_row_number"],
            row["source_column"],
            row["source_match_index"],
            row["raw_nhi_drug_code"],
            row["normalized_nhi_drug_code"],
            row["corrected_nhi_drug_code"],
            row["effective_nhi_drug_code"],
            row["official_join_status"],
            row["review_status"],
            row["official_drug_name_zh"],
            row["official_drug_name_en"],
        ]))
    lines.extend([
        "",
        "## 不寫 DB 說明",
        "",
        "本輪 dry-run 沒有連線資料庫、沒有建立 table、沒有 INSERT/UPDATE/DELETE/TRUNCATE。`--apply` 需明確指定才會執行。",
        "",
        "## 下一步 apply 前檢查清單",
        "",
        "1. 確認 occurrence-level source unique 欄位可滿足 schema：source_csv/source_row_number/source_column/raw_nhi_drug_code/source_match_index/import_batch_id。",
        "2. 對 `auto_accepted` 抽樣確認 raw OCR 值、corrected 值與 official NHI snapshot 是否合理。",
        "3. 對 `needs_review` 先人工確認是否為 OCR 誤讀或舊碼。",
        "4. 做 DB preflight：確認 `prescription_nhi_drug_code_candidates` 不存在或 schema 相容。",
        "5. apply 前再檢查 official NHI staging row count 與 source version。",
    ])
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_dry_run() -> None:
    regex_rows = read_csv(REGEX_CSV)
    cleaning_rows = read_csv(CLEANING_CSV)
    imported_at = datetime.now().replace(microsecond=0).isoformat()
    import_batch_id = "prescription_nhi_occurrence_" + datetime.now().strftime("%Y%m%d_%H%M%S")
    preview, diagnostics = build_preview(regex_rows, cleaning_rows, import_batch_id, imported_at)
    write_preview(preview)
    write_report(regex_rows, cleaning_rows, preview, diagnostics, import_batch_id)
    review_counts = Counter(row["review_status"] for row in preview)
    join_counts = Counter(row["official_join_status"] for row in preview)
    print(f"regex_occurrence_rows={len(regex_rows)}")
    print(f"unique_code_rows={len(cleaning_rows)}")
    print(f"preview_occurrence_rows={len(preview)}")
    print("review_counts=" + ",".join(f"{k}:{v}" for k, v in sorted(review_counts.items())))
    print("join_counts=" + ",".join(f"{k}:{v}" for k, v in sorted(join_counts.items())))
    print("diagnostics=" + ",".join(f"{k}:{v}" for k, v in sorted(diagnostics.items())))
    print(f"wrote={PREVIEW_CSV}")
    print(f"wrote={REPORT_MD}")


def run_apply() -> None:
    import psycopg2
    from psycopg2.extras import execute_values

    preview_rows = read_csv(PREVIEW_CSV)
    import_batch_id = validate_preview_rows(preview_rows)
    values = [row_to_insert_values(row) for row in preview_rows]
    url = database_url()
    create_sql = CREATE_SQL.read_text(encoding="utf-8")
    insert_sql = f"""
        INSERT INTO {TARGET_TABLE} ({", ".join(INSERT_COLUMNS)})
        VALUES %s
    """

    conn = psycopg2.connect(url)
    conn.autocommit = False
    try:
        with conn.cursor() as cur:
            cur.execute(create_sql)
            cur.execute(
                f"SELECT COUNT(*) FROM {TARGET_TABLE} WHERE import_batch_id = %s",
                (import_batch_id,),
            )
            existing_batch_rows = int(cur.fetchone()[0])
            if existing_batch_rows:
                raise RuntimeError(
                    f"import_batch_id already exists in {TARGET_TABLE}: "
                    f"{import_batch_id} ({existing_batch_rows} rows)"
                )

            drug_items_before = table_count(cur, "drug_items")
            links_before = table_count(cur, "drug_diagnosis_links")
            execute_values(cur, insert_sql, values, page_size=1000)
            final_table_count = table_count(cur, TARGET_TABLE)
            drug_items_after = table_count(cur, "drug_items")
            links_after = table_count(cur, "drug_diagnosis_links")

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    write_apply_report(
        import_batch_id=import_batch_id,
        inserted_rows=len(values),
        final_table_count=final_table_count,
        preview_rows=preview_rows,
        drug_items_before=drug_items_before,
        drug_items_after=drug_items_after,
        links_before=links_before,
        links_after=links_after,
    )
    print(f"apply_ok=True")
    print(f"import_batch_id={import_batch_id}")
    print(f"inserted_rows={len(values)}")
    print(f"final_table_count={final_table_count}")
    print(f"drug_items_count={drug_items_before}/{drug_items_after}")
    print(f"drug_diagnosis_links_count={links_before}/{links_after}")
    print(f"wrote={APPLY_REPORT_MD}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="create staging table and import preview rows")
    args = parser.parse_args()
    if args.apply:
        run_apply()
        return 0
    run_dry_run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
