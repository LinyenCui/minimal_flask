"""Preview-gated formal Drug/ICD adapter for Prescription OCR Review V1.

The adapter consumes only persisted approve/corrected structured values from
the existing import queue.  Preview is SELECT-only.  Formal mutations reuse
the production-proven drug_items/diagnosis_codes field contracts, run with
``auto_commit=False``, and leave commit/rollback ownership to the LIFF route.
Drug-diagnosis relation rows are never accepted here.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import unicodedata
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

from sqlalchemy import text

from rewrite.tools.base import ToolResult
from rewrite.tools import prescription_ocr_reference_matcher as reference_tools
from rewrite.tools import prescription_ocr_review as review_tools


FORMAL_REVIEW_ACTIONS = {"approve", "corrected"}
FORMAL_DECISION_TYPES = {"drug", "icd"}
READY_STATUSES = {"ready_for_create", "ready_for_update"}
SAFE_DRUG_MATCH_STATUSES = {"exact_code_match", "exact_name_match", "name_strength_match"}
SAFE_ICD_MATCH_STATUSES = {"exact_code_match", "normalized_code_match", "diagnosis_text_match"}
PREVIEW_EXPIRES_MINUTES = 10
PREVIEW_ID_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


class MedicalApplyError(RuntimeError):
    """Raised when a formal medical gate is not satisfied."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise MedicalApplyError(message)


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _json_default(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=_json_default)


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _json_safe(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def normalize_text(value: Any) -> str:
    text_value = unicodedata.normalize("NFKC", _clean(value)).upper()
    return re.sub(r"[^A-Z0-9\u3400-\u9FFF]+", "", text_value)


def normalize_code(value: Any) -> str:
    return re.sub(r"[^A-Z0-9]+", "", unicodedata.normalize("NFKC", _clean(value)).upper())


def _parse_json_object(value: Any, *, error_name: str) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    raw = _clean(value)
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise MedicalApplyError(f"{error_name}_invalid_json") from exc
    _require(isinstance(parsed, dict), f"{error_name}_must_be_object")
    return parsed


def _queue_row(run_id: str, decision_id: str) -> tuple[Path, dict[str, str], dict[str, Any]]:
    path, _fieldnames, rows = review_tools._read_decision_queue(run_id)
    matches = [row for row in rows if _clean(row.get("decision_id")) == _clean(decision_id)]
    _require(len(matches) == 1, "formal_review_row_missing_or_duplicated")
    row = matches[0]
    _require(row.get("decision_type") in FORMAL_DECISION_TYPES, "formal_review_row_is_not_drug_or_icd")
    return path, row, review_tools._queue_revision(path)


def _approved_structured_values(row: dict[str, str]) -> tuple[dict[str, Any], dict[str, Any]]:
    decision_type = _clean(row.get("decision_type"))
    review_action = _clean(row.get("review_decision"))
    _require(decision_type in FORMAL_DECISION_TYPES, "formal_decision_type_not_supported")
    _require(review_action in FORMAL_REVIEW_ACTIONS, "formal_review_not_approved_or_corrected")
    source = _parse_json_object(row.get("structured_fields"), error_name="structured_fields")

    expected_prefix = f"prescription-{decision_type}-official-match-"
    _require(_clean(source.get("schema_version")).startswith(expected_prefix), "official_match_structured_fields_required")
    official_match = source.get("official_match") or {}

    if review_action == "corrected":
        corrected = _parse_json_object(
            row.get("structured_corrected_fields"),
            error_name="structured_corrected_fields",
        )
        _require(bool(corrected), "corrected_structured_fields_required_no_ocr_fallback")
        if decision_type == "drug":
            validated, error = review_tools._validate_drug_structured_correction(corrected)
        else:
            validated, error = review_tools._validate_icd_structured_correction(corrected)
        _require(not error, f"corrected_{decision_type}_invalid:{error}")
        return validated, source

    safe_statuses = SAFE_DRUG_MATCH_STATUSES if decision_type == "drug" else SAFE_ICD_MATCH_STATUSES
    _require(_clean(official_match.get("match_status")) in safe_statuses, "approved_official_match_status_not_safe")
    _require(_clean(official_match.get("confidence")) == "high", "approved_official_match_confidence_not_high")
    effective = source.get("effective_fields") or {}
    if decision_type == "drug":
        validated, error = review_tools._validate_drug_structured_correction(effective)
    else:
        validated, error = review_tools._validate_icd_structured_correction(effective)
    _require(not error, f"approved_{decision_type}_invalid:{error}")
    return validated, source


@lru_cache(maxsize=1)
def _official_references() -> tuple[Any, Any, Any]:
    reference_tools._verify_reference(
        reference_tools.DEFAULT_DRUG_REFERENCE,
        reference_tools.DRUG_REFERENCE_SHA256,
        "Drug",
    )
    reference_tools._verify_reference(
        reference_tools.DEFAULT_ICD_REFERENCE,
        reference_tools.ICD_REFERENCE_SHA256,
        "ICD",
    )
    module = reference_tools._load_verified_matcher()
    return (
        module,
        module.load_drug_reference(reference_tools.DEFAULT_DRUG_REFERENCE),
        module.load_icd_reference(reference_tools.DEFAULT_ICD_REFERENCE),
    )


def _dosage_class(value: str) -> tuple[str, str]:
    dosage = _clean(value)
    if any(token in dosage for token in ("注射", "針劑", "輸注")):
        return "injection", "injection_drug"
    if any(
        token in dosage
        for token in ("軟膏", "乳膏", "凝膠", "外用", "貼片", "貼布", "眼用", "點眼", "鼻用", "噴霧", "吸入", "栓劑")
    ):
        return "topical", "topical_drug"
    if any(token in dosage for token in ("錠", "膠囊", "顆粒", "散劑", "粉劑", "糖漿", "口服", "懸液", "內服", "丸劑")):
        return "oral", "oral_drug"
    return "unknown", "unknown"


def _drug_official_record(code: str) -> dict[str, Any]:
    module, drug_reference, _icd_reference = _official_references()
    records = reference_tools._distinct_drug_products(drug_reference.code_index.get(module.normalize_code(code), []))
    _require(bool(records), "confirmed_drug_code_not_found_in_pinned_official_reference")
    _require(len(records) == 1, "confirmed_drug_code_has_multiple_official_products")
    return records[0]


def _icd_official_record(code: str) -> dict[str, Any]:
    module, _drug_reference, icd_reference = _official_references()
    record = icd_reference.code_index.get(module.normalize_icd(code))
    _require(bool(record), "confirmed_icd_not_found_in_pinned_official_reference")
    return record


def load_reviewed_medical_candidate(*, run_id: str, decision_id: str) -> dict[str, Any]:
    """Load one persisted Drug/ICD decision without OCR fallback."""
    queue_path, row, queue_revision = _queue_row(run_id, decision_id)
    values, source = _approved_structured_values(row)
    decision_type = _clean(row.get("decision_type"))
    official_match = source.get("official_match") or {}
    source_image = _clean(row.get("source_image_filename"))

    candidate: dict[str, Any] = {
        "run_id": run_id,
        "decision_id": _clean(row.get("decision_id")),
        "row_number": int(row.get("_row_number") or 0),
        "candidate_id": _clean(row.get("candidate_id")),
        "decision_type": decision_type,
        "review_action": _clean(row.get("review_decision")),
        "source_image": source_image,
        "confirmed_fields": values,
        "original_match_status": _clean(official_match.get("match_status")),
        "original_match_confidence": _clean(official_match.get("confidence")),
        "ocr_evidence": (source.get("ocr") or {}).get("evidence") or [],
        "queue_path": str(queue_path),
        "queue_revision": queue_revision,
        "queue_row_hash": review_tools._row_hash(row),
        "relation_formal_apply_allowed": False,
    }
    if decision_type == "drug":
        official = _drug_official_record(values["drug_code"])
        payload = official.get("payload") or {}
        table_type, item_kind = _dosage_class(payload.get("劑型", ""))
        _require(bool(_clean(values.get("ingredient"))), "confirmed_drug_ingredient_required")
        candidate["official_reference"] = {
            "path": str(reference_tools.DEFAULT_DRUG_REFERENCE),
            "sha256": reference_tools.DRUG_REFERENCE_SHA256,
            "row_number": official.get("row_number"),
            "drug_code": official.get("drug_code", ""),
            "english_name": official.get("english_name", ""),
            "chinese_name": official.get("chinese_name", ""),
            "ingredient": official.get("ingredient", ""),
            "dosage_form": payload.get("劑型", ""),
        }
        candidate["formal_fields"] = {
            "seq_no": f"NHI-{values['drug_code']}",
            "table_type": table_type,
            "generic_name": values["ingredient"],
            "brand_name": values["drug_name"],
            "aliases": official.get("chinese_name", ""),
            "item_kind": item_kind,
            "needs_manual_check": False,
            "source_photo": source_image,
            "source_version": "prescription_ocr_v1",
            "staging_import_batch_id": f"prescription_ocr:{run_id}",
            "staging_row_id": int(row.get("_row_number") or 0),
            "is_active": True,
            "nhi_drug_code": values["drug_code"],
            "nhi_drug_code_source": "official_nhi",
            "nhi_drug_code_confidence": "high",
        }
        candidate["reference_discrepancies"] = [
            label
            for label, confirmed, official_value in (
                ("drug_name", values["drug_name"], official.get("english_name", "")),
                ("ingredient", values["ingredient"], official.get("ingredient", "")),
                (
                    "strength_specification",
                    values.get("strength_specification", ""),
                    reference_tools._drug_specification(official),
                ),
            )
            if confirmed and official_value and normalize_text(confirmed) != normalize_text(official_value)
        ]
    else:
        official = _icd_official_record(values["icd_code"])
        candidate["official_reference"] = {
            "path": str(reference_tools.DEFAULT_ICD_REFERENCE),
            "sha256": reference_tools.ICD_REFERENCE_SHA256,
            "row_number": official.get("row_number"),
            "icd_code": official.get("code", ""),
            "chinese_name": official.get("chinese_name", ""),
            "english_name": official.get("english_name", ""),
        }
        candidate["formal_fields"] = {
            "icd9_code": None,
            "icd10_code": values["icd_code"],
            "name_zh": values["chinese_name"],
            "name_en": values.get("english_name") or None,
            "is_high_frequency": False,
            "is_handwritten": False,
            "is_deprecated": False,
            "confidence": "confirmed",
        }
        candidate["reference_discrepancies"] = [
            label
            for label, confirmed, official_value in (
                ("chinese_name", values["chinese_name"], official.get("chinese_name", "")),
                ("english_name", values.get("english_name", ""), official.get("english_name", "")),
            )
            if confirmed and official_value and normalize_text(confirmed) != normalize_text(official_value)
        ]
    return candidate


def _drug_rows(session: Any) -> list[dict[str, Any]]:
    rows = session.execute(text("""
        SELECT id, seq_no, generic_name, brand_name, aliases, is_active,
               nhi_drug_code, nhi_drug_code_source, nhi_drug_code_confidence
        FROM public.drug_items
        ORDER BY id
    """)).mappings().all()
    return [dict(row) for row in rows]


def _icd_rows(session: Any) -> list[dict[str, Any]]:
    rows = session.execute(text("""
        SELECT id, icd9_code, icd10_code, name_zh, name_en,
               is_high_frequency, is_handwritten, is_deprecated, confidence
        FROM public.diagnosis_codes
        ORDER BY id
    """)).mappings().all()
    return [dict(row) for row in rows]


def classify_drug_plan(candidate: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    fields = candidate["formal_fields"]
    code = normalize_code(fields["nhi_drug_code"])
    seq_no = _clean(fields["seq_no"])
    names = {
        normalize_text(fields.get("generic_name")),
        normalize_text(fields.get("brand_name")),
        normalize_text(fields.get("aliases")),
    } - {""}
    code_rows = [row for row in rows if normalize_code(row.get("nhi_drug_code")) == code]
    seq_rows = [row for row in rows if row.get("is_active") is True and _clean(row.get("seq_no")) == seq_no]
    identity_rows = {int(row["id"]): row for row in [*code_rows, *seq_rows]}
    name_rows = [
        row
        for row in rows
        if names
        & {
            normalize_text(row.get("generic_name")),
            normalize_text(row.get("brand_name")),
            normalize_text(row.get("aliases")),
        }
    ]
    duplicate_check = {
        "nhi_drug_code": [_json_safe(row) for row in code_rows],
        "active_seq_no": [_json_safe(row) for row in seq_rows],
        "normalized_names": [_json_safe(row) for row in name_rows],
    }
    hard_excluded = ["drug_diagnosis_links", "relation_apply"]

    if len(identity_rows) > 1:
        status, reasons, target_id, write_fields = "blocked", ["code_or_seq_matches_multiple_rows"], None, {}
    elif identity_rows:
        row = next(iter(identity_rows.values()))
        target_id = int(row["id"])
        same_generic = normalize_text(fields.get("generic_name")) == normalize_text(row.get("generic_name"))
        same_brand = normalize_text(fields.get("brand_name")) == normalize_text(row.get("brand_name"))
        if same_generic and same_brand:
            status, reasons, write_fields = "already_exists", ["same_formal_drug_already_present"], {}
        else:
            status, reasons, write_fields = "blocked", [f"drug_code_or_seq_name_conflict:drug_item#{target_id}"], {}
    elif name_rows:
        distinct = {int(row["id"]): row for row in name_rows}
        if len(distinct) != 1:
            status, reasons, target_id, write_fields = "needs_manual_confirmation", ["multiple_formal_name_matches"], None, {}
        else:
            row = next(iter(distinct.values()))
            target_id = int(row["id"])
            existing_code = normalize_code(row.get("nhi_drug_code"))
            brand_match = normalize_text(fields.get("brand_name")) in {
                normalize_text(row.get("brand_name")), normalize_text(row.get("aliases"))
            }
            ingredient_match = normalize_text(fields.get("generic_name")) == normalize_text(row.get("generic_name"))
            if existing_code and existing_code != code:
                status, reasons, write_fields = "blocked", [f"formal_name_existing_under_different_code:drug_item#{target_id}"], {}
            elif not existing_code and brand_match and ingredient_match:
                status = "ready_for_update"
                reasons = ["single_formal_name_match_with_blank_nhi_code"]
                write_fields = {
                    "nhi_drug_code": fields["nhi_drug_code"],
                    "nhi_drug_code_source": "official_nhi",
                    "nhi_drug_code_confidence": "high",
                }
            elif existing_code:
                status, reasons, write_fields = "already_exists", ["same_formal_drug_already_present"], {}
            else:
                status, reasons, write_fields = "needs_manual_confirmation", ["name_match_not_safe_composite"], {}
    else:
        status, reasons, target_id, write_fields = "ready_for_create", ["no_production_duplicate_or_conflict"], None, fields

    return {
        "status": status,
        "reasons": reasons,
        "formal_tool": (
            "rewrite.tools.prescription_ocr_medical_apply.create_drug_item"
            if status == "ready_for_create"
            else "rewrite.tools.prescription_ocr_medical_apply.update_drug_item"
            if status == "ready_for_update"
            else None
        ),
        "target_id": target_id,
        "write_fields": _json_safe(write_fields),
        "duplicate_check": duplicate_check,
        "hard_excluded_fields": hard_excluded,
    }


def classify_icd_plan(candidate: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    fields = candidate["formal_fields"]
    code = normalize_code(fields["icd10_code"])
    chinese = normalize_text(fields["name_zh"])
    english = normalize_text(fields.get("name_en"))
    code_rows = [row for row in rows if normalize_code(row.get("icd10_code")) == code]
    name_rows = [
        row
        for row in rows
        if chinese == normalize_text(row.get("name_zh")) or (english and english == normalize_text(row.get("name_en")))
    ]
    duplicate_check = {
        "normalized_icd10_code": [_json_safe(row) for row in code_rows],
        "official_names": [_json_safe(row) for row in name_rows],
    }
    hard_excluded = ["drug_diagnosis_links", "relation_apply"]

    if len(code_rows) > 1:
        status, reasons, target_id, write_fields = "blocked", ["normalized_icd_matches_multiple_rows"], None, {}
    elif code_rows:
        row = code_rows[0]
        target_id = int(row["id"])
        if chinese != normalize_text(row.get("name_zh")):
            status, reasons, write_fields = "blocked", [f"icd_code_chinese_name_conflict:diagnosis_code#{target_id}"], {}
        elif english and row.get("name_en") and english != normalize_text(row.get("name_en")):
            status, reasons, write_fields = "blocked", [f"icd_code_english_name_conflict:diagnosis_code#{target_id}"], {}
        elif english and not _clean(row.get("name_en")):
            status, reasons, write_fields = "ready_for_update", ["same_icd_with_blank_english_name"], {"name_en": fields["name_en"]}
        else:
            status, reasons, write_fields = "already_exists", ["same_formal_icd_already_present"], {}
    elif name_rows:
        target_ids = sorted({int(row["id"]) for row in name_rows})
        status = "blocked" if len(target_ids) == 1 else "needs_manual_confirmation"
        reasons = ["official_name_existing_under_different_icd"] if len(target_ids) == 1 else ["multiple_formal_name_matches"]
        target_id = target_ids[0] if len(target_ids) == 1 else None
        write_fields = {}
    else:
        status, reasons, target_id, write_fields = "ready_for_create", ["no_production_duplicate_or_conflict"], None, fields

    return {
        "status": status,
        "reasons": reasons,
        "formal_tool": (
            "rewrite.tools.prescription_ocr_medical_apply.create_diagnosis_code"
            if status == "ready_for_create"
            else "rewrite.tools.prescription_ocr_medical_apply.update_diagnosis_code"
            if status == "ready_for_update"
            else None
        ),
        "target_id": target_id,
        "write_fields": _json_safe(write_fields),
        "duplicate_check": duplicate_check,
        "hard_excluded_fields": hard_excluded,
    }


def build_medical_apply_plan(*, session: Any, candidate: dict[str, Any]) -> dict[str, Any]:
    decision_type = candidate["decision_type"]
    if decision_type == "drug":
        plan = classify_drug_plan(candidate, _drug_rows(session))
        target_table = "drug_items"
    elif decision_type == "icd":
        plan = classify_icd_plan(candidate, _icd_rows(session))
        target_table = "diagnosis_codes"
    else:
        raise MedicalApplyError("relation_or_unknown_formal_apply_hard_excluded")
    if candidate.get("review_action") == "approve" and candidate.get("reference_discrepancies"):
        plan = {
            **plan,
            "status": "blocked",
            "reasons": ["approved_fields_conflict_with_pinned_official_reference"],
            "formal_tool": None,
            "target_id": None,
            "write_fields": {},
        }
    return {
        "candidate": {
            key: _json_safe(candidate.get(key))
            for key in (
                "run_id", "decision_id", "row_number", "candidate_id", "decision_type",
                "review_action", "source_image", "confirmed_fields", "original_match_status",
                "original_match_confidence", "ocr_evidence", "official_reference",
                "reference_discrepancies",
            )
        },
        "target_table": target_table,
        "plan": plan,
        "relation": {
            "classification": "evidence_only",
            "formal_apply_allowed": False,
            "target_table": "drug_diagnosis_links",
        },
    }


def _preview_dir(run_id: str) -> Path:
    path = review_tools.decision_queue_path(run_id).parent / "formal_apply_previews"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _preview_path(run_id: str, preview_id: str) -> Path:
    _require(bool(PREVIEW_ID_RE.fullmatch(preview_id)), "formal_preview_id_invalid")
    return _preview_dir(run_id) / f"{preview_id}.json"


def _write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=_json_default)
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def preview_medical_apply(
    *, session: Any, run_id: str, decision_id: str, reviewer_id: str = "", persist_artifact: bool = True
) -> ToolResult:
    """Build a current Drug/ICD plan without mutating a formal table."""
    try:
        candidate = load_reviewed_medical_candidate(run_id=run_id, decision_id=decision_id)
        result = build_medical_apply_plan(session=session, candidate=candidate)
        result.update({
            "run_id": run_id,
            "decision_id": decision_id,
            "dry_run": True,
            "formal_tables_touched": "none",
        })
        result_hash = _hash(result)
        result["formal_preview_result_hash"] = result_hash
        if persist_artifact:
            created_at = datetime.now(timezone.utc)
            preview_id = f"formal_preview_{created_at.strftime('%Y%m%dT%H%M%S')}_{result_hash[:12]}"
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
            _write_json_atomic(_preview_path(run_id, preview_id), artifact)
            result["formal_preview_id"] = preview_id
            result["formal_preview_expires_at"] = artifact["expires_at"]
        return ToolResult.success(data=result)
    except (MedicalApplyError, OSError, ValueError, json.JSONDecodeError) as exc:
        return ToolResult.fail(str(exc))


def _load_preview_artifact(run_id: str, preview_id: str) -> dict[str, Any]:
    path = _preview_path(run_id, preview_id)
    _require(path.is_file(), "formal_preview_not_found")
    artifact = json.loads(path.read_text(encoding="utf-8"))
    expires_at = datetime.fromisoformat(_clean(artifact.get("expires_at")))
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    _require(datetime.now(timezone.utc) <= expires_at, "formal_preview_expired")
    return artifact


def create_drug_item(*, session: Any, auto_commit: bool = True, **fields: Any) -> ToolResult:
    """Create one production drug item; caller may own the transaction."""
    allowed = {
        "seq_no", "table_type", "generic_name", "brand_name", "aliases", "item_kind",
        "needs_manual_check", "source_photo", "source_version", "staging_import_batch_id",
        "staging_row_id", "is_active", "nhi_drug_code", "nhi_drug_code_source",
        "nhi_drug_code_confidence",
    }
    if set(fields) != allowed:
        return ToolResult.fail(f"drug_create_fields_invalid:{sorted(set(fields) ^ allowed)}")
    row = session.execute(text("""
        INSERT INTO public.drug_items
            (seq_no, table_type, generic_name, brand_name, aliases, item_kind,
             needs_manual_check, source_photo, source_version, staging_import_batch_id,
             staging_row_id, is_active, nhi_drug_code, nhi_drug_code_source,
             nhi_drug_code_confidence)
        VALUES
            (:seq_no, :table_type, :generic_name, :brand_name, :aliases, :item_kind,
             :needs_manual_check, :source_photo, :source_version, :staging_import_batch_id,
             :staging_row_id, :is_active, :nhi_drug_code, :nhi_drug_code_source,
             :nhi_drug_code_confidence)
        RETURNING id, seq_no, table_type, generic_name, brand_name, aliases, item_kind,
                  needs_manual_check, source_photo, source_version, staging_import_batch_id,
                  staging_row_id, is_active, nhi_drug_code, nhi_drug_code_source,
                  nhi_drug_code_confidence
    """), fields).mappings().one()
    if auto_commit:
        session.commit()
    return ToolResult.success(data=dict(row))


def update_drug_item(*, session: Any, drug_item_id: int, auto_commit: bool = True, **fields: Any) -> ToolResult:
    """Fill a blank official NHI code on one name-matched formal drug."""
    allowed = {"nhi_drug_code", "nhi_drug_code_source", "nhi_drug_code_confidence"}
    if not fields or not set(fields) <= allowed:
        return ToolResult.fail("drug_update_fields_invalid")
    row = session.execute(text("""
        UPDATE public.drug_items
        SET nhi_drug_code = :nhi_drug_code,
            nhi_drug_code_source = :nhi_drug_code_source,
            nhi_drug_code_confidence = :nhi_drug_code_confidence
        WHERE id = :id AND btrim(coalesce(nhi_drug_code, '')) = ''
        RETURNING id, seq_no, generic_name, brand_name, aliases, is_active,
                  nhi_drug_code, nhi_drug_code_source, nhi_drug_code_confidence
    """), {**fields, "id": drug_item_id}).mappings().one_or_none()
    if row is None:
        return ToolResult.fail("drug_update_target_changed_or_missing")
    if auto_commit:
        session.commit()
    return ToolResult.success(data=dict(row))


def create_diagnosis_code(*, session: Any, auto_commit: bool = True, **fields: Any) -> ToolResult:
    """Create one production diagnosis code; caller may own transaction."""
    allowed = {
        "icd9_code", "icd10_code", "name_zh", "name_en", "is_high_frequency",
        "is_handwritten", "is_deprecated", "confidence",
    }
    if set(fields) != allowed:
        return ToolResult.fail(f"icd_create_fields_invalid:{sorted(set(fields) ^ allowed)}")
    row = session.execute(text("""
        INSERT INTO public.diagnosis_codes
            (icd9_code, icd10_code, name_zh, name_en, is_high_frequency,
             is_handwritten, is_deprecated, confidence)
        VALUES
            (:icd9_code, :icd10_code, :name_zh, :name_en, :is_high_frequency,
             :is_handwritten, :is_deprecated, :confidence)
        RETURNING id, icd9_code, icd10_code, name_zh, name_en, is_high_frequency,
                  is_handwritten, is_deprecated, confidence
    """), fields).mappings().one()
    if auto_commit:
        session.commit()
    return ToolResult.success(data=dict(row))


def update_diagnosis_code(
    *, session: Any, diagnosis_code_id: int, auto_commit: bool = True, **fields: Any
) -> ToolResult:
    """Fill a blank English name on an exact-code formal diagnosis row."""
    if set(fields) != {"name_en"} or not _clean(fields.get("name_en")):
        return ToolResult.fail("icd_update_fields_invalid")
    row = session.execute(text("""
        UPDATE public.diagnosis_codes
        SET name_en = :name_en
        WHERE id = :id AND btrim(coalesce(name_en, '')) = ''
        RETURNING id, icd9_code, icd10_code, name_zh, name_en, is_high_frequency,
                  is_handwritten, is_deprecated, confidence
    """), {**fields, "id": diagnosis_code_id}).mappings().one_or_none()
    if row is None:
        return ToolResult.fail("icd_update_target_changed_or_missing")
    if auto_commit:
        session.commit()
    return ToolResult.success(data=dict(row))


def _postcheck_row(session: Any, decision_type: str, row_id: int, expected: dict[str, Any]) -> dict[str, Any]:
    table = "drug_items" if decision_type == "drug" else "diagnosis_codes"
    row = session.execute(text(f"SELECT * FROM public.{table} WHERE id = :id"), {"id": row_id}).mappings().one_or_none()
    _require(row is not None, "formal_postcheck_row_missing")
    actual = dict(row)
    for key, value in expected.items():
        _require(actual.get(key) == value, f"formal_postcheck_field_mismatch:{key}")
    return actual


def apply_medical_preview(
    *, session: Any, run_id: str, decision_id: str, formal_preview_id: str, formal_preview_result_hash: str
) -> ToolResult:
    """Apply one preview-gated Drug/ICD plan without committing."""
    try:
        artifact = _load_preview_artifact(run_id, formal_preview_id)
        _require(artifact.get("run_id") == run_id, "formal_preview_run_changed")
        _require(artifact.get("decision_id") == decision_id, "formal_preview_decision_changed")
        _require(artifact.get("result_hash") == formal_preview_result_hash, "formal_preview_hash_mismatch")
        candidate = load_reviewed_medical_candidate(run_id=run_id, decision_id=decision_id)
        _require(artifact.get("queue_revision") == candidate["queue_revision"], "formal_preview_queue_changed")
        _require(artifact.get("queue_row_hash") == candidate["queue_row_hash"], "formal_preview_row_changed")
        _require(artifact.get("candidate_hash") == _hash(candidate), "formal_preview_candidate_changed")

        table = "drug_items" if candidate["decision_type"] == "drug" else "diagnosis_codes"
        session.execute(text(f"LOCK TABLE public.{table} IN SHARE ROW EXCLUSIVE MODE"))
        current = build_medical_apply_plan(session=session, candidate=candidate)
        current.update({"run_id": run_id, "decision_id": decision_id, "dry_run": True, "formal_tables_touched": "none"})
        _require(_hash(current) == formal_preview_result_hash, "formal_apply_plan_changed")
        plan = current["plan"]
        status = plan.get("status")
        _require(status in READY_STATUSES, f"formal_apply_not_ready:{status}")
        fields = dict(plan.get("write_fields") or {})

        if candidate["decision_type"] == "drug" and status == "ready_for_create":
            service_result = create_drug_item(session=session, auto_commit=False, **fields)
        elif candidate["decision_type"] == "drug":
            service_result = update_drug_item(
                session=session, drug_item_id=int(plan.get("target_id") or 0), auto_commit=False, **fields
            )
        elif status == "ready_for_create":
            service_result = create_diagnosis_code(session=session, auto_commit=False, **fields)
        else:
            service_result = update_diagnosis_code(
                session=session, diagnosis_code_id=int(plan.get("target_id") or 0), auto_commit=False, **fields
            )
        _require(service_result.ok, f"formal_service_failed:{service_result.error}")
        row_id = int(service_result.data["id"])
        postcheck = _postcheck_row(session, candidate["decision_type"], row_id, fields)
        return ToolResult.success(data={
            "run_id": run_id,
            "decision_id": decision_id,
            "decision_type": candidate["decision_type"],
            "formal_preview_id": formal_preview_id,
            "formal_action": status,
            "target_table": table,
            "target_id": row_id,
            "written_fields": _json_safe(fields),
            "postcheck": _json_safe(postcheck),
            "relation_formal_apply_allowed": False,
            "caller_must_commit": True,
        })
    except (MedicalApplyError, OSError, ValueError, json.JSONDecodeError) as exc:
        return ToolResult.fail(str(exc))


def verify_committed_medical_result(*, session: Any, result: dict[str, Any]) -> ToolResult:
    """Fresh-connection verification for a committed Drug/ICD result."""
    try:
        actual = _postcheck_row(
            session,
            _clean(result.get("decision_type")),
            int(result.get("target_id") or 0),
            dict(result.get("written_fields") or {}),
        )
        return ToolResult.success(data={"fresh_postcheck": _json_safe(actual)})
    except (MedicalApplyError, ValueError) as exc:
        return ToolResult.fail(str(exc))
