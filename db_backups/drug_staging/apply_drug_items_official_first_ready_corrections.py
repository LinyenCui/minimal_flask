#!/usr/bin/env python3
"""Apply official-first corrections for selected drug_items.

Default mode is dry-run and does not connect to the database.
Only --apply may create a backup table and update drug_items.
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

try:
    import psycopg2
except ImportError:  # pragma: no cover - handled at runtime
    psycopg2 = None

ROOT = Path(__file__).resolve().parents[2]
DECISIONS_CSV = ROOT / "db_backups" / "drug_staging" / "drug_items_official_first_ready_decisions.csv"
REPORT_PATH = ROOT / "db_backups" / "drug_staging" / "00_drug_items_official_first_ready_apply_report.md"
ALLOWED_IDS = {4, 10, 13, 96, 123, 150}
BLOCKED_IDS = {14, 17, 77}
ALLOWED_ACTIONS = {"correct_generic_name", "add_alias_only", "keep_current"}


@dataclass(frozen=True)
class Decision:
    drug_item_id: int
    current_generic_name: str
    current_brand_name: str
    proposed_generic_name: str
    proposed_brand_name: str
    action_type: str
    decision: str
    confidence: str
    official_source: str
    official_evidence: str
    has_drug_diagnosis_links: str
    risk_level: str
    ready_to_apply: str
    review_note: str


def normalize_database_url(url: str) -> str:
    if url.startswith("postgresql+psycopg://"):
        return "postgresql://" + url.split("://", 1)[1]
    if url.startswith("postgresql+psycopg2://"):
        return "postgresql://" + url.split("://", 1)[1]
    return url


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def load_decisions(path: Path = DECISIONS_CSV) -> list[Decision]:
    if not path.exists():
        raise FileNotFoundError(f"decisions CSV not found: {path}")
    decisions: list[Decision] = []
    with path.open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if row.get("ready_to_apply") != "yes":
                continue
            drug_item_id = int(row["drug_item_id"])
            decisions.append(
                Decision(
                    drug_item_id=drug_item_id,
                    current_generic_name=row.get("current_generic_name", ""),
                    current_brand_name=row.get("current_brand_name", ""),
                    proposed_generic_name=row.get("proposed_generic_name", ""),
                    proposed_brand_name=row.get("proposed_brand_name", ""),
                    action_type=row.get("action_type", ""),
                    decision=row.get("decision", ""),
                    confidence=row.get("confidence", ""),
                    official_source=row.get("official_source", ""),
                    official_evidence=row.get("official_evidence", ""),
                    has_drug_diagnosis_links=row.get("has_drug_diagnosis_links", ""),
                    risk_level=row.get("risk_level", ""),
                    ready_to_apply=row.get("ready_to_apply", ""),
                    review_note=row.get("review_note", ""),
                )
            )
    validate_decision_file(decisions)
    return decisions


def validate_decision_file(decisions: list[Decision]) -> None:
    ids = {d.drug_item_id for d in decisions}
    if ids != ALLOWED_IDS:
        raise ValueError(f"ready_to_apply ids must be exactly {sorted(ALLOWED_IDS)}, got {sorted(ids)}")
    if ids & BLOCKED_IDS:
        raise ValueError(f"blocked ids must not be processed: {sorted(ids & BLOCKED_IDS)}")
    bad_actions = sorted({d.action_type for d in decisions} - ALLOWED_ACTIONS)
    if bad_actions:
        raise ValueError(f"unsupported action_type: {bad_actions}")
    for d in decisions:
        if d.has_drug_diagnosis_links != "no":
            raise ValueError(f"drug_item_id {d.drug_item_id} has links in CSV; refusing")
        if d.ready_to_apply != "yes":
            raise ValueError(f"drug_item_id {d.drug_item_id} is not ready_to_apply")
        if d.action_type == "correct_generic_name" and not d.proposed_generic_name:
            raise ValueError(f"drug_item_id {d.drug_item_id} missing proposed_generic_name")


def print_dry_run(decisions: Iterable[Decision]) -> None:
    print("Dry-run only. No database connection will be opened.")
    print(f"Source CSV: {DECISIONS_CSV}")
    print("Planned rows:")
    for d in decisions:
        if d.action_type == "correct_generic_name":
            detail = f"generic_name: {d.current_generic_name!r} -> {d.proposed_generic_name!r}"
        elif d.action_type == "add_alias_only":
            detail = "aliases only; generic_name and brand_name unchanged"
        else:
            detail = "keep_current; no database write"
        print(f"- id={d.drug_item_id} action={d.action_type} {detail}")


def get_database_url() -> str:
    load_dotenv(ROOT / ".env")
    raw = os.getenv("DATABASE_URL")
    if not raw:
        raise RuntimeError("DATABASE_URL is not set")
    dsn = normalize_database_url(raw)
    parsed = urlparse(dsn)
    if parsed.hostname not in {"localhost", "127.0.0.1"}:
        raise RuntimeError("Refusing to apply: DATABASE_URL is not localhost")
    if parsed.port != 5432 or parsed.path.lstrip("/") != "dispatch_db":
        raise RuntimeError("Refusing to apply: DATABASE_URL is not localhost:5432/dispatch_db")
    return dsn


def validate_database_state(cur, decisions: list[Decision]) -> dict[int, dict[str, object]]:
    before: dict[int, dict[str, object]] = {}
    for d in decisions:
        cur.execute(
            """
            SELECT d.id, d.generic_name, d.brand_name, d.aliases, COUNT(l.id) AS link_count
            FROM drug_items d
            LEFT JOIN drug_diagnosis_links l ON l.drug_item_id = d.id
            WHERE d.id = %s
            GROUP BY d.id, d.generic_name, d.brand_name, d.aliases
            """,
            (d.drug_item_id,),
        )
        row = cur.fetchone()
        if row is None:
            raise RuntimeError(f"drug_items.id {d.drug_item_id} not found")
        _, generic_name, brand_name, aliases, link_count = row
        if generic_name != d.current_generic_name:
            raise RuntimeError(
                f"drug_items.id {d.drug_item_id} generic_name mismatch: "
                f"DB={generic_name!r}, CSV={d.current_generic_name!r}"
            )
        if brand_name != d.current_brand_name:
            raise RuntimeError(
                f"drug_items.id {d.drug_item_id} brand_name mismatch: "
                f"DB={brand_name!r}, CSV={d.current_brand_name!r}"
            )
        if link_count:
            raise RuntimeError(f"drug_items.id {d.drug_item_id} has drug_diagnosis_links; refusing")
        before[d.drug_item_id] = {
            "generic_name": generic_name,
            "brand_name": brand_name,
            "aliases": aliases or "",
            "link_count": link_count,
        }
    return before


def merge_aliases(existing: str, values: Iterable[str]) -> str:
    seen: set[str] = set()
    merged: list[str] = []
    for raw in [existing, *values]:
        for part in str(raw or "").replace("；", ";").split(";"):
            item = part.strip()
            if not item:
                continue
            key = item.lower()
            if key in seen:
                continue
            seen.add(key)
            merged.append(item)
    return "; ".join(merged)


def alias_values_for(decision: Decision) -> list[str]:
    values = [decision.current_generic_name]
    if decision.proposed_generic_name:
        values.append(decision.proposed_generic_name)
    if decision.current_brand_name:
        values.append(decision.current_brand_name)
    if decision.proposed_brand_name:
        values.append(decision.proposed_brand_name)
    return values


def apply_changes(cur, decisions: list[Decision], before: dict[int, dict[str, object]]) -> list[dict[str, object]]:
    changes: list[dict[str, object]] = []
    for d in decisions:
        current = before[d.drug_item_id]
        old_aliases = str(current["aliases"] or "")
        new_aliases = merge_aliases(old_aliases, alias_values_for(d))
        if d.action_type == "correct_generic_name":
            cur.execute(
                """
                UPDATE drug_items
                SET generic_name = %s,
                    aliases = %s,
                    updated_at = NOW()
                WHERE id = %s
                  AND generic_name = %s
                  AND brand_name = %s
                RETURNING id, generic_name, brand_name, aliases
                """,
                (d.proposed_generic_name, new_aliases, d.drug_item_id, d.current_generic_name, d.current_brand_name),
            )
        elif d.action_type == "add_alias_only":
            cur.execute(
                """
                UPDATE drug_items
                SET aliases = %s,
                    updated_at = NOW()
                WHERE id = %s
                  AND generic_name = %s
                  AND brand_name = %s
                RETURNING id, generic_name, brand_name, aliases
                """,
                (new_aliases, d.drug_item_id, d.current_generic_name, d.current_brand_name),
            )
        else:
            changes.append(
                {
                    "id": d.drug_item_id,
                    "action": d.action_type,
                    "old_generic_name": current["generic_name"],
                    "new_generic_name": current["generic_name"],
                    "old_aliases": old_aliases,
                    "new_aliases": old_aliases,
                    "status": "no_write",
                }
            )
            continue
        row = cur.fetchone()
        if row is None:
            raise RuntimeError(f"drug_items.id {d.drug_item_id} update affected no rows; aborting")
        _, new_generic_name, new_brand_name, returned_aliases = row
        changes.append(
            {
                "id": d.drug_item_id,
                "action": d.action_type,
                "old_generic_name": current["generic_name"],
                "new_generic_name": new_generic_name,
                "old_brand_name": current["brand_name"],
                "new_brand_name": new_brand_name,
                "old_aliases": old_aliases,
                "new_aliases": returned_aliases or "",
                "status": "updated",
            }
        )
    return changes


def write_report(
    backup_table: str,
    changes: list[dict[str, object]],
    before_counts: dict[str, int],
    after_counts: dict[str, int],
) -> None:
    lines = [
        "# Drug Items Official-first Ready Apply Report",
        "",
        "## Summary",
        "",
        f"- backup_table: `{backup_table}`",
        f"- updated_or_checked_ids: {', '.join(str(c['id']) for c in changes)}",
        f"- drug_items count before / after: {before_counts['drug_items']} / {after_counts['drug_items']}",
        f"- drug_diagnosis_links count before / after: {before_counts['drug_diagnosis_links']} / {after_counts['drug_diagnosis_links']}",
        "- modified tables: `drug_items` only",
        "- not modified: `drug_diagnosis_links`, official staging tables, diagnosis tables, id 14 / 17 / 77",
        "",
        "## Changes",
        "",
        "| id | action | old generic_name | new generic_name | brand_name changed | aliases after | status |",
        "|---:|---|---|---|---|---|---|",
    ]
    for c in changes:
        brand_changed = "yes" if c.get("old_brand_name") != c.get("new_brand_name") else "no"
        vals = [
            c["id"],
            c["action"],
            c.get("old_generic_name", ""),
            c.get("new_generic_name", ""),
            brand_changed,
            c.get("new_aliases", ""),
            c["status"],
        ]
        vals = [str(v).replace("|", "/").replace("\n", " ") for v in vals]
        lines.append("| " + " | ".join(vals) + " |")
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_apply(decisions: list[Decision]) -> None:
    if psycopg2 is None:
        raise RuntimeError("psycopg2 is required for --apply")
    dsn = get_database_url()
    backup_table = "drug_items_official_first_ready_backup_" + datetime.now().strftime("%Y%m%d_%H%M%S")
    conn = psycopg2.connect(dsn)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM drug_items")
            drug_items_before = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM drug_diagnosis_links")
            links_before = cur.fetchone()[0]
            before = validate_database_state(cur, decisions)
            cur.execute(f'CREATE TABLE "{backup_table}" AS TABLE drug_items')
            changes = apply_changes(cur, decisions, before)
            cur.execute("SELECT COUNT(*) FROM drug_items")
            drug_items_after = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM drug_diagnosis_links")
            links_after = cur.fetchone()[0]
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
    write_report(
        backup_table,
        changes,
        {"drug_items": drug_items_before, "drug_diagnosis_links": links_before},
        {"drug_items": drug_items_after, "drug_diagnosis_links": links_after},
    )
    print("Apply completed")
    print(f"backup_table={backup_table}")
    print(f"report={REPORT_PATH}")
    print("updated_ids=" + ",".join(str(c["id"]) for c in changes if c["status"] == "updated"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="write approved corrections to local DB")
    args = parser.parse_args()
    decisions = load_decisions()
    if not args.apply:
        print_dry_run(decisions)
        return 0
    run_apply(decisions)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
