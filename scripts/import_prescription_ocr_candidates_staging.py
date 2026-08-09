#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import unicodedata
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUNS_DIR = Path(
    os.environ.get(
        "PRESCRIPTION_OCR_RUNS_DIR",
        str(REPO_ROOT / "runtime_data" / "prescription_ocr_runs"),
    )
)
DEFAULT_INPUT_CSV = DEFAULT_RUNS_DIR / "old_20260715_003300" / "review" / "manual_review_queue.csv"
DEFAULT_DRUG_REFERENCE = REPO_ROOT / "reference_data" / "drug" / "raw" / "nhi_drug_payment_20260522.csv"
DEFAULT_ICD_REFERENCE = REPO_ROOT / "reference_data" / "icd" / "nhi_2023_icd10_cm_pcs.xlsx"

DRUG_SOURCE_NAME = "nhi_drug_payment_20260522"
ICD_SOURCE_NAME = "nhi_2023_icd10_cm_pcs"
ICD_CM_SHEET_NAME = "ICD-10-CM"

REVIEW_DECISION_VALUES = {
    "",
    "accept",
    "reject",
    "needs_better_ocr",
    "needs_drug_lookup",
    "needs_icd_lookup",
    "duplicate",
    "unclear",
}

SIGNIFICANT_STOP_TOKENS = {
    "TAB",
    "TABS",
    "TABLET",
    "TABLETS",
    "CAP",
    "CAPS",
    "CAPSULE",
    "CAPSULES",
    "FILM",
    "COATED",
    "F",
    "C",
    "FC",
    "CR",
    "SR",
    "ER",
    "RETARD",
    "INJECTION",
    "INJ",
    "CREAM",
    "OINTMENT",
    "SOLUTION",
    "SUSPENSION",
    "DROPS",
    "PATCH",
    "PLUS",
}

STRENGTH_RE = re.compile(
    r"\b(\d+(?:\.\d+)?)\s*(MG|MCG|UG|G|ML|IU|UNIT|UNITS|%)\b|\b(\d{1,3})M\b",
    re.IGNORECASE,
)
POSSIBLE_NAME_STRENGTH_RE = re.compile(r"\b(0\.\d{1,3}|[1-9]\d{0,2}(?:\.\d{1,2})?)\b")
DATE_OR_ID_RE = re.compile(r"\b(?:\d{2,4}[./-]\d{1,2}(?:[./-]\d{1,2})?|[A-Z0-9]{12,})\b", re.IGNORECASE)
ICD_RE = re.compile(r"^[A-TV-Z][0-9]{2}(?:\.?[0-9A-Z]{1,4})?$", re.IGNORECASE)


@dataclass
class Evidence:
    evidence_source: str
    evidence_type: str
    matched_key: str
    confidence_contribution: str
    source_file: str
    source_sheet: str = ""
    source_row_number: int | None = None
    source_payload: dict[str, str] = field(default_factory=dict)
    match_notes: str = ""


@dataclass
class Candidate:
    image_filename: str
    candidate_kind: str
    candidate_value: str
    normalized_candidate_value: str
    drug_code_candidate: str = ""
    drug_name_candidate: str = ""
    dose_candidate: str = ""
    strength_candidate: str = ""
    frequency_candidate: str = ""
    days_candidate: str = ""
    diagnosis_text_candidate: str = ""
    icd10_candidate: str = ""
    review_priority: str = ""
    review_category: str = ""
    source_status: str = ""
    filter_reason: str = ""
    candidate_context: str = ""
    line_text: str = ""
    source_rows: int = 0
    confidence_level: str = "low"
    confidence_reason: str = "ocr_only_no_public_evidence"
    evidences: list[Evidence] = field(default_factory=list)

    @property
    def signature(self) -> tuple[str, str, str, str]:
        return (
            self.image_filename,
            self.candidate_kind,
            self.normalized_candidate_value,
            self.candidate_value,
        )


@dataclass
class DrugReference:
    path: Path
    columns: list[str]
    row_count: int
    code_index: dict[str, list[dict[str, Any]]]
    exact_name_index: dict[str, list[dict[str, Any]]]
    first_token_index: dict[str, list[dict[str, Any]]]
    ingredient_index: dict[str, list[dict[str, Any]]]
    normalized_names: list[str]


@dataclass
class IcdReference:
    path: Path
    sheet: str
    columns: list[str]
    row_count: int
    code_index: dict[str, dict[str, Any]]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Dry-run prescription OCR candidate staging import. Defaults to no database connection and no writes."
        )
    )
    parser.add_argument(
        "--input-csv",
        default=str(DEFAULT_INPUT_CSV),
        help="manual_review_queue.csv or prescription_candidates_filtered.csv.",
    )
    parser.add_argument(
        "--drug-reference",
        default=str(DEFAULT_DRUG_REFERENCE),
        help="Public NHI drug payment CSV.",
    )
    parser.add_argument(
        "--icd-reference",
        default=str(DEFAULT_ICD_REFERENCE),
        help="Public NHI ICD-10 CM/PCS xlsx.",
    )
    parser.add_argument(
        "--report",
        help="Dry-run Markdown report path. Default: <run_dir>/reports/03_staging_import_dry_run.md.",
    )
    parser.add_argument(
        "--only-safe-exact",
        action="store_true",
        help=(
            "Restrict planned staging rows to safe exact matches only: "
            "drug_code exact public match and ICD-10 exact public match."
        ),
    )
    parser.add_argument("--apply", action="store_true", help="Write high-confidence rows to staging tables.")
    parser.add_argument(
        "--database-url",
        help="Required with --apply. The script does not read DATABASE_URL implicitly.",
    )
    parser.add_argument(
        "--max-fuzzy-candidates",
        type=int,
        default=3000,
        help="Maximum normalized official names to scan for fuzzy matching per candidate.",
    )
    return parser


def split_values(value: str) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(" | ") if item.strip() and item.strip() != "(none)"]


def unique(values: list[str], limit: int = 200) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        clean = value.strip()
        if not clean:
            continue
        key = clean.lower()
        if key in seen:
            continue
        result.append(clean)
        seen.add(key)
        if len(result) >= limit:
            break
    return result


def join_values(values: list[str], limit: int = 200) -> str:
    return " | ".join(unique(values, limit=limit))


def normalize_text(value: str) -> str:
    text = unicodedata.normalize("NFKC", value or "").upper()
    text = re.sub(r"[^A-Z0-9.\u4e00-\u9fff]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_compact(value: str) -> str:
    return re.sub(r"[^A-Z0-9\u4e00-\u9fff]+", "", normalize_text(value))


def normalize_code(value: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "", unicodedata.normalize("NFKC", value or "").upper())


def normalize_icd(value: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "", unicodedata.normalize("NFKC", value or "").upper())


def extract_strengths(value: str) -> list[str]:
    strengths: list[str] = []
    for match in STRENGTH_RE.finditer(unicodedata.normalize("NFKC", value or "").upper()):
        if match.group(1) and match.group(2):
            amount = match.group(1).rstrip("0").rstrip(".") if "." in match.group(1) else match.group(1)
            unit = match.group(2).upper()
            if unit == "UG":
                unit = "MCG"
            strengths.append(f"{amount}{unit}")
        elif match.group(3):
            strengths.append(f"{match.group(3)}MG")
    return unique(strengths, limit=40)


def remove_strength_tokens(value: str) -> str:
    text = unicodedata.normalize("NFKC", value or "").upper()
    text = STRENGTH_RE.sub(" ", text)
    text = re.sub(r"\b\d+(?:\.\d+)?\b", " ", text)
    return normalize_text(text)


def significant_tokens(value: str) -> list[str]:
    tokens = [token for token in re.split(r"\s+", normalize_text(value)) if token]
    result = []
    for token in tokens:
        if token in SIGNIFICANT_STOP_TOKENS:
            continue
        if len(token) < 3 and not re.search(r"[\u4e00-\u9fff]", token):
            continue
        result.append(token)
    return unique(result, limit=12)


def md_escape(value: str, limit: int | None = None) -> str:
    text = " ".join(str(value or "").replace("\n", " ").replace("\r", " ").split())
    if limit and len(text) > limit:
        text = text[: limit - 1] + "…"
    return text.replace("|", "\\|") or "(none)"


def infer_run_dir(input_csv: Path) -> Path:
    parts = input_csv.parts
    if "review" in parts:
        return input_csv.parent.parent
    if "extracted" in parts:
        return input_csv.parent.parent
    return input_csv.parent


def run_id_for(work_dir: Path) -> str:
    return work_dir.name


def read_csv_rows(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader), list(reader.fieldnames or [])


def source_payload(row: dict[str, str], keys: list[str]) -> dict[str, str]:
    return {key: row.get(key, "") for key in keys if key in row and row.get(key, "")}


def parse_license_id(url: str) -> str:
    match = re.search(r"licId=([A-Za-z0-9]+)", url or "")
    return match.group(1) if match else ""


def load_drug_reference(path: Path) -> DrugReference:
    rows, columns = read_csv_rows(path)
    code_index: dict[str, list[dict[str, Any]]] = defaultdict(list)
    exact_name_index: dict[str, list[dict[str, Any]]] = defaultdict(list)
    first_token_index: dict[str, list[dict[str, Any]]] = defaultdict(list)
    ingredient_index: dict[str, list[dict[str, Any]]] = defaultdict(list)
    normalized_name_set: set[str] = set()

    payload_keys = [
        "藥品代號",
        "藥品英文名稱",
        "藥品中文名稱",
        "成分",
        "規格量",
        "規格單位",
        "支付價",
        "有效起日",
        "有效迄日",
        "藥商",
        "製造廠名稱",
        "劑型",
        "ATC代碼",
        "藥品代碼超連結",
    ]

    for row_number, row in enumerate(rows, start=2):
        english = row.get("藥品英文名稱", "")
        chinese = row.get("藥品中文名稱", "")
        ingredient = row.get("成分", "")
        category = row.get("分類分組名稱", "")
        spec_text = f"{row.get('規格量', '')}{row.get('規格單位', '')}"
        names = unique([english, chinese])
        name_norms = unique([normalize_text(name) for name in names if name])
        name_compacts = unique([normalize_compact(name) for name in names if name])
        ingredient_norm = normalize_text(ingredient)
        strengths = unique(
            extract_strengths(" | ".join([english, chinese, ingredient, category, spec_text])),
            limit=80,
        )
        record = {
            "row_number": row_number,
            "drug_code": normalize_code(row.get("藥品代號", "")),
            "english_name": english,
            "chinese_name": chinese,
            "ingredient": ingredient,
            "atc_code": row.get("ATC代碼", ""),
            "license_id": parse_license_id(row.get("藥品代碼超連結", "")),
            "strengths": strengths,
            "name_norms": name_norms,
            "name_compacts": name_compacts,
            "ingredient_norm": ingredient_norm,
            "payload": source_payload(row, payload_keys),
        }
        if record["license_id"]:
            record["payload"]["許可證字號_from_link"] = record["license_id"]

        if record["drug_code"]:
            code_index[record["drug_code"]].append(record)
        for norm in name_norms:
            exact_name_index[norm].append(record)
            normalized_name_set.add(norm)
            tokens = significant_tokens(norm)
            if tokens:
                first_token_index[tokens[0]].append(record)
        if ingredient_norm:
            ingredient_index[ingredient_norm].append(record)

    return DrugReference(
        path=path,
        columns=columns,
        row_count=len(rows),
        code_index=dict(code_index),
        exact_name_index=dict(exact_name_index),
        first_token_index=dict(first_token_index),
        ingredient_index=dict(ingredient_index),
        normalized_names=sorted(normalized_name_set),
    )


def xlsx_shared_strings(zf: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in zf.namelist():
        return []
    ns = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    values = []
    for si in root.findall("a:si", ns):
        values.append("".join(t.text or "" for t in si.findall(".//a:t", ns)))
    return values


def xlsx_sheet_targets(zf: zipfile.ZipFile) -> dict[str, str]:
    ns = {
        "a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
        "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    }
    rel_ns = {"rel": "http://schemas.openxmlformats.org/package/2006/relationships"}
    workbook = ET.fromstring(zf.read("xl/workbook.xml"))
    rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
    rid_to_target = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels.findall("rel:Relationship", rel_ns)}
    targets: dict[str, str] = {}
    for sheet in workbook.findall("a:sheets/a:sheet", ns):
        rid = sheet.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id", "")
        target = rid_to_target.get(rid, "")
        if not target.startswith("xl/"):
            target = "xl/" + target.lstrip("/")
        targets[sheet.attrib.get("name", "")] = target
    return targets


def xlsx_cell_value(cell: ET.Element, shared: list[str]) -> str:
    ns = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        return "".join(t.text or "" for t in cell.findall(".//a:t", ns))
    value = cell.find("a:v", ns)
    if value is None:
        return ""
    text = value.text or ""
    if cell_type == "s":
        try:
            return shared[int(text)]
        except (ValueError, IndexError):
            return text
    return text


def load_icd_reference(path: Path) -> IcdReference:
    ns = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(path) as zf:
        shared = xlsx_shared_strings(zf)
        targets = xlsx_sheet_targets(zf)
        target = targets.get(ICD_CM_SHEET_NAME)
        if not target:
            raise SystemExit(f"ICD sheet not found: {ICD_CM_SHEET_NAME}")
        root = ET.fromstring(zf.read(target))
        rows = root.findall("a:sheetData/a:row", ns)
        header: list[str] = []
        code_index: dict[str, dict[str, Any]] = {}
        for row_number, row in enumerate(rows, start=1):
            values = [xlsx_cell_value(cell, shared) for cell in row.findall("a:c", ns)]
            if row_number == 1:
                header = values
                continue
            if len(values) < 4:
                continue
            code = values[0].strip()
            if not code:
                continue
            normalized = normalize_icd(code)
            code_index[normalized] = {
                "row_number": row_number,
                "code": code,
                "use": values[1] if len(values) > 1 else "",
                "english_name": values[2] if len(values) > 2 else "",
                "chinese_name": values[3] if len(values) > 3 else "",
                "status": values[4] if len(values) > 4 else "",
                "revision_date": values[5] if len(values) > 5 else "",
                "payload": {
                    "code": code,
                    "USE": values[1] if len(values) > 1 else "",
                    "english_name": values[2] if len(values) > 2 else "",
                    "chinese_name": values[3] if len(values) > 3 else "",
                    "status": values[4] if len(values) > 4 else "",
                    "revision_date": values[5] if len(values) > 5 else "",
                },
            }
    return IcdReference(
        path=path,
        sheet=ICD_CM_SHEET_NAME,
        columns=header,
        row_count=len(code_index),
        code_index=code_index,
    )


def aggregate_input_rows(rows: list[dict[str, str]]) -> dict[str, dict[str, list[str]]]:
    fields = [
        "drug_code_candidate",
        "drug_name_candidate",
        "dose_candidate",
        "strength_candidate",
        "frequency_candidate",
        "days_candidate",
        "diagnosis_text_candidate",
        "icd10_candidate",
        "review_priority",
        "review_category",
        "source_status",
        "filter_reason",
        "candidate_context",
        "line_text",
    ]
    aggregated: dict[str, dict[str, list[str]]] = defaultdict(lambda: {field: [] for field in fields})
    for row in rows:
        image = row.get("image_filename", "").strip()
        if not image:
            continue
        for field_name in fields:
            values = split_values(row.get(field_name, ""))
            if not values and row.get(field_name, "").strip():
                values = [row.get(field_name, "").strip()]
            aggregated[image][field_name].extend(values)
    for image, values in aggregated.items():
        for field_name in list(values):
            values[field_name] = unique(values[field_name], limit=300)
    return aggregated


def build_candidates(rows: list[dict[str, str]]) -> list[Candidate]:
    aggregated = aggregate_input_rows(rows)
    candidates: dict[tuple[str, str, str], Candidate] = {}

    def add(candidate: Candidate) -> None:
        key = (candidate.image_filename, candidate.candidate_kind, candidate.normalized_candidate_value)
        if not candidate.normalized_candidate_value:
            return
        if key not in candidates:
            candidates[key] = candidate

    for image, values in aggregated.items():
        common = {
            "dose_candidate": join_values(values["dose_candidate"]),
            "strength_candidate": join_values(values["strength_candidate"]),
            "frequency_candidate": join_values(values["frequency_candidate"]),
            "days_candidate": join_values(values["days_candidate"]),
            "diagnosis_text_candidate": join_values(values["diagnosis_text_candidate"]),
            "review_priority": join_values(values["review_priority"], limit=20),
            "review_category": join_values(values["review_category"], limit=20),
            "source_status": join_values(values["source_status"], limit=20),
            "filter_reason": join_values(values["filter_reason"], limit=80),
            "candidate_context": join_values(values["candidate_context"], limit=80),
            "line_text": join_values(values["line_text"], limit=40),
        }
        for code in values["drug_code_candidate"]:
            add(
                Candidate(
                    image_filename=image,
                    candidate_kind="drug_code",
                    candidate_value=code,
                    normalized_candidate_value=normalize_code(code),
                    drug_code_candidate=code,
                    drug_name_candidate=join_values(values["drug_name_candidate"]),
                    icd10_candidate=join_values(values["icd10_candidate"]),
                    **common,
                )
            )
        for name in values["drug_name_candidate"]:
            kind = "drug_name_strength" if extract_strengths(name) or values["strength_candidate"] else "drug_name"
            add(
                Candidate(
                    image_filename=image,
                    candidate_kind=kind,
                    candidate_value=name,
                    normalized_candidate_value=normalize_text(name),
                    drug_name_candidate=name,
                    drug_code_candidate=join_values(values["drug_code_candidate"]),
                    icd10_candidate=join_values(values["icd10_candidate"]),
                    **common,
                )
            )
        for icd in values["icd10_candidate"]:
            if not ICD_RE.match(icd.strip()):
                continue
            add(
                Candidate(
                    image_filename=image,
                    candidate_kind="icd10_candidate",
                    candidate_value=icd,
                    normalized_candidate_value=normalize_icd(icd),
                    icd10_candidate=icd,
                    drug_code_candidate=join_values(values["drug_code_candidate"]),
                    drug_name_candidate=join_values(values["drug_name_candidate"]),
                    **common,
                )
            )
        for diagnosis in values["diagnosis_text_candidate"]:
            add(
                Candidate(
                    image_filename=image,
                    candidate_kind="diagnosis_text",
                    candidate_value=diagnosis,
                    normalized_candidate_value=normalize_text(diagnosis),
                    drug_code_candidate=join_values(values["drug_code_candidate"]),
                    drug_name_candidate=join_values(values["drug_name_candidate"]),
                    icd10_candidate=join_values(values["icd10_candidate"]),
                    **common,
                )
            )
    return list(candidates.values())


def evidence_from_drug_record(
    record: dict[str, Any],
    evidence_type: str,
    matched_key: str,
    contribution: str,
    source_file: Path,
    notes: str,
) -> Evidence:
    return Evidence(
        evidence_source=DRUG_SOURCE_NAME,
        evidence_type=evidence_type,
        matched_key=matched_key,
        confidence_contribution=contribution,
        source_file=str(source_file),
        source_row_number=record.get("row_number"),
        source_payload=record.get("payload", {}),
        match_notes=notes,
    )


def candidate_value_strengths(value: str) -> list[str]:
    strengths = extract_strengths(value)
    clean = unicodedata.normalize("NFKC", value or "").upper()
    if re.search(r"[A-Z]", clean):
        for match in POSSIBLE_NAME_STRENGTH_RE.finditer(clean):
            amount = match.group(1)
            if amount in {"14", "28", "56", "110", "375"}:
                continue
            before = clean[: match.start()]
            after = clean[match.end() :]
            near_name = bool(re.search(r"[A-Z][A-Z0-9./() -]{0,40}$", before))
            trailing = not re.search(r"[A-Z0-9]", after.strip(" ./()-"))
            if near_name and trailing:
                normalized_amount = amount.rstrip("0").rstrip(".") if "." in amount else amount
                strengths.append(f"{normalized_amount}MG")
    return unique(strengths, limit=40)


def candidate_strengths(candidate: Candidate, include_context: bool = False) -> list[str]:
    strengths = candidate_value_strengths(candidate.candidate_value)
    if include_context:
        strengths.extend(strength.upper().replace(" ", "") for strength in split_values(candidate.strength_candidate))
    return unique(strengths, limit=80)


def strength_matches(candidate: Candidate, record: dict[str, Any]) -> bool:
    candidate_values = set(candidate_strengths(candidate, include_context=False))
    official_values = set(record.get("strengths", []))
    if not candidate_values or not official_values:
        return False
    return bool(candidate_values & official_values)


def clean_name_strength_candidate(candidate: Candidate) -> bool:
    value = candidate.candidate_value
    if len(value) > 100:
        return False
    if DATE_OR_ID_RE.search(value):
        return False
    if not re.search(r"[A-Za-z]", value):
        return False
    if not candidate_strengths(candidate, include_context=False):
        return False
    tokens = significant_tokens(remove_strength_tokens(value))
    if not tokens or len(tokens) > 8:
        return False
    return True


def add_drug_name_evidence(candidate: Candidate, drug_ref: DrugReference, max_fuzzy: int) -> list[Evidence]:
    evidences: list[Evidence] = []
    normalized_name = normalize_text(candidate.candidate_value)
    allow_high_name_strength = clean_name_strength_candidate(candidate)
    exact_matches = drug_ref.exact_name_index.get(normalized_name, [])
    for record in exact_matches[:10]:
        contribution = "high" if allow_high_name_strength and strength_matches(candidate, record) else "medium"
        evidence_type = "drug_name_strength" if contribution == "high" else "drug_name_normalized"
        evidences.append(
            evidence_from_drug_record(
                record,
                evidence_type,
                normalized_name,
                contribution,
                drug_ref.path,
                "official drug name normalized exact match",
            )
        )

    tokens = significant_tokens(remove_strength_tokens(candidate.candidate_value))
    if tokens:
        token_matches = drug_ref.first_token_index.get(tokens[0], [])
        for record in token_matches[:200]:
            official_norms = record.get("name_norms", [])
            if not official_norms:
                continue
            official_blob = " ".join(official_norms)
            if allow_high_name_strength and all(token in official_blob for token in tokens) and strength_matches(candidate, record):
                evidences.append(
                    evidence_from_drug_record(
                        record,
                        "drug_name_strength",
                        " ".join(tokens + candidate_strengths(candidate)),
                        "high",
                        drug_ref.path,
                        "official name token match with strength match",
                    )
                )

    if not evidences and normalized_name:
        best_name = ""
        best_ratio = 0.0
        for official_name in drug_ref.normalized_names[:max_fuzzy]:
            ratio = SequenceMatcher(None, normalized_name, official_name).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_name = official_name
        if best_ratio >= 0.86 and best_name in drug_ref.exact_name_index:
            record = drug_ref.exact_name_index[best_name][0]
            evidences.append(
                evidence_from_drug_record(
                    record,
                    "drug_name_fuzzy",
                    best_name,
                    "medium",
                    drug_ref.path,
                    f"fuzzy normalized name ratio={best_ratio:.2f}",
                )
            )

    ingredient_matches = drug_ref.ingredient_index.get(normalized_name, [])
    for record in ingredient_matches[:5]:
        evidences.append(
            evidence_from_drug_record(
                record,
                "ingredient_name",
                normalized_name,
                "medium",
                drug_ref.path,
                "candidate matched ingredient text, not product name",
            )
        )
    return unique_evidence(evidences)


def unique_evidence(evidences: list[Evidence]) -> list[Evidence]:
    result = []
    seen = set()
    for evidence in evidences:
        key = (
            evidence.evidence_source,
            evidence.evidence_type,
            evidence.matched_key,
            evidence.source_row_number,
        )
        if key in seen:
            continue
        result.append(evidence)
        seen.add(key)
    return result


def evaluate_candidates(
    candidates: list[Candidate],
    drug_ref: DrugReference,
    icd_ref: IcdReference,
    max_fuzzy: int,
) -> list[Candidate]:
    for candidate in candidates:
        evidences: list[Evidence] = []
        if candidate.candidate_kind == "drug_code":
            matches = drug_ref.code_index.get(normalize_code(candidate.candidate_value), [])
            for record in matches[:20]:
                evidences.append(
                    evidence_from_drug_record(
                        record,
                        "drug_code_exact",
                        normalize_code(candidate.candidate_value),
                        "high",
                        drug_ref.path,
                        "official NHI drug code exact match",
                    )
                )
            candidate.source_rows = len(matches)
        elif candidate.candidate_kind in {"drug_name", "drug_name_strength"}:
            evidences.extend(add_drug_name_evidence(candidate, drug_ref, max_fuzzy=max_fuzzy))
            candidate.source_rows = len(evidences)
        elif candidate.candidate_kind == "icd10_candidate":
            match = icd_ref.code_index.get(normalize_icd(candidate.candidate_value))
            if match:
                evidences.append(
                    Evidence(
                        evidence_source=ICD_SOURCE_NAME,
                        evidence_type="icd10_exact",
                        matched_key=match["code"],
                        confidence_contribution="high",
                        source_file=str(icd_ref.path),
                        source_sheet=icd_ref.sheet,
                        source_row_number=match.get("row_number"),
                        source_payload=match.get("payload", {}),
                        match_notes="official NHI ICD-10-CM exact code match",
                    )
                )
                candidate.source_rows = 1

        candidate.evidences = unique_evidence(evidences)
        contributions = {evidence.confidence_contribution for evidence in candidate.evidences}
        sources = {evidence.evidence_source for evidence in candidate.evidences}
        if "high" in contributions or len(sources) >= 2:
            candidate.confidence_level = "high"
            high_reasons = sorted({evidence.evidence_type for evidence in candidate.evidences if evidence.confidence_contribution == "high"})
            candidate.confidence_reason = join_values(high_reasons) or "two_public_sources_matched"
        elif "medium" in contributions:
            candidate.confidence_level = "medium"
            candidate.confidence_reason = join_values(sorted({evidence.evidence_type for evidence in candidate.evidences}))
        else:
            candidate.confidence_level = "low"
            if candidate.candidate_kind == "diagnosis_text":
                candidate.confidence_reason = "diagnosis_text_has_no_exact_public_source_rule"
            else:
                candidate.confidence_reason = "ocr_only_no_public_evidence"
    return candidates


def evidence_summary(candidate: Candidate) -> dict[str, Any]:
    return {
        "evidence_sources": sorted({evidence.evidence_source for evidence in candidate.evidences}),
        "evidence_types": sorted({evidence.evidence_type for evidence in candidate.evidences}),
        "evidence_count": len(candidate.evidences),
        "source_rows": candidate.source_rows,
        "sample_evidence": [evidence.source_payload for evidence in candidate.evidences[:3]],
    }


def staging_row(candidate: Candidate, import_batch_id: str, run_id: str, work_dir: Path, input_csv: Path) -> dict[str, Any]:
    return {
        "import_batch_id": import_batch_id,
        "run_id": run_id,
        "source_work_dir": str(work_dir),
        "source_input_csv": str(input_csv),
        "image_filename": candidate.image_filename,
        "candidate_kind": candidate.candidate_kind,
        "candidate_value": candidate.candidate_value,
        "normalized_candidate_value": candidate.normalized_candidate_value,
        "drug_code_candidate": candidate.drug_code_candidate or None,
        "drug_name_candidate": candidate.drug_name_candidate or None,
        "dose_candidate": candidate.dose_candidate or None,
        "strength_candidate": candidate.strength_candidate or None,
        "frequency_candidate": candidate.frequency_candidate or None,
        "days_candidate": candidate.days_candidate or None,
        "diagnosis_text_candidate": candidate.diagnosis_text_candidate or None,
        "icd10_candidate": candidate.icd10_candidate or None,
        "ocr_source_engine": "mineru",
        "review_priority": candidate.review_priority or None,
        "review_category": candidate.review_category or None,
        "source_status": candidate.source_status or None,
        "filter_reason": candidate.filter_reason or None,
        "candidate_context": candidate.candidate_context or None,
        "line_text": candidate.line_text or None,
        "confidence_level": candidate.confidence_level,
        "confidence_reason": candidate.confidence_reason,
        "evidence_count": len(candidate.evidences),
        "evidence_sources": sorted({evidence.evidence_source for evidence in candidate.evidences}),
        "evidence_summary": evidence_summary(candidate),
        "review_status": "pending",
        "review_decision": None,
        "review_note": None,
    }


def inventory_for(drug_ref: DrugReference, icd_ref: IcdReference) -> list[dict[str, Any]]:
    return [
        {
            "source": DRUG_SOURCE_NAME,
            "path": str(drug_ref.path),
            "row_count": drug_ref.row_count,
            "fields": drug_ref.columns,
            "match_keys": ["藥品代號", "藥品英文名稱", "藥品中文名稱", "成分", "ATC代碼"],
            "contains_drug_code": True,
            "contains_drug_name": True,
            "contains_ingredient": True,
            "contains_atc": "ATC代碼" in drug_ref.columns,
            "contains_nhi_code": "藥品代號" in drug_ref.columns,
            "contains_license": "藥品代碼超連結" in drug_ref.columns,
            "contains_icd10": False,
        },
        {
            "source": ICD_SOURCE_NAME,
            "path": str(icd_ref.path),
            "row_count": icd_ref.row_count,
            "fields": icd_ref.columns,
            "match_keys": ["2023年版 ICD-10-CM code", "CM English name", "CM Chinese name"],
            "contains_drug_code": False,
            "contains_drug_name": False,
            "contains_ingredient": False,
            "contains_atc": False,
            "contains_nhi_code": False,
            "contains_license": False,
            "contains_icd10": True,
        },
    ]


def duplicate_summary(candidates: list[Candidate]) -> tuple[list[tuple[str, int, list[str]]], list[Candidate]]:
    by_value: dict[str, list[Candidate]] = defaultdict(list)
    for candidate in candidates:
        by_value[f"{candidate.candidate_kind}:{candidate.normalized_candidate_value}"].append(candidate)
    repeated = []
    for key, items in by_value.items():
        if len(items) > 1:
            repeated.append((key, len(items), sorted({item.image_filename for item in items})[:8]))
    repeated.sort(key=lambda item: item[1], reverse=True)
    official_ambiguous = [candidate for candidate in candidates if candidate.confidence_level == "high" and candidate.source_rows > 1]
    official_ambiguous.sort(key=lambda item: item.source_rows, reverse=True)
    return repeated, official_ambiguous


def is_safe_exact_candidate(candidate: Candidate) -> bool:
    evidence_types = {evidence.evidence_type for evidence in candidate.evidences}
    if candidate.candidate_kind == "drug_code":
        return candidate.confidence_level == "high" and evidence_types == {"drug_code_exact"}
    if candidate.candidate_kind == "icd10_candidate":
        return candidate.confidence_level == "high" and evidence_types == {"icd10_exact"}
    return False


def unique_constraint_duplicates(candidates: list[Candidate]) -> list[tuple[str, int]]:
    counts: Counter[str] = Counter()
    for candidate in candidates:
        key = "|".join(
            [
                candidate.image_filename,
                candidate.candidate_kind,
                candidate.normalized_candidate_value,
            ]
        )
        counts[key] += 1
    return sorted((key, count) for key, count in counts.items() if count > 1)


def write_report(
    report_path: Path,
    input_csv: Path,
    work_dir: Path,
    import_batch_id: str,
    candidates: list[Candidate],
    high_candidates: list[Candidate],
    inventory: list[dict[str, Any]],
    dry_run: bool,
    only_safe_exact: bool = False,
) -> None:
    confidence_counts = Counter(candidate.confidence_level for candidate in candidates)
    kind_counts = Counter(candidate.candidate_kind for candidate in candidates)
    planned_kind_counts = Counter(candidate.candidate_kind for candidate in high_candidates)
    excluded_reason_counts = Counter(candidate.confidence_reason for candidate in candidates if candidate.confidence_level != "high")
    repeated_candidates, official_ambiguous = duplicate_summary(candidates)
    unique_duplicates = unique_constraint_duplicates(high_candidates)
    evidence_rows_count = sum(len(candidate.evidences) for candidate in high_candidates)
    forbidden_planned = [
        candidate
        for candidate in high_candidates
        if candidate.candidate_kind not in {"drug_code", "icd10_candidate"}
        or {evidence.evidence_type for evidence in candidate.evidences} - {"drug_code_exact", "icd10_exact"}
    ]
    review_status_all_pending = True
    safe_to_apply = (
        dry_run
        and only_safe_exact
        and not forbidden_planned
        and not unique_duplicates
        and bool(high_candidates)
    )

    lines = [
        "# Prescription OCR Staging Import Dry Run",
        "",
        "> OCR candidates are not verified medical facts. This report did not write to formal tables.",
        "",
        "## Safety",
        "",
        f"- dry_run: `{str(dry_run).lower()}`",
        "- apply_executed: `false`" if dry_run else "- apply_executed: `true`",
        "- formal tables touched: `none`",
        "- review_status for all planned staging rows: `pending`",
        "- medium/low confidence rows are excluded from staging.",
        "- formal destination tables excluded: `drug_items`, `diagnosis_codes`, `drug_diagnosis_links`, `customers`",
        f"- only_safe_exact: `{str(only_safe_exact).lower()}`",
        "",
        "## Inputs",
        "",
        f"- input_csv: `{input_csv}`",
        f"- work_dir: `{work_dir}`",
        f"- import_batch_id: `{import_batch_id}`",
        "",
        "## Public Source Inventory",
        "",
        "| source | path | rows | match keys | drug_code | drug_name | ingredient | ATC | NHI code | license | ICD-10 |",
        "|---|---|---:|---|---|---|---|---|---|---|---|",
    ]
    for item in inventory:
        lines.append(
            "| {source} | `{path}` | {rows} | {keys} | {drug_code} | {drug_name} | {ingredient} | {atc} | {nhi} | {license} | {icd} |".format(
                source=md_escape(item["source"]),
                path=md_escape(item["path"]),
                rows=item["row_count"],
                keys=md_escape(", ".join(item["match_keys"]), 140),
                drug_code="yes" if item["contains_drug_code"] else "no",
                drug_name="yes" if item["contains_drug_name"] else "no",
                ingredient="yes" if item["contains_ingredient"] else "no",
                atc="yes" if item["contains_atc"] else "no",
                nhi="yes" if item["contains_nhi_code"] else "no",
                license="yes" if item["contains_license"] else "no",
                icd="yes" if item["contains_icd10"] else "no",
            )
        )

    lines.extend(
        [
            "",
            "## Counts",
            "",
            f"- OCR candidate records considered: {len(candidates)}",
            f"- high confidence: {confidence_counts.get('high', 0)}",
            f"- medium confidence: {confidence_counts.get('medium', 0)}",
            f"- low confidence: {confidence_counts.get('low', 0)}",
            f"- planned staging rows: {len(high_candidates)}",
            f"- planned evidence rows: {evidence_rows_count}",
            f"- safe_to_apply rows: {len(high_candidates) if only_safe_exact else 'not_subset_mode'}",
            f"- planned drug_code exact rows: {planned_kind_counts.get('drug_code', 0)}",
            f"- planned ICD exact rows: {planned_kind_counts.get('icd10_candidate', 0)}",
            f"- planned forbidden/non-safe rows: {len(forbidden_planned)}",
            f"- unique constraint duplicate signatures: {len(unique_duplicates)}",
            f"- review_status all pending: `{str(review_status_all_pending).lower()}`",
            "",
            "## Candidate Kind Counts",
            "",
        ]
    )
    for kind, count in sorted(kind_counts.items()):
        lines.append(f"- {kind}: {count}")

    lines.extend(
        [
            "",
            "## Apply Subset Gate",
            "",
            "| check | result |",
            "|---|---|",
            f"| only safe exact mode | `{str(only_safe_exact).lower()}` |",
            f"| planned row kinds | `{', '.join(f'{k}:{v}' for k, v in sorted(planned_kind_counts.items())) or 'none'}` |",
            f"| allowed evidence types only | `{str(not forbidden_planned).lower()}` |",
            f"| unique constraint duplicates | `{len(unique_duplicates)}` |",
            f"| review_status pending for all planned rows | `{str(review_status_all_pending).lower()}` |",
            f"| safe_to_apply after review | `{str(safe_to_apply).lower()}` |",
            "",
            "Allowed planned rows in this subset:",
            "",
            "- `candidate_kind=drug_code` with `evidence_type=drug_code_exact`",
            "- `candidate_kind=icd10_candidate` with `evidence_type=icd10_exact`",
            "",
            "Explicitly excluded:",
            "",
            "- `drug_name_strength`",
            "- fuzzy or normalized drug name matches",
            "- customer candidates",
            "- relation candidates",
            "- medium / low confidence candidates",
            "- any formal table mutation",
        ]
    )

    lines.extend(
        [
            "",
            "## Planned Safe Exact Staging Rows" if only_safe_exact else "## Planned High Confidence Staging Rows",
            "",
            "| # | image | kind | candidate | normalized_candidate | confidence_reason | evidence_sources | evidence_count | review_status | unique_signature |",
            "|---:|---|---|---|---|---|---|---:|---|---|",
        ]
    )
    for idx, candidate in enumerate(high_candidates, start=1):
        unique_signature = "|".join(
            [
                run_id_for(work_dir),
                candidate.image_filename,
                candidate.candidate_kind,
                candidate.normalized_candidate_value,
            ]
        )
        lines.append(
            "| {idx} | {image} | {kind} | {candidate_value} | {normalized} | {reason} | {sources} | {count} | pending | {signature} |".format(
                idx=idx,
                image=md_escape(candidate.image_filename),
                kind=md_escape(candidate.candidate_kind),
                candidate_value=md_escape(candidate.candidate_value, 120),
                normalized=md_escape(candidate.normalized_candidate_value, 120),
                reason=md_escape(candidate.confidence_reason, 100),
                sources=md_escape(", ".join(sorted({e.evidence_source for e in candidate.evidences}))),
                count=len(candidate.evidences),
                signature=md_escape(unique_signature, 180),
            )
        )

    lines.extend(
        [
            "",
            "## Every Evidence Row Summary For Planned Rows",
            "",
            "| # | staging_row | image | candidate | evidence_type | matched_key | source_row | confidence | source_payload |",
            "|---:|---:|---|---|---|---|---:|---|---|",
        ]
    )
    evidence_idx = 0
    for staging_idx, candidate in enumerate(high_candidates, start=1):
        for evidence in candidate.evidences:
            evidence_idx += 1
            lines.append(
                "| {idx} | {staging_idx} | {image} | {candidate_value} | {etype} | {matched} | {rownum} | {confidence} | {payload} |".format(
                    idx=evidence_idx,
                    staging_idx=staging_idx,
                    image=md_escape(candidate.image_filename),
                    candidate_value=md_escape(candidate.candidate_value, 80),
                    etype=md_escape(evidence.evidence_type),
                    matched=md_escape(evidence.matched_key, 80),
                    rownum=evidence.source_row_number or "",
                    confidence=md_escape(evidence.confidence_contribution),
                    payload=md_escape(json.dumps(evidence.source_payload, ensure_ascii=False), 180),
                )
            )

    lines.extend(
        [
            "",
            "## Excluded Medium/Low Reasons",
            "",
        ]
    )
    for reason, count in excluded_reason_counts.most_common():
        lines.append(f"- {reason}: {count}")

    lines.extend(
        [
            "",
            "## Possible Duplicate Candidates",
            "",
            "| candidate_signature | count | sample_images |",
            "|---|---:|---|",
        ]
    )
    for key, count, images in repeated_candidates[:50]:
        lines.append(f"| {md_escape(key, 120)} | {count} | {md_escape(', '.join(images), 140)} |")

    lines.extend(
        [
            "",
            "## Unique Constraint Check",
            "",
            "Expected staging unique key:",
            "",
            "`(run_id, image_filename, candidate_kind, normalized_candidate_value)`",
            "",
            f"- duplicate signatures inside planned subset: {len(unique_duplicates)}",
        ]
    )
    if unique_duplicates:
        lines.extend(["", "| unique_signature | count |", "|---|---:|"])
        for key, count in unique_duplicates:
            lines.append(f"| {md_escape(key, 180)} | {count} |")
    else:
        lines.append("- result: no duplicate unique signatures in planned subset")

    lines.extend(
        [
            "",
            "## Official Source Ambiguity",
            "",
            "Rows here have high confidence but matched multiple official source rows, usually because the public drug table contains historical price/effective-date rows.",
            "",
            "| image | candidate | source_rows | confidence_reason |",
            "|---|---|---:|---|",
        ]
    )
    for candidate in official_ambiguous[:80]:
        lines.append(
            f"| {md_escape(candidate.image_filename)} | {md_escape(candidate.candidate_value, 120)} | {candidate.source_rows} | {md_escape(candidate.confidence_reason)} |"
        )

    lines.extend(
        [
            "",
            "## DB Rows That Would Be Created",
            "",
            f"- `prescription_ocr_candidate_staging`: {len(high_candidates)} rows",
            f"- `prescription_ocr_candidate_evidence`: {evidence_rows_count} rows",
            "- Every staging row would use `review_status='pending'`.",
            "- No rows would be created for medium or low confidence candidates.",
            "- No rows would be written to `drug_items`, `diagnosis_codes`, `drug_diagnosis_links`, or `customers`.",
            "",
            "## Apply Safety",
            "",
            f"- safe_to_apply_now: `{str(safe_to_apply).lower()}`",
            "- apply_executed: `false`" if dry_run else "- apply_executed: `true`",
            "- The script is dry-run by default and does not read `DATABASE_URL` implicitly.",
            "- This run intentionally stopped before `--apply`.",
            "- Next step, if approved, is to run with explicit `--apply --database-url ...` using the same `--only-safe-exact` subset.",
        ]
    )

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def apply_to_database(staging_rows: list[dict[str, Any]], candidates: list[Candidate], database_url: str) -> None:
    try:
        import psycopg
    except ImportError as exc:
        raise SystemExit("psycopg is required for --apply but is not installed in this environment.") from exc

    staging_columns = [
        "import_batch_id",
        "run_id",
        "source_work_dir",
        "source_input_csv",
        "image_filename",
        "candidate_kind",
        "candidate_value",
        "normalized_candidate_value",
        "drug_code_candidate",
        "drug_name_candidate",
        "dose_candidate",
        "strength_candidate",
        "frequency_candidate",
        "days_candidate",
        "diagnosis_text_candidate",
        "icd10_candidate",
        "ocr_source_engine",
        "review_priority",
        "review_category",
        "source_status",
        "filter_reason",
        "candidate_context",
        "line_text",
        "confidence_level",
        "confidence_reason",
        "evidence_count",
        "evidence_sources",
        "evidence_summary",
        "review_status",
        "review_decision",
        "review_note",
    ]
    placeholders = ", ".join(["%s"] * len(staging_columns))
    column_sql = ", ".join(staging_columns)
    update_sql = ", ".join(
        f"{column}=EXCLUDED.{column}"
        for column in staging_columns
        if column not in {"import_batch_id", "run_id", "image_filename", "candidate_kind", "normalized_candidate_value"}
    )
    insert_sql = f"""
        INSERT INTO prescription_ocr_candidate_staging ({column_sql})
        VALUES ({placeholders})
        ON CONFLICT (run_id, image_filename, candidate_kind, normalized_candidate_value)
        DO UPDATE SET {update_sql}, updated_at = now()
        RETURNING id
    """
    evidence_sql = """
        INSERT INTO prescription_ocr_candidate_evidence (
            staging_candidate_id,
            import_batch_id,
            run_id,
            image_filename,
            candidate_kind,
            candidate_value,
            normalized_candidate_value,
            evidence_source,
            evidence_type,
            matched_key,
            confidence_contribution,
            source_file,
            source_sheet,
            source_row_number,
            source_payload,
            match_notes
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """

    high_candidates_by_signature = {
        (row["image_filename"], row["candidate_kind"], row["normalized_candidate_value"]): candidate
        for row, candidate in zip(staging_rows, candidates)
    }
    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            for row in staging_rows:
                values = []
                for column in staging_columns:
                    value = row[column]
                    if column == "evidence_summary":
                        value = json.dumps(value, ensure_ascii=False)
                    values.append(value)
                cur.execute(insert_sql, values)
                staging_id = cur.fetchone()[0]
                cur.execute("DELETE FROM prescription_ocr_candidate_evidence WHERE staging_candidate_id = %s", (staging_id,))
                candidate = high_candidates_by_signature[
                    (row["image_filename"], row["candidate_kind"], row["normalized_candidate_value"])
                ]
                for evidence in candidate.evidences:
                    cur.execute(
                        evidence_sql,
                        (
                            staging_id,
                            row["import_batch_id"],
                            row["run_id"],
                            row["image_filename"],
                            row["candidate_kind"],
                            row["candidate_value"],
                            row["normalized_candidate_value"],
                            evidence.evidence_source,
                            evidence.evidence_type,
                            evidence.matched_key,
                            evidence.confidence_contribution,
                            evidence.source_file,
                            evidence.source_sheet or None,
                            evidence.source_row_number,
                            json.dumps(evidence.source_payload, ensure_ascii=False),
                            evidence.match_notes,
                        ),
                    )
        conn.commit()


def main() -> int:
    args = build_parser().parse_args()
    input_csv = Path(args.input_csv).expanduser()
    drug_reference = Path(args.drug_reference).expanduser()
    icd_reference = Path(args.icd_reference).expanduser()
    if not input_csv.exists():
        raise SystemExit(f"Input CSV does not exist: {input_csv}")
    if not drug_reference.exists():
        raise SystemExit(f"Drug reference does not exist: {drug_reference}")
    if not icd_reference.exists():
        raise SystemExit(f"ICD reference does not exist: {icd_reference}")
    if args.apply and not args.database_url:
        raise SystemExit("--apply requires --database-url. This script does not read DATABASE_URL implicitly.")

    work_dir = infer_run_dir(input_csv)
    report_path = Path(args.report).expanduser() if args.report else work_dir / "reports" / "03_staging_import_dry_run.md"
    rows, input_columns = read_csv_rows(input_csv)
    if not rows:
        raise SystemExit(f"Input CSV has no rows: {input_csv}")
    invalid_decisions = sorted({row.get("review_decision", "") for row in rows} - REVIEW_DECISION_VALUES)
    if invalid_decisions:
        raise SystemExit(f"Unexpected review_decision values: {invalid_decisions}")

    drug_ref = load_drug_reference(drug_reference)
    icd_ref = load_icd_reference(icd_reference)
    candidates = build_candidates(rows)
    candidates = evaluate_candidates(candidates, drug_ref, icd_ref, args.max_fuzzy_candidates)
    candidates.sort(key=lambda item: (item.confidence_level != "high", item.candidate_kind, item.image_filename, item.candidate_value))
    high_candidates = [candidate for candidate in candidates if candidate.confidence_level == "high"]
    if args.only_safe_exact:
        high_candidates = [candidate for candidate in high_candidates if is_safe_exact_candidate(candidate)]

    import_batch_id = f"prescription_ocr_{run_id_for(work_dir)}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    staging_rows = [staging_row(candidate, import_batch_id, run_id_for(work_dir), work_dir, input_csv) for candidate in high_candidates]

    write_report(
        report_path=report_path,
        input_csv=input_csv,
        work_dir=work_dir,
        import_batch_id=import_batch_id,
        candidates=candidates,
        high_candidates=high_candidates,
        inventory=inventory_for(drug_ref, icd_ref),
        dry_run=not args.apply,
        only_safe_exact=args.only_safe_exact,
    )

    if args.apply:
        apply_to_database(staging_rows, high_candidates, args.database_url)

    counts = Counter(candidate.confidence_level for candidate in candidates)
    print(
        json.dumps(
            {
                "input_csv": str(input_csv),
                "input_columns": input_columns,
                "report": str(report_path),
                "dry_run": not args.apply,
                "candidate_records": len(candidates),
                "high_confidence": counts.get("high", 0),
                "medium_confidence": counts.get("medium", 0),
                "low_confidence": counts.get("low", 0),
                "only_safe_exact": args.only_safe_exact,
                "planned_staging_rows": len(high_candidates),
                "planned_drug_code_exact_rows": sum(candidate.candidate_kind == "drug_code" for candidate in high_candidates),
                "planned_icd10_exact_rows": sum(candidate.candidate_kind == "icd10_candidate" for candidate in high_candidates),
                "planned_evidence_rows": sum(len(candidate.evidences) for candidate in high_candidates),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
