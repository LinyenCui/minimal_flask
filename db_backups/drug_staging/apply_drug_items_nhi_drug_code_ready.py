#!/usr/bin/env python3
"""Apply approved primary NHI drug codes to drug_items.

Default dry-run is file-only and does not connect to the database.
--apply updates only drug_items NHI code fields for ready_to_apply rows.
"""

from __future__ import annotations

import argparse
import csv
import os
from collections import Counter
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
DRUG_STAGING_DIR = ROOT / "db_backups" / "drug_staging"
INPUT_CSV = DRUG_STAGING_DIR / "drug_items_nhi_drug_code_update_dry_run_candidates.csv"
APPLY_REPORT = DRUG_STAGING_DIR / "00_drug_items_nhi_drug_code_ready_apply_report.md"
EXPECTED_READY_ROWS = 31


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'").strip('"'))


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


def read_rows() -> list[dict[str, str]]:
    with INPUT_CSV.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    ready = [
        row for row in rows
        if row.get("dry_run_status") == "ready_to_apply"
    ]
    if len(ready) != EXPECTED_READY_ROWS:
        raise RuntimeError(f"Expected {EXPECTED_READY_ROWS} ready rows, got {len(ready)}")
    duplicate_drug_ids = [
        drug_id for drug_id, count in Counter(row["drug_item_id"] for row in ready).items()
        if count > 1
    ]
    if duplicate_drug_ids:
        raise RuntimeError(f"Duplicate ready drug_item_id values: {duplicate_drug_ids}")
    return ready


def table_count(cursor, table_name: str) -> int:
    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
    return int(cursor.fetchone()[0])


def run_dry_run() -> None:
    rows = read_rows()
    print(f"input_csv={INPUT_CSV}")
    print(f"ready_rows={len(rows)}")
    print("drug_item_ids=" + ",".join(row["drug_item_id"] for row in rows))
    print("nhi_drug_codes=" + ",".join(row["proposed_nhi_drug_code"] for row in rows))
    print("dry_run_only=True")
    print("db_connected=False")


def write_apply_report(
    backup_table: str,
    rows: list[dict[str, str]],
    before_count: int,
    after_count: int,
    links_before: int,
    links_after: int,
) -> None:
    lines = [
        "# Drug Items NHI Drug Code Ready Apply Report",
        "",
        "## 結果",
        "",
        f"- backup table: `{backup_table}`",
        f"- updated rows: {len(rows)}",
        f"- drug_items count before / after: {before_count} / {after_count}",
        f"- drug_diagnosis_links count before / after: {links_before} / {links_after}",
        "",
        "## Updated Rows",
        "",
        "| drug_item_id | drug | nhi_drug_code | source | confidence |",
        "|---:|---|---|---|---|",
    ]
    for row in rows:
        drug = f"{row['current_generic_name']} / {row['current_brand_name']}"
        values = [
            row["drug_item_id"],
            drug,
            row["proposed_nhi_drug_code"],
            row["proposed_source"],
            row["proposed_confidence"],
        ]
        lines.append("| " + " | ".join(str(v).replace("|", "/") for v in values) + " |")
    lines.extend([
        "",
        "## 未修改項目",
        "",
        "- 未修改 generic_name / brand_name / aliases。",
        "- 未修改 drug_diagnosis_links。",
        "- 未修改 official staging。",
        "- drug_item 87 只處理人工確認的主碼 AC585341G0；AC58534100 未處理，保留到 mapping table review。",
    ])
    APPLY_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_apply() -> None:
    import psycopg2

    rows = read_rows()
    url = database_url()
    backup_table = "drug_items_nhi_drug_code_ready_backup_" + datetime.now().strftime("%Y%m%d_%H%M%S")
    verified_at = datetime.now().replace(microsecond=0).isoformat()
    conn = psycopg2.connect(url)
    conn.autocommit = False
    try:
        with conn.cursor() as cur:
            before_count = table_count(cur, "drug_items")
            links_before = table_count(cur, "drug_diagnosis_links")
            cur.execute(f"CREATE TABLE {backup_table} AS TABLE drug_items")
            cur.execute(f"SELECT COUNT(*) FROM {backup_table}")
            backup_count = int(cur.fetchone()[0])
            if backup_count != before_count:
                raise RuntimeError(f"Backup count mismatch: {backup_count} != {before_count}")

            for row in rows:
                drug_item_id = int(row["drug_item_id"])
                code = row["proposed_nhi_drug_code"]
                cur.execute(
                    """
                    SELECT id, generic_name, brand_name, nhi_drug_code
                    FROM drug_items
                    WHERE id = %s
                    FOR UPDATE
                    """,
                    (drug_item_id,),
                )
                current = cur.fetchone()
                if current is None:
                    raise RuntimeError(f"drug_items.id not found: {drug_item_id}")
                _, generic_name, brand_name, current_code = current
                if current_code is not None:
                    raise RuntimeError(f"drug_items.id {drug_item_id} already has nhi_drug_code")
                if generic_name != row["current_generic_name"] or brand_name != row["current_brand_name"]:
                    raise RuntimeError(f"drug_items.id {drug_item_id} generic/brand mismatch")
                cur.execute(
                    """
                    SELECT COUNT(*)
                    FROM official_nhi_drug_payment_staging
                    WHERE normalized_drug_code = %s
                    """,
                    (code,),
                )
                if int(cur.fetchone()[0]) == 0:
                    raise RuntimeError(f"NHI code not found in official staging: {code}")
                cur.execute(
                    """
                    UPDATE drug_items
                    SET nhi_drug_code = %s,
                        nhi_drug_code_source = %s,
                        nhi_drug_code_confidence = %s,
                        nhi_drug_code_verified_at = %s,
                        nhi_drug_code_note = %s
                    WHERE id = %s
                      AND nhi_drug_code IS NULL
                    """,
                    (
                        code,
                        row["proposed_source"],
                        row["proposed_confidence"],
                        verified_at,
                        f"From prescription OCR NHI code candidates; source_photos={row['source_photos']}; occurrence_count={row['occurrence_count']}",
                        drug_item_id,
                    ),
                )
                if cur.rowcount != 1:
                    raise RuntimeError(f"Update affected {cur.rowcount} rows for drug_items.id {drug_item_id}")

            after_count = table_count(cur, "drug_items")
            links_after = table_count(cur, "drug_diagnosis_links")
            if before_count != after_count:
                raise RuntimeError("drug_items count changed unexpectedly")
            if links_before != links_after:
                raise RuntimeError("drug_diagnosis_links count changed unexpectedly")

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    write_apply_report(backup_table, rows, before_count, after_count, links_before, links_after)
    print("apply_ok=True")
    print(f"backup_table={backup_table}")
    print(f"updated_rows={len(rows)}")
    print(f"drug_items_count={before_count}/{after_count}")
    print(f"drug_diagnosis_links_count={links_before}/{links_after}")
    print(f"wrote={APPLY_REPORT}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="apply the 30 ready NHI code updates")
    args = parser.parse_args()
    if args.apply:
        run_apply()
    else:
        run_dry_run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
