from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from rewrite.tools.prescription_ocr_reference_matcher import DEFAULT_ICD_REFERENCE, build_import_decision_queue


DRUG_HEADER = [
    "異動", "藥品代號", "藥品英文名稱", "藥品中文名稱", "成分", "規格量", "規格單位",
    "單複方", "支付價", "有效起日", "有效迄日", "藥商", "製造廠名稱", "劑型", "藥品分類",
    "分類分組名稱", "ATC代碼", "給付規定章節", "藥品代碼超連結", "給付規定章節連結",
]


class PrescriptionOcrReferenceMatcherTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.run = self.root / "run_test"
        (self.run / "extracted").mkdir(parents=True)
        (self.run / "customer_matching").mkdir()
        self.drug_ref = self.root / "drug.csv"
        with self.drug_ref.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=DRUG_HEADER)
            writer.writeheader()
            writer.writerows([
                {
                    "藥品代號": "AC12345678", "藥品英文名稱": "ALPHA TABLETS 10MG",
                    "藥品中文名稱": "阿法錠10毫克", "成分": "ALPHA 10 MG", "規格量": "10",
                    "規格單位": "MG", "有效迄日": "9991231", "ATC代碼": "A01AA01",
                },
                {
                    "藥品代號": "AC87654321", "藥品英文名稱": "BETA TABLETS 20MG",
                    "藥品中文名稱": "貝他錠20毫克", "成分": "BETA 20 MG", "規格量": "20",
                    "規格單位": "MG", "有效迄日": "9991231", "ATC代碼": "B01BB02",
                },
            ])
        self.icd_ref = DEFAULT_ICD_REFERENCE
        fields = [
            "image_filename", "drug_code_candidate", "drug_name_candidate", "strength_candidate",
            "diagnosis_text_candidate", "icd10_candidate", "line_text", "raw_text",
        ]
        with (self.run / "extracted" / "prescription_candidates_filtered.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows([
                {
                    "image_filename": "IMG_EXACT.JPG", "drug_code_candidate": "AC12345678",
                    "drug_name_candidate": "ALPHA TABLETS 10MG", "strength_candidate": "10MG",
                    "icd10_candidate": "E119", "line_text": "AC12345678 ALPHA TABLETS 10MG E119",
                    "raw_text": "AC12345678 ALPHA TABLETS 10MG\nE119 第二型糖尿病",
                },
                {
                    "image_filename": "IMG_CONFLICT.JPG", "drug_code_candidate": "ZZ99999999",
                    "drug_name_candidate": "BETA TABLETS 20MG", "strength_candidate": "20MG",
                    "icd10_candidate": "E39", "line_text": "ZZ99999999 BETA TABLETS 20MG E39",
                    "raw_text": "ZZ99999999 BETA TABLETS 20MG\nE39",
                },
            ])
        customer_structured = {
            "schema_version": "prescription-customer-review-v2",
            "source_images": ["IMG_EXACT.JPG"],
            "name": {"normalized_value": "王小明"},
        }
        action_fields = [
            "source_image_filename", "action_type", "ocr_text_candidate", "normalized_candidate",
            "matched_short_name", "match_status", "match_score", "line_text", "review_decision",
            "review_note", "structured_fields",
        ]
        with (self.run / "customer_matching" / "ocr_customer_liff_actions.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=action_fields)
            writer.writeheader()
            writer.writerow({
                "source_image_filename": "IMG_EXACT.JPG", "action_type": "new_customer_prefill",
                "ocr_text_candidate": "王小明", "normalized_candidate": "王小明", "match_status": "no_match_possible_new_customer",
                "structured_fields": json.dumps(customer_structured, ensure_ascii=False),
            })

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_builds_existing_queue_contract_with_official_matches(self) -> None:
        result = build_import_decision_queue(
            self.run,
            drug_reference=self.drug_ref,
            icd_reference=self.icd_ref,
            write_artifacts=True,
        )
        self.assertEqual(result["decision_type_counts"]["customer"], 1)
        self.assertEqual(result["drug_match_status_counts"]["exact_code_match"], 1)
        self.assertEqual(result["drug_match_status_counts"]["conflict"], 1)
        self.assertEqual(result["icd_match_status_counts"]["normalized_code_match"], 1)
        self.assertEqual(result["icd_match_status_counts"]["not_found"], 1)
        self.assertFalse(result["relation_formal_apply_allowed"])
        with (self.run / "review" / "import_decision_queue.csv").open(encoding="utf-8") as handle:
            queue = list(csv.DictReader(handle))
        relation = next(row for row in queue if row["decision_type"] == "drug_diagnosis_link")
        self.assertEqual(relation["suggested_action"], "defer_relation")
        self.assertEqual(json.loads(relation["structured_fields"])["formal_apply_allowed"], False)
