#!/usr/bin/env python3
"""Phase 4 single approved ICD-10 apply script.

Default mode is dry-run and does not connect/write. Use --apply to:
1. Re-validate the single approved row from phase_4_single_icd10_mapping_decision.csv.
2. Verify candidate ICD-10 N17.9 against official_icd10_cm_reference_staging.
3. Create a full diagnosis_codes backup table.
4. Update only diagnosis_codes.icd10_code for diagnosis_codes.id = 76.
5. Write an apply report.

Safety constraints:
- Does not modify name_zh, icd9_code, aliases, description, usage_note.
- Does not modify drug_diagnosis_links.
- Does not modify staging tables.
- Stops the batch if validation fails.
"""

from __future__ import annotations

import argparse
import csv
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:  # pragma: no cover
    psycopg2 = None
    RealDictCursor = None

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parents[1]
DECISION_CSV = BASE_DIR / "phase_4_single_icd10_mapping_decision.csv"
APPLY_REPORT = BASE_DIR / "00_phase_4_single_icd10_mapping_apply_report.md"
EXPECTED_ID = 76
EXPECTED_ICD9 = "5849"
EXPECTED_NAME_ZH = "急性腎衰竭"
EXPECTED_ICD10 = "N17.9"
ICD10_RE = re.compile(r"^[A-Z][0-9][0-9A-Z](?:\.[0-9A-Z]{1,4})?$")


@dataclass(frozen=True)
class DecisionRow:
    diagnosis_code_id: int
    current_icd9_code: str
    current_icd10_code: str
    current_name_zh: str
    candidate_icd10_code: str
    official_name_zh: str
    official_name_en: str
    use_flag: str
    reviewer_decision: str
    review_note: str


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


def read_decision() -> DecisionRow:
    with DECISION_CSV.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if len(rows) != 1:
        raise RuntimeError(f"Expected exactly 1 decision row, found {len(rows)}")
    row = rows[0]
    return DecisionRow(
        diagnosis_code_id=int((row.get("diagnosis_code_id") or "0").strip()),
        current_icd9_code=(row.get("current_icd9_code") or "").strip(),
        current_icd10_code=(row.get("current_icd10_code") or "").strip(),
        current_name_zh=(row.get("current_name_zh") or "").strip(),
        candidate_icd10_code=(row.get("candidate_icd10_code") or "").strip().upper(),
        official_name_zh=(row.get("official_name_zh") or "").strip(),
        official_name_en=(row.get("official_name_en") or "").strip(),
        use_flag=(row.get("use_flag") or "").strip(),
        reviewer_decision=(row.get("reviewer_decision") or "").strip(),
        review_note=(row.get("review_note") or "").strip(),
    )


def validate_decision_shape(decision: DecisionRow) -> list[str]:
    blocked: list[str] = []
    if decision.diagnosis_code_id != EXPECTED_ID:
        blocked.append(f"decision diagnosis_code_id must be {EXPECTED_ID}")
    if decision.current_icd9_code != EXPECTED_ICD9:
        blocked.append(f"decision current_icd9_code must be {EXPECTED_ICD9}")
    if decision.current_icd10_code:
        blocked.append("decision current_icd10_code must be blank")
    if decision.current_name_zh != EXPECTED_NAME_ZH:
        blocked.append(f"decision current_name_zh must be {EXPECTED_NAME_ZH}")
    if decision.candidate_icd10_code != EXPECTED_ICD10:
        blocked.append(f"decision candidate_icd10_code must be {EXPECTED_ICD10}")
    if decision.use_flag != "1":
        blocked.append("decision use_flag must be 1")
    if decision.reviewer_decision != "approve":
        blocked.append("decision reviewer_decision must be approve")
    if not ICD10_RE.match(decision.candidate_icd10_code):
        blocked.append("decision candidate_icd10_code has invalid format")
    return blocked


def connect():
    if psycopg2 is None:
        raise RuntimeError("缺少 psycopg2，無法連線資料庫。")
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("缺少 DATABASE_URL。")
    return psycopg2.connect(normalize_database_url(database_url))


def quote_identifier(identifier: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", identifier):
        raise ValueError(f"Unsafe identifier: {identifier}")
    return '"' + identifier + '"'


def backup_table_name(now: datetime | None = None) -> str:
    now = now or datetime.now()
    return f"diagnosis_codes_phase_4_single_icd10_apply_backup_{now:%Y%m%d_%H%M%S}"


def count_table(cursor, table_name: str) -> int:
    cursor.execute(f"SELECT COUNT(*) AS n FROM {quote_identifier(table_name)}")
    return int(cursor.fetchone()["n"])


def fetch_current(cursor):
    cursor.execute(
        """
        SELECT id, icd9_code, icd10_code, name_zh
        FROM diagnosis_codes
        WHERE id = %s
        """,
        (EXPECTED_ID,),
    )
    row = cursor.fetchone()
    return dict(row) if row else None


def fetch_official(cursor):
    cursor.execute(
        """
        SELECT icd10_code, official_name_zh, official_name_en, use_flag
        FROM official_icd10_cm_reference_staging
        WHERE icd10_code = %s
        """,
        (EXPECTED_ICD10,),
    )
    row = cursor.fetchone()
    return dict(row) if row else None


def validate_apply_state(decision: DecisionRow, current: dict | None, official: dict | None) -> list[str]:
    blocked = validate_decision_shape(decision)
    if current is None:
        blocked.append("diagnosis_codes.id=76 not found")
    else:
        if (current.get("icd10_code") or "").strip():
            blocked.append("diagnosis_codes.id=76 already has icd10_code; will not overwrite")
        if (current.get("icd9_code") or "").strip() != EXPECTED_ICD9:
            blocked.append("diagnosis_codes.id=76 icd9_code mismatch")
        if (current.get("name_zh") or "").strip() != EXPECTED_NAME_ZH:
            blocked.append("diagnosis_codes.id=76 name_zh mismatch")
    if official is None:
        blocked.append("official N17.9 not found")
    else:
        if (official.get("use_flag") or "").strip() != "1":
            blocked.append("official N17.9 use_flag is not 1")
        if (official.get("official_name_zh") or "").strip() != EXPECTED_NAME_ZH:
            blocked.append("official N17.9 name_zh mismatch")
    return blocked


def create_backup(cursor, table_name: str) -> None:
    cursor.execute(f"CREATE TABLE {quote_identifier(table_name)} AS TABLE diagnosis_codes")


def update_single_row(cursor, decision: DecisionRow):
    cursor.execute(
        """
        UPDATE diagnosis_codes
        SET icd10_code = %s
        WHERE id = %s
          AND (icd10_code IS NULL OR BTRIM(icd10_code) = '')
          AND icd9_code = %s
          AND name_zh = %s
        RETURNING id, icd9_code, icd10_code, name_zh
        """,
        (decision.candidate_icd10_code, EXPECTED_ID, EXPECTED_ICD9, EXPECTED_NAME_ZH),
    )
    row = cursor.fetchone()
    if row is None:
        raise RuntimeError("UPDATE affected no rows; rolling back")
    return dict(row)


def write_report(*, mode: str, backup_name: str | None, decision: DecisionRow, current_before: dict | None, official: dict | None, updated: dict | None, blocked: list[str], diagnosis_count_before: int | None, diagnosis_count_after: int | None, link_count_before: int | None, link_count_after: int | None) -> None:
    before_icd10 = (current_before or {}).get("icd10_code") or ""
    after_icd10 = (updated or {}).get("icd10_code") or before_icd10
    skipped_blocked = 1 if blocked else 0
    updated_id = str(updated["id"]) if updated else ""
    lines = [
        "# Phase 4 Single ICD-10 Mapping Apply Report",
        "",
        "## 執行模式",
        "",
        f"- mode: {mode}",
        "- 本腳本只允許更新 `diagnosis_codes.id=76` 的 `icd10_code`。",
        "- 不修改 `name_zh`、`icd9_code`、`aliases`、`description`、`usage_note`。",
        "- 不修改 `drug_diagnosis_links` 或 staging tables。",
        "",
        "## 摘要",
        "",
        "| 項目 | 值 |",
        "| --- | --- |",
        f"| backup table name | {backup_name or 'dry-run 未建立'} |",
        f"| updated id | {updated_id} |",
        f"| skipped / blocked | {skipped_blocked} |",
        f"| diagnosis_codes count before | {diagnosis_count_before if diagnosis_count_before is not None else ''} |",
        f"| diagnosis_codes count after | {diagnosis_count_after if diagnosis_count_after is not None else ''} |",
        f"| drug_diagnosis_links count before | {link_count_before if link_count_before is not None else ''} |",
        f"| drug_diagnosis_links count after | {link_count_after if link_count_after is not None else ''} |",
        "",
        "## before / after icd10_code",
        "",
        "| diagnosis_codes.id | name_zh | icd9_code | before icd10_code | after icd10_code | official_name_zh | official_name_en | use_flag | status | reason |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        f"| {EXPECTED_ID} | {EXPECTED_NAME_ZH} | {EXPECTED_ICD9} | {before_icd10} | {after_icd10} | {(official or {}).get('official_name_zh', '')} | {(official or {}).get('official_name_en', '')} | {(official or {}).get('use_flag', '')} | {'blocked' if blocked else 'ready_to_apply'} | {'; '.join(blocked) if blocked else 'ok'} |",
        "",
        "## 備註",
        "",
        "- 本報告由 apply 腳本產出。",
        "- 若 validation 失敗，apply 模式會整批停止並 rollback。",
        "- 本腳本不處理其他 needs_more_source 候選。",
    ]
    APPLY_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def dry_run(decision: DecisionRow) -> int:
    blocked = validate_decision_shape(decision)
    print("Phase 4 single ICD-10 mapping dry-run")
    print(f"Decision CSV: {DECISION_CSV}")
    print(f"diagnosis_code_id: {decision.diagnosis_code_id}")
    print(f"candidate_icd10_code: {decision.candidate_icd10_code}")
    print(f"reviewer_decision: {decision.reviewer_decision}")
    print(f"decision_status: {'ready_for_db_validation' if not blocked else 'blocked'}")
    if blocked:
        print("blocked:", "; ".join(blocked))
    print("No database connection and no database writes were performed. Use --apply to write after final confirmation.")
    return 0 if not blocked else 1


def apply(decision: DecisionRow) -> int:
    load_env()
    backup_name = backup_table_name()
    with connect() as conn, conn.cursor(cursor_factory=RealDictCursor) as cursor:
        diagnosis_count_before = count_table(cursor, "diagnosis_codes")
        link_count_before = count_table(cursor, "drug_diagnosis_links")
        current_before = fetch_current(cursor)
        official = fetch_official(cursor)
        blocked = validate_apply_state(decision, current_before, official)
        if blocked:
            write_report(
                mode="apply-blocked",
                backup_name=None,
                decision=decision,
                current_before=current_before,
                official=official,
                updated=None,
                blocked=blocked,
                diagnosis_count_before=diagnosis_count_before,
                diagnosis_count_after=diagnosis_count_before,
                link_count_before=link_count_before,
                link_count_after=link_count_before,
            )
            raise RuntimeError("驗證失敗，未建立備份表，未更新資料。")
        create_backup(cursor, backup_name)
        updated = update_single_row(cursor, decision)
        diagnosis_count_after = count_table(cursor, "diagnosis_codes")
        link_count_after = count_table(cursor, "drug_diagnosis_links")
        write_report(
            mode="apply",
            backup_name=backup_name,
            decision=decision,
            current_before=current_before,
            official=official,
            updated=updated,
            blocked=[],
            diagnosis_count_before=diagnosis_count_before,
            diagnosis_count_after=diagnosis_count_after,
            link_count_before=link_count_before,
            link_count_after=link_count_after,
        )
    print(f"Backup table: {backup_name}")
    print(f"Updated id: {EXPECTED_ID}")
    print(f"Report: {APPLY_REPORT}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply Phase 4 single ICD-10 mapping for diagnosis_codes.id=76")
    parser.add_argument("--apply", action="store_true", help="Create backup table and update diagnosis_codes.id=76 icd10_code")
    args = parser.parse_args()

    decision = read_decision()
    if args.apply:
        return apply(decision)
    return dry_run(decision)


if __name__ == "__main__":
    raise SystemExit(main())
