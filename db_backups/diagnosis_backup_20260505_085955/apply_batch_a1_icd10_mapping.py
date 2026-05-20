#!/usr/bin/env python3
"""Batch A1 approved ICD-10 apply script.

Default mode is dry-run and does not connect/write. Use --apply to:
1. Re-validate approved rows from batch_a1_icd10_mapping_decisions.csv.
2. Verify candidate ICD-10 codes against official_icd10_cm_reference_staging.
3. Create a full diagnosis_codes backup table.
4. Update only diagnosis_codes.icd10_code for the approved Batch A1 rows.
5. Write an apply report.

Safety constraints:
- Does not modify name_zh, icd9_code, aliases, description, usage_note.
- Does not modify drug_diagnosis_links.
- Does not modify staging tables or official_icd10_cm_reference_staging.
- Stops the whole batch if any row fails validation.
"""

from __future__ import annotations

import argparse
import csv
import os
import re
from collections import Counter
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
DECISIONS_CSV = BASE_DIR / "batch_a1_icd10_mapping_decisions.csv"
APPLY_REPORT = BASE_DIR / "00_batch_a1_icd10_mapping_apply_report.md"
EXPECTED = {
    8: ("7821", "皮疹", "R21"),
    13: ("2149", "脂肪瘤", "D17.9"),
    18: ("1104", "足癬", "B35.3"),
    19: ("1110", "汗斑", "B36.0"),
    20: ("7089", "蕁麻疹", "L50.9"),
    32: ("7231", "頸椎痛", "M54.2"),
    68: ("78841", "頻尿", "R35.0"),
}
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


def read_decisions() -> list[DecisionRow]:
    with DECISIONS_CSV.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    decisions: list[DecisionRow] = []
    for row in rows:
        if (row.get("reviewer_decision") or "").strip() != "approve":
            continue
        decisions.append(
            DecisionRow(
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
        )
    return decisions


def validate_decision_shape(decisions: list[DecisionRow]) -> list[str]:
    blocked: list[str] = []
    ids = [row.diagnosis_code_id for row in decisions]
    if ids != list(EXPECTED.keys()):
        blocked.append(f"approved ids must be {list(EXPECTED.keys())}, got {ids}")
    if len(decisions) != 7:
        blocked.append(f"expected 7 approved rows, got {len(decisions)}")
    if len(set(ids)) != len(ids):
        blocked.append("duplicate diagnosis_code_id in decisions")
    for row in decisions:
        expected = EXPECTED.get(row.diagnosis_code_id)
        if expected is None:
            blocked.append(f"unexpected diagnosis_code_id {row.diagnosis_code_id}")
            continue
        expected_icd9, expected_name, expected_icd10 = expected
        if row.current_icd9_code != expected_icd9:
            blocked.append(f"id {row.diagnosis_code_id} current_icd9_code mismatch")
        if row.current_icd10_code:
            blocked.append(f"id {row.diagnosis_code_id} current_icd10_code must be blank")
        if row.current_name_zh != expected_name:
            blocked.append(f"id {row.diagnosis_code_id} current_name_zh mismatch")
        if row.candidate_icd10_code != expected_icd10:
            blocked.append(f"id {row.diagnosis_code_id} candidate_icd10_code mismatch")
        if row.use_flag != "1":
            blocked.append(f"id {row.diagnosis_code_id} use_flag must be 1")
        if not ICD10_RE.match(row.candidate_icd10_code):
            blocked.append(f"id {row.diagnosis_code_id} candidate_icd10_code invalid format")
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
    return f"diagnosis_codes_batch_a1_icd10_apply_backup_{now:%Y%m%d_%H%M%S}"


def count_table(cursor, table_name: str) -> int:
    cursor.execute(f"SELECT COUNT(*) AS n FROM {quote_identifier(table_name)}")
    return int(cursor.fetchone()["n"])


def fetch_current_rows(cursor, ids: list[int]) -> dict[int, dict]:
    cursor.execute(
        """
        SELECT id, icd9_code, icd10_code, name_zh
        FROM diagnosis_codes
        WHERE id = ANY(%s)
        ORDER BY id
        """,
        (ids,),
    )
    return {row["id"]: dict(row) for row in cursor.fetchall()}


def fetch_official_rows(cursor, codes: list[str]) -> dict[str, dict]:
    cursor.execute(
        """
        SELECT icd10_code, official_name_zh, official_name_en, use_flag
        FROM official_icd10_cm_reference_staging
        WHERE icd10_code = ANY(%s)
        ORDER BY icd10_code
        """,
        (codes,),
    )
    return {row["icd10_code"]: dict(row) for row in cursor.fetchall()}


def validate_apply_state(decisions: list[DecisionRow], current_rows: dict[int, dict], official_rows: dict[str, dict]) -> dict[int, list[str]]:
    blocked_by_id: dict[int, list[str]] = {row.diagnosis_code_id: [] for row in decisions}
    shape_blocked = validate_decision_shape(decisions)
    if shape_blocked:
        blocked_by_id.setdefault(0, []).extend(shape_blocked)
    for row in decisions:
        current = current_rows.get(row.diagnosis_code_id)
        if current is None:
            blocked_by_id[row.diagnosis_code_id].append("diagnosis_codes row not found")
            continue
        if (current.get("icd10_code") or "").strip():
            blocked_by_id[row.diagnosis_code_id].append("existing icd10_code is not blank; will not overwrite")
        if (current.get("icd9_code") or "").strip() != row.current_icd9_code:
            blocked_by_id[row.diagnosis_code_id].append("icd9_code mismatch")
        if (current.get("name_zh") or "").strip() != row.current_name_zh:
            blocked_by_id[row.diagnosis_code_id].append("name_zh mismatch")
        official = official_rows.get(row.candidate_icd10_code)
        if official is None:
            blocked_by_id[row.diagnosis_code_id].append("candidate ICD-10 not found in official staging")
        else:
            if (official.get("use_flag") or "").strip() != "1":
                blocked_by_id[row.diagnosis_code_id].append("official use_flag is not 1")
    return {k: v for k, v in blocked_by_id.items() if v}


def create_backup(cursor, table_name: str) -> None:
    cursor.execute(f"CREATE TABLE {quote_identifier(table_name)} AS TABLE diagnosis_codes")


def update_rows(cursor, decisions: list[DecisionRow]) -> list[dict]:
    updated: list[dict] = []
    for row in decisions:
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
            (row.candidate_icd10_code, row.diagnosis_code_id, row.current_icd9_code, row.current_name_zh),
        )
        result = cursor.fetchone()
        if result is None:
            raise RuntimeError(f"UPDATE affected no rows for id {row.diagnosis_code_id}; rolling back")
        updated.append(dict(result))
    return updated


def write_report(*, mode: str, backup_name: str | None, decisions: list[DecisionRow], current_rows: dict[int, dict], official_rows: dict[str, dict], updated_rows: list[dict], blocked_by_id: dict[int, list[str]], diagnosis_count_before: int | None, diagnosis_count_after: int | None, link_count_before: int | None, link_count_after: int | None) -> None:
    updated_by_id = {row["id"]: row for row in updated_rows}
    lines = [
        "# Batch A1 ICD-10 Mapping Apply Report",
        "",
        "## 執行模式",
        "",
        f"- mode: {mode}",
        "- 本腳本只允許更新 Batch A1 7 筆 `diagnosis_codes.icd10_code`。",
        "- 不修改 `name_zh`、`icd9_code`、`aliases`、`description`、`usage_note`。",
        "- 不修改 `drug_diagnosis_links`、staging tables 或 `official_icd10_cm_reference_staging`。",
        "",
        "## 摘要",
        "",
        "| 項目 | 值 |",
        "| --- | --- |",
        f"| backup table name | {backup_name or 'dry-run 未建立'} |",
        f"| updated ids | {', '.join(str(row['id']) for row in updated_rows)} |",
        f"| skipped / blocked | {sum(len(v) for v in blocked_by_id.values())} |",
        f"| diagnosis_codes count before | {diagnosis_count_before if diagnosis_count_before is not None else ''} |",
        f"| diagnosis_codes count after | {diagnosis_count_after if diagnosis_count_after is not None else ''} |",
        f"| drug_diagnosis_links count before | {link_count_before if link_count_before is not None else ''} |",
        f"| drug_diagnosis_links count after | {link_count_after if link_count_after is not None else ''} |",
        "",
        "## before / after icd10_code",
        "",
        "| diagnosis_codes.id | name_zh | icd9_code | before icd10_code | after icd10_code | official_name_zh | official_name_en | use_flag | status | reason |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for decision in decisions:
        current = current_rows.get(decision.diagnosis_code_id, {})
        official = official_rows.get(decision.candidate_icd10_code, {})
        updated = updated_by_id.get(decision.diagnosis_code_id)
        blocked = blocked_by_id.get(decision.diagnosis_code_id, [])
        before_icd10 = current.get("icd10_code") or ""
        after_icd10 = updated.get("icd10_code") if updated else before_icd10
        status = "blocked" if blocked else "ready_to_apply"
        reason = "; ".join(blocked) if blocked else "ok"
        lines.append(
            f"| {decision.diagnosis_code_id} | {decision.current_name_zh} | {decision.current_icd9_code} | {before_icd10} | {after_icd10} | {official.get('official_name_zh', '')} | {official.get('official_name_en', '')} | {official.get('use_flag', '')} | {status} | {reason} |"
        )
    lines.extend([
        "",
        "## 備註",
        "",
        "- 本報告由 apply 腳本產出。",
        "- 若 validation 失敗，apply 模式會整批停止並 rollback。",
        "- 本腳本不處理 Batch A 其他 43 筆，也不處理 Batch B/C/D。",
    ])
    APPLY_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def dry_run(decisions: list[DecisionRow]) -> int:
    blocked = validate_decision_shape(decisions)
    print("Batch A1 ICD-10 mapping dry-run")
    print(f"Decision CSV: {DECISIONS_CSV}")
    print(f"Approved rows: {len(decisions)}")
    for row in decisions:
        print(f"{row.diagnosis_code_id}\t{row.current_name_zh}\t{row.current_icd9_code}\t{row.candidate_icd10_code}\t{row.reviewer_decision}")
    print(f"decision_status: {'ready_for_db_validation' if not blocked else 'blocked'}")
    if blocked:
        print("blocked:", "; ".join(blocked))
    print("No database connection and no database writes were performed. Use --apply to write after final confirmation.")
    return 0 if not blocked else 1


def apply(decisions: list[DecisionRow]) -> int:
    load_env()
    backup_name = backup_table_name()
    ids = [row.diagnosis_code_id for row in decisions]
    codes = [row.candidate_icd10_code for row in decisions]
    with connect() as conn, conn.cursor(cursor_factory=RealDictCursor) as cursor:
        diagnosis_count_before = count_table(cursor, "diagnosis_codes")
        link_count_before = count_table(cursor, "drug_diagnosis_links")
        current_rows = fetch_current_rows(cursor, ids)
        official_rows = fetch_official_rows(cursor, codes)
        blocked_by_id = validate_apply_state(decisions, current_rows, official_rows)
        if blocked_by_id:
            write_report(
                mode="apply-blocked",
                backup_name=None,
                decisions=decisions,
                current_rows=current_rows,
                official_rows=official_rows,
                updated_rows=[],
                blocked_by_id=blocked_by_id,
                diagnosis_count_before=diagnosis_count_before,
                diagnosis_count_after=diagnosis_count_before,
                link_count_before=link_count_before,
                link_count_after=link_count_before,
            )
            raise RuntimeError("驗證失敗，未建立備份表，未更新資料。")
        create_backup(cursor, backup_name)
        updated_rows = update_rows(cursor, decisions)
        diagnosis_count_after = count_table(cursor, "diagnosis_codes")
        link_count_after = count_table(cursor, "drug_diagnosis_links")
        write_report(
            mode="apply",
            backup_name=backup_name,
            decisions=decisions,
            current_rows=current_rows,
            official_rows=official_rows,
            updated_rows=updated_rows,
            blocked_by_id={},
            diagnosis_count_before=diagnosis_count_before,
            diagnosis_count_after=diagnosis_count_after,
            link_count_before=link_count_before,
            link_count_after=link_count_after,
        )
    print(f"Backup table: {backup_name}")
    print(f"Updated ids: {', '.join(str(row.diagnosis_code_id) for row in decisions)}")
    print(f"Report: {APPLY_REPORT}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply Batch A1 ICD-10 mappings")
    parser.add_argument("--apply", action="store_true", help="Create backup table and update Batch A1 diagnosis_codes.icd10_code")
    args = parser.parse_args()

    decisions = read_decisions()
    if args.apply:
        return apply(decisions)
    return dry_run(decisions)


if __name__ == "__main__":
    raise SystemExit(main())
