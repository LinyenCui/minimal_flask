"""Prescription OCR import review decision tools.

This module only updates OCR review artifacts and the prescription OCR staging
tables. It must never promote data into customers, drug_items, diagnosis_codes,
or drug_diagnosis_links.
"""
from __future__ import annotations

import csv
import base64
import hashlib
import io
import json
import os
import re
import shutil
import tempfile
import zipfile
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import bindparam, text
from sqlalchemy.exc import SQLAlchemyError

from rewrite.tools.base import ToolResult


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUNS_DIR = Path(
    os.environ.get(
        "PRESCRIPTION_OCR_RUNS_DIR",
        str(REPO_ROOT / "runtime_data" / "prescription_ocr_runs"),
    )
)
SEED_BUNDLE_PATH = Path(
    os.environ.get(
        "PRESCRIPTION_OCR_SEED_BUNDLE",
        "/etc/secrets/prescription_ocr_release_smoke.zip.b64",
    )
)
SEED_BUNDLE_SHA256 = os.environ.get(
    "PRESCRIPTION_OCR_SEED_BUNDLE_SHA256",
    "05eafd74964d738e00b9bdb7b1a911ceabbefd9925d98b53e45acf6aee5aefaf",
).strip().lower()
SEED_RUN_FILES = {
    "review/import_decision_queue.csv",
    "customer_matching/ocr_customer_liff_actions.csv",
}

RUN_ID_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
STAGING_ID_RE = re.compile(r"\bstaging:(\d+)\b")
OFFICIAL_MATCH_ID_RE = re.compile(r"^(?:drug|icd)_match:\d+$")

DECISION_TYPES = {"customer", "drug", "icd", "drug_diagnosis_link"}
REQUESTED_ACTIONS = {"approve", "reject", "skip", "defer", "corrected"}
FINAL_REVIEW_DECISIONS = {"approve", "reject", "skip", "defer", "corrected"}

# Existing DB CHECK constraint values in prescription_ocr_candidate_staging.
STAGING_REVIEW_STATUS_BY_ACTION = {
    "approve": "accept",
    "reject": "reject",
    "skip": "duplicate",
    "defer": "unclear",
    "corrected": "unclear",
}

DEV_TEST_BATCH_LIMIT = 3
PRODUCTION_BATCH_LIMIT = 10
CORRECTED_BATCH_LIMIT = 5
PREVIEW_EXPIRES_MINUTES = 10

SUPPORTED_PATIENT_IDENTITY_MARKERS = ("榮", "榮民", "榮保", "友", "眷", "員", "重大", "殘障")
SUPPORTED_PATIENT_IDENTITY_MARKER_SET = set(SUPPORTED_PATIENT_IDENTITY_MARKERS)
MEDICAL_RECORD_NO_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]{0,19}$")
TAIWAN_ID_RE = re.compile(r"^[A-Z][12][0-9]{8}$")
DRUG_CODE_RE = re.compile(r"^[A-Z0-9]{8,13}$")
ICD_CODE_RE = re.compile(r"^[A-TV-Z][0-9]{2}(?:\.?[0-9A-Z]{1,4})?$", re.IGNORECASE)


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", _clean(value))[:120] or "blank"


def _run_dir(run_id: str) -> Path:
    run_id = _clean(run_id)
    if not run_id or not RUN_ID_RE.match(run_id):
        raise ValueError("run_id 格式錯")
    path = DEFAULT_RUNS_DIR / run_id
    base = DEFAULT_RUNS_DIR.resolve()
    resolved = path.resolve()
    if base not in resolved.parents and resolved != base:
        raise ValueError("run_id 超出允許目錄")
    return resolved


def _install_seed_run(run_id: str, target: Path) -> bool:
    """Install one controlled release run from a Render Secret File bundle.

    The bundle is base64-encoded ZIP content so it can be stored as a text
    Secret File.  Only the existing queue and customer action contracts are
    accepted; no arbitrary archive paths are extracted.
    """
    if not SEED_BUNDLE_PATH.is_file():
        return False

    encoded = b"".join(SEED_BUNDLE_PATH.read_bytes().split())
    try:
        payload = base64.b64decode(encoded, validate=True)
    except (ValueError, TypeError) as exc:
        raise ValueError("Prescription OCR seed bundle 不是有效 base64") from exc

    if SEED_BUNDLE_SHA256:
        actual_sha256 = hashlib.sha256(payload).hexdigest()
        if actual_sha256 != SEED_BUNDLE_SHA256:
            raise ValueError(
                "Prescription OCR seed bundle SHA-256 不符: "
                f"expected={SEED_BUNDLE_SHA256} actual={actual_sha256}"
            )

    base = DEFAULT_RUNS_DIR.resolve()
    base.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{run_id}.", dir=str(base)))
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            members = {name: archive.getinfo(name) for name in archive.namelist()}
            for relative_name in sorted(SEED_RUN_FILES):
                member_name = f"{run_id}/{relative_name}"
                member = members.get(member_name)
                if member is None or member.is_dir():
                    raise FileNotFoundError(f"seed bundle 缺少 {member_name}")
                destination = staging / relative_name
                destination.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member, "r") as source, destination.open("wb") as output:
                    shutil.copyfileobj(source, output)

        if target.exists():
            return True
        os.replace(staging, target)
        staging = None
        return True
    finally:
        if staging is not None:
            shutil.rmtree(staging, ignore_errors=True)


def decision_queue_path(run_id: str) -> Path:
    run_dir = _run_dir(run_id)
    queue_path = run_dir / "review" / "import_decision_queue.csv"
    if not queue_path.is_file():
        _install_seed_run(run_id, run_dir)
    return queue_path


def _review_dir(run_id: str) -> Path:
    return _run_dir(run_id) / "review"


def _apply_runs_dir(run_id: str) -> Path:
    path = _review_dir(run_id) / "apply_runs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _apply_previews_dir(run_id: str) -> Path:
    path = _review_dir(run_id) / "apply_previews"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _backup_dir(run_id: str) -> Path:
    path = _review_dir(run_id) / "backups"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _canonical_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=_json_default)


def _parse_json_object(value: Any) -> tuple[dict[str, Any], str]:
    if isinstance(value, dict):
        return value, ""
    raw = _clean(value)
    if not raw:
        return {}, ""
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}, "invalid_json"
    if not isinstance(parsed, dict):
        return {}, "json_value_must_be_object"
    return parsed, ""


def _validate_customer_structured_correction(value: Any) -> tuple[dict[str, Any], str]:
    data, parse_error = _parse_json_object(value)
    if parse_error:
        return {}, f"structured_fields_{parse_error}"
    if not data:
        return {}, ""

    allowed = {
        "customer_name",
        "short_name",
        "birthday",
        "medical_record_no",
        "gender",
        "patient_identity_markers",
    }
    unexpected = sorted(set(data) - allowed)
    if unexpected:
        return {}, f"structured_fields_unexpected_keys:{','.join(unexpected)}"

    customer_name = _clean(data.get("customer_name"))
    if not customer_name or len(customer_name) > 100:
        return {}, "structured_customer_name_invalid"

    short_name = _clean(data.get("short_name"))
    if short_name and len(short_name) > 50:
        return {}, "structured_customer_short_name_invalid"

    gender = _clean(data.get("gender")).upper()
    if gender and gender not in {"M", "F"}:
        return {}, "structured_customer_gender_invalid"

    birthday = _clean(data.get("birthday"))
    if birthday:
        try:
            datetime.strptime(birthday, "%Y-%m-%d")
        except ValueError:
            return {}, "structured_birthday_must_be_iso_date"

    medical_record_no = _clean(data.get("medical_record_no")).upper()
    if medical_record_no:
        if not MEDICAL_RECORD_NO_RE.fullmatch(medical_record_no):
            return {}, "structured_medical_record_no_invalid"
        if medical_record_no.isdigit() and set(medical_record_no) == {"0"}:
            return {}, "structured_medical_record_no_invalid"
        if TAIWAN_ID_RE.fullmatch(medical_record_no):
            return {}, "structured_medical_record_no_looks_like_identity_card"

    markers = data.get("patient_identity_markers") or []
    if not isinstance(markers, list):
        return {}, "structured_patient_identity_markers_must_be_list"
    normalized_markers: list[str] = []
    for marker in markers:
        marker = _clean(marker)
        if marker not in SUPPORTED_PATIENT_IDENTITY_MARKER_SET:
            return {}, f"structured_patient_identity_marker_not_supported:{marker}"
        if marker not in normalized_markers:
            normalized_markers.append(marker)
    normalized_markers.sort(key=SUPPORTED_PATIENT_IDENTITY_MARKERS.index)

    return {
        "customer_name": customer_name,
        "short_name": short_name,
        "birthday": birthday,
        "medical_record_no": medical_record_no,
        "gender": gender,
        "patient_identity_markers": normalized_markers,
        "patient_identity_scope": "prescription_review_only",
    }, ""


def _validate_drug_structured_correction(value: Any) -> tuple[dict[str, Any], str]:
    data, parse_error = _parse_json_object(value)
    if parse_error:
        return {}, f"structured_fields_{parse_error}"
    allowed = {"drug_code", "drug_name", "ingredient", "strength_specification"}
    unexpected = sorted(set(data) - allowed)
    if unexpected:
        return {}, f"structured_fields_unexpected_keys:{','.join(unexpected)}"
    code = re.sub(r"[^A-Z0-9]", "", _clean(data.get("drug_code")).upper())
    name = _clean(data.get("drug_name"))
    if not code or not DRUG_CODE_RE.fullmatch(code):
        return {}, "structured_drug_code_invalid"
    if not name or len(name) > 300:
        return {}, "structured_drug_name_invalid"
    ingredient = _clean(data.get("ingredient"))
    specification = _clean(data.get("strength_specification"))
    if len(ingredient) > 500 or len(specification) > 300:
        return {}, "structured_drug_field_too_long"
    return {
        "drug_code": code,
        "drug_name": name,
        "ingredient": ingredient,
        "strength_specification": specification,
    }, ""


def _validate_icd_structured_correction(value: Any) -> tuple[dict[str, Any], str]:
    data, parse_error = _parse_json_object(value)
    if parse_error:
        return {}, f"structured_fields_{parse_error}"
    allowed = {"icd_code", "chinese_name", "english_name"}
    unexpected = sorted(set(data) - allowed)
    if unexpected:
        return {}, f"structured_fields_unexpected_keys:{','.join(unexpected)}"
    code = _clean(data.get("icd_code")).upper()
    if not code or not ICD_CODE_RE.fullmatch(code):
        return {}, "structured_icd_code_invalid"
    chinese = _clean(data.get("chinese_name"))
    english = _clean(data.get("english_name"))
    if not chinese or len(chinese) > 500 or len(english) > 500:
        return {}, "structured_icd_name_invalid"
    return {"icd_code": code, "chinese_name": chinese, "english_name": english}, ""


def _validate_structured_correction(decision_type: str, value: Any) -> tuple[dict[str, Any], str]:
    if decision_type == "customer":
        return _validate_customer_structured_correction(value)
    if decision_type == "drug":
        return _validate_drug_structured_correction(value)
    if decision_type == "icd":
        return _validate_icd_structured_correction(value)
    return {}, "structured_fields_not_supported_for_decision_type"


def _effective_structured_fields(
    row: dict[str, str],
    requested_action: str,
    structured_corrected_fields: dict[str, Any],
) -> tuple[dict[str, Any], str, str]:
    """Resolve downstream fields without corrected-to-OCR fallback."""
    base, parse_error = _parse_json_object(row.get("structured_fields"))
    if parse_error:
        return {}, "", f"structured_fields_{parse_error}"
    schema = _clean(base.get("schema_version"))
    if not schema:
        return {}, "", ""
    if requested_action == "corrected":
        if schema.startswith(("prescription-drug-official-match-", "prescription-icd-official-match-")):
            if not structured_corrected_fields:
                return {}, "", "structured_corrected_fields_required_no_ocr_fallback"
            return dict(structured_corrected_fields), "structured_corrected_fields", ""
        return dict(structured_corrected_fields), "structured_corrected_fields", ""
    effective = base.get("effective_fields")
    if isinstance(effective, dict):
        return dict(effective), "official_matched_effective_fields", ""
    return {}, "", ""


def _hash_data(data: Any) -> str:
    return hashlib.sha256(_canonical_json(data).encode("utf-8")).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _write_json_atomic(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2, sort_keys=True, default=_json_default)
            fh.write("\n")
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def _queue_revision(path: Path) -> dict[str, Any]:
    stat = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return {
        "path": str(path),
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "sha256": digest.hexdigest(),
    }


def _row_hash(row: dict[str, str]) -> str:
    keys = [
        "decision_id",
        "_row_number",
        "decision_type",
        "candidate_id",
        "candidate_value",
        "review_decision",
        "corrected_value",
        "suggested_action",
        "existing_status",
        "confidence_level",
        "evidence_summary",
        "structured_fields",
        "structured_corrected_fields",
    ]
    return _hash_data({key: _clean(row.get(key)) for key in keys})


def _selected_rows_hash(rows: list[dict[str, str]]) -> str:
    return _hash_data([
        {
            "decision_id": row["decision_id"],
            "row_number": int(row["_row_number"]),
            "row_hash": _row_hash(row),
        }
        for row in rows
    ])


def _request_fingerprint(
    *,
    run_id: str,
    requested_action: str,
    decision_items: list[dict[str, Any]],
    corrected_values: dict[str, Any],
    review_note: str,
) -> str:
    normalized_items = []
    for item in decision_items:
        normalized_items.append({
            "decision_id": _clean(item.get("decision_id")),
            "row_number": _clean(item.get("row_number")),
            "decision_type": _clean(item.get("decision_type")),
            "candidate_id": _clean(item.get("candidate_id")),
            "expected_review_decision": _clean(item.get("expected_review_decision")),
        })
    normalized_corrections = {
        _clean(key): value
        for key, value in sorted((corrected_values or {}).items(), key=lambda pair: _clean(pair[0]))
    }
    return _hash_data({
        "run_id": run_id,
        "requested_action": requested_action,
        "decision_items": normalized_items,
        "corrected_values": normalized_corrections,
        "review_note": _clean(review_note),
    })


def _make_apply_run_id(idempotency_key: str, created_at: str) -> str:
    stamp = created_at.replace("-", "").replace(":", "").split(".", 1)[0]
    stamp = stamp.replace("+0000", "Z").replace("+00", "Z")
    key_hash = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()[:12]
    return f"ocr_apply_{_safe_name(stamp)}_{key_hash}"


def _make_preview_id(request_hash: str, created_at: str) -> str:
    stamp = created_at.replace("-", "").replace(":", "").split(".", 1)[0]
    stamp = stamp.replace("+0000", "Z").replace("+00", "Z")
    return f"ocr_preview_{_safe_name(stamp)}_{request_hash[:12]}"


def _make_decision_id(run_id: str, row_number: int, row: dict[str, str]) -> str:
    raw = "|".join(
        [
            run_id,
            str(row_number),
            _clean(row.get("decision_type")),
            _clean(row.get("candidate_id")),
            _clean(row.get("source_image_filename")),
            _clean(row.get("candidate_value")),
        ]
    )
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]
    return f"{run_id}:row:{row_number}:{digest}"


def _read_decision_queue(run_id: str) -> tuple[Path, list[str], list[dict[str, str]]]:
    path = decision_queue_path(run_id)
    if not path.exists():
        raise FileNotFoundError(f"找不到 import_decision_queue.csv: {path}")
    with path.open("r", newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        fieldnames = list(reader.fieldnames or [])
        rows = []
        for row_number, row in enumerate(reader, start=1):
            clean_row = {key: _clean(value) for key, value in row.items()}
            clean_row["_row_number"] = str(row_number)
            clean_row["decision_id"] = _make_decision_id(run_id, row_number, clean_row)
            rows.append(clean_row)
    return path, fieldnames, rows


def _write_decision_queue(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    writable_fields = [field for field in fieldnames if field and not field.startswith("_")]
    directory = path.parent
    fd, tmp_name = tempfile.mkstemp(prefix=".import_decision_queue.", suffix=".csv", dir=str(directory))
    try:
        with os.fdopen(fd, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=writable_fields)
            writer.writeheader()
            for row in rows:
                writer.writerow({field: row.get(field, "") for field in writable_fields})
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def _split_candidate_ids(candidate_id: str) -> list[int]:
    ids = []
    for match in STAGING_ID_RE.finditer(candidate_id or ""):
        value = int(match.group(1))
        if value not in ids:
            ids.append(value)
    return ids


def _passes_filters(row: dict[str, str], filters: dict[str, str] | None) -> bool:
    if not filters:
        return True
    for key in (
        "decision_type",
        "suggested_action",
        "confidence_level",
        "existing_status",
        "review_decision",
    ):
        wanted = _clean(filters.get(key))
        if not wanted or wanted == "all":
            continue
        actual = _clean(row.get(key))
        if key == "review_decision" and wanted == "pending":
            if actual:
                return False
            continue
        if actual != wanted:
            return False
    return True


def _summarize(rows: list[dict[str, str]]) -> dict[str, Any]:
    def counts(column: str) -> dict[str, int]:
        counter = Counter(_clean(row.get(column)) or "<blank>" for row in rows)
        return dict(sorted(counter.items()))

    return {
        "total": len(rows),
        "decision_type_counts": counts("decision_type"),
        "suggested_action_counts": counts("suggested_action"),
        "existing_status_counts": counts("existing_status"),
        "confidence_level_counts": counts("confidence_level"),
        "review_decision_counts": counts("review_decision"),
    }


def load_import_decision_items(
    run_id: str,
    *,
    filters: dict[str, str] | None = None,
) -> ToolResult:
    """Load import decision queue rows for the LIFF review page."""
    try:
        path, _fieldnames, rows = _read_decision_queue(run_id)
    except (FileNotFoundError, ValueError) as exc:
        return ToolResult.fail(str(exc))

    filtered = [row for row in rows if _passes_filters(row, filters)]
    items = []
    for row in filtered:
        item = {key: value for key, value in row.items() if not key.startswith("_")}
        structured, structured_error = _parse_json_object(item.get("structured_fields"))
        structured_corrected, structured_corrected_error = _parse_json_object(
            item.get("structured_corrected_fields")
        )
        item["structured_fields"] = structured
        item["structured_corrected_fields"] = structured_corrected
        item["structured_fields_error"] = structured_error or structured_corrected_error
        item["row_number"] = int(row["_row_number"])
        item["disabled"] = bool(_clean(row.get("review_decision")))
        item["disable_reason"] = "already_reviewed" if item["disabled"] else ""
        items.append(item)

    return ToolResult.success(
        data={
            "run_id": run_id,
            "queue_path": str(path),
            "items": items,
            "summary": _summarize(rows),
            "filtered_summary": _summarize(filtered),
        }
    )


def _fetch_staging_rows(session, ids: list[int]) -> dict[int, dict[str, Any]]:
    if not ids:
        return {}
    stmt = (
        text(
            """
            SELECT
                id,
                run_id,
                image_filename,
                candidate_kind,
                candidate_value,
                normalized_candidate_value,
                drug_code_candidate,
                icd10_candidate,
                review_status,
                review_decision,
                review_note
            FROM prescription_ocr_candidate_staging
            WHERE id IN :ids
            """
        )
        .bindparams(bindparam("ids", expanding=True))
    )
    rows = session.execute(stmt, {"ids": ids}).mappings().all()
    return {int(row["id"]): dict(row) for row in rows}


def _table_columns(session, table_name: str) -> set[str]:
    rows = session.execute(
        text(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = :table_name
            """
        ),
        {"table_name": table_name},
    ).fetchall()
    return {row[0] for row in rows}


def _drug_code_exists(session, code: str) -> bool | None:
    code = _clean(code).upper()
    if not code:
        return None
    cols = _table_columns(session, "drug_items")
    if not cols:
        return None
    checks = []
    params = {"code": code, "norm": re.sub(r"[^A-Z0-9]+", "", code)}
    if "nhi_drug_code" in cols:
        checks.append("UPPER(COALESCE(nhi_drug_code, '')) = :code")
    if "drug_code" in cols:
        checks.append("UPPER(COALESCE(drug_code, '')) = :code")
    if "normalized_drug_code" in cols:
        checks.append("UPPER(COALESCE(normalized_drug_code, '')) = :norm")
    if not checks:
        return None
    sql = "SELECT 1 FROM drug_items WHERE " + " OR ".join(checks) + " LIMIT 1"
    return session.execute(text(sql), params).first() is not None


def _icd_code_exists(session, code: str) -> bool | None:
    code = _clean(code).upper()
    if not code:
        return None
    cols = _table_columns(session, "diagnosis_codes")
    if not cols:
        return None
    checks = []
    norm = re.sub(r"[^A-Z0-9]+", "", code)
    params = {"code": code, "norm": norm}
    if "icd10_code" in cols:
        checks.append("UPPER(COALESCE(icd10_code, '')) = :code")
        checks.append("REGEXP_REPLACE(UPPER(COALESCE(icd10_code, '')), '[^A-Z0-9]', '', 'g') = :norm")
    if "icd9_code" in cols:
        checks.append("UPPER(COALESCE(icd9_code, '')) = :code")
        checks.append("REGEXP_REPLACE(UPPER(COALESCE(icd9_code, '')), '[^A-Z0-9]', '', 'g') = :norm")
    if not checks:
        return None
    sql = "SELECT 1 FROM diagnosis_codes WHERE " + " OR ".join(checks) + " LIMIT 1"
    return session.execute(text(sql), params).first() is not None


def _planned_staging_status(action: str, row: dict[str, str]) -> str:
    suggested = _clean(row.get("suggested_action"))
    if action == "approve" and suggested.startswith("skip_"):
        return "duplicate"
    return STAGING_REVIEW_STATUS_BY_ACTION[action]


def _validate_row(
    *,
    session,
    row: dict[str, str],
    requested_action: str,
    corrected_value: str,
    structured_corrected_fields: dict[str, Any],
    item_review_note: str,
    bulk_review_note: str,
) -> dict[str, Any]:
    decision_type = _clean(row.get("decision_type"))
    candidate_id = _clean(row.get("candidate_id"))
    candidate_value = _clean(row.get("candidate_value"))
    suggested_action = _clean(row.get("suggested_action"))
    confidence_level = _clean(row.get("confidence_level"))
    existing_status = _clean(row.get("existing_status"))
    effective_structured_fields, effective_source, effective_error = _effective_structured_fields(
        row, requested_action, structured_corrected_fields
    )

    result = {
        "decision_id": row["decision_id"],
        "row_number": int(row["_row_number"]),
        "decision_type": decision_type,
        "candidate_id": candidate_id,
        "candidate_value": candidate_value,
        "result": "success",
        "reason": "review_decision_recordable",
        "previous_review_decision": _clean(row.get("review_decision")),
        "new_review_decision": requested_action,
        "previous_review_status": "",
        "new_review_status": "",
        "staging_ids": [],
        "staging_status": "",
        "structured_corrected_fields": structured_corrected_fields,
        "effective_structured_fields": effective_structured_fields,
        "effective_structured_fields_source": effective_source,
    }

    if decision_type not in DECISION_TYPES:
        result.update(result="failed", reason="invalid_decision_type")
        return result
    if _clean(row.get("review_decision")):
        result.update(result="skipped", reason="already_reviewed")
        return result
    if effective_error:
        result.update(result="failed", reason=effective_error)
        return result
    if requested_action == "corrected" and not corrected_value and not structured_corrected_fields:
        result.update(result="failed", reason="corrected_requires_value")
        return result
    if requested_action == "approve":
        if suggested_action in {"needs_review", "defer_relation"} or existing_status == "not_applicable":
            result.update(result="skipped", reason="action_not_applicable")
            return result
        if decision_type in {"drug", "icd"} and confidence_level != "high":
            result.update(result="skipped", reason="confidence_not_bulk_approvable")
            return result
        if decision_type == "drug_diagnosis_link" and suggested_action not in {
            "create_drug_diagnosis_link",
            "skip_relation_existing",
        }:
            result.update(result="skipped", reason="relation_not_approvable_in_v1")
            return result

    if decision_type not in {"drug", "icd"}:
        result["reason"] = f"{decision_type}_review_decision_only_no_formal_write"
        return result

    if OFFICIAL_MATCH_ID_RE.fullmatch(candidate_id):
        result["reason"] = "official_match_review_decision_recordable_no_formal_write"
        return result

    staging_ids = _split_candidate_ids(candidate_id)
    result["staging_ids"] = staging_ids
    if not staging_ids:
        result.update(result="failed", reason="missing_staging_ids")
        return result
    if session is None:
        result.update(result="failed", reason="database_session_required_for_staging_validation")
        return result

    try:
        staging_rows = _fetch_staging_rows(session, staging_ids)
    except SQLAlchemyError as exc:
        result.update(result="failed", reason=f"staging_lookup_failed: {exc}")
        return result

    missing = [staging_id for staging_id in staging_ids if staging_id not in staging_rows]
    if missing:
        result.update(result="failed", reason=f"staging_ids_missing:{','.join(map(str, missing))}")
        return result
    non_pending = [
        staging_id for staging_id, staging_row in staging_rows.items()
        if _clean(staging_row.get("review_status")) != "pending"
    ]
    result["previous_review_status"] = " | ".join(
        _clean(staging_rows[staging_id].get("review_status")) for staging_id in staging_ids
    )
    if non_pending:
        result.update(result="skipped", reason=f"staging_not_pending:{','.join(map(str, non_pending))}")
        return result

    if requested_action == "approve" and suggested_action.startswith("insert_"):
        if decision_type == "drug":
            exists = _drug_code_exists(session, candidate_value)
            if exists is True:
                result.update(result="skipped", reason="target_already_exists_drug_items")
                return result
        elif decision_type == "icd":
            exists = _icd_code_exists(session, candidate_value)
            if exists is True:
                result.update(result="skipped", reason="target_already_exists_diagnosis_codes")
                return result

    status = _planned_staging_status(requested_action, row)
    result["new_review_status"] = status
    result["staging_status"] = status
    result["reason"] = "staging_review_status_recordable"
    return result


def _update_staging_rows(
    *,
    session,
    staging_ids: list[int],
    review_status: str,
    review_decision: str,
    review_note: str,
) -> None:
    if not staging_ids:
        return
    stmt = (
        text(
            """
            UPDATE prescription_ocr_candidate_staging
            SET review_status = :review_status,
                review_decision = :review_decision,
                review_note = :review_note,
                updated_at = now()
            WHERE id IN :ids
              AND review_status = 'pending'
            """
        )
        .bindparams(bindparam("ids", expanding=True))
    )
    session.execute(
        stmt,
        {
            "review_status": review_status,
            "review_decision": review_decision,
            "review_note": review_note or None,
            "ids": staging_ids,
        },
    )


def _batch_limit(batch_mode: str, requested_action: str) -> int:
    base = DEV_TEST_BATCH_LIMIT if batch_mode == "dev_test" else PRODUCTION_BATCH_LIMIT
    if requested_action == "corrected":
        return min(base, CORRECTED_BATCH_LIMIT)
    return base


def _validate_batch_rules(
    *,
    rows: list[dict[str, str]],
    requested_action: str,
    batch_mode: str,
) -> str:
    limit = _batch_limit(batch_mode, requested_action)
    if len(rows) > limit:
        return f"batch_size_exceeded:{len(rows)}>{limit}"

    if requested_action == "approve" and len(rows) > 1:
        for row in rows:
            decision_type = _clean(row.get("decision_type"))
            suggested_action = _clean(row.get("suggested_action"))
            confidence_level = _clean(row.get("confidence_level"))
            if suggested_action in {"needs_review", "defer_relation"} or confidence_level == "manual_review":
                return "bulk_approve_manual_review_not_allowed"
            if decision_type == "customer":
                return "bulk_approve_customer_not_allowed"
            if decision_type == "drug_diagnosis_link":
                return "bulk_approve_relation_not_allowed_in_v1"
            if decision_type in {"drug", "icd"} and confidence_level != "high":
                return "bulk_approve_requires_high_confidence"
    return ""


def _idempotency_index_path(run_id: str) -> Path:
    return _apply_runs_dir(run_id) / "idempotency_index.json"


def _idempotency_lock_path(run_id: str, idempotency_key: str) -> Path:
    key_hash = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()
    return _apply_runs_dir(run_id) / f"{key_hash}.lock"


def _load_idempotency_index(run_id: str) -> dict[str, Any]:
    path = _idempotency_index_path(run_id)
    if not path.exists():
        return {"entries": {}}
    return _read_json(path)


def _write_idempotency_index(run_id: str, index: dict[str, Any]) -> None:
    _write_json_atomic(_idempotency_index_path(run_id), index)


def _idempotency_entry(index: dict[str, Any], idempotency_key: str) -> dict[str, Any] | None:
    key_hash = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()
    return (index.get("entries") or {}).get(key_hash)


def _set_idempotency_entry(run_id: str, idempotency_key: str, entry: dict[str, Any]) -> None:
    index = _load_idempotency_index(run_id)
    key_hash = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()
    index.setdefault("entries", {})[key_hash] = entry
    _write_idempotency_index(run_id, index)


def _acquire_idempotency_lock(run_id: str, idempotency_key: str) -> Path:
    path = _idempotency_lock_path(run_id, idempotency_key)
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    fd = os.open(str(path), flags)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(_now_iso())
        fh.write("\n")
    return path


def _staging_snapshot(session, results: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    ids: list[int] = []
    for result in results:
        for staging_id in result.get("staging_ids") or []:
            if staging_id not in ids:
                ids.append(staging_id)
    if not ids or session is None:
        return {}
    return _fetch_staging_rows(session, ids)


def _queue_snapshot(rows_by_id: dict[str, dict[str, str]], decision_id: str) -> dict[str, str]:
    row = rows_by_id.get(decision_id) or {}
    return {
        "review_decision": _clean(row.get("review_decision")),
        "corrected_value": _clean(row.get("corrected_value")),
        "review_note": _clean(row.get("review_note")),
        "candidate_value": _clean(row.get("candidate_value")),
        "display_name": _clean(row.get("display_name")),
        "evidence_summary": _clean(row.get("evidence_summary")),
        "structured_fields": _clean(row.get("structured_fields")),
        "structured_corrected_fields": _clean(row.get("structured_corrected_fields")),
    }


def _audit_items(
    *,
    results: list[dict[str, Any]],
    rows_before: dict[str, dict[str, str]],
    rows_after: dict[str, dict[str, str]],
    staging_before: dict[int, dict[str, Any]],
    staging_after: dict[int, dict[str, Any]],
    requested_action: str,
) -> list[dict[str, Any]]:
    items = []
    for result in results:
        decision_id = _clean(result.get("decision_id"))
        before_row = rows_before.get(decision_id) or {}
        after_row = rows_after.get(decision_id) or {}
        staging_ids = list(result.get("staging_ids") or [])
        staging_before_values = {
            str(staging_id): staging_before.get(staging_id, {})
            for staging_id in staging_ids
        }
        staging_after_values = {
            str(staging_id): staging_after.get(staging_id, {})
            for staging_id in staging_ids
        }
        items.append({
            "decision_id": decision_id,
            "row_number": result.get("row_number"),
            "decision_type": result.get("decision_type"),
            "candidate_id": result.get("candidate_id"),
            "candidate_value": result.get("candidate_value"),
            "requested_action": requested_action,
            "result": result.get("result"),
            "reason": result.get("reason"),
            "before": {
                "queue": _queue_snapshot(rows_before, decision_id),
                "staging": staging_before_values,
            },
            "after": {
                "queue": _queue_snapshot(rows_after, decision_id),
                "staging": staging_after_values,
            },
        })
    return items


def _save_preview_artifact(
    *,
    run_id: str,
    request_hash: str,
    requested_action: str,
    decision_items: list[dict[str, Any]],
    corrected_values: dict[str, Any],
    review_note: str,
    user_id: str | None,
    queue_revision: dict[str, Any],
    selected_rows_hash: str,
    result_data: dict[str, Any],
) -> dict[str, Any]:
    created_at = _now_iso()
    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=PREVIEW_EXPIRES_MINUTES)).isoformat()
    preview_id = _make_preview_id(request_hash, created_at)
    preview_path = _apply_previews_dir(run_id) / f"{preview_id}.json"
    preview_result_hash = _hash_data({
        "success_count": result_data.get("success_count"),
        "skipped_count": result_data.get("skipped_count"),
        "failed_count": result_data.get("failed_count"),
        "per_item_result": result_data.get("per_item_result"),
    })
    artifact = {
        "preview_id": preview_id,
        "run_id": run_id,
        "request_hash": request_hash,
        "requested_action": requested_action,
        "decision_items": decision_items,
        "corrected_values": corrected_values,
        "review_note": review_note,
        "reviewer": user_id or "",
        "created_at": created_at,
        "expires_at": expires_at,
        "queue_revision": queue_revision,
        "selected_rows_hash": selected_rows_hash,
        "preview_result_hash": preview_result_hash,
        "result": result_data,
    }
    _write_json_atomic(preview_path, artifact)
    return {
        "preview_id": preview_id,
        "preview_path": str(preview_path),
        "preview_expires_at": expires_at,
        "queue_revision": queue_revision,
        "selected_rows_hash": selected_rows_hash,
        "preview_result_hash": preview_result_hash,
    }


def _validate_preview_gate(
    *,
    run_id: str,
    preview_id: str,
    request_hash: str,
    queue_revision: dict[str, Any],
    selected_rows_hash: str,
    preview_result_hash: str,
    allow_skipped: bool,
) -> str:
    preview_id = _safe_name(preview_id)
    if not preview_id:
        return "preview_required"
    path = _apply_previews_dir(run_id) / f"{preview_id}.json"
    if not path.exists():
        return "preview_not_found"
    try:
        artifact = _read_json(path)
    except (OSError, json.JSONDecodeError):
        return "preview_artifact_invalid"

    expires_at = _clean(artifact.get("expires_at"))
    if expires_at:
        try:
            expires_dt = datetime.fromisoformat(expires_at)
            if datetime.now(timezone.utc) > expires_dt:
                return "preview_expired"
        except ValueError:
            return "preview_expiration_invalid"

    if _clean(artifact.get("request_hash")) != request_hash:
        return "preview_request_changed"
    if artifact.get("queue_revision") != queue_revision:
        return "preview_queue_revision_changed"
    if _clean(artifact.get("selected_rows_hash")) != selected_rows_hash:
        return "preview_selected_rows_changed"
    if _clean(artifact.get("preview_result_hash")) != _clean(preview_result_hash):
        return "preview_result_hash_mismatch"

    result = artifact.get("result") or {}
    if int(result.get("failed_count") or 0) > 0:
        return "preview_had_failures"
    if int(result.get("skipped_count") or 0) > 0 and not allow_skipped:
        return "preview_skipped_requires_confirmation"
    return ""


def apply_import_review_decisions(
    *,
    session=None,
    run_id: str,
    requested_action: str,
    decision_items: list[dict[str, Any]],
    corrected_values: dict[str, Any] | None = None,
    review_note: str = "",
    idempotency_key: str = "",
    preview_id: str = "",
    queue_revision: dict[str, Any] | None = None,
    selected_rows_hash: str = "",
    preview_result_hash: str = "",
    accept_skipped: bool = False,
    batch_mode: str = "production",
    user_id: str | None = None,
    user_name: str | None = None,
    dry_run: bool = True,
    via: str = "unknown",
) -> ToolResult:
    """Preview or apply OCR import review decisions.

    V1 writes only:
    - review/import_decision_queue.csv review_decision/corrected_value,
      structured_corrected_fields/review_note
    - prescription_ocr_candidate_staging review_status/review_decision/review_note

    It never writes customers, drug_items, diagnosis_codes, or
    drug_diagnosis_links.
    """
    requested_action = _clean(requested_action).lower()
    if requested_action not in REQUESTED_ACTIONS:
        return ToolResult.fail("requested_action 不支援")
    if not isinstance(decision_items, list) or not decision_items:
        return ToolResult.fail("decision_items 不可空")

    corrected_values = corrected_values or {}
    bulk_review_note = _clean(review_note)
    batch_mode = "dev_test" if batch_mode == "dev_test" else "production"
    idempotency_key = _clean(idempotency_key)
    request_hash = _request_fingerprint(
        run_id=run_id,
        requested_action=requested_action,
        decision_items=decision_items,
        corrected_values=corrected_values,
        review_note=bulk_review_note,
    )

    apply_run_id = ""
    apply_started_at = ""
    lock_path: Path | None = None
    idempotency_result_path = ""

    if not dry_run:
        if not idempotency_key:
            return ToolResult.fail("idempotency_key 必填")
        try:
            index = _load_idempotency_index(run_id)
            existing_entry = _idempotency_entry(index, idempotency_key)
            if existing_entry:
                if _clean(existing_entry.get("request_hash")) != request_hash:
                    return ToolResult.fail("idempotency_conflict")
                status = _clean(existing_entry.get("status"))
                if status == "completed":
                    result_path = Path(_clean(existing_entry.get("result_path")))
                    if not result_path.exists():
                        return ToolResult.fail("idempotency_result_missing")
                    saved = _read_json(result_path)
                    saved["idempotency_replay"] = True
                    return ToolResult.success(data=saved)
                if status == "started":
                    return ToolResult.fail("apply_in_progress")
                return ToolResult.fail(f"idempotency_previous_status:{status or 'unknown'}")
        except Exception as exc:
            return ToolResult.fail(f"idempotency_state_invalid:{exc}")

    try:
        path, fieldnames, rows = _read_decision_queue(run_id)
    except (FileNotFoundError, ValueError) as exc:
        return ToolResult.fail(str(exc))

    rows_by_id = {row["decision_id"]: row for row in rows}
    selected_rows = [rows_by_id[_clean(item.get("decision_id"))] for item in decision_items if _clean(item.get("decision_id")) in rows_by_id]
    batch_error = _validate_batch_rules(
        rows=selected_rows,
        requested_action=requested_action,
        batch_mode=batch_mode,
    )
    if batch_error:
        return ToolResult.fail(batch_error)

    current_queue_revision = _queue_revision(path)
    current_selected_rows_hash = _selected_rows_hash(selected_rows)

    results: list[dict[str, Any]] = []
    row_updates: dict[str, dict[str, str]] = {}

    for item in decision_items:
        decision_id = _clean(item.get("decision_id"))
        row = rows_by_id.get(decision_id)
        if not row:
            results.append({
                "decision_id": decision_id,
                "result": "failed",
                "reason": "decision_item_not_found_or_stale",
            })
            continue
        expected = _clean(item.get("expected_review_decision"))
        actual = _clean(row.get("review_decision"))
        if expected and expected != actual:
            results.append({
                "decision_id": decision_id,
                "row_number": int(row["_row_number"]),
                "result": "skipped",
                "reason": "stale_review_decision",
                "previous_review_decision": actual,
            })
            continue

        correction = corrected_values.get(decision_id) or {}
        if isinstance(correction, str):
            corrected_value = correction.strip()
            item_note = ""
        else:
            corrected_value = _clean(correction.get("corrected_value"))
            item_note = _clean(correction.get("review_note"))
        decision_type = _clean(row.get("decision_type"))
        raw_structured = correction.get("structured_fields") if isinstance(correction, dict) else None
        structured_corrected_fields: dict[str, Any] = {}
        if raw_structured:
            structured_corrected_fields, structured_error = _validate_structured_correction(decision_type, raw_structured)
            if structured_error:
                results.append({
                    "decision_id": decision_id,
                    "row_number": int(row["_row_number"]),
                    "decision_type": _clean(row.get("decision_type")),
                    "candidate_id": _clean(row.get("candidate_id")),
                    "candidate_value": _clean(row.get("candidate_value")),
                    "result": "failed",
                    "reason": structured_error,
                })
                continue

        validation = _validate_row(
            session=session,
            row=row,
            requested_action=requested_action,
            corrected_value=corrected_value,
            structured_corrected_fields=structured_corrected_fields,
            item_review_note=item_note,
            bulk_review_note=bulk_review_note,
        )
        results.append(validation)
        if validation.get("result") == "success":
            row_updates[decision_id] = {
                "review_decision": requested_action,
                "corrected_value": corrected_value,
                "structured_corrected_fields": (
                    _canonical_json(structured_corrected_fields) if structured_corrected_fields else ""
                ),
                "review_note": item_note or bulk_review_note,
            }

    success_count = sum(1 for item in results if item.get("result") == "success")
    skipped_count = sum(1 for item in results if item.get("result") == "skipped")
    failed_count = sum(1 for item in results if item.get("result") == "failed")

    result_data = {
        "run_id": run_id,
        "queue_path": str(path),
        "requested_action": requested_action,
        "dry_run": bool(dry_run),
        "requested_count": len(decision_items),
        "success_count": success_count,
        "skipped_count": skipped_count,
        "failed_count": failed_count,
        "per_item_result": results,
        "formal_tables_touched": "none",
        "batch_mode": batch_mode,
        "max_batch_size": _batch_limit(batch_mode, requested_action),
        "request_hash": request_hash,
        "queue_revision": current_queue_revision,
        "selected_rows_hash": current_selected_rows_hash,
    }

    if dry_run:
        preview_meta = _save_preview_artifact(
            run_id=run_id,
            request_hash=request_hash,
            requested_action=requested_action,
            decision_items=decision_items,
            corrected_values=corrected_values,
            review_note=bulk_review_note,
            user_id=user_id,
            queue_revision=current_queue_revision,
            selected_rows_hash=current_selected_rows_hash,
            result_data=result_data,
        )
        result_data.update(preview_meta)
        return ToolResult.success(data=result_data)

    preview_error = _validate_preview_gate(
        run_id=run_id,
        preview_id=preview_id,
        request_hash=request_hash,
        queue_revision=current_queue_revision,
        selected_rows_hash=current_selected_rows_hash,
        preview_result_hash=preview_result_hash,
        allow_skipped=accept_skipped,
    )
    if preview_error:
        return ToolResult.fail(preview_error)
    if failed_count:
        return ToolResult.fail("apply_validation_failed")
    if skipped_count and not accept_skipped:
        return ToolResult.fail("apply_skipped_requires_confirmation")

    try:
        lock_path = _acquire_idempotency_lock(run_id, idempotency_key)
        apply_started_at = _now_iso()
        apply_run_id = _make_apply_run_id(idempotency_key, apply_started_at)
        run_dir = _apply_runs_dir(run_id)
        idempotency_result_path = str(run_dir / f"{apply_run_id}.result.json")
        _set_idempotency_entry(
            run_id,
            idempotency_key,
            {
                "idempotency_key_hash": hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest(),
                "request_hash": request_hash,
                "apply_run_id": apply_run_id,
                "status": "started",
                "created_at": apply_started_at,
                "completed_at": "",
                "reviewer": user_id or "",
                "result_path": idempotency_result_path,
            },
        )
    except FileExistsError:
        return ToolResult.fail("apply_in_progress")
    except Exception as exc:
        return ToolResult.fail(f"idempotency_state_invalid:{exc}")

    backup_path = ""
    audit_path = ""
    staging_before: dict[int, dict[str, Any]] = {}
    rows_before_by_id = {decision_id: dict(row) for decision_id, row in rows_by_id.items()}

    if success_count:
        try:
            if "structured_corrected_fields" not in fieldnames:
                fieldnames.append("structured_corrected_fields")
            reviewed_at = _now_iso()
            backup_path_obj = _backup_dir(run_id) / f"import_decision_queue.{apply_run_id}.csv"
            shutil.copy2(path, backup_path_obj)
            backup_path = str(backup_path_obj)
            staging_before = _staging_snapshot(session, results)

            for result in results:
                if result.get("result") != "success":
                    continue
                decision_id = result.get("decision_id")
                update = row_updates.get(decision_id, {})
                note = update.get("review_note") or ""
                audit_note = (
                    f"{note}\n"
                    f"reviewed_by={user_id or ''}; via={via}; reviewed_at={reviewed_at}; apply_run_id={apply_run_id}"
                ).strip()
                if result.get("staging_ids"):
                    _update_staging_rows(
                        session=session,
                        staging_ids=list(result["staging_ids"]),
                        review_status=result.get("staging_status") or "unclear",
                        review_decision=requested_action,
                        review_note=audit_note,
                    )
                row = rows_by_id.get(decision_id)
                if row is not None:
                    row["review_decision"] = requested_action
                    row["corrected_value"] = update.get("corrected_value", "")
                    row["structured_corrected_fields"] = update.get("structured_corrected_fields", "")
                    row["review_note"] = audit_note

            _write_decision_queue(path, fieldnames, rows)
            if session is not None:
                session.commit()

            _after_path, _after_fieldnames, rows_after = _read_decision_queue(run_id)
            rows_after_by_id = {row["decision_id"]: row for row in rows_after}
            staging_after = _staging_snapshot(session, results)
            completed_at = _now_iso()
            audit = {
                "apply_run_id": apply_run_id,
                "run_id": run_id,
                "idempotency_key_hash": hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest(),
                "request_hash": request_hash,
                "requested_action": requested_action,
                "reviewer": {
                    "line_user_id": user_id or "",
                    "line_user_name": user_name or "",
                },
                "started_at": apply_started_at,
                "completed_at": completed_at,
                "selected_count": len(decision_items),
                "success_count": success_count,
                "skipped_count": skipped_count,
                "failed_count": failed_count,
                "formal_tables_touched": "none",
                "queue_backup_path": backup_path,
                "items": _audit_items(
                    results=results,
                    rows_before=rows_before_by_id,
                    rows_after=rows_after_by_id,
                    staging_before=staging_before,
                    staging_after=staging_after,
                    requested_action=requested_action,
                ),
            }
            audit_path_obj = _apply_runs_dir(run_id) / f"{apply_run_id}.audit.json"
            _write_json_atomic(audit_path_obj, audit)
            audit_path = str(audit_path_obj)

            result_data.update({
                "apply_run_id": apply_run_id,
                "idempotency_key_hash": hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest(),
                "queue_backup_path": backup_path,
                "audit_path": audit_path,
            })
            _write_json_atomic(Path(idempotency_result_path), result_data)
            _set_idempotency_entry(
                run_id,
                idempotency_key,
                {
                    "idempotency_key_hash": hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest(),
                    "request_hash": request_hash,
                    "apply_run_id": apply_run_id,
                    "status": "completed",
                    "created_at": apply_started_at,
                    "completed_at": completed_at,
                    "reviewer": user_id or "",
                    "result_path": idempotency_result_path,
                },
            )
        except Exception as exc:
            if session is not None:
                session.rollback()
            if apply_run_id:
                failed_data = {**result_data, "apply_run_id": apply_run_id, "error": f"apply failed: {exc}"}
                if idempotency_result_path:
                    _write_json_atomic(Path(idempotency_result_path), failed_data)
                _set_idempotency_entry(
                    run_id,
                    idempotency_key,
                    {
                        "idempotency_key_hash": hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest(),
                        "request_hash": request_hash,
                        "apply_run_id": apply_run_id,
                        "status": "failed",
                        "created_at": apply_started_at,
                        "completed_at": _now_iso(),
                        "reviewer": user_id or "",
                        "result_path": idempotency_result_path,
                    },
            )
            return ToolResult.fail(f"apply failed: {exc}")

    if not success_count:
        completed_at = _now_iso()
        audit = {
            "apply_run_id": apply_run_id,
            "run_id": run_id,
            "idempotency_key_hash": hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest(),
            "request_hash": request_hash,
            "requested_action": requested_action,
            "reviewer": {
                "line_user_id": user_id or "",
                "line_user_name": user_name or "",
            },
            "started_at": apply_started_at,
            "completed_at": completed_at,
            "selected_count": len(decision_items),
            "success_count": success_count,
            "skipped_count": skipped_count,
            "failed_count": failed_count,
            "formal_tables_touched": "none",
            "queue_backup_path": "",
            "items": _audit_items(
                results=results,
                rows_before=rows_before_by_id,
                rows_after=rows_before_by_id,
                staging_before={},
                staging_after={},
                requested_action=requested_action,
            ),
        }
        audit_path_obj = _apply_runs_dir(run_id) / f"{apply_run_id}.audit.json"
        _write_json_atomic(audit_path_obj, audit)
        result_data.update({
            "apply_run_id": apply_run_id,
            "idempotency_key_hash": hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest(),
            "queue_backup_path": "",
            "audit_path": str(audit_path_obj),
        })
        _write_json_atomic(Path(idempotency_result_path), result_data)
        _set_idempotency_entry(
            run_id,
            idempotency_key,
            {
                "idempotency_key_hash": hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest(),
                "request_hash": request_hash,
                "apply_run_id": apply_run_id,
                "status": "completed",
                "created_at": apply_started_at,
                "completed_at": completed_at,
                "reviewer": user_id or "",
                "result_path": idempotency_result_path,
            },
        )

    return ToolResult.success(data=result_data)
