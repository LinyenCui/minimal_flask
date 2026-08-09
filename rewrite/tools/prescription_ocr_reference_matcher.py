"""Official-reference matching and queue building for Prescription OCR review.

This module is artifact-only.  It consumes the existing structured OCR and
customer matching artifacts, matches Drug/ICD candidates against the pinned
NHI snapshots, and writes the existing ``import_decision_queue.csv`` contract.
It never opens a database connection and never writes formal tables.

The normalization and source loaders deliberately reuse the already-verified
staging importer implementation.  This keeps the pre-LIFF decisions aligned
with the evidence rules used by the historical Prescription OCR runs.
"""
from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import os
import re
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[2]
STAGING_MATCHER_PATH = Path(
    os.environ.get(
        "PRESCRIPTION_OCR_STAGING_MATCHER_PATH",
        str(REPO_ROOT / "scripts" / "import_prescription_ocr_candidates_staging.py"),
    )
)
DEFAULT_DRUG_REFERENCE = REPO_ROOT / "reference_data/drug/raw/nhi_drug_payment_20260522.csv"
DEFAULT_ICD_REFERENCE = REPO_ROOT / "reference_data/icd/nhi_2023_icd10_cm_pcs.xlsx"
DRUG_REFERENCE_SHA256 = "2968cacc020ebcddcf53749cf501ab4f5d3ca86217b6fdf2f1d9d6455cb6d90d"
ICD_REFERENCE_SHA256 = "1bf34d1f92930f299349607991a11220a5c2b35e5c9b80518204c3e2fc6533cd"

QUEUE_FIELDS = [
    "source_image_filename",
    "decision_type",
    "candidate_id",
    "candidate_value",
    "display_name",
    "existing_status",
    "existing_target",
    "suggested_action",
    "evidence_summary",
    "confidence_level",
    "review_decision",
    "corrected_value",
    "review_note",
    "structured_fields",
    "structured_corrected_fields",
]

DRUG_MATCH_FIELDS = [
    "source_run_id",
    "source_image_filename",
    "ocr_drug_name",
    "ocr_drug_code",
    "ocr_strength",
    "normalized_drug_name",
    "matched_official_drug_code",
    "official_drug_name",
    "official_drug_name_zh",
    "official_ingredient",
    "official_strength_specification",
    "match_basis",
    "match_status",
    "match_confidence",
    "ambiguity",
    "warnings",
    "ocr_evidence",
    "official_evidence",
    "reference_source",
    "reference_path",
    "reference_sha256",
    "structured_fields",
]

ICD_MATCH_FIELDS = [
    "source_run_id",
    "source_image_filename",
    "ocr_diagnosis_text",
    "ocr_icd_code",
    "normalized_icd",
    "matched_official_icd_code",
    "official_chinese_name",
    "official_english_name",
    "match_basis",
    "match_status",
    "match_confidence",
    "ambiguity",
    "warnings",
    "ocr_evidence",
    "official_evidence",
    "reference_source",
    "reference_path",
    "reference_sha256",
    "structured_fields",
]

RELATION_FIELDS = [
    "source_run_id",
    "source_image_filename",
    "drug_code",
    "drug_name",
    "icd_code",
    "diagnosis_name",
    "relation_basis",
    "classification",
    "formal_apply_allowed",
    "evidence_summary",
    "structured_fields",
]


def _load_verified_matcher():
    if not STAGING_MATCHER_PATH.exists():
        raise FileNotFoundError(f"verified staging matcher missing: {STAGING_MATCHER_PATH}")
    spec = importlib.util.spec_from_file_location("prescription_ocr_verified_staging_matcher", STAGING_MATCHER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load verified staging matcher: {STAGING_MATCHER_PATH}")
    module = importlib.util.module_from_spec(spec)
    # dataclasses resolves the defining module through sys.modules.
    import sys

    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_reference(path: Path, expected_sha256: str, label: str) -> str:
    if not path.exists():
        raise FileNotFoundError(f"{label} reference missing: {path}")
    actual = _sha256(path)
    if path.resolve() in {DEFAULT_DRUG_REFERENCE.resolve(), DEFAULT_ICD_REFERENCE.resolve()} and actual != expected_sha256:
        raise ValueError(f"{label} reference hash mismatch: expected={expected_sha256} actual={actual}")
    return actual


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv_atomic(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            for row in rows:
                writer.writerow({field: row.get(field, "") for field in fields})
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _split(value: str) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for part in re.split(r"\s*\|\s*|\n+", value or ""):
        clean = " ".join(part.split()).strip(" ,，;；")
        key = clean.casefold()
        if clean and key not in seen:
            result.append(clean)
            seen.add(key)
    return result


def _unique(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        clean = " ".join(str(value or "").split()).strip()
        key = clean.casefold()
        if clean and key not in seen:
            result.append(clean)
            seen.add(key)
    return result


def _best_text(values: Iterable[str]) -> str:
    candidates = _unique(values)
    plausible = [
        value
        for value in candidates
        if re.search(r"[A-Za-z\u4e00-\u9fff]", value)
        and not re.fullmatch(r"[\d\s./-]+", value)
        and len(value) <= 140
    ]
    if not plausible:
        return candidates[0] if candidates else ""
    return max(plausible, key=lambda value: (len(re.findall(r"[A-Za-z\u4e00-\u9fff]+", value)), len(value)))


def _evidence_snippets(rows: list[dict[str, str]], needles: Iterable[str]) -> list[str]:
    wanted = [needle for needle in _unique(needles) if len(needle) >= 3]
    snippets: list[str] = []
    for row in rows:
        line = " ".join((row.get("line_text") or "").split())
        if line and (not wanted or any(needle.casefold() in line.casefold() for needle in wanted)):
            snippets.append(line[:360])
        raw = row.get("raw_text") or ""
        for raw_line in raw.splitlines():
            clean = " ".join(raw_line.split())
            if clean and any(needle.casefold() in clean.casefold() for needle in wanted):
                snippets.append(clean[:360])
                break
    return _unique(snippets)[:4]


def _drug_product_key(record: dict[str, Any]) -> tuple[str, ...]:
    payload = record.get("payload", {})
    return (
        record.get("drug_code", ""),
        record.get("english_name", ""),
        record.get("chinese_name", ""),
        record.get("ingredient", ""),
        payload.get("規格量", ""),
        payload.get("規格單位", ""),
    )


def _distinct_drug_products(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    by_key: dict[tuple[str, ...], dict[str, Any]] = {}
    for record in records:
        key = _drug_product_key(record)
        current = by_key.get(key)
        end = str(record.get("payload", {}).get("有效迄日", ""))
        current_end = str((current or {}).get("payload", {}).get("有效迄日", ""))
        if current is None or (end == "9991231", end) > (current_end == "9991231", current_end):
            by_key[key] = record
    return sorted(by_key.values(), key=lambda row: (row.get("drug_code", ""), row.get("english_name", "")))


def _drug_specification(record: dict[str, Any]) -> str:
    payload = record.get("payload", {})
    specification = " ".join(
        part for part in (str(payload.get("規格量", "")).strip(), str(payload.get("規格單位", "")).strip()) if part
    )
    return specification or " | ".join(record.get("strengths", []) or [])


def _name_records(module, drug_ref, name: str, strength_text: str) -> tuple[list[dict[str, Any]], str]:
    if not name:
        return [], ""
    normalized = module.normalize_text(name)
    exact = _distinct_drug_products(drug_ref.exact_name_index.get(normalized, []))
    candidate = module.Candidate(
        image_filename="",
        candidate_kind="drug_name_strength",
        candidate_value=name,
        normalized_candidate_value=normalized,
        strength_candidate=strength_text,
    )
    explicit_strengths = set(module.candidate_value_strengths(name))
    explicit_strengths.update(module.extract_strengths(strength_text))
    if exact:
        if explicit_strengths:
            strength_matches = [record for record in exact if explicit_strengths & set(record.get("strengths", []))]
            if strength_matches:
                return _distinct_drug_products(strength_matches), "name_strength_match"
        return exact, "exact_name_match"

    # This is the existing validated token+strength rule from the staging
    # matcher, applied without fuzzy/AI promotion.
    evidence = module.add_drug_name_evidence(candidate, drug_ref, max_fuzzy=0)
    high_rows = {
        item.source_row_number
        for item in evidence
        if item.evidence_type == "drug_name_strength" and item.source_row_number is not None
    }
    records = [
        record
        for candidates in drug_ref.code_index.values()
        for record in candidates
        if record.get("row_number") in high_rows
    ]
    if records:
        return _distinct_drug_products(records), "name_strength_match"

    # Prefix/token matches without a strength are not promoted.  They are used
    # only to expose official ambiguity to the reviewer.
    tokens = module.significant_tokens(module.remove_strength_tokens(name))
    if len(tokens) >= 2:
        candidates = drug_ref.first_token_index.get(tokens[0], [])
        partial = [
            record
            for record in candidates
            if all(token in " ".join(record.get("name_norms", [])) for token in tokens)
        ]
        if partial:
            return _distinct_drug_products(partial), "partial_name_reference_candidates"
    return [], ""


def _aggregate_drug_candidates(rows: list[dict[str, str]], module) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in rows:
        image = (row.get("image_filename") or "").strip()
        code = (row.get("drug_code_candidate") or "").strip()
        name = (row.get("drug_name_candidate") or "").strip()
        if not image or not (code or name):
            continue
        normalized_code = module.normalize_code(code)
        normalized_name = module.normalize_text(name)
        key = (image, normalized_code, "" if normalized_code else normalized_name)
        group = groups.setdefault(
            key,
            {"image": image, "codes": [], "names": [], "strengths": [], "rows": []},
        )
        group["codes"].extend(_split(code))
        group["names"].extend(_split(name))
        group["strengths"].extend(_split(row.get("strength_candidate", "")))
        group["rows"].append(row)
    return list(groups.values())


def match_drug_candidates(rows: list[dict[str, str]], drug_ref, module, *, run_id: str, reference_path: Path, reference_sha256: str) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for group in _aggregate_drug_candidates(rows, module):
        image = group["image"]
        ocr_code = _unique(group["codes"])[0] if group["codes"] else ""
        normalized_code = module.normalize_code(ocr_code)
        ocr_name = _best_text(group["names"])
        normalized_name = module.normalize_text(ocr_name)
        ocr_strength = " | ".join(_unique(group["strengths"]))
        code_records = _distinct_drug_products(drug_ref.code_index.get(normalized_code, [])) if normalized_code else []
        name_records, name_basis = _name_records(module, drug_ref, ocr_name, ocr_strength)
        name_codes = {record.get("drug_code", "") for record in name_records if record.get("drug_code")}
        warnings: list[str] = []
        ambiguity = ""
        selected: dict[str, Any] | None = None
        status = "not_found"
        basis = "no_official_reference_match"
        confidence = "low"

        if code_records:
            selected = code_records[0]
            if len(code_records) > 1:
                status = "multiple_candidates"
                basis = "exact_code_multiple_official_products"
                confidence = "low"
                ambiguity = " | ".join(record.get("drug_code", "") + " " + record.get("english_name", "") for record in code_records)
            elif name_codes and normalized_code not in name_codes:
                status = "conflict"
                basis = "exact_code_vs_ocr_name_conflict"
                confidence = "low"
                warnings.append("exact_code_match_but_ocr_name_points_to_different_official_code")
                ambiguity = "ocr_name_candidates=" + ",".join(sorted(name_codes))
            else:
                candidate_strengths = set(module.candidate_value_strengths(ocr_name))
                candidate_strengths.update(module.extract_strengths(ocr_strength))
                official_strengths = set(selected.get("strengths", []))
                if candidate_strengths and official_strengths and not candidate_strengths & official_strengths:
                    status = "conflict"
                    basis = "exact_code_vs_ocr_strength_conflict"
                    confidence = "low"
                    warnings.append("exact_code_match_but_ocr_strength_conflicts_with_official_specification")
                else:
                    status = "exact_code_match"
                    basis = "official_nhi_drug_code_exact"
                    confidence = "high"
        elif name_records:
            selected = name_records[0]
            if len({record.get("drug_code", "") for record in name_records}) > 1:
                status = "multiple_candidates"
                basis = name_basis or "multiple_official_name_candidates"
                confidence = "low"
                ambiguity = " | ".join(record.get("drug_code", "") + " " + record.get("english_name", "") for record in name_records)
            elif normalized_code:
                status = "conflict"
                basis = "ocr_code_not_found_but_name_matches_official"
                confidence = "low"
                warnings.append("ocr_drug_code_conflicts_with_official_name_match")
            else:
                status = name_basis if name_basis in {"exact_name_match", "name_strength_match"} else "multiple_candidates"
                basis = name_basis
                confidence = "high" if status == "name_strength_match" else "medium"
        elif normalized_code:
            warnings.append("ocr_drug_code_not_found_in_pinned_nhi_reference")

        official_payload = (selected or {}).get("payload", {})
        official_code = (selected or {}).get("drug_code", "")
        official_name = (selected or {}).get("english_name", "")
        official_name_zh = (selected or {}).get("chinese_name", "")
        official_ingredient = (selected or {}).get("ingredient", "")
        official_spec = _drug_specification(selected or {}) if selected else ""
        source_rows = [record.get("row_number") for record in (code_records or name_records) if record.get("row_number")]
        ocr_evidence = _evidence_snippets(group["rows"], [ocr_code, ocr_name])
        structured = {
            "schema_version": "prescription-drug-official-match-v1",
            "candidate_type": "drug",
            "source_images": [image],
            "ocr": {
                "drug_name": ocr_name,
                "drug_code": ocr_code,
                "strength": ocr_strength,
                "normalized_drug_name": normalized_name,
                "evidence": ocr_evidence,
            },
            "official_match": {
                "drug_code": official_code,
                "drug_name": official_name,
                "drug_name_zh": official_name_zh,
                "ingredient": official_ingredient,
                "strength_specification": official_spec,
                "match_basis": basis,
                "match_status": status,
                "confidence": confidence,
                "ambiguity": ambiguity,
                "warnings": warnings,
                "source": "nhi_drug_payment_20260522",
                "source_path": str(reference_path),
                "source_sha256": reference_sha256,
                "source_rows": source_rows,
                "source_payload": official_payload,
            },
            "effective_fields": {
                "drug_code": official_code,
                "drug_name": official_name,
                "ingredient": official_ingredient,
                "strength_specification": official_spec,
            },
        }
        results.append(
            {
                "source_run_id": run_id,
                "source_image_filename": image,
                "ocr_drug_name": ocr_name,
                "ocr_drug_code": ocr_code,
                "ocr_strength": ocr_strength,
                "normalized_drug_name": normalized_name,
                "matched_official_drug_code": official_code,
                "official_drug_name": official_name,
                "official_drug_name_zh": official_name_zh,
                "official_ingredient": official_ingredient,
                "official_strength_specification": official_spec,
                "match_basis": basis,
                "match_status": status,
                "match_confidence": confidence,
                "ambiguity": ambiguity,
                "warnings": ";".join(warnings),
                "ocr_evidence": " | ".join(ocr_evidence),
                "official_evidence": _json(official_payload) if official_payload else "",
                "reference_source": "nhi_drug_payment_20260522",
                "reference_path": str(reference_path),
                "reference_sha256": reference_sha256,
                "structured_fields": _json(structured),
            }
        )
    return sorted(results, key=lambda row: (row["source_image_filename"], row["ocr_drug_code"], row["ocr_drug_name"]))


def _icd_name_indexes(icd_ref, module) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in icd_ref.code_index.values():
        for value in (record.get("chinese_name", ""), record.get("english_name", "")):
            normalized = module.normalize_text(value)
            if normalized:
                result[normalized].append(record)
    return dict(result)


def _aggregate_icd_candidates(rows: list[dict[str, str]], module) -> list[dict[str, Any]]:
    by_image: dict[str, dict[str, Any]] = defaultdict(lambda: {"codes": [], "diagnoses": [], "rows": []})
    for row in rows:
        image = (row.get("image_filename") or "").strip()
        if not image:
            continue
        by_image[image]["codes"].extend(_split(row.get("icd10_candidate", "")))
        by_image[image]["diagnoses"].extend(_split(row.get("diagnosis_text_candidate", "")))
        by_image[image]["rows"].append(row)
    groups: list[dict[str, Any]] = []
    for image, data in by_image.items():
        codes = _unique(data["codes"])
        diagnoses = _unique(data["diagnoses"])
        for code in codes:
            groups.append({"image": image, "code": code, "diagnoses": diagnoses, "rows": data["rows"]})
        if not codes:
            for diagnosis in diagnoses:
                groups.append({"image": image, "code": "", "diagnoses": [diagnosis], "rows": data["rows"]})
    return groups


def match_icd_candidates(rows: list[dict[str, str]], icd_ref, module, *, run_id: str, reference_path: Path, reference_sha256: str) -> list[dict[str, Any]]:
    name_index = _icd_name_indexes(icd_ref, module)
    results: list[dict[str, Any]] = []
    for group in _aggregate_icd_candidates(rows, module):
        image = group["image"]
        ocr_code = group["code"]
        normalized = module.normalize_icd(ocr_code)
        diagnosis_values = _unique(group["diagnoses"])
        ocr_diagnosis = " | ".join(diagnosis_values)
        official = icd_ref.code_index.get(normalized) if normalized else None
        diagnosis_matches: list[dict[str, Any]] = []
        for diagnosis in diagnosis_values:
            diagnosis_matches.extend(name_index.get(module.normalize_text(diagnosis), []))
        diagnosis_by_code = {record.get("code", ""): record for record in diagnosis_matches}
        diagnosis_matches = list(diagnosis_by_code.values())
        warnings: list[str] = []
        ambiguity = ""
        selected = official
        status = "not_found"
        basis = "no_official_reference_match"
        confidence = "low"

        if official:
            if str(official.get("use", "")).strip() != "1":
                status = "conflict"
                basis = "official_code_not_selectable_use_flag"
                warnings.append("official_icd_use_is_not_1")
            elif diagnosis_matches and official.get("code") not in diagnosis_by_code:
                status = "conflict"
                basis = "icd_code_vs_diagnosis_text_conflict"
                warnings.append("ocr_diagnosis_text_points_to_different_official_icd")
                ambiguity = "diagnosis_text_candidates=" + ",".join(sorted(diagnosis_by_code))
            else:
                official_code = str(official.get("code", "")).strip().upper()
                if ocr_code.strip().upper() == official_code:
                    status = "exact_code_match"
                    basis = "official_nhi_icd_code_exact"
                else:
                    status = "normalized_code_match"
                    basis = "official_nhi_icd_code_normalized"
                confidence = "high"
        elif diagnosis_matches:
            selected = diagnosis_matches[0]
            if len(diagnosis_matches) > 1:
                status = "multiple_candidates"
                basis = "diagnosis_text_multiple_official_codes"
                ambiguity = " | ".join(record.get("code", "") + " " + record.get("chinese_name", "") for record in diagnosis_matches)
            elif normalized:
                status = "conflict"
                basis = "ocr_icd_not_found_but_diagnosis_text_matches_official"
                warnings.append("ocr_icd_conflicts_with_official_diagnosis_text_match")
            else:
                status = "diagnosis_text_match"
                basis = "official_diagnosis_text_normalized_exact"
                confidence = "medium"
        elif normalized:
            warnings.append("ocr_icd_not_found_in_pinned_nhi_reference")

        payload = (selected or {}).get("payload", {})
        official_code = (selected or {}).get("code", "")
        chinese = (selected or {}).get("chinese_name", "")
        english = (selected or {}).get("english_name", "")
        evidence = _evidence_snippets(group["rows"], [ocr_code, *diagnosis_values])
        structured = {
            "schema_version": "prescription-icd-official-match-v1",
            "candidate_type": "icd",
            "source_images": [image],
            "ocr": {
                "diagnosis_text": ocr_diagnosis,
                "icd_code": ocr_code,
                "normalized_icd": normalized,
                "evidence": evidence,
            },
            "official_match": {
                "icd_code": official_code,
                "chinese_name": chinese,
                "english_name": english,
                "match_basis": basis,
                "match_status": status,
                "confidence": confidence,
                "ambiguity": ambiguity,
                "warnings": warnings,
                "source": "nhi_2023_icd10_cm_pcs",
                "source_path": str(reference_path),
                "source_sha256": reference_sha256,
                "source_sheet": icd_ref.sheet,
                "source_row": (selected or {}).get("row_number"),
                "source_payload": payload,
            },
            "effective_fields": {
                "icd_code": official_code,
                "chinese_name": chinese,
                "english_name": english,
            },
        }
        results.append(
            {
                "source_run_id": run_id,
                "source_image_filename": image,
                "ocr_diagnosis_text": ocr_diagnosis,
                "ocr_icd_code": ocr_code,
                "normalized_icd": normalized,
                "matched_official_icd_code": official_code,
                "official_chinese_name": chinese,
                "official_english_name": english,
                "match_basis": basis,
                "match_status": status,
                "match_confidence": confidence,
                "ambiguity": ambiguity,
                "warnings": ";".join(warnings),
                "ocr_evidence": " | ".join(evidence),
                "official_evidence": _json(payload) if payload else "",
                "reference_source": "nhi_2023_icd10_cm_pcs",
                "reference_path": str(reference_path),
                "reference_sha256": reference_sha256,
                "structured_fields": _json(structured),
            }
        )
    return sorted(results, key=lambda row: (row["source_image_filename"], row["normalized_icd"], row["ocr_diagnosis_text"]))


def build_relation_evidence(drug_rows: list[dict[str, Any]], icd_rows: list[dict[str, Any]], run_id: str) -> list[dict[str, Any]]:
    safe_drug = {"exact_code_match", "exact_name_match", "name_strength_match"}
    safe_icd = {"exact_code_match", "normalized_code_match", "diagnosis_text_match"}
    drugs_by_image: dict[str, list[dict[str, Any]]] = defaultdict(list)
    icds_by_image: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in drug_rows:
        if row.get("match_status") in safe_drug:
            drugs_by_image[row["source_image_filename"]].append(row)
    for row in icd_rows:
        if row.get("match_status") in safe_icd:
            icds_by_image[row["source_image_filename"]].append(row)
    results: list[dict[str, Any]] = []
    for image in sorted(set(drugs_by_image) & set(icds_by_image)):
        for drug in drugs_by_image[image]:
            for icd in icds_by_image[image]:
                evidence = {
                    "schema_version": "prescription-relation-evidence-v1",
                    "candidate_type": "drug_diagnosis_link",
                    "source_images": [image],
                    "relation_basis": "same_image",
                    "classification": "evidence_only",
                    "formal_apply_allowed": False,
                    "drug": {
                        "code": drug.get("matched_official_drug_code", ""),
                        "name": drug.get("official_drug_name", ""),
                        "match_status": drug.get("match_status", ""),
                    },
                    "icd": {
                        "code": icd.get("matched_official_icd_code", ""),
                        "name": icd.get("official_chinese_name", ""),
                        "match_status": icd.get("match_status", ""),
                    },
                    "warning": "cooccurrence_is_not_a_formal_drug_diagnosis_relation",
                }
                results.append(
                    {
                        "source_run_id": run_id,
                        "source_image_filename": image,
                        "drug_code": drug.get("matched_official_drug_code", ""),
                        "drug_name": drug.get("official_drug_name", ""),
                        "icd_code": icd.get("matched_official_icd_code", ""),
                        "diagnosis_name": icd.get("official_chinese_name", ""),
                        "relation_basis": "same_image",
                        "classification": "evidence_only",
                        "formal_apply_allowed": "false",
                        "evidence_summary": "same_image co-occurrence only; formal relation apply hard-excluded",
                        "structured_fields": _json(evidence),
                    }
                )
    return results


def _customer_queue_rows(work_dir: Path) -> list[dict[str, Any]]:
    actions = _read_csv(work_dir / "customer_matching" / "ocr_customer_liff_actions.csv")
    results: list[dict[str, Any]] = []
    for index, row in enumerate(actions, start=1):
        action = row.get("action_type", "")
        if action == "new_customer_prefill":
            existing_status, suggested, confidence = "not_found", "create_customer", "manual_review"
        elif action == "attach_existing_customer":
            existing_status, suggested, confidence = "exists", "attach_existing_customer", "high"
        else:
            existing_status, suggested, confidence = "ambiguous", "needs_review", "manual_review"
        structured = row.get("structured_fields", "")
        display = f"客戶候選:{row.get('ocr_text_candidate', '')}"
        results.append(
            {
                "source_image_filename": row.get("source_image_filename", ""),
                "decision_type": "customer",
                "candidate_id": f"customer_action:{index}",
                "candidate_value": row.get("ocr_text_candidate", ""),
                "display_name": display,
                "existing_status": existing_status,
                "existing_target": row.get("matched_short_name", ""),
                "suggested_action": suggested,
                "evidence_summary": "; ".join(
                    part
                    for part in (
                        f"match_status={row.get('match_status', '')}",
                        f"match_score={row.get('match_score', '')}",
                        row.get("line_text", ""),
                    )
                    if part
                ),
                "confidence_level": confidence,
                "review_decision": row.get("review_decision", ""),
                "corrected_value": "",
                "review_note": row.get("review_note", ""),
                "structured_fields": structured,
                "structured_corrected_fields": "",
            }
        )
    return results


def _drug_queue_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        status = row["match_status"]
        safe = status in {"exact_code_match", "exact_name_match", "name_strength_match"}
        existing_status = "reference_matched" if safe else ("ambiguous" if status == "multiple_candidates" else status)
        official = row.get("matched_official_drug_code", "")
        candidate = official or row.get("ocr_drug_code", "") or row.get("normalized_drug_name", "")
        display = " | ".join(
            part
            for part in (
                official,
                row.get("official_drug_name", ""),
                row.get("official_strength_specification", ""),
            )
            if part
        ) or candidate
        results.append(
            {
                "source_image_filename": row["source_image_filename"],
                "decision_type": "drug",
                "candidate_id": f"drug_match:{index}",
                "candidate_value": candidate,
                "display_name": display,
                "existing_status": existing_status,
                "existing_target": official,
                "suggested_action": "insert_drug" if safe and row["match_confidence"] == "high" else "needs_review",
                "evidence_summary": f"match={status}; basis={row['match_basis']}; OCR={row.get('ocr_evidence', '')}",
                "confidence_level": row["match_confidence"],
                "review_decision": "",
                "corrected_value": "",
                "review_note": "",
                "structured_fields": row["structured_fields"],
                "structured_corrected_fields": "",
            }
        )
    return results


def _icd_queue_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        status = row["match_status"]
        safe = status in {"exact_code_match", "normalized_code_match", "diagnosis_text_match"}
        existing_status = "reference_matched" if safe else ("ambiguous" if status == "multiple_candidates" else status)
        official = row.get("matched_official_icd_code", "")
        candidate = official or row.get("normalized_icd", "") or row.get("ocr_diagnosis_text", "")
        display = " | ".join(part for part in (official, row.get("official_chinese_name", ""), row.get("official_english_name", "")) if part) or candidate
        results.append(
            {
                "source_image_filename": row["source_image_filename"],
                "decision_type": "icd",
                "candidate_id": f"icd_match:{index}",
                "candidate_value": candidate,
                "display_name": display,
                "existing_status": existing_status,
                "existing_target": official,
                "suggested_action": "insert_icd" if safe and row["match_confidence"] == "high" else "needs_review",
                "evidence_summary": f"match={status}; basis={row['match_basis']}; OCR={row.get('ocr_evidence', '')}",
                "confidence_level": row["match_confidence"],
                "review_decision": "",
                "corrected_value": "",
                "review_note": "",
                "structured_fields": row["structured_fields"],
                "structured_corrected_fields": "",
            }
        )
    return results


def _relation_queue_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        candidate = f"{row.get('drug_code', '')} -> {row.get('icd_code', '')}"
        results.append(
            {
                "source_image_filename": row["source_image_filename"],
                "decision_type": "drug_diagnosis_link",
                "candidate_id": f"relation_evidence:{index}",
                "candidate_value": candidate,
                "display_name": f"{row.get('drug_name', '')} ↔ {row.get('diagnosis_name', '')}",
                "existing_status": "not_applicable",
                "existing_target": "",
                "suggested_action": "defer_relation",
                "evidence_summary": row["evidence_summary"],
                "confidence_level": "manual_review",
                "review_decision": "",
                "corrected_value": "",
                "review_note": "",
                "structured_fields": row["structured_fields"],
                "structured_corrected_fields": "",
            }
        )
    return results


def _merge_review_state(new_rows: list[dict[str, Any]], existing_rows: list[dict[str, str]]) -> int:
    by_key = {
        (row.get("decision_type", ""), row.get("source_image_filename", ""), row.get("candidate_value", "")): row
        for row in existing_rows
        if row.get("review_decision")
    }
    carried = 0
    for row in new_rows:
        old = by_key.get((row.get("decision_type", ""), row.get("source_image_filename", ""), row.get("candidate_value", "")))
        if not old:
            continue
        for field in ("review_decision", "corrected_value", "review_note", "structured_corrected_fields"):
            row[field] = old.get(field, "")
        carried += 1
    return carried


def _write_queue_markdown(path: Path, rows: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    lines = [
        "# Prescription OCR Import Decision Queue",
        "",
        "> Drug and ICD values were matched to pinned official references before LIFF review. Relations are evidence-only.",
        "",
        f"- rows: {len(rows)}",
        f"- decision_type_counts: `{json.dumps(summary['decision_type_counts'], ensure_ascii=False, sort_keys=True)}`",
        f"- drug_match_status_counts: `{json.dumps(summary['drug_match_status_counts'], ensure_ascii=False, sort_keys=True)}`",
        f"- icd_match_status_counts: `{json.dumps(summary['icd_match_status_counts'], ensure_ascii=False, sort_keys=True)}`",
        "- formal database writes: `none`",
        "- relation formal apply: `hard-excluded`",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _reference_context(
    work_dir: Path,
    *,
    drug_reference: Path = DEFAULT_DRUG_REFERENCE,
    icd_reference: Path = DEFAULT_ICD_REFERENCE,
) -> dict[str, Any]:
    work_dir = work_dir.expanduser().resolve()
    input_path = work_dir / "extracted" / "prescription_candidates_filtered.csv"
    input_rows = _read_csv(input_path)
    if not input_rows:
        raise FileNotFoundError(f"filtered candidate artifact missing or empty: {input_path}")

    drug_reference = drug_reference.expanduser().resolve()
    icd_reference = icd_reference.expanduser().resolve()
    drug_hash = _verify_reference(drug_reference, DRUG_REFERENCE_SHA256, "Drug")
    icd_hash = _verify_reference(icd_reference, ICD_REFERENCE_SHA256, "ICD")
    module = _load_verified_matcher()
    drug_ref = module.load_drug_reference(drug_reference)
    icd_ref = module.load_icd_reference(icd_reference)
    return {
        "work_dir": work_dir,
        "run_id": work_dir.name,
        "input_path": input_path,
        "input_rows": input_rows,
        "drug_reference": drug_reference,
        "icd_reference": icd_reference,
        "drug_hash": drug_hash,
        "icd_hash": icd_hash,
        "module": module,
        "drug_ref": drug_ref,
        "icd_ref": icd_ref,
    }


def _reference_summary(context: dict[str, Any]) -> dict[str, Any]:
    drug_ref = context["drug_ref"]
    icd_ref = context["icd_ref"]
    return {
        "run_id": context["run_id"],
        "work_dir": str(context["work_dir"]),
        "input_path": str(context["input_path"]),
        "input_rows": len(context["input_rows"]),
        "drug_reference": {
            "path": str(context["drug_reference"]),
            "sha256": context["drug_hash"],
            "rows": drug_ref.row_count,
            "schema": drug_ref.columns,
            "source": "NHI drug payment items snapshot downloaded 2026-05-22",
        },
        "icd_reference": {
            "path": str(context["icd_reference"]),
            "sha256": context["icd_hash"],
            "rows": icd_ref.row_count,
            "schema": icd_ref.columns,
            "sheet": icd_ref.sheet,
            "source": "NHI 2023 ICD-10-CM/PCS Chinese edition, ICD-10-CM sheet",
        },
    }


def _match_official_rows(context: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    run_id = context["run_id"]
    module = context["module"]

    drug_rows = match_drug_candidates(
        context["input_rows"],
        context["drug_ref"],
        module,
        run_id=run_id,
        reference_path=context["drug_reference"],
        reference_sha256=context["drug_hash"],
    )
    icd_rows = match_icd_candidates(
        context["input_rows"],
        context["icd_ref"],
        module,
        run_id=run_id,
        reference_path=context["icd_reference"],
        reference_sha256=context["icd_hash"],
    )
    relation_rows = build_relation_evidence(drug_rows, icd_rows, run_id)
    return drug_rows, icd_rows, relation_rows


def _build_queue_from_rows(
    context: dict[str, Any],
    drug_rows: list[dict[str, Any]],
    icd_rows: list[dict[str, Any]],
    relation_rows: list[dict[str, Any]],
    *,
    write_artifacts: bool,
) -> dict[str, Any]:
    work_dir = context["work_dir"]
    queue_rows = [
        *_customer_queue_rows(work_dir),
        *_drug_queue_rows(drug_rows),
        *_icd_queue_rows(icd_rows),
        *_relation_queue_rows(relation_rows),
    ]
    queue_path = work_dir / "review" / "import_decision_queue.csv"
    carried = _merge_review_state(queue_rows, _read_csv(queue_path))

    summary = {
        **_reference_summary(context),
        "phase": "import_queue",
        "drug_match_rows": len(drug_rows),
        "drug_match_status_counts": dict(Counter(row["match_status"] for row in drug_rows)),
        "icd_match_rows": len(icd_rows),
        "icd_match_status_counts": dict(Counter(row["match_status"] for row in icd_rows)),
        "relation_evidence_rows": len(relation_rows),
        "relation_formal_apply_allowed": False,
        "queue_rows": len(queue_rows),
        "decision_type_counts": dict(Counter(row["decision_type"] for row in queue_rows)),
        "review_state_rows_carried": carried,
        "queue_path": str(queue_path),
        "database_connected": False,
        "database_written": False,
        "formal_tables_touched": "none",
    }

    if write_artifacts:
        _write_csv_atomic(queue_path, queue_rows, QUEUE_FIELDS)
        _write_queue_markdown(work_dir / "review" / "import_decision_queue.md", queue_rows, summary)
        summary["artifacts"] = {
            "drug_matches": str(work_dir / "reference_matching" / "drug_official_matches.csv"),
            "icd_matches": str(work_dir / "reference_matching" / "icd_official_matches.csv"),
            "relation_evidence": str(work_dir / "reference_matching" / "drug_diagnosis_relation_evidence.csv"),
            "decision_queue": str(queue_path),
        }
    return summary


def build_official_reference_matches(
    work_dir: Path,
    *,
    drug_reference: Path = DEFAULT_DRUG_REFERENCE,
    icd_reference: Path = DEFAULT_ICD_REFERENCE,
    write_artifacts: bool = True,
) -> dict[str, Any]:
    """Run the pinned Drug/ICD match stage before Customer matching."""
    context = _reference_context(work_dir, drug_reference=drug_reference, icd_reference=icd_reference)
    drug_rows, icd_rows, relation_rows = _match_official_rows(context)
    summary = {
        **_reference_summary(context),
        "phase": "official_reference_matching",
        "drug_match_rows": len(drug_rows),
        "drug_match_status_counts": dict(Counter(row["match_status"] for row in drug_rows)),
        "icd_match_rows": len(icd_rows),
        "icd_match_status_counts": dict(Counter(row["match_status"] for row in icd_rows)),
        "relation_evidence_rows": len(relation_rows),
        "relation_formal_apply_allowed": False,
        "database_connected": False,
        "database_written": False,
        "formal_tables_touched": "none",
    }
    if write_artifacts:
        match_dir = context["work_dir"] / "reference_matching"
        _write_csv_atomic(match_dir / "drug_official_matches.csv", drug_rows, DRUG_MATCH_FIELDS)
        _write_csv_atomic(match_dir / "icd_official_matches.csv", icd_rows, ICD_MATCH_FIELDS)
        _write_csv_atomic(match_dir / "drug_diagnosis_relation_evidence.csv", relation_rows, RELATION_FIELDS)
        summary["artifacts"] = {
            "drug_matches": str(match_dir / "drug_official_matches.csv"),
            "icd_matches": str(match_dir / "icd_official_matches.csv"),
            "relation_evidence": str(match_dir / "drug_diagnosis_relation_evidence.csv"),
        }
    return summary


def build_import_queue_from_match_artifacts(
    work_dir: Path,
    *,
    drug_reference: Path = DEFAULT_DRUG_REFERENCE,
    icd_reference: Path = DEFAULT_ICD_REFERENCE,
    write_artifacts: bool = True,
) -> dict[str, Any]:
    """Combine existing official matches and Customer results into the one queue."""
    context = _reference_context(work_dir, drug_reference=drug_reference, icd_reference=icd_reference)
    match_dir = context["work_dir"] / "reference_matching"
    drug_path = match_dir / "drug_official_matches.csv"
    icd_path = match_dir / "icd_official_matches.csv"
    relation_path = match_dir / "drug_diagnosis_relation_evidence.csv"
    if not all(path.is_file() for path in (drug_path, icd_path, relation_path)):
        raise FileNotFoundError("official match artifacts missing; run match-only before queue-only")
    drug_rows = _read_csv(drug_path)
    icd_rows = _read_csv(icd_path)
    relation_rows = _read_csv(relation_path)
    return _build_queue_from_rows(
        context, drug_rows, icd_rows, relation_rows, write_artifacts=write_artifacts
    )


def build_import_decision_queue(
    work_dir: Path,
    *,
    drug_reference: Path = DEFAULT_DRUG_REFERENCE,
    icd_reference: Path = DEFAULT_ICD_REFERENCE,
    write_artifacts: bool = True,
) -> dict[str, Any]:
    """Backward-compatible one-call official match plus queue builder."""
    context = _reference_context(work_dir, drug_reference=drug_reference, icd_reference=icd_reference)
    drug_rows, icd_rows, relation_rows = _match_official_rows(context)
    if write_artifacts:
        match_dir = context["work_dir"] / "reference_matching"
        _write_csv_atomic(match_dir / "drug_official_matches.csv", drug_rows, DRUG_MATCH_FIELDS)
        _write_csv_atomic(match_dir / "icd_official_matches.csv", icd_rows, ICD_MATCH_FIELDS)
        _write_csv_atomic(match_dir / "drug_diagnosis_relation_evidence.csv", relation_rows, RELATION_FIELDS)
    return _build_queue_from_rows(
        context, drug_rows, icd_rows, relation_rows, write_artifacts=write_artifacts
    )
