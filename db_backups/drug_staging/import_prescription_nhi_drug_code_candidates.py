#!/usr/bin/env python3
"""Build an occurrence-level dry-run preview for prescription NHI drug codes.

Default mode is read-only and does not connect to the database.
--apply is intentionally not implemented in this phase.
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[2]
DRUG_STAGING_DIR = ROOT / "db_backups" / "drug_staging"
REGEX_CSV = DRUG_STAGING_DIR / "prescription_nhi_drug_code_regex_candidates.csv"
CLEANING_CSV = DRUG_STAGING_DIR / "prescription_nhi_drug_code_cleaning_candidates.csv"
PREVIEW_CSV = DRUG_STAGING_DIR / "prescription_nhi_drug_code_candidates_import_preview.csv"
REPORT_MD = DRUG_STAGING_DIR / "00_prescription_nhi_drug_code_candidates_import_dry_run_report.md"
SOURCE_TABLE = "official_nhi_drug_payment_staging"

PREVIEW_FIELDS = [
    "source_photo",
    "source_csv",
    "source_photo_page_or_index",
    "source_row_number",
    "source_column",
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
        source_row_number = clean(occurrence.get("source_row_number"))
        source_column = clean(occurrence.get("source_column"))
        if not source_photo:
            missing_source_photo += 1
        if not source_row_number:
            missing_source_row_number += 1
        if not source_column:
            missing_source_column += 1

        preview.append({
            "source_photo": source_photo,
            "source_csv": clean(occurrence.get("source_csv")),
            "source_photo_page_or_index": "",
            "source_row_number": source_row_number,
            "source_column": source_column,
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
        f"- missing cleaning lookup: {diagnostics['missing_cleaning']}",
        "- source_photo_page_or_index：原 OCR CSV 未提供，preview 先留空。",
        "- raw_dosage_text / raw_frequency_text / raw_days_text：原 regex candidates 未拆出結構化欄位，preview 先留空。",
        "- official_atc_code：cleaning candidates 未輸出 ATC，preview 先留空。",
        "",
        "## 前 20 筆 Preview",
        "",
        "| photo | row | column | raw | normalized | corrected | effective | join_status | review_status | official zh | official en |",
        "|---|---:|---|---|---|---|---|---|---|---|---|",
    ])
    for row in preview[:20]:
        lines.append(markdown_table_row([
            row["source_photo"],
            row["source_row_number"],
            row["source_column"],
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
        "本輪沒有連線資料庫、沒有建立 table、沒有 INSERT/UPDATE/DELETE/TRUNCATE。`--apply` 尚未實作。",
        "",
        "## 下一步 apply 前檢查清單",
        "",
        "1. 確認 occurrence-level source unique 欄位可滿足 schema：source_csv/source_row_number/source_column/raw_nhi_drug_code/import_batch_id。",
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="not implemented in this phase")
    args = parser.parse_args()
    if args.apply:
        raise NotImplementedError("--apply is intentionally not implemented in this dry-run phase")
    run_dry_run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
