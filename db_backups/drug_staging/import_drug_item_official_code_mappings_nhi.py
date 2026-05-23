#!/usr/bin/env python3
"""Import NHI official-code mappings for drug_items.

Default mode is file-only dry-run and does not connect to the database.
Use --apply to create drug_item_official_code_mappings if needed and insert
the 31 ready NHI mappings from the dry-run CSV.
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
INPUT_CSV = DRUG_STAGING_DIR / "drug_item_official_code_mappings_nhi_from_main_dry_run.csv"
CREATE_SQL = DRUG_STAGING_DIR / "create_drug_item_official_code_mappings.sql"
APPLY_REPORT = DRUG_STAGING_DIR / "00_drug_item_official_code_mappings_nhi_apply_report.md"
TARGET_TABLE = "drug_item_official_code_mappings"
EXPECTED_ROWS = 31


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
        return "postgresql://" + url[len("postgresql+psycopg://") :]
    if url.startswith("postgresql+psycopg2://"):
        return "postgresql://" + url[len("postgresql+psycopg2://") :]
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

    ready_rows = [row for row in rows if row.get("ready_to_apply") == "true"]
    if len(ready_rows) != EXPECTED_ROWS:
        raise RuntimeError(f"Expected {EXPECTED_ROWS} ready rows, got {len(ready_rows)}")
    if len(rows) != EXPECTED_ROWS:
        raise RuntimeError(f"Expected input CSV to contain {EXPECTED_ROWS} rows, got {len(rows)}")

    duplicate_keys = [
        key
        for key, count in Counter(
            (
                row["drug_item_id"],
                row["code_type"],
                row["code_value"],
                row["official_source_version"],
            )
            for row in ready_rows
        ).items()
        if count > 1
    ]
    if duplicate_keys:
        raise RuntimeError(f"Duplicate mapping keys in input CSV: {duplicate_keys}")

    for row in ready_rows:
        if row.get("code_type") != "NHI":
            raise RuntimeError(f"Unexpected code_type for drug_item_id={row.get('drug_item_id')}")
        if row.get("match_method") != "prescription_nhi_code":
            raise RuntimeError(f"Unexpected match_method for drug_item_id={row.get('drug_item_id')}")
        if row.get("confidence") != "high":
            raise RuntimeError(f"Unexpected confidence for drug_item_id={row.get('drug_item_id')}")
        if row.get("review_status") != "auto_accepted":
            raise RuntimeError(f"Unexpected review_status for drug_item_id={row.get('drug_item_id')}")
        if row.get("review_decision") != "approve":
            raise RuntimeError(f"Unexpected review_decision for drug_item_id={row.get('drug_item_id')}")

    return ready_rows


def table_exists(cursor, table_name: str) -> bool:
    cursor.execute(
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = current_schema()
              AND table_name = %s
        )
        """,
        (table_name,),
    )
    return bool(cursor.fetchone()[0])


def table_count(cursor, table_name: str) -> int:
    cursor.execute(f'SELECT COUNT(*) FROM "{table_name}"')
    return int(cursor.fetchone()[0])


def run_dry_run() -> None:
    rows = read_rows()
    print(f"input_csv={INPUT_CSV}")
    print(f"ready_rows={len(rows)}")
    print("drug_item_ids=" + ",".join(row["drug_item_id"] for row in rows))
    print("code_values=" + ",".join(row["code_value"] for row in rows))
    print("code_type_distribution=" + str(dict(Counter(row["code_type"] for row in rows))))
    print("review_status_distribution=" + str(dict(Counter(row["review_status"] for row in rows))))
    print("dry_run_only=True")
    print("db_connected=False")


def write_apply_report(
    *,
    import_batch_id: str,
    inserted_rows: int,
    final_table_count: int,
    code_type_counts: dict[str, int],
    review_status_counts: dict[str, int],
    drug_items_before: int,
    drug_items_after: int,
    links_before: int,
    links_after: int,
) -> None:
    lines = [
        "# Drug Item Official Code Mappings NHI Apply Report",
        "",
        "## 結果",
        "",
        f"- import_batch_id: `{import_batch_id}`",
        f"- inserted rows: {inserted_rows}",
        f"- final table row count: {final_table_count}",
        f"- drug_items count before / after: {drug_items_before} / {drug_items_after}",
        f"- drug_diagnosis_links count before / after: {links_before} / {links_after}",
        "",
        "## code_type distribution",
        "",
        "| code_type | count |",
        "|---|---:|",
    ]
    for key, count in sorted(code_type_counts.items()):
        lines.append(f"| {key} | {count} |")
    lines.extend(
        [
            "",
            "## review_status distribution",
            "",
            "| review_status | count |",
            "|---|---:|",
        ]
    )
    for key, count in sorted(review_status_counts.items()):
        lines.append(f"| {key} | {count} |")
    lines.extend(
        [
            "",
            "## 未修改項目",
            "",
            "- 未修改 drug_items。",
            "- 未修改 drug_diagnosis_links。",
            "- 未修改 official staging。",
            "- 未修改 prescription staging。",
            "- 未修改 diagnosis tables。",
        ]
    )
    APPLY_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_apply() -> None:
    import psycopg2

    rows = read_rows()
    url = database_url()
    import_batch_id = "drug_item_nhi_mapping_" + datetime.now().strftime("%Y%m%d_%H%M%S")
    conn = psycopg2.connect(url)
    conn.autocommit = False
    inserted_rows = 0
    try:
        with conn.cursor() as cur:
            drug_items_before = table_count(cur, "drug_items")
            links_before = table_count(cur, "drug_diagnosis_links")

            if not table_exists(cur, TARGET_TABLE):
                cur.execute(CREATE_SQL.read_text(encoding="utf-8"))

            for row in rows:
                drug_item_id = int(row["drug_item_id"])
                code_value = row["code_value"]
                official_source_version = row["official_source_version"]

                cur.execute(
                    """
                    SELECT id, nhi_drug_code
                    FROM drug_items
                    WHERE id = %s
                    """,
                    (drug_item_id,),
                )
                drug = cur.fetchone()
                if drug is None:
                    raise RuntimeError(f"drug_items.id not found: {drug_item_id}")
                if drug[1] != code_value:
                    raise RuntimeError(
                        f"drug_items.id {drug_item_id} nhi_drug_code mismatch: {drug[1]} != {code_value}"
                    )

                cur.execute(
                    """
                    SELECT id
                    FROM official_nhi_drug_payment_staging
                    WHERE normalized_drug_code = %s
                      AND source_version = %s
                    ORDER BY
                        effective_start_date DESC NULLS LAST,
                        effective_end_date DESC NULLS LAST,
                        id DESC
                    LIMIT 1
                    """,
                    (code_value, official_source_version),
                )
                official = cur.fetchone()
                if official is None:
                    raise RuntimeError(f"Official NHI row not found for {code_value}")
                official_source_id = int(official[0])

                cur.execute(
                    f"""
                    SELECT id
                    FROM {TARGET_TABLE}
                    WHERE drug_item_id = %s
                      AND code_type = %s
                      AND code_value = %s
                      AND official_source_version = %s
                    """,
                    (drug_item_id, row["code_type"], code_value, official_source_version),
                )
                if cur.fetchone() is not None:
                    raise RuntimeError(
                        f"Mapping already exists for drug_item_id={drug_item_id}, code={code_value}"
                    )

                cur.execute(
                    f"""
                    INSERT INTO {TARGET_TABLE} (
                        drug_item_id,
                        code_type,
                        code_value,
                        official_source_table,
                        official_source_id,
                        official_source_version,
                        match_method,
                        confidence,
                        review_status,
                        review_decision,
                        source_candidate_id,
                        note_text,
                        is_primary,
                        is_active
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NULL, %s, TRUE, TRUE)
                    """,
                    (
                        drug_item_id,
                        row["code_type"],
                        code_value,
                        row["official_source_table"],
                        official_source_id,
                        official_source_version,
                        row["match_method"],
                        row["confidence"],
                        row["review_status"],
                        row["review_decision"],
                        row["note_text"],
                    ),
                )
                inserted_rows += 1

            drug_items_after = table_count(cur, "drug_items")
            links_after = table_count(cur, "drug_diagnosis_links")
            final_table_count = table_count(cur, TARGET_TABLE)
            if drug_items_before != drug_items_after:
                raise RuntimeError("drug_items count changed unexpectedly")
            if links_before != links_after:
                raise RuntimeError("drug_diagnosis_links count changed unexpectedly")

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    code_type_counts = dict(Counter(row["code_type"] for row in rows))
    review_status_counts = dict(Counter(row["review_status"] for row in rows))
    write_apply_report(
        import_batch_id=import_batch_id,
        inserted_rows=inserted_rows,
        final_table_count=final_table_count,
        code_type_counts=code_type_counts,
        review_status_counts=review_status_counts,
        drug_items_before=drug_items_before,
        drug_items_after=drug_items_after,
        links_before=links_before,
        links_after=links_after,
    )
    print("apply_ok=True")
    print(f"import_batch_id={import_batch_id}")
    print(f"inserted_rows={inserted_rows}")
    print(f"final_table_count={final_table_count}")
    print(f"wrote={APPLY_REPORT}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="create table if needed and insert mappings")
    args = parser.parse_args()
    if args.apply:
        run_apply()
    else:
        run_dry_run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
