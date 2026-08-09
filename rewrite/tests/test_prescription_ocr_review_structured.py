from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from rewrite.tools import prescription_ocr_review as review


class PrescriptionOcrReleaseSeedTest(unittest.TestCase):
    def test_controlled_bundle_installs_only_requested_run_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run_id = "release_smoke_test"
            payload_file = io.StringIO()
            writer = csv.DictWriter(payload_file, fieldnames=["decision_type", "candidate_id"])
            writer.writeheader()
            writer.writerow({"decision_type": "customer", "candidate_id": "customer_action:1"})

            archive_buffer = io.BytesIO()
            with zipfile.ZipFile(archive_buffer, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.writestr(
                    f"{run_id}/review/import_decision_queue.csv",
                    payload_file.getvalue(),
                )
                archive.writestr(
                    f"{run_id}/customer_matching/ocr_customer_liff_actions.csv",
                    "source_image_filename\nIMG_TEST.JPG\n",
                )
            archive_payload = archive_buffer.getvalue()
            bundle = root / "seed.zip.b64"
            bundle.write_bytes(base64.b64encode(archive_payload))

            original_runs_dir = review.DEFAULT_RUNS_DIR
            original_bundle_path = review.SEED_BUNDLE_PATH
            original_bundle_sha256 = review.SEED_BUNDLE_SHA256
            try:
                review.DEFAULT_RUNS_DIR = root / "runtime"
                review.SEED_BUNDLE_PATH = bundle
                review.SEED_BUNDLE_SHA256 = hashlib.sha256(archive_payload).hexdigest()
                queue_path = review.decision_queue_path(run_id)
                self.assertTrue(queue_path.is_file())
                self.assertTrue(
                    (queue_path.parent.parent / "customer_matching" / "ocr_customer_liff_actions.csv").is_file()
                )
                self.assertEqual(queue_path.parents[1].name, run_id)
            finally:
                review.DEFAULT_RUNS_DIR = original_runs_dir
                review.SEED_BUNDLE_PATH = original_bundle_path
                review.SEED_BUNDLE_SHA256 = original_bundle_sha256


class PrescriptionOcrStructuredReviewTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_runs_dir = review.DEFAULT_RUNS_DIR
        review.DEFAULT_RUNS_DIR = Path(self.temp_dir.name)
        self.run_id = "structured_review_test"
        queue = review.DEFAULT_RUNS_DIR / self.run_id / "review" / "import_decision_queue.csv"
        queue.parent.mkdir(parents=True)
        self.structured_fields = {
            "schema_version": "prescription-customer-review-v2",
            "source_images": ["IMG_TEST.JPG"],
            "name": {"normalized_value": "王小明"},
            "short_name": {"normalized_value": "小明"},
            "birthday": {"normalized_value": "1980-01-02"},
            "gender": {"normalized_value": "M"},
            "medical_record_no": {
                "raw_value": "[000517]",
                "normalized_value": "000517",
                "confidence": "medium",
                "evidence": ["病歷號碼 ... [000517]"],
            },
            "patient_identity_markers": {
                "scope": "prescription",
                "raw_values": ["身份：榮保"],
                "normalized_values": ["榮保"],
                "evidence": [{"marker": "榮保", "raw_text": "身份：榮保"}],
            },
        }
        fieldnames = [
            "decision_type",
            "candidate_id",
            "source_image_filename",
            "candidate_value",
            "display_name",
            "suggested_action",
            "existing_status",
            "confidence_level",
            "evidence_summary",
            "review_decision",
            "corrected_value",
            "review_note",
            "structured_fields",
            "structured_corrected_fields",
        ]
        with queue.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerow(
                {
                    "decision_type": "customer",
                    "candidate_id": "customer_action:1",
                    "source_image_filename": "IMG_TEST.JPG",
                    "candidate_value": "王小明",
                    "display_name": "新客戶:王小明",
                    "suggested_action": "create_customer",
                    "existing_status": "not_found",
                    "confidence_level": "manual_review",
                    "evidence_summary": "artifact-only test",
                    "structured_fields": json.dumps(self.structured_fields, ensure_ascii=False),
                }
            )

    def tearDown(self) -> None:
        review.DEFAULT_RUNS_DIR = self.original_runs_dir
        self.temp_dir.cleanup()

    def test_items_parse_structured_customer_fields(self) -> None:
        result = review.load_import_decision_items(self.run_id)
        self.assertTrue(result.ok)
        item = result.data["items"][0]
        self.assertEqual(item["structured_fields"]["medical_record_no"]["normalized_value"], "000517")
        self.assertEqual(
            item["structured_fields"]["patient_identity_markers"]["normalized_values"],
            ["榮保"],
        )

    def test_corrected_preview_is_artifact_only(self) -> None:
        loaded = review.load_import_decision_items(self.run_id)
        item = loaded.data["items"][0]
        result = review.apply_import_review_decisions(
            session=None,
            run_id=self.run_id,
            requested_action="corrected",
            decision_items=[
                {
                    "decision_id": item["decision_id"],
                    "row_number": item["row_number"],
                    "decision_type": "customer",
                    "candidate_id": item["candidate_id"],
                    "expected_review_decision": "",
                }
            ],
            corrected_values={
                item["decision_id"]: {
                    "corrected_value": "王小明",
                    "structured_fields": {
                        "customer_name": "王小明",
                        "short_name": "小明",
                        "birthday": "1980-01-02",
                        "medical_record_no": "000518",
                        "gender": "M",
                        "patient_identity_markers": ["榮保", "重大"],
                    },
                }
            },
            batch_mode="dev_test",
            dry_run=True,
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.data["success_count"], 1)
        self.assertEqual(result.data["formal_tables_touched"], "none")
        per_item = result.data["per_item_result"][0]
        self.assertEqual(per_item["structured_corrected_fields"]["medical_record_no"], "000518")
        self.assertEqual(per_item["structured_corrected_fields"]["short_name"], "小明")
        self.assertEqual(per_item["structured_corrected_fields"]["gender"], "M")
        self.assertEqual(
            per_item["structured_corrected_fields"]["patient_identity_scope"],
            "prescription_review_only",
        )

    def test_identity_card_like_medical_record_is_rejected(self) -> None:
        _data, error = review._validate_customer_structured_correction(
            {
                "customer_name": "王小明",
                "birthday": "",
                "medical_record_no": "A123456789",
                "patient_identity_markers": [],
            }
        )
        self.assertEqual(error, "structured_medical_record_no_looks_like_identity_card")


class PrescriptionOcrOfficialMatchStructuredReviewTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_runs_dir = review.DEFAULT_RUNS_DIR
        review.DEFAULT_RUNS_DIR = Path(self.temp_dir.name)
        self.run_id = "official_structured_review_test"
        queue = review.DEFAULT_RUNS_DIR / self.run_id / "review" / "import_decision_queue.csv"
        queue.parent.mkdir(parents=True)
        fields = [
            "decision_type", "candidate_id", "source_image_filename", "candidate_value",
            "display_name", "suggested_action", "existing_status", "confidence_level",
            "evidence_summary", "review_decision", "corrected_value", "review_note",
            "structured_fields", "structured_corrected_fields",
        ]
        rows = [
            {
                "decision_type": "drug",
                "candidate_id": "drug_match:1",
                "source_image_filename": "IMG_DRUG.JPG",
                "candidate_value": "AC12345678",
                "display_name": "Official Drug",
                "suggested_action": "insert_drug",
                "existing_status": "reference_matched",
                "confidence_level": "high",
                "structured_fields": json.dumps({
                    "schema_version": "prescription-drug-official-match-v1",
                    "effective_fields": {
                        "drug_code": "AC12345678",
                        "drug_name": "Official Drug 10mg",
                        "ingredient": "INGREDIENT 10 MG",
                        "strength_specification": "10MG",
                    },
                }),
            },
            {
                "decision_type": "icd",
                "candidate_id": "icd_match:1",
                "source_image_filename": "IMG_ICD.JPG",
                "candidate_value": "E11.9",
                "display_name": "E11.9 Diabetes",
                "suggested_action": "insert_icd",
                "existing_status": "reference_matched",
                "confidence_level": "high",
                "structured_fields": json.dumps({
                    "schema_version": "prescription-icd-official-match-v1",
                    "effective_fields": {
                        "icd_code": "E11.9",
                        "chinese_name": "第二型糖尿病",
                        "english_name": "Type 2 diabetes mellitus",
                    },
                }, ensure_ascii=False),
            },
        ]
        with queue.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)

    def tearDown(self) -> None:
        review.DEFAULT_RUNS_DIR = self.original_runs_dir
        self.temp_dir.cleanup()

    def test_corrected_requires_complete_structured_value_without_ocr_fallback(self) -> None:
        item = review.load_import_decision_items(self.run_id).data["items"][0]
        result = review.apply_import_review_decisions(
            session=None,
            run_id=self.run_id,
            requested_action="corrected",
            decision_items=[{"decision_id": item["decision_id"]}],
            corrected_values={item["decision_id"]: {"corrected_value": "AC12345678"}},
            batch_mode="dev_test",
            dry_run=True,
        )
        self.assertEqual(result.data["failed_count"], 1)
        self.assertEqual(
            result.data["per_item_result"][0]["reason"],
            "structured_corrected_fields_required_no_ocr_fallback",
        )

    def test_drug_and_icd_corrected_preview_uses_only_structured_corrections(self) -> None:
        items = review.load_import_decision_items(self.run_id).data["items"]
        drug, icd = items
        corrections = {
            drug["decision_id"]: {
                "corrected_value": "AC12345678",
                "structured_fields": {
                    "drug_code": "AC12345678",
                    "drug_name": "Corrected Drug 10mg",
                    "ingredient": "INGREDIENT 10 MG",
                    "strength_specification": "10MG",
                },
            },
            icd["decision_id"]: {
                "corrected_value": "E11.9",
                "structured_fields": {
                    "icd_code": "E11.9",
                    "chinese_name": "第二型糖尿病，未伴有併發症",
                    "english_name": "Type 2 diabetes mellitus without complications",
                },
            },
        }
        result = review.apply_import_review_decisions(
            session=None,
            run_id=self.run_id,
            requested_action="corrected",
            decision_items=[{"decision_id": item["decision_id"]} for item in items],
            corrected_values=corrections,
            batch_mode="dev_test",
            dry_run=True,
        )
        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.data["success_count"], 2)
        self.assertEqual(result.data["formal_tables_touched"], "none")
        for item in result.data["per_item_result"]:
            self.assertEqual(item["effective_structured_fields_source"], "structured_corrected_fields")
            self.assertEqual(item["reason"], "official_match_review_decision_recordable_no_formal_write")


if __name__ == "__main__":
    unittest.main()
