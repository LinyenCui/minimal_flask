#!/usr/bin/env python3
"""Import official drug raw files into staging tables.

Default mode is dry-run and does not connect to the database.
Use --apply only after reviewing the dry-run report.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import os
import re
import sys
import zipfile
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Callable, Iterable
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "reference_data/drug/raw"
STAGING_DIR = ROOT / "db_backups/drug_staging"
MANIFEST_PATH = RAW_DIR / "00_download_manifest.md"
DRY_RUN_REPORT = STAGING_DIR / "00_official_drug_staging_import_dry_run_report.md"
APPLY_REPORT = STAGING_DIR / "00_official_drug_staging_import_apply_report.md"
SOURCE_VERSION = "official_drug_raw_20260522"
BATCH_PREFIX = "official_drug_staging"
BATCH_SIZE = 5000


@dataclass(frozen=True)
class DatasetSpec:
    key: str
    title: str
    table_name: str
    local_path: str
    create_sql_path: str
    inner_file: str | None
    kind: str


DATASETS = [
    DatasetSpec(
        key="nhi_payment",
        title="NHI drug payment",
        table_name="official_nhi_drug_payment_staging",
        local_path="reference_data/drug/raw/nhi_drug_payment_20260522.csv",
        create_sql_path="db_backups/drug_staging/create_official_nhi_drug_payment_staging.sql",
        inner_file=None,
        kind="nhi",
    ),
    DatasetSpec(
        key="tfda_license",
        title="TFDA license",
        table_name="official_tfda_drug_license_staging",
        local_path="reference_data/drug/raw/tfda_drug_license_20260522.zip",
        create_sql_path="db_backups/drug_staging/create_official_tfda_drug_license_staging.sql",
        inner_file="36_2.csv",
        kind="tfda_license",
    ),
    DatasetSpec(
        key="tfda_ingredient",
        title="TFDA ingredient",
        table_name="official_tfda_drug_ingredient_staging",
        local_path="reference_data/drug/raw/tfda_drug_ingredient_20260522.zip",
        create_sql_path="db_backups/drug_staging/create_official_tfda_drug_ingredient_staging.sql",
        inner_file="43_2.csv",
        kind="tfda_ingredient",
    ),
    DatasetSpec(
        key="tfda_atc",
        title="TFDA ATC",
        table_name="official_tfda_atc_staging",
        local_path="reference_data/drug/raw/tfda_atc_20260522.zip",
        create_sql_path="db_backups/drug_staging/create_official_tfda_atc_staging.sql",
        inner_file="41_2.csv",
        kind="tfda_atc",
    ),
]

DATASET_BY_KEY = {spec.key: spec for spec in DATASETS}


NHI_COLUMNS = [
    "raw_change_flag",
    "raw_drug_code",
    "raw_drug_name_en",
    "raw_drug_name_zh",
    "raw_ingredient",
    "raw_spec_amount",
    "raw_spec_unit",
    "raw_single_or_compound",
    "raw_payment_price",
    "raw_effective_start_date",
    "raw_effective_end_date",
    "raw_supplier",
    "raw_manufacturer_name",
    "raw_dosage_form",
    "raw_drug_category",
    "raw_category_group_name",
    "raw_atc_code",
    "raw_reimbursement_rule_chapter",
    "raw_drug_code_url",
    "raw_reimbursement_rule_url",
    "normalized_drug_code",
    "normalized_drug_name_en",
    "normalized_drug_name_zh",
    "normalized_ingredient",
    "normalized_spec_amount",
    "normalized_spec_unit",
    "normalized_payment_price",
    "effective_start_date",
    "effective_end_date",
    "normalized_supplier",
    "normalized_manufacturer_name",
    "normalized_dosage_form",
    "normalized_atc_code",
    "parsed_tfda_license_id",
    "normalized_license_no",
    "source_file",
    "source_url",
    "source_version",
    "import_batch_id",
    "source_checksum",
    "source_row_number",
    "notes",
]

TFDA_LICENSE_COLUMNS = [
    "raw_license_no",
    "raw_cancel_status",
    "raw_cancel_date",
    "raw_cancel_reason",
    "raw_valid_until",
    "raw_issue_date",
    "raw_license_type",
    "raw_old_license_no",
    "raw_import_clearance_no",
    "raw_product_name_zh",
    "raw_product_name_en",
    "raw_indication",
    "raw_dosage_form",
    "raw_package",
    "raw_drug_category",
    "raw_controlled_drug_level",
    "raw_main_ingredient_summary",
    "raw_applicant_name",
    "raw_applicant_address",
    "raw_applicant_tax_id",
    "raw_manufacturer_name",
    "raw_manufacturer_address",
    "raw_manufacturer_company_address",
    "raw_manufacturer_country",
    "raw_manufacturing_process",
    "raw_changed_at",
    "raw_usage_dosage",
    "raw_package_and_barcode",
    "normalized_license_no",
    "normalized_old_license_no",
    "normalized_product_name_zh",
    "normalized_product_name_en",
    "normalized_dosage_form",
    "normalized_main_ingredient_summary",
    "normalized_applicant_name",
    "normalized_manufacturer_name",
    "normalized_manufacturer_country",
    "license_valid_until",
    "license_issue_date",
    "cancel_date",
    "changed_at",
    "is_cancelled",
    "is_active_license",
    "source_file",
    "source_inner_file",
    "source_url",
    "source_version",
    "import_batch_id",
    "source_checksum",
    "source_row_number",
    "notes",
]

TFDA_INGREDIENT_COLUMNS = [
    "raw_license_no",
    "raw_prescription_label",
    "raw_ingredient_name",
    "raw_ingredient_code",
    "raw_amount_description",
    "raw_amount",
    "raw_amount_unit",
    "normalized_license_no",
    "normalized_ingredient_name",
    "normalized_ingredient_code",
    "normalized_amount",
    "normalized_amount_unit",
    "source_file",
    "source_inner_file",
    "source_url",
    "source_version",
    "import_batch_id",
    "source_checksum",
    "source_row_number",
    "notes",
]

TFDA_ATC_COLUMNS = [
    "raw_license_no",
    "raw_primary_or_secondary",
    "raw_atc_code",
    "raw_atc_name_en",
    "raw_atc_name_zh",
    "normalized_license_no",
    "normalized_atc_code",
    "normalized_atc_name_en",
    "normalized_atc_name_zh",
    "is_primary_atc",
    "source_file",
    "source_inner_file",
    "source_url",
    "source_version",
    "import_batch_id",
    "source_checksum",
    "source_row_number",
    "notes",
]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_manifest() -> dict[str, dict[str, str]]:
    text = MANIFEST_PATH.read_text(encoding="utf-8")
    entries: dict[str, dict[str, str]] = {}
    current: str | None = None
    for line in text.splitlines():
        m = re.match(r"- local_path：(.+)", line)
        if m:
            current = m.group(1).strip("` ")
            entries[current] = {}
            continue
        if not current:
            continue
        for key in ["file_size", "sha256", "source_url", "資料名稱", "來源類型", "檔案格式"]:
            m2 = re.match(rf"- {key}：(.+)", line)
            if m2:
                entries[current][key] = m2.group(1).strip()
    return entries


def verify_manifest(entries: dict[str, dict[str, str]], datasets: list[DatasetSpec]) -> list[dict[str, object]]:
    results = []
    for spec in datasets:
        path = ROOT / spec.local_path
        entry = entries.get(spec.local_path, {})
        got_sha = sha256_file(path)
        size = path.stat().st_size
        expected_size = int(entry.get("file_size", "0") or 0)
        expected_sha = entry.get("sha256", "")
        results.append(
            {
                "dataset": spec.title,
                "path": spec.local_path,
                "exists": path.exists(),
                "size": size,
                "manifest_size": expected_size,
                "sha256": got_sha,
                "manifest_sha256": expected_sha,
                "sha256_match": got_sha == expected_sha,
                "size_match": size == expected_size,
                "source_url": entry.get("source_url", ""),
            }
        )
    return results


def open_dataset_text(spec: DatasetSpec):
    path = ROOT / spec.local_path
    if spec.inner_file:
        zf = zipfile.ZipFile(path)
        raw = zf.open(spec.inner_file)
        wrapper = io.TextIOWrapper(raw, encoding="utf-8-sig", newline="")
        return zf, wrapper
    return None, path.open(encoding="utf-8-sig", newline="")


def count_rows(spec: DatasetSpec) -> int:
    holder, text_file = open_dataset_text(spec)
    try:
        reader = csv.DictReader(text_file)
        return sum(1 for _ in reader)
    finally:
        text_file.close()
        if holder:
            holder.close()


def normalize_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    text = re.sub(r"\s+", " ", text)
    return text.upper()


def raw_text(row: dict[str, str], key: str) -> str | None:
    value = row.get(key)
    if value is None:
        return None
    value = value.strip()
    return value if value != "" else None


def parse_decimal(value: str | None) -> Decimal | None:
    if not value:
        return None
    try:
        return Decimal(str(value).strip().replace(",", ""))
    except (InvalidOperation, ValueError):
        return None


def parse_roc_date(value: str | None) -> str | None:
    if not value:
        return None
    digits = re.sub(r"\D", "", value)
    if len(digits) == 6:
        year = int(digits[:2]) + 1911
        month = int(digits[2:4])
        day = int(digits[4:6])
    elif len(digits) == 7:
        year = int(digits[:3]) + 1911
        month = int(digits[3:5])
        day = int(digits[5:7])
    else:
        return None
    try:
        return f"{year:04d}-{month:02d}-{day:02d}"
    except ValueError:
        return None


def parse_yyyy_slash_date(value: str | None) -> str | None:
    if not value:
        return None
    text = value.strip()
    if not text:
        return None
    for sep in ["/", "-"]:
        parts = text.split(sep)
        if len(parts) == 3:
            try:
                year, month, day = [int(p) for p in parts]
                return f"{year:04d}-{month:02d}-{day:02d}"
            except ValueError:
                return None
    return None


def parse_lic_id(url: str | None) -> str | None:
    if not url:
        return None
    parsed = urlparse(url.strip())
    values = parse_qs(parsed.query).get("licId")
    if not values:
        return None
    return values[0].strip() or None


def normalize_atc(value: str | None) -> str | None:
    return normalize_text(value)


def is_cancelled(value: str | None) -> bool | None:
    if value is None:
        return None
    return bool(value.strip())


def is_primary_atc(value: str | None) -> bool | None:
    if value is None:
        return None
    stripped = value.strip()
    if stripped == "主":
        return True
    if stripped == "次":
        return False
    return None


def add_meta(record: OrderedDict, spec: DatasetSpec, source_url: str, checksum: str, source_row_number: int, import_batch_id: str) -> OrderedDict:
    record["source_file"] = spec.local_path
    if spec.inner_file:
        record["source_inner_file"] = spec.inner_file
    record["source_url"] = source_url
    record["source_version"] = SOURCE_VERSION
    record["import_batch_id"] = import_batch_id
    record["source_checksum"] = checksum
    record["source_row_number"] = source_row_number
    record["notes"] = None
    return record


def map_nhi(row: dict[str, str], spec: DatasetSpec, source_url: str, checksum: str, source_row_number: int, import_batch_id: str) -> OrderedDict:
    parsed_lic_id = parse_lic_id(raw_text(row, "藥品代碼超連結"))
    record = OrderedDict(
        [
            ("raw_change_flag", raw_text(row, "異動")),
            ("raw_drug_code", raw_text(row, "藥品代號")),
            ("raw_drug_name_en", raw_text(row, "藥品英文名稱")),
            ("raw_drug_name_zh", raw_text(row, "藥品中文名稱")),
            ("raw_ingredient", raw_text(row, "成分")),
            ("raw_spec_amount", raw_text(row, "規格量")),
            ("raw_spec_unit", raw_text(row, "規格單位")),
            ("raw_single_or_compound", raw_text(row, "單複方")),
            ("raw_payment_price", raw_text(row, "支付價")),
            ("raw_effective_start_date", raw_text(row, "有效起日")),
            ("raw_effective_end_date", raw_text(row, "有效迄日")),
            ("raw_supplier", raw_text(row, "藥商")),
            ("raw_manufacturer_name", raw_text(row, "製造廠名稱")),
            ("raw_dosage_form", raw_text(row, "劑型")),
            ("raw_drug_category", raw_text(row, "藥品分類")),
            ("raw_category_group_name", raw_text(row, "分類分組名稱")),
            ("raw_atc_code", raw_text(row, "ATC代碼")),
            ("raw_reimbursement_rule_chapter", raw_text(row, "給付規定章節")),
            ("raw_drug_code_url", raw_text(row, "藥品代碼超連結")),
            ("raw_reimbursement_rule_url", raw_text(row, "給付規定章節連結")),
            ("normalized_drug_code", normalize_text(raw_text(row, "藥品代號"))),
            ("normalized_drug_name_en", normalize_text(raw_text(row, "藥品英文名稱"))),
            ("normalized_drug_name_zh", normalize_text(raw_text(row, "藥品中文名稱"))),
            ("normalized_ingredient", normalize_text(raw_text(row, "成分"))),
            ("normalized_spec_amount", parse_decimal(raw_text(row, "規格量"))),
            ("normalized_spec_unit", normalize_text(raw_text(row, "規格單位"))),
            ("normalized_payment_price", parse_decimal(raw_text(row, "支付價"))),
            ("effective_start_date", parse_roc_date(raw_text(row, "有效起日"))),
            ("effective_end_date", parse_roc_date(raw_text(row, "有效迄日"))),
            ("normalized_supplier", normalize_text(raw_text(row, "藥商"))),
            ("normalized_manufacturer_name", normalize_text(raw_text(row, "製造廠名稱"))),
            ("normalized_dosage_form", normalize_text(raw_text(row, "劑型"))),
            ("normalized_atc_code", normalize_atc(raw_text(row, "ATC代碼"))),
            ("parsed_tfda_license_id", parsed_lic_id),
            ("normalized_license_no", None),
        ]
    )
    return add_meta(record, spec, source_url, checksum, source_row_number, import_batch_id)


def map_tfda_license(row: dict[str, str], spec: DatasetSpec, source_url: str, checksum: str, source_row_number: int, import_batch_id: str) -> OrderedDict:
    cancel = raw_text(row, "註銷狀態")
    record = OrderedDict(
        [
            ("raw_license_no", raw_text(row, "許可證字號")),
            ("raw_cancel_status", cancel),
            ("raw_cancel_date", raw_text(row, "註銷日期")),
            ("raw_cancel_reason", raw_text(row, "註銷理由")),
            ("raw_valid_until", raw_text(row, "有效日期")),
            ("raw_issue_date", raw_text(row, "發證日期")),
            ("raw_license_type", raw_text(row, "許可證種類")),
            ("raw_old_license_no", raw_text(row, "舊證字號")),
            ("raw_import_clearance_no", raw_text(row, "通關簽審文件編號")),
            ("raw_product_name_zh", raw_text(row, "中文品名")),
            ("raw_product_name_en", raw_text(row, "英文品名")),
            ("raw_indication", raw_text(row, "適應症")),
            ("raw_dosage_form", raw_text(row, "劑型")),
            ("raw_package", raw_text(row, "包裝")),
            ("raw_drug_category", raw_text(row, "藥品類別")),
            ("raw_controlled_drug_level", raw_text(row, "管制藥品分類級別")),
            ("raw_main_ingredient_summary", raw_text(row, "主成分略述")),
            ("raw_applicant_name", raw_text(row, "申請商名稱")),
            ("raw_applicant_address", raw_text(row, "申請商地址")),
            ("raw_applicant_tax_id", raw_text(row, "申請商統一編號")),
            ("raw_manufacturer_name", raw_text(row, "製造商名稱")),
            ("raw_manufacturer_address", raw_text(row, "製造廠廠址")),
            ("raw_manufacturer_company_address", raw_text(row, "製造廠公司地址")),
            ("raw_manufacturer_country", raw_text(row, "製造廠國別")),
            ("raw_manufacturing_process", raw_text(row, "製程")),
            ("raw_changed_at", raw_text(row, "異動日期")),
            ("raw_usage_dosage", raw_text(row, "用法用量")),
            ("raw_package_and_barcode", raw_text(row, "包裝與國際條碼")),
            ("normalized_license_no", normalize_text(raw_text(row, "許可證字號"))),
            ("normalized_old_license_no", normalize_text(raw_text(row, "舊證字號"))),
            ("normalized_product_name_zh", normalize_text(raw_text(row, "中文品名"))),
            ("normalized_product_name_en", normalize_text(raw_text(row, "英文品名"))),
            ("normalized_dosage_form", normalize_text(raw_text(row, "劑型"))),
            ("normalized_main_ingredient_summary", normalize_text(raw_text(row, "主成分略述"))),
            ("normalized_applicant_name", normalize_text(raw_text(row, "申請商名稱"))),
            ("normalized_manufacturer_name", normalize_text(raw_text(row, "製造商名稱"))),
            ("normalized_manufacturer_country", normalize_text(raw_text(row, "製造廠國別"))),
            ("license_valid_until", parse_yyyy_slash_date(raw_text(row, "有效日期"))),
            ("license_issue_date", parse_yyyy_slash_date(raw_text(row, "發證日期"))),
            ("cancel_date", parse_yyyy_slash_date(raw_text(row, "註銷日期"))),
            ("changed_at", parse_yyyy_slash_date(raw_text(row, "異動日期"))),
            ("is_cancelled", is_cancelled(cancel)),
            ("is_active_license", False if is_cancelled(cancel) else True),
        ]
    )
    return add_meta(record, spec, source_url, checksum, source_row_number, import_batch_id)


def map_tfda_ingredient(row: dict[str, str], spec: DatasetSpec, source_url: str, checksum: str, source_row_number: int, import_batch_id: str) -> OrderedDict:
    record = OrderedDict(
        [
            ("raw_license_no", raw_text(row, "許可證字號")),
            ("raw_prescription_label", raw_text(row, "處方標示")),
            ("raw_ingredient_name", raw_text(row, "成分名稱")),
            ("raw_ingredient_code", raw_text(row, "成分代碼")),
            ("raw_amount_description", raw_text(row, "含量描述")),
            ("raw_amount", raw_text(row, "含量")),
            ("raw_amount_unit", raw_text(row, "含量單位")),
            ("normalized_license_no", normalize_text(raw_text(row, "許可證字號"))),
            ("normalized_ingredient_name", normalize_text(raw_text(row, "成分名稱"))),
            ("normalized_ingredient_code", normalize_text(raw_text(row, "成分代碼"))),
            ("normalized_amount", parse_decimal(raw_text(row, "含量"))),
            ("normalized_amount_unit", normalize_text(raw_text(row, "含量單位"))),
        ]
    )
    return add_meta(record, spec, source_url, checksum, source_row_number, import_batch_id)


def map_tfda_atc(row: dict[str, str], spec: DatasetSpec, source_url: str, checksum: str, source_row_number: int, import_batch_id: str) -> OrderedDict:
    record = OrderedDict(
        [
            ("raw_license_no", raw_text(row, "許可證字號")),
            ("raw_primary_or_secondary", raw_text(row, "主或次項")),
            ("raw_atc_code", raw_text(row, "代碼")),
            ("raw_atc_name_en", raw_text(row, "英文分類名稱")),
            ("raw_atc_name_zh", raw_text(row, "中文分類名稱")),
            ("normalized_license_no", normalize_text(raw_text(row, "許可證字號"))),
            ("normalized_atc_code", normalize_atc(raw_text(row, "代碼"))),
            ("normalized_atc_name_en", normalize_text(raw_text(row, "英文分類名稱"))),
            ("normalized_atc_name_zh", normalize_text(raw_text(row, "中文分類名稱"))),
            ("is_primary_atc", is_primary_atc(raw_text(row, "主或次項"))),
        ]
    )
    return add_meta(record, spec, source_url, checksum, source_row_number, import_batch_id)


MAPPERS: dict[str, tuple[list[str], Callable[..., OrderedDict]]] = {
    "nhi": (NHI_COLUMNS, map_nhi),
    "tfda_license": (TFDA_LICENSE_COLUMNS, map_tfda_license),
    "tfda_ingredient": (TFDA_INGREDIENT_COLUMNS, map_tfda_ingredient),
    "tfda_atc": (TFDA_ATC_COLUMNS, map_tfda_atc),
}


def iter_records(spec: DatasetSpec, source_url: str, checksum: str, import_batch_id: str) -> Iterable[OrderedDict]:
    holder, text_file = open_dataset_text(spec)
    try:
        reader = csv.DictReader(text_file)
        _, mapper = MAPPERS[spec.kind]
        for line_number, row in enumerate(reader, start=2):
            yield mapper(row, spec, source_url, checksum, line_number, import_batch_id)
    finally:
        text_file.close()
        if holder:
            holder.close()


def make_batch_id() -> str:
    return f"{BATCH_PREFIX}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"


def md_table(headers: list[str], rows: list[list[object]]) -> str:
    out = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in rows:
        out.append("| " + " | ".join(str(item).replace("|", "/").replace("\n", " ") for item in row) + " |")
    return "\n".join(out)


def write_dry_run_report(import_batch_id: str, sha_results: list[dict[str, object]], row_counts: dict[str, int], datasets: list[DatasetSpec]) -> None:
    rows = []
    for spec in datasets:
        sha = next(item for item in sha_results if item["path"] == spec.local_path)
        rows.append([
            spec.title,
            spec.local_path,
            spec.table_name,
            row_counts[spec.key],
            "yes" if sha["sha256_match"] else "NO",
            sha["sha256"],
        ])
    lines = [
        "# 官方藥品 staging import dry-run report",
        "",
        f"產生時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"import_batch_id：`{import_batch_id}`",
        "",
        "## 本階段行為",
        "",
        "本次為 dry-run：只讀 manifest 與 raw files，驗證 sha256，統計 row count，未連資料庫、未建立 table、未寫入資料。",
        "",
        "## manifest verification / target tables",
        "",
        md_table(["dataset", "source_file", "target_table", "estimated_insert_count", "sha256_match", "sha256"], rows),
        "",
        "## 預計匯入策略",
        "",
        "- 只有執行 `--apply` 才會讀取 `.env` / `DATABASE_URL`。",
        "- apply 時只會建立/寫入四張 official drug raw staging tables。",
        "- apply 時會先檢查同一 `source_version + source_checksum` 是否已存在；若存在則停止，避免重複匯入。",
        "- 不會修改 `drug_items`、`drug_diagnosis_links` 或 diagnosis 相關資料表。",
    ]
    DRY_RUN_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_env_file() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def normalize_database_url(url: str) -> str:
    if url.startswith("postgresql+psycopg://"):
        return "postgresql://" + url[len("postgresql+psycopg://") :]
    if url.startswith("postgresql+psycopg2://"):
        return "postgresql://" + url[len("postgresql+psycopg2://") :]
    return url


def validate_database_url(url: str) -> str:
    normalized = normalize_database_url(url)
    parsed = urlparse(normalized)
    host = parsed.hostname or ""
    port = parsed.port or 5432
    db_name = (parsed.path or "").lstrip("/")
    if host not in {"localhost", "127.0.0.1"} or port != 5432 or db_name != "dispatch_db":
        raise SystemExit("DATABASE_URL must point to localhost:5432/dispatch_db for this importer.")
    return normalized


def table_count(cur, table_name: str) -> int | None:
    cur.execute("SELECT to_regclass(%s)", (table_name,))
    if cur.fetchone()[0] is None:
        return None
    cur.execute(f"SELECT COUNT(*) FROM {table_name}")
    return int(cur.fetchone()[0])


def count_matching_source(cur, table_name: str, source_version: str, checksum: str) -> int:
    cur.execute(f"SELECT COUNT(*) FROM {table_name} WHERE source_version = %s AND source_checksum = %s", (source_version, checksum))
    return int(cur.fetchone()[0])


def execute_create_sql(cur, datasets: list[DatasetSpec]) -> None:
    for spec in datasets:
        sql_path = ROOT / spec.create_sql_path
        cur.execute(sql_path.read_text(encoding="utf-8"))


def insert_dataset(conn, spec: DatasetSpec, source_url: str, checksum: str, import_batch_id: str) -> dict[str, object]:
    from psycopg2.extras import execute_values

    columns, _ = MAPPERS[spec.kind]
    inserted = 0
    with conn:
        with conn.cursor() as cur:
            existing = count_matching_source(cur, spec.table_name, SOURCE_VERSION, checksum)
            if existing:
                raise RuntimeError(f"{spec.table_name} already has {existing} rows for source_version/source_checksum")
            sql = f"INSERT INTO {spec.table_name} ({', '.join(columns)}) VALUES %s"
            batch = []
            for record in iter_records(spec, source_url, checksum, import_batch_id):
                batch.append(tuple(record[col] for col in columns))
                if len(batch) >= BATCH_SIZE:
                    execute_values(cur, sql, batch, page_size=BATCH_SIZE)
                    inserted += len(batch)
                    batch.clear()
            if batch:
                execute_values(cur, sql, batch, page_size=BATCH_SIZE)
                inserted += len(batch)
            final_count = table_count(cur, spec.table_name)
    return {"dataset": spec.title, "table": spec.table_name, "inserted": inserted, "final_count": final_count, "status": "inserted"}


def write_apply_report(import_batch_id: str, sha_results: list[dict[str, object]], results: list[dict[str, object]], counts_before: dict[str, int | None], counts_after: dict[str, int | None]) -> None:
    rows = []
    for result in results:
        sha = next(item for item in sha_results if item["dataset"] == result["dataset"])
        rows.append([
            result["dataset"],
            sha["path"],
            sha["sha256"],
            result["table"],
            result.get("inserted", 0),
            result.get("final_count", "-"),
            result.get("status", "-"),
        ])
    lines = [
        "# 官方藥品 staging import apply report",
        "",
        f"產生時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"import_batch_id：`{import_batch_id}`",
        "",
        "## 匯入結果",
        "",
        md_table(["dataset", "source_file", "sha256", "table", "inserted_rows", "final_table_rows", "status"], rows),
        "",
        "## 正式表筆數檢查",
        "",
        md_table(
            ["table", "before", "after"],
            [[name, counts_before.get(name), counts_after.get(name)] for name in ["drug_items", "drug_diagnosis_links"]],
        ),
        "",
        "本次只建立/寫入 official drug raw staging tables。未修改 `drug_items`，未修改 `drug_diagnosis_links`，未修改 diagnosis 相關資料表。",
    ]
    APPLY_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_dry_run(import_batch_id: str, datasets: list[DatasetSpec]) -> None:
    entries = parse_manifest()
    sha_results = verify_manifest(entries, datasets)
    row_counts = {spec.key: count_rows(spec) for spec in datasets}
    write_dry_run_report(import_batch_id, sha_results, row_counts, datasets)
    print(f"import_batch_id: {import_batch_id}")
    for item in sha_results:
        print(f"{item['dataset']}: sha256_match={item['sha256_match']} size_match={item['size_match']}")
    for spec in datasets:
        print(f"{spec.title}: target={spec.table_name} rows={row_counts[spec.key]}")
    print(f"dry-run report: {DRY_RUN_REPORT}")


def run_apply(import_batch_id: str, datasets: list[DatasetSpec]) -> None:
    load_env_file()
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL is required for --apply.")
    safe_url = validate_database_url(database_url)

    try:
        import psycopg2
    except ImportError as exc:
        raise SystemExit("psycopg2 is required for --apply.") from exc

    entries = parse_manifest()
    sha_results = verify_manifest(entries, datasets)
    if not all(item["sha256_match"] and item["size_match"] for item in sha_results):
        raise SystemExit("Manifest verification failed; stop before database work.")

    results = []
    conn = psycopg2.connect(safe_url)
    try:
        with conn.cursor() as cur:
            counts_before = {
                "drug_items": table_count(cur, "drug_items"),
                "drug_diagnosis_links": table_count(cur, "drug_diagnosis_links"),
            }
            execute_create_sql(cur, datasets)
        conn.commit()

        for spec in datasets:
            sha = next(item for item in sha_results if item["path"] == spec.local_path)
            try:
                result = insert_dataset(conn, spec, str(sha["source_url"]), str(sha["sha256"]), import_batch_id)
            except Exception as exc:
                results.append({"dataset": spec.title, "table": spec.table_name, "inserted": 0, "final_count": "unknown", "status": f"failed: {exc}"})
                raise
            else:
                results.append(result)
        with conn.cursor() as cur:
            counts_after = {
                "drug_items": table_count(cur, "drug_items"),
                "drug_diagnosis_links": table_count(cur, "drug_diagnosis_links"),
            }
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    write_apply_report(import_batch_id, sha_results, results, counts_before, counts_after)
    print(f"apply report: {APPLY_REPORT}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Import official drug raw files into staging tables.")
    parser.add_argument("--apply", action="store_true", help="create staging tables and insert raw data")
    parser.add_argument(
        "--dataset",
        choices=["all", *DATASET_BY_KEY.keys()],
        default="all",
        help="limit dry-run/apply to one dataset",
    )
    args = parser.parse_args()
    datasets = DATASETS if args.dataset == "all" else [DATASET_BY_KEY[args.dataset]]
    import_batch_id = make_batch_id()
    if args.apply:
        run_apply(import_batch_id, datasets)
    else:
        run_dry_run(import_batch_id, datasets)


if __name__ == "__main__":
    main()
