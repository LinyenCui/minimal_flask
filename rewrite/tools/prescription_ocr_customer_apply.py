"""Approved-only Prescription OCR customer preview/apply adapter.

This module is the only formal-customer bridge for the existing OCR Review
LIFF.  Preview is SELECT-only.  Formal mutations delegate exclusively to the
existing customer services and never copy prescription identity markers into
customers or remarks.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import tempfile
import unicodedata
from datetime import date, datetime, timedelta, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from sqlalchemy import text

from rewrite.tools.base import ToolResult
from rewrite.tools import customer as customer_tools
from rewrite.tools import prescription_ocr_review as review_tools


FORMAL_REVIEW_ACTIONS = {"approve", "corrected"}
FORMAL_PLAN_STATUSES = {
    "ready_for_create",
    "ready_for_update",
    "already_exists",
    "needs_manual_confirmation",
    "blocked",
}
CUSTOMER_WRITABLE_FIELDS = {
    "name",
    "short_name",
    "birthday",
    "medical_record_no",
    "gender",
    "address",
    "category",
    "remarks",
}
HARD_EXCLUDED_FIELDS = {
    "patient_identity_markers",
    "patient_identity_raw",
    "contact_phone",
    "dm_care_no",
    "latitude",
    "longitude",
}
PREVIEW_EXPIRES_MINUTES = 10
PREVIEW_ID_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


class CustomerApplyError(RuntimeError):
    """Raised when an approved-only or customer safety gate fails."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CustomerApplyError(message)


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=_json_default)


def _json_default(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


def _json_safe(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def normalize_person_name(value: Any) -> str:
    """Match the normalization already used by the Prescription OCR pipeline."""
    normalized = unicodedata.normalize("NFKC", _clean(value))
    normalized = re.sub(r"[\s　:：|,，;；\[\]（）()]+", "", normalized)
    return normalized.strip()


def normalize_phone(value: Any) -> str:
    return re.sub(r"\D+", "", _clean(value))


def parse_date(value: Any) -> date | None:
    raw = _clean(value)
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise CustomerApplyError(f"birthday_invalid:{raw}") from exc


def _parse_json_object(value: Any, *, error_name: str) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    raw = _clean(value)
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CustomerApplyError(f"{error_name}_invalid_json") from exc
    _require(isinstance(parsed, dict), f"{error_name}_must_be_object")
    return parsed


def _read_csv(path: Path) -> list[dict[str, str]]:
    _require(path.is_file(), f"artifact_missing:{path}")
    with path.open("r", encoding="utf-8-sig", newline="") as file_obj:
        return list(csv.DictReader(file_obj))


def _queue_row(run_id: str, decision_id: str) -> tuple[Path, dict[str, str], dict[str, Any]]:
    path, _fieldnames, rows = review_tools._read_decision_queue(run_id)
    matches = [row for row in rows if _clean(row.get("decision_id")) == _clean(decision_id)]
    _require(len(matches) == 1, "customer_review_row_missing_or_duplicated")
    row = matches[0]
    _require(row.get("decision_type") == "customer", "review_row_is_not_customer")
    return path, row, review_tools._queue_revision(path)


def _action_row(run_id: str, source_image: str) -> dict[str, str]:
    run_dir = review_tools.decision_queue_path(run_id).parent.parent
    path = run_dir / "customer_matching" / "ocr_customer_liff_actions.csv"
    matches = [row for row in _read_csv(path) if _clean(row.get("source_image_filename")) == source_image]
    _require(len(matches) == 1, "customer_action_row_missing_or_duplicated")
    return matches[0]


def _approved_structured_values(row: dict[str, str]) -> tuple[dict[str, Any], dict[str, Any]]:
    review_action = _clean(row.get("review_decision"))
    _require(review_action in FORMAL_REVIEW_ACTIONS, "customer_review_not_approved_or_corrected")
    source = _parse_json_object(row.get("structured_fields"), error_name="structured_fields")

    if review_action == "corrected":
        corrected = _parse_json_object(
            row.get("structured_corrected_fields"),
            error_name="structured_corrected_fields",
        )
        _require(bool(corrected), "corrected_customer_structured_fields_required")
        # The Review backend persists this derived scope marker alongside the
        # user fields. Validate it, then remove it before reusing the input
        # validator (which intentionally accepts user-editable keys only).
        persisted_scope = _clean(corrected.get("patient_identity_scope"))
        _require(
            not persisted_scope or persisted_scope == "prescription_review_only",
            "corrected_customer_identity_scope_invalid",
        )
        corrected_input = dict(corrected)
        corrected_input.pop("patient_identity_scope", None)
        validated, error = review_tools._validate_customer_structured_correction(corrected_input)
        _require(not error, f"corrected_customer_invalid:{error}")
        _require(bool(validated), "corrected_customer_structured_fields_required")
        return validated, source

    approved = {
        "customer_name": _clean((source.get("name") or {}).get("normalized_value")),
        "short_name": _clean((source.get("short_name") or {}).get("normalized_value")),
        "birthday": _clean((source.get("birthday") or {}).get("normalized_value")),
        "medical_record_no": _clean((source.get("medical_record_no") or {}).get("normalized_value")),
        "gender": _clean((source.get("gender") or {}).get("normalized_value")),
        "patient_identity_markers": list(
            (source.get("patient_identity_markers") or {}).get("normalized_values") or []
        ),
    }
    validated, error = review_tools._validate_customer_structured_correction(approved)
    _require(not error, f"approved_customer_invalid:{error}")
    _require(bool(validated), "approved_customer_structured_fields_required")
    return validated, source


def load_reviewed_customer_candidate(*, run_id: str, decision_id: str) -> dict[str, Any]:
    """Load only persisted approve/corrected fields for one customer row."""
    queue_path, row, queue_revision = _queue_row(run_id, decision_id)
    reviewed, source = _approved_structured_values(row)
    review_action = _clean(row.get("review_decision"))
    source_image = _clean(row.get("source_image_filename"))
    action = _action_row(run_id, source_image)
    confirmed_name = reviewed["customer_name"]
    short_name = _clean(reviewed.get("short_name"))
    if short_name:
        short_name_source = "review_structured_fields"
    elif review_action == "corrected":
        # Legacy corrected artifacts predate the short_name field.  Derive
        # only from the user-confirmed name; never fall back to raw OCR.
        short_name = confirmed_name
        short_name_source = "legacy_corrected_customer_name"
    else:
        short_name = (
            _clean(action.get("prefill_short_name"))
            or _clean(action.get("matched_short_name"))
            or confirmed_name
        )
        short_name_source = "legacy_customer_action_prefill_or_match"

    identity_field = source.get("patient_identity_markers") or {}
    gender = _clean(reviewed.get("gender"))
    _require(not gender or gender in {"M", "F"}, "confirmed_gender_invalid")
    candidate = {
        "run_id": run_id,
        "decision_id": _clean(row.get("decision_id")),
        "row_number": int(row.get("_row_number") or 0),
        "candidate_id": _clean(row.get("candidate_id")),
        "review_action": review_action,
        "source_image": source_image,
        "ocr_raw_name": _clean((source.get("name") or {}).get("raw_value") or row.get("candidate_value")),
        "confirmed_name": confirmed_name,
        "short_name": short_name,
        "short_name_source": short_name_source,
        "birthday": reviewed["birthday"],
        "medical_record_no": reviewed["medical_record_no"],
        "gender": gender,
        "phone": _clean(action.get("prefill_phone")),
        "identity_markers": list(reviewed["patient_identity_markers"]),
        "identity_raw": list(identity_field.get("raw_values") or []),
        "identity_scope": "prescription_review_only",
        "address": "門診",
        "category": "診所",
        "queue_path": str(queue_path),
        "queue_revision": queue_revision,
        "queue_row_hash": review_tools._row_hash(row),
    }
    _validate_candidate(candidate)
    return candidate


def _validate_candidate(candidate: dict[str, Any]) -> None:
    _require(candidate.get("review_action") in FORMAL_REVIEW_ACTIONS, "customer_review_not_approved_or_corrected")
    _require(bool(_clean(candidate.get("confirmed_name"))), "confirmed_customer_name_required")
    _require(bool(_clean(candidate.get("short_name"))), "confirmed_customer_short_name_required")
    _require(candidate.get("address") == "門診", "customer_address_rule_mismatch")
    _require(candidate.get("category") == "診所", "customer_category_rule_mismatch")
    _require(candidate.get("identity_scope") == "prescription_review_only", "identity_scope_mismatch")
    parse_date(candidate.get("birthday"))


def customer_rows(session: Any) -> list[dict[str, Any]]:
    rows = session.execute(text("""
        SELECT id, name, short_name, birthday, medical_record_no,
               contact_phone, address, category, remarks, gender
        FROM public.customers
        ORDER BY id
    """)).mappings().all()
    return [dict(row) for row in rows]


def alias_score(candidate: str, existing: str) -> float:
    candidate_norm = normalize_person_name(candidate)
    existing_norm = normalize_person_name(existing)
    if not candidate_norm or not existing_norm:
        return 0.0
    ratio = SequenceMatcher(None, candidate_norm, existing_norm).ratio()
    shared = len(set(candidate_norm) & set(existing_norm))
    return max(ratio, shared / max(len(set(candidate_norm)), len(set(existing_norm)), 1))


def duplicate_details(candidate: dict[str, Any], customers: list[dict[str, Any]]) -> dict[str, Any]:
    name = _clean(candidate.get("confirmed_name"))
    short_name = _clean(candidate.get("short_name"))
    normalized_name = normalize_person_name(name)
    normalized_short = normalize_person_name(short_name)
    birthday = parse_date(candidate.get("birthday"))
    medical_record_no = _clean(candidate.get("medical_record_no"))
    phone = normalize_phone(candidate.get("phone"))
    checks: dict[str, list[dict[str, Any]]] = {
        "exact_name": [],
        "exact_short_name": [],
        "normalized_name_or_short_name": [],
        "birthday": [],
        "medical_record_no": [],
        "phone": [],
    }
    rows_by_id: dict[int, dict[str, Any]] = {}
    best_alias: tuple[float, dict[str, Any], str] | None = None
    for row in customers:
        row_id = int(row["id"])
        row_name = _clean(row.get("name"))
        row_short = _clean(row.get("short_name"))
        row_name_norm = normalize_person_name(row_name)
        row_short_norm = normalize_person_name(row_short)
        public_summary = {
            "id": row_id,
            "name": row_name,
            "short_name": row_short,
            "birthday": _json_safe(row.get("birthday")),
            "medical_record_no": _clean(row.get("medical_record_no")),
            "contact_phone": _clean(row.get("contact_phone")),
            "gender": _clean(row.get("gender")),
        }
        rows_by_id[row_id] = {**public_summary, "remarks": _clean(row.get("remarks"))}
        if name and row_name == name:
            checks["exact_name"].append(public_summary)
        if short_name and row_short == short_name:
            checks["exact_short_name"].append(public_summary)
        if normalized_name and normalized_name in {row_name_norm, row_short_norm}:
            checks["normalized_name_or_short_name"].append(public_summary)
        elif normalized_short and normalized_short in {row_name_norm, row_short_norm}:
            checks["normalized_name_or_short_name"].append(public_summary)
        if birthday and row.get("birthday") == birthday:
            checks["birthday"].append(public_summary)
        if medical_record_no and _clean(row.get("medical_record_no")) == medical_record_no:
            checks["medical_record_no"].append(public_summary)
        if phone and normalize_phone(row.get("contact_phone")) == phone:
            checks["phone"].append(public_summary)
        for field, value in (("name", row_name), ("short_name", row_short)):
            score = alias_score(name, value)
            if score >= 0.66 and normalize_person_name(value) not in {normalized_name, normalized_short}:
                if best_alias is None or score > best_alias[0]:
                    best_alias = (score, public_summary, field)

    checks["normalized_name_or_short_name"] = list({
        row["id"]: row for row in checks["normalized_name_or_short_name"]
    }.values())
    alias_like: list[dict[str, Any]] = []
    if best_alias:
        alias_like.append({**best_alias[1], "matched_field": best_alias[2], "score": round(best_alias[0], 4)})
    return {
        "candidate_values": {
            "exact_name": name,
            "short_name": short_name,
            "normalized_name": normalized_name,
            "normalized_short_name": normalized_short,
            "birthday": _json_safe(birthday),
            "medical_record_no": medical_record_no,
            "phone": phone,
        },
        "matches": {**checks, "alias_like_best": alias_like},
        "matched_rows_by_id": rows_by_id,
    }


def _provenance(candidate: dict[str, Any]) -> str:
    value = (
        f"Prescription OCR run={candidate['run_id']}; source_image={candidate['source_image']}; "
        f"review_action={candidate['review_action']}; decision_id={candidate['decision_id']}"
    )
    identity_text = list(candidate.get("identity_markers") or []) + list(candidate.get("identity_raw") or [])
    _require(not any(_clean(item) and _clean(item) in value for item in identity_text), "identity_leaked_into_remarks")
    return value


def _prepare_create(session: Any, candidate: dict[str, Any], remarks: str) -> ToolResult:
    return customer_tools.prepare_create_customer(
        session=session,
        name=candidate["confirmed_name"],
        short_name=candidate["short_name"],
        birthday=parse_date(candidate.get("birthday")),
        medical_record_no=_clean(candidate.get("medical_record_no")) or None,
        gender=_clean(candidate.get("gender")) or None,
        address="門診",
        category="診所",
        remarks=remarks,
    )


def classify_apply_plan(
    candidate: dict[str, Any],
    duplicate_check: dict[str, Any],
    prepare_result: ToolResult,
) -> dict[str, Any]:
    matches = duplicate_check["matches"]
    candidate_name = normalize_person_name(candidate["confirmed_name"])
    candidate_short = normalize_person_name(candidate["short_name"])
    candidate_birthday = parse_date(candidate.get("birthday"))
    candidate_medical = _clean(candidate.get("medical_record_no"))
    candidate_gender = _clean(candidate.get("gender"))
    candidate_phone = normalize_phone(candidate.get("phone"))
    conflicts: list[str] = []

    name_ids = {
        int(row["id"])
        for key in ("exact_name", "exact_short_name", "normalized_name_or_short_name")
        for row in matches[key]
    }
    medical_ids = {int(row["id"]) for row in matches["medical_record_no"]}
    birthday_ids = {int(row["id"]) for row in matches["birthday"]}
    phone_ids = {int(row["id"]) for row in matches["phone"]}

    for row in matches["medical_record_no"]:
        row_id = int(row["id"])
        row_names = {normalize_person_name(row.get("name")), normalize_person_name(row.get("short_name"))}
        if candidate_name not in row_names and candidate_short not in row_names:
            conflicts.append(f"medical_record_no_match_name_conflict:customer#{row_id}")
        existing_birthday = parse_date(row.get("birthday"))
        if candidate_birthday and existing_birthday and candidate_birthday != existing_birthday:
            conflicts.append(f"medical_record_no_match_birthday_conflict:customer#{row_id}")

    for key in ("exact_name", "exact_short_name", "normalized_name_or_short_name"):
        for row in matches[key]:
            row_id = int(row["id"])
            existing_birthday = parse_date(row.get("birthday"))
            existing_medical = _clean(row.get("medical_record_no"))
            existing_gender = _clean(row.get("gender"))
            if candidate_birthday and existing_birthday and candidate_birthday != existing_birthday:
                conflicts.append(f"same_name_birthday_conflict:customer#{row_id}")
            if candidate_medical and existing_medical and candidate_medical != existing_medical:
                conflicts.append(f"same_name_medical_record_no_conflict:customer#{row_id}")
            if candidate_gender and existing_gender and candidate_gender != existing_gender:
                conflicts.append(f"same_name_gender_conflict:customer#{row_id}")

    for row in matches["exact_short_name"]:
        if candidate_name != normalize_person_name(row.get("name")):
            conflicts.append(f"exact_short_name_name_conflict:customer#{row['id']}")

    conflicts = list(dict.fromkeys(conflicts))
    hard_excluded = sorted(HARD_EXCLUDED_FIELDS | {"patient_identity_relation"})
    if conflicts:
        return {
            "status": "blocked",
            "reasons": conflicts,
            "formal_tool": None,
            "target_customer_id": None,
            "write_fields": {},
            "hard_excluded_fields": hard_excluded,
        }

    exact_short_ids = {int(row["id"]) for row in matches["exact_short_name"]}
    supporting_ids = medical_ids | birthday_ids | phone_ids
    strong_ids: set[int] = set()
    for row_id in exact_short_ids | (name_ids & supporting_ids):
        row = duplicate_check["matched_rows_by_id"][row_id]
        row_names = {normalize_person_name(row.get("name")), normalize_person_name(row.get("short_name"))}
        if candidate_name in row_names or candidate_short in row_names:
            strong_ids.add(row_id)

    if len(strong_ids) > 1:
        return {
            "status": "needs_manual_confirmation",
            "reasons": ["multiple_consistent_existing_customers"],
            "formal_tool": None,
            "target_customer_id": None,
            "write_fields": {},
            "hard_excluded_fields": hard_excluded,
        }

    remarks = _provenance(candidate)
    if len(strong_ids) == 1:
        target_id = next(iter(strong_ids))
        existing = duplicate_check["matched_rows_by_id"][target_id]
        update_fields: dict[str, Any] = {}
        if candidate_birthday and not existing.get("birthday"):
            update_fields["birthday"] = candidate_birthday
        if candidate_medical and not _clean(existing.get("medical_record_no")):
            update_fields["medical_record_no"] = candidate_medical
        if candidate_gender and not _clean(existing.get("gender")):
            update_fields["gender"] = candidate_gender
        existing_remarks = _clean(existing.get("remarks"))
        if remarks not in existing_remarks:
            update_fields["remarks"] = f"{existing_remarks}\n{remarks}".strip()
        _require(set(update_fields) <= CUSTOMER_WRITABLE_FIELDS, "update_plan_contains_disallowed_field")
        if not update_fields:
            return {
                "status": "already_exists",
                "reasons": ["same_reviewed_customer_already_present"],
                "formal_tool": None,
                "target_customer_id": target_id,
                "write_fields": {},
                "no_op": True,
                "hard_excluded_fields": hard_excluded,
            }
        return {
            "status": "ready_for_update",
            "reasons": ["one_consistent_existing_customer"],
            "formal_tool": "rewrite.tools.customer.update_customer",
            "target_customer_id": target_id,
            "write_fields": _json_safe(update_fields),
            "no_op": False,
            "hard_excluded_fields": hard_excluded,
        }

    any_direct_match = any(matches[key] for key in (
        "exact_name",
        "exact_short_name",
        "normalized_name_or_short_name",
        "medical_record_no",
        "phone",
    ))
    if any_direct_match or matches["alias_like_best"]:
        return {
            "status": "needs_manual_confirmation",
            "reasons": ["possible_existing_customer_without_safe_composite_match"],
            "formal_tool": None,
            "target_customer_id": None,
            "write_fields": {},
            "hard_excluded_fields": hard_excluded,
        }

    if not prepare_result.ok:
        return {
            "status": "blocked",
            "reasons": [f"create_customer_contract:{prepare_result.error}"],
            "formal_tool": None,
            "target_customer_id": None,
            "write_fields": {},
            "hard_excluded_fields": hard_excluded,
        }

    create_fields = {
        key: value
        for key, value in prepare_result.data.items()
        if key in CUSTOMER_WRITABLE_FIELDS
    }
    _require(set(create_fields) <= CUSTOMER_WRITABLE_FIELDS, "create_plan_contains_disallowed_field")
    return {
        "status": "ready_for_create",
        "reasons": ["no_duplicate_or_conflict_match", "create_customer_prepare_contract_passed"],
        "formal_tool": "rewrite.tools.customer.create_customer",
        "target_customer_id": None,
        "write_fields": _json_safe(create_fields),
        "no_op": False,
        "hard_excluded_fields": hard_excluded,
    }


def build_customer_apply_plan(*, session: Any, candidate: dict[str, Any]) -> dict[str, Any]:
    _validate_candidate(candidate)
    remarks = _provenance(candidate)
    duplicates = duplicate_details(candidate, customer_rows(session))
    prepared = _prepare_create(session, candidate, remarks)
    plan = classify_apply_plan(candidate, duplicates, prepared)
    _require(plan["status"] in FORMAL_PLAN_STATUSES, "formal_plan_status_invalid")
    _require(set(plan.get("write_fields") or {}) <= CUSTOMER_WRITABLE_FIELDS, "formal_plan_contains_disallowed_field")
    serialized_write = _canonical_json(plan.get("write_fields") or {})
    identity_text = list(candidate.get("identity_markers") or []) + list(candidate.get("identity_raw") or [])
    _require(
        not any(_clean(item) and _clean(item) in serialized_write for item in identity_text),
        "identity_leaked_into_customer_plan",
    )
    return {
        "candidate": {
            key: _json_safe(candidate.get(key))
            for key in (
                "run_id",
                "decision_id",
                "row_number",
                "candidate_id",
                "review_action",
                "source_image",
                "ocr_raw_name",
                "confirmed_name",
                "short_name",
                "short_name_source",
                "birthday",
                "medical_record_no",
                "gender",
                "phone",
                "address",
                "category",
            )
        },
        "patient_identity": {
            "markers": list(candidate.get("identity_markers") or []),
            "raw_text": list(candidate.get("identity_raw") or []),
            "scope": "prescription_review_only",
            "write_to_customers": False,
            "write_to_remarks": False,
            "create_relation": False,
        },
        "duplicate_check": {
            "candidate_values": duplicates["candidate_values"],
            "matches": duplicates["matches"],
            "medical_record_no_is_unique_key": False,
        },
        "plan": plan,
        "create_customer_prepare_contract": {
            "ok": prepared.ok,
            "error": prepared.error,
        },
        "formal_mutation_called": False,
    }


def _preview_dir(run_id: str) -> Path:
    path = review_tools.decision_queue_path(run_id).parent / "customer_apply_previews"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _preview_path(run_id: str, preview_id: str) -> Path:
    _require(bool(PREVIEW_ID_RE.fullmatch(_clean(preview_id))), "customer_preview_id_invalid")
    return _preview_dir(run_id) / f"{preview_id}.json"


def _write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file_obj:
            json.dump(value, file_obj, ensure_ascii=False, indent=2, sort_keys=True, default=_json_default)
            file_obj.write("\n")
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def preview_customer_apply(
    *,
    session: Any,
    run_id: str,
    decision_id: str,
    reviewer_id: str = "",
    persist_artifact: bool = True,
) -> ToolResult:
    """Build a current create/update plan; never mutate a formal table."""
    try:
        candidate = load_reviewed_customer_candidate(run_id=run_id, decision_id=decision_id)
        result = build_customer_apply_plan(session=session, candidate=candidate)
        result["run_id"] = run_id
        result["decision_id"] = decision_id
        result["dry_run"] = True
        result["formal_tables_touched"] = "none"
        result["customer_writable_fields"] = sorted(CUSTOMER_WRITABLE_FIELDS)
        result["hard_excluded_fields"] = sorted(HARD_EXCLUDED_FIELDS | {"patient_identity_relation"})
        result_hash = _hash(result)
        result["customer_preview_result_hash"] = result_hash
        if persist_artifact:
            created_at = datetime.now(timezone.utc)
            preview_id = f"customer_preview_{created_at.strftime('%Y%m%dT%H%M%S')}_{result_hash[:12]}"
            artifact = {
                "preview_id": preview_id,
                "created_at": created_at.isoformat(),
                "expires_at": (created_at + timedelta(minutes=PREVIEW_EXPIRES_MINUTES)).isoformat(),
                "reviewer_id": _clean(reviewer_id),
                "run_id": run_id,
                "decision_id": decision_id,
                "queue_revision": candidate["queue_revision"],
                "queue_row_hash": candidate["queue_row_hash"],
                "candidate_hash": _hash(candidate),
                "result_hash": result_hash,
                "result": result,
            }
            path = _preview_path(run_id, preview_id)
            _write_json_atomic(path, artifact)
            result["customer_preview_id"] = preview_id
            result["customer_preview_expires_at"] = artifact["expires_at"]
        return ToolResult.success(data=result)
    except (CustomerApplyError, OSError, ValueError, json.JSONDecodeError) as exc:
        return ToolResult.fail(str(exc))


def _load_preview_artifact(run_id: str, preview_id: str) -> dict[str, Any]:
    path = _preview_path(run_id, preview_id)
    _require(path.is_file(), "customer_preview_not_found")
    artifact = json.loads(path.read_text(encoding="utf-8"))
    expires_at = datetime.fromisoformat(_clean(artifact.get("expires_at")))
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    _require(datetime.now(timezone.utc) <= expires_at, "customer_preview_expired")
    return artifact


def _service_payload(plan: dict[str, Any]) -> dict[str, Any]:
    fields = dict(plan.get("write_fields") or {})
    _require(set(fields) <= CUSTOMER_WRITABLE_FIELDS, "formal_apply_contains_disallowed_field")
    for excluded in HARD_EXCLUDED_FIELDS:
        _require(excluded not in fields, f"formal_apply_hard_excluded:{excluded}")
    if "birthday" in fields:
        fields["birthday"] = parse_date(fields["birthday"])
    return fields


def apply_customer_preview(
    *,
    session: Any,
    run_id: str,
    decision_id: str,
    customer_preview_id: str,
    customer_preview_result_hash: str,
) -> ToolResult:
    """Apply one gated customer plan without committing the caller's session."""
    try:
        artifact = _load_preview_artifact(run_id, customer_preview_id)
        _require(artifact.get("run_id") == run_id, "customer_preview_run_changed")
        _require(artifact.get("decision_id") == decision_id, "customer_preview_decision_changed")
        _require(artifact.get("result_hash") == customer_preview_result_hash, "customer_preview_hash_mismatch")
        candidate = load_reviewed_customer_candidate(run_id=run_id, decision_id=decision_id)
        _require(artifact.get("queue_revision") == candidate["queue_revision"], "customer_preview_queue_changed")
        _require(artifact.get("queue_row_hash") == candidate["queue_row_hash"], "customer_preview_row_changed")
        _require(artifact.get("candidate_hash") == _hash(candidate), "customer_preview_candidate_changed")

        session.execute(text("LOCK TABLE public.customers IN SHARE ROW EXCLUSIVE MODE"))
        current = build_customer_apply_plan(session=session, candidate=candidate)
        current.update({
            "run_id": run_id,
            "decision_id": decision_id,
            "dry_run": True,
            "formal_tables_touched": "none",
            "customer_writable_fields": sorted(CUSTOMER_WRITABLE_FIELDS),
            "hard_excluded_fields": sorted(HARD_EXCLUDED_FIELDS | {"patient_identity_relation"}),
        })
        _require(_hash(current) == customer_preview_result_hash, "customer_formal_plan_changed")
        plan = current["plan"]
        status = plan.get("status")
        _require(status in {"ready_for_create", "ready_for_update"}, f"customer_formal_apply_not_ready:{status}")
        fields = _service_payload(plan)

        if status == "ready_for_create":
            service_result = customer_tools.create_customer(
                session=session,
                auto_commit=False,
                **fields,
            )
        else:
            target_id = int(plan.get("target_customer_id") or 0)
            _require(target_id > 0, "customer_update_target_missing")
            if plan.get("no_op"):
                service_result = customer_tools.get_customer_by_id(target_id, session=session)
            else:
                service_result = customer_tools.update_customer(
                    session=session,
                    customer_id=target_id,
                    auto_commit=False,
                    **fields,
                )
        _require(service_result.ok, f"customer_service_failed:{service_result.error}")
        customer_view = service_result.data
        customer_data = _json_safe(customer_view.to_dict())
        for field, expected in _json_safe(fields).items():
            _require(
                customer_data.get(field) == expected,
                f"customer_postcheck_field_mismatch:{field}",
            )
        serialized_customer = _canonical_json(_json_safe(fields))
        identity_text = list(candidate.get("identity_markers") or []) + list(candidate.get("identity_raw") or [])
        _require(
            not any(_clean(item) and _clean(item) in serialized_customer for item in identity_text),
            "identity_leaked_into_customer_postcheck",
        )
        return ToolResult.success(data={
            "run_id": run_id,
            "decision_id": decision_id,
            "customer_preview_id": customer_preview_id,
            "formal_action": status,
            "customer_id": int(customer_view.id),
            "customer": customer_data,
            "written_fields": _json_safe(fields),
            "patient_identity": current["patient_identity"],
            "formal_tables_touched": "customers",
            "caller_must_commit": True,
        })
    except (CustomerApplyError, OSError, ValueError, json.JSONDecodeError) as exc:
        return ToolResult.fail(str(exc))
