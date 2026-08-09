from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from unittest.mock import patch

from rewrite.tools.base import ToolResult
from rewrite.tools import prescription_ocr_review as review
from rewrite.tools import prescription_ocr_medical_apply as adapter
from rewrite.tools.prescription_ocr_medical_apply import classify_drug_plan, classify_icd_plan


def drug_candidate(**overrides):
    value = {
        "formal_fields": {
            "seq_no": "NHI-AC12345678",
            "table_type": "oral",
            "generic_name": "TEST INGREDIENT 10 MG",
            "brand_name": "TEST TABLETS 10MG",
            "aliases": "測試錠10毫克",
            "item_kind": "oral_drug",
            "needs_manual_check": False,
            "source_photo": "IMG_TEST.JPG",
            "source_version": "prescription_ocr_v1",
            "staging_import_batch_id": "prescription_ocr:test",
            "staging_row_id": 1,
            "is_active": True,
            "nhi_drug_code": "AC12345678",
            "nhi_drug_code_source": "official_nhi",
            "nhi_drug_code_confidence": "high",
        }
    }
    value.update(overrides)
    return value


def icd_candidate(**overrides):
    value = {
        "formal_fields": {
            "icd9_code": None,
            "icd10_code": "E11.9",
            "name_zh": "第二型糖尿病",
            "name_en": "Type 2 diabetes mellitus",
            "is_high_frequency": False,
            "is_handwritten": False,
            "is_deprecated": False,
            "confidence": "confirmed",
        }
    }
    value.update(overrides)
    return value


class DrugFormalClassifierTest(unittest.TestCase):
    def test_absent_drug_is_ready_for_create(self):
        plan = classify_drug_plan(drug_candidate(), [])
        self.assertEqual(plan["status"], "ready_for_create")
        self.assertEqual(plan["write_fields"]["nhi_drug_code"], "AC12345678")
        self.assertIn("drug_diagnosis_links", plan["hard_excluded_fields"])

    def test_same_code_and_name_is_already_exists(self):
        plan = classify_drug_plan(
            drug_candidate(),
            [{
                "id": 7,
                "seq_no": "NHI-AC12345678",
                "generic_name": "TEST INGREDIENT 10 MG",
                "brand_name": "TEST TABLETS 10MG",
                "aliases": "測試錠10毫克",
                "is_active": True,
                "nhi_drug_code": "AC12345678",
            }],
        )
        self.assertEqual(plan["status"], "already_exists")
        self.assertEqual(plan["target_id"], 7)

    def test_same_code_different_name_is_blocked(self):
        plan = classify_drug_plan(
            drug_candidate(),
            [{
                "id": 8,
                "seq_no": "NHI-AC12345678",
                "generic_name": "OTHER",
                "brand_name": "OTHER BRAND",
                "aliases": "其他",
                "is_active": True,
                "nhi_drug_code": "AC12345678",
            }],
        )
        self.assertEqual(plan["status"], "blocked")

    def test_same_code_same_ingredient_but_different_brand_is_blocked(self):
        plan = classify_drug_plan(
            drug_candidate(),
            [{
                "id": 81,
                "seq_no": "NHI-AC12345678",
                "generic_name": "TEST INGREDIENT 10 MG",
                "brand_name": "OTHER BRAND",
                "aliases": "其他",
                "is_active": True,
                "nhi_drug_code": "AC12345678",
            }],
        )
        self.assertEqual(plan["status"], "blocked")

    def test_name_match_with_blank_code_is_gated_update(self):
        plan = classify_drug_plan(
            drug_candidate(),
            [{
                "id": 9,
                "seq_no": "legacy-9",
                "generic_name": "TEST INGREDIENT 10 MG",
                "brand_name": "TEST TABLETS 10MG",
                "aliases": "測試錠10毫克",
                "is_active": True,
                "nhi_drug_code": None,
            }],
        )
        self.assertEqual(plan["status"], "ready_for_update")
        self.assertEqual(plan["target_id"], 9)
        self.assertEqual(set(plan["write_fields"]), {
            "nhi_drug_code", "nhi_drug_code_source", "nhi_drug_code_confidence"
        })

    def test_approve_with_pinned_reference_discrepancy_is_blocked(self):
        candidate = {
            **drug_candidate(),
            "decision_type": "drug",
            "review_action": "approve",
            "reference_discrepancies": ["drug_name"],
        }
        with patch.object(adapter, "_drug_rows", return_value=[]):
            result = adapter.build_medical_apply_plan(session=object(), candidate=candidate)
        self.assertEqual(result["plan"]["status"], "blocked")
        self.assertEqual(result["plan"]["write_fields"], {})


class IcdFormalClassifierTest(unittest.TestCase):
    def test_absent_icd_is_ready_for_create(self):
        plan = classify_icd_plan(icd_candidate(), [])
        self.assertEqual(plan["status"], "ready_for_create")

    def test_same_icd_is_already_exists(self):
        plan = classify_icd_plan(
            icd_candidate(),
            [{
                "id": 20,
                "icd9_code": None,
                "icd10_code": "E119",
                "name_zh": "第二型糖尿病",
                "name_en": "Type 2 diabetes mellitus",
                "is_high_frequency": False,
                "is_handwritten": False,
                "is_deprecated": False,
                "confidence": "confirmed",
            }],
        )
        self.assertEqual(plan["status"], "already_exists")

    def test_same_code_conflicting_name_is_blocked(self):
        plan = classify_icd_plan(
            icd_candidate(),
            [{
                "id": 21,
                "icd9_code": None,
                "icd10_code": "E11.9",
                "name_zh": "不同診斷",
                "name_en": "Different diagnosis",
                "is_high_frequency": False,
                "is_handwritten": False,
                "is_deprecated": False,
                "confidence": "confirmed",
            }],
        )
        self.assertEqual(plan["status"], "blocked")


class _LockOnlySession:
    def __init__(self):
        self.statements = []

    def execute(self, statement, params=None):
        self.statements.append((str(statement), params or {}))
        if not str(statement).startswith("LOCK TABLE public.drug_items"):
            raise AssertionError(f"unexpected SQL: {statement}")
        return object()


class MedicalFormalPreviewApplyGateTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_runs_dir = review.DEFAULT_RUNS_DIR
        review.DEFAULT_RUNS_DIR = Path(self.temp_dir.name)
        self.run_id = "medical_formal_gate_test"
        queue = review.DEFAULT_RUNS_DIR / self.run_id / "review" / "import_decision_queue.csv"
        queue.parent.mkdir(parents=True)
        fields = [
            "decision_type", "candidate_id", "source_image_filename", "candidate_value",
            "display_name", "suggested_action", "existing_status", "confidence_level",
            "evidence_summary", "review_decision", "corrected_value", "review_note",
            "structured_fields", "structured_corrected_fields",
        ]
        structured = {
            "schema_version": "prescription-drug-official-match-v1",
            "ocr": {"drug_code": "AC12345678", "evidence": ["OCR AC12345678"]},
            "official_match": {"match_status": "exact_code_match", "confidence": "high"},
            "effective_fields": {
                "drug_code": "AC12345678",
                "drug_name": "TEST TABLETS 10MG",
                "ingredient": "TEST INGREDIENT 10 MG",
                "strength_specification": "10MG",
            },
        }
        with queue.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerow({
                "decision_type": "drug",
                "candidate_id": "drug_match:1",
                "source_image_filename": "IMG_TEST.JPG",
                "candidate_value": "AC12345678",
                "display_name": "TEST TABLETS 10MG",
                "suggested_action": "insert_drug",
                "existing_status": "reference_matched",
                "confidence_level": "high",
                "review_decision": "approve",
                "structured_fields": json.dumps(structured),
            })
        self.decision_id = review._read_decision_queue(self.run_id)[2][0]["decision_id"]
        self.official = {
            "row_number": 2,
            "drug_code": "AC12345678",
            "english_name": "TEST TABLETS 10MG",
            "chinese_name": "測試錠10毫克",
            "ingredient": "TEST INGREDIENT 10 MG",
            "strengths": ["10MG"],
            "payload": {"劑型": "錠劑"},
        }

    def tearDown(self):
        review.DEFAULT_RUNS_DIR = self.original_runs_dir
        self.temp_dir.cleanup()

    def test_preview_hash_gate_then_create_service_without_commit(self):
        session = _LockOnlySession()
        with patch.object(adapter, "_drug_official_record", return_value=self.official), patch.object(
            adapter, "_drug_rows", return_value=[]
        ):
            preview = adapter.preview_medical_apply(
                session=session,
                run_id=self.run_id,
                decision_id=self.decision_id,
                persist_artifact=True,
            )
        self.assertTrue(preview.ok, preview.error)
        self.assertEqual(preview.data["plan"]["status"], "ready_for_create")
        expected_fields = preview.data["plan"]["write_fields"]
        with patch.object(adapter, "_drug_official_record", return_value=self.official), patch.object(
            adapter, "_drug_rows", return_value=[]
        ), patch.object(
            adapter,
            "create_drug_item",
            return_value=ToolResult.success(data={"id": 701, **expected_fields}),
        ) as create_mock, patch.object(
            adapter, "_postcheck_row", return_value={"id": 701, **expected_fields}
        ):
            applied = adapter.apply_medical_preview(
                session=session,
                run_id=self.run_id,
                decision_id=self.decision_id,
                formal_preview_id=preview.data["formal_preview_id"],
                formal_preview_result_hash=preview.data["formal_preview_result_hash"],
            )
        self.assertTrue(applied.ok, applied.error)
        self.assertEqual(applied.data["target_id"], 701)
        self.assertTrue(applied.data["caller_must_commit"])
        self.assertFalse(applied.data["relation_formal_apply_allowed"])
        self.assertIs(create_mock.call_args.kwargs["auto_commit"], False)


if __name__ == "__main__":
    unittest.main()
