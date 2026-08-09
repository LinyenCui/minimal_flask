from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from flask import Flask

from rewrite.tools.base import ToolResult
from rewrite.tools import prescription_ocr_review as review
from rewrite.tools import prescription_ocr_customer_apply as adapter


class _QueryResult:
    def __init__(self, rows=None, row=None):
        self._rows = list(rows or [])
        self._row = row

    def mappings(self):
        return self

    def all(self):
        return self._rows

    def fetchone(self):
        return self._row


class _ReadOnlySession:
    def __init__(self, customers=None):
        self.customers = list(customers or [])
        self.statements = []

    def execute(self, statement, params=None):
        sql = " ".join(str(statement).split())
        self.statements.append((sql, params or {}))
        if sql.startswith("SET TRANSACTION READ ONLY"):
            return _QueryResult()
        if sql.startswith("LOCK TABLE public.customers"):
            return _QueryResult()
        if "SELECT id, name, short_name, birthday" in sql:
            return _QueryResult(rows=self.customers)
        if sql.startswith("SELECT id FROM customers WHERE short_name"):
            value = (params or {}).get("v")
            match = next((row for row in self.customers if row.get("short_name") == value), None)
            return _QueryResult(row=(match["id"],) if match else None)
        raise AssertionError(f"unexpected or mutating SQL: {sql}")

    def rollback(self):
        return None

    def close(self):
        return None


class PrescriptionOcrCustomerApplyAdapterTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_runs_dir = review.DEFAULT_RUNS_DIR
        review.DEFAULT_RUNS_DIR = Path(self.temp_dir.name)
        self.run_id = "generic_customer_adapter_test"
        self.queue_path = review.DEFAULT_RUNS_DIR / self.run_id / "review" / "import_decision_queue.csv"
        self.queue_path.parent.mkdir(parents=True)
        self.action_path = (
            review.DEFAULT_RUNS_DIR
            / self.run_id
            / "customer_matching"
            / "ocr_customer_liff_actions.csv"
        )
        self.action_path.parent.mkdir(parents=True)
        self.source_structured = {
            "schema_version": "prescription-customer-review-v2",
            "source_images": ["IMG_GENERIC.JPG"],
            "name": {"raw_value": "王小名", "normalized_value": "王小名"},
            "birthday": {"normalized_value": "1979-01-01"},
            "medical_record_no": {"normalized_value": "000111"},
            "patient_identity_markers": {
                "scope": "prescription",
                "raw_values": ["身份：榮保"],
                "normalized_values": ["榮保"],
            },
        }
        self.corrected = {
            "customer_name": "王小明",
            "birthday": "1980-01-02",
            "medical_record_no": "000518",
            "patient_identity_markers": ["重大"],
            "patient_identity_scope": "prescription_review_only",
        }
        self._write_queue(review_decision="corrected", corrected=self.corrected)
        with self.action_path.open("w", encoding="utf-8", newline="") as file_obj:
            writer = csv.DictWriter(
                file_obj,
                fieldnames=[
                    "source_image_filename",
                    "prefill_short_name",
                    "matched_short_name",
                    "prefill_phone",
                ],
            )
            writer.writeheader()
            writer.writerow({
                "source_image_filename": "IMG_GENERIC.JPG",
                "prefill_short_name": "王小名",
                "matched_short_name": "",
                "prefill_phone": "0912-345-678",
            })

    def tearDown(self):
        review.DEFAULT_RUNS_DIR = self.original_runs_dir
        self.temp_dir.cleanup()

    def _write_queue(self, *, review_decision, corrected):
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
        with self.queue_path.open("w", encoding="utf-8", newline="") as file_obj:
            writer = csv.DictWriter(file_obj, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerow({
                "decision_type": "customer",
                "candidate_id": "customer_action:generic",
                "source_image_filename": "IMG_GENERIC.JPG",
                "candidate_value": "王小名",
                "display_name": "新客戶:王小名",
                "suggested_action": "create_customer",
                "existing_status": "not_found",
                "confidence_level": "manual_review",
                "evidence_summary": "generic adapter test",
                "review_decision": review_decision,
                "corrected_value": "王小明" if corrected else "",
                "structured_fields": json.dumps(self.source_structured, ensure_ascii=False),
                "structured_corrected_fields": json.dumps(corrected, ensure_ascii=False) if corrected else "",
            })

    def decision_id(self):
        _path, _fields, rows = review._read_decision_queue(self.run_id)
        return rows[0]["decision_id"]

    def test_corrected_payload_never_falls_back_to_ocr_values(self):
        candidate = adapter.load_reviewed_customer_candidate(
            run_id=self.run_id,
            decision_id=self.decision_id(),
        )
        self.assertEqual(candidate["ocr_raw_name"], "王小名")
        self.assertEqual(candidate["confirmed_name"], "王小明")
        self.assertEqual(candidate["short_name"], "王小明")
        self.assertEqual(candidate["birthday"], "1980-01-02")
        self.assertEqual(candidate["medical_record_no"], "000518")
        self.assertEqual(candidate["identity_markers"], ["重大"])

    def test_corrected_without_structured_fields_is_blocked(self):
        self._write_queue(review_decision="corrected", corrected=None)
        with self.assertRaisesRegex(adapter.CustomerApplyError, "structured_fields_required"):
            adapter.load_reviewed_customer_candidate(
                run_id=self.run_id,
                decision_id=self.decision_id(),
            )

    def test_non_approved_action_is_blocked(self):
        self._write_queue(review_decision="defer", corrected=None)
        with self.assertRaisesRegex(adapter.CustomerApplyError, "not_approved_or_corrected"):
            adapter.load_reviewed_customer_candidate(
                run_id=self.run_id,
                decision_id=self.decision_id(),
            )

    def test_preview_hard_excludes_identity_and_phone(self):
        result = adapter.preview_customer_apply(
            session=_ReadOnlySession(),
            run_id=self.run_id,
            decision_id=self.decision_id(),
            persist_artifact=False,
        )
        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.data["plan"]["status"], "ready_for_create")
        fields = result.data["plan"]["write_fields"]
        self.assertEqual(fields["name"], "王小明")
        self.assertEqual(fields["medical_record_no"], "000518")
        self.assertNotIn("patient_identity_markers", fields)
        self.assertNotIn("contact_phone", fields)
        self.assertNotIn("重大", json.dumps(fields, ensure_ascii=False))
        self.assertEqual(result.data["patient_identity"]["write_to_customers"], False)

    def test_formal_apply_delegates_to_create_service_without_commit(self):
        session = _ReadOnlySession()
        preview = adapter.preview_customer_apply(
            session=session,
            run_id=self.run_id,
            decision_id=self.decision_id(),
            persist_artifact=True,
        )
        self.assertTrue(preview.ok, preview.error)
        fake_view = SimpleNamespace(
            id=701,
            to_dict=lambda: {"id": 701, **preview.data["plan"]["write_fields"]},
        )
        with patch.object(
            adapter.customer_tools,
            "create_customer",
            return_value=ToolResult.success(data=fake_view),
        ) as create_mock:
            applied = adapter.apply_customer_preview(
                session=session,
                run_id=self.run_id,
                decision_id=self.decision_id(),
                customer_preview_id=preview.data["customer_preview_id"],
                customer_preview_result_hash=preview.data["customer_preview_result_hash"],
            )
        self.assertTrue(applied.ok, applied.error)
        self.assertEqual(applied.data["customer_id"], 701)
        kwargs = create_mock.call_args.kwargs
        self.assertIs(kwargs["auto_commit"], False)
        self.assertNotIn("contact_phone", kwargs)
        self.assertNotIn("patient_identity_markers", kwargs)
        self.assertEqual(applied.data["caller_must_commit"], True)

    def test_formal_update_delegates_to_existing_update_service(self):
        session = _ReadOnlySession(customers=[{
            "id": 88,
            "name": "王小明",
            "short_name": "王小明",
            "birthday": adapter.parse_date("1980-01-02"),
            "medical_record_no": None,
            "contact_phone": None,
            "address": "既有地址",
            "category": "既有分類",
            "remarks": "",
            "gender": None,
        }])
        preview = adapter.preview_customer_apply(
            session=session,
            run_id=self.run_id,
            decision_id=self.decision_id(),
            persist_artifact=True,
        )
        self.assertTrue(preview.ok, preview.error)
        self.assertEqual(preview.data["plan"]["status"], "ready_for_update")
        fake_view = SimpleNamespace(
            id=88,
            to_dict=lambda: {"id": 88, "name": "王小明", **preview.data["plan"]["write_fields"]},
        )
        with patch.object(
            adapter.customer_tools,
            "update_customer",
            return_value=ToolResult.success(data=fake_view),
        ) as update_mock:
            applied = adapter.apply_customer_preview(
                session=session,
                run_id=self.run_id,
                decision_id=self.decision_id(),
                customer_preview_id=preview.data["customer_preview_id"],
                customer_preview_result_hash=preview.data["customer_preview_result_hash"],
            )
        self.assertTrue(applied.ok, applied.error)
        kwargs = update_mock.call_args.kwargs
        self.assertEqual(kwargs["customer_id"], 88)
        self.assertIs(kwargs["auto_commit"], False)
        self.assertEqual(kwargs["medical_record_no"], "000518")
        self.assertNotIn("address", kwargs)
        self.assertNotIn("category", kwargs)
        self.assertNotIn("contact_phone", kwargs)


class CustomerFormalRouteTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from rewrite.handlers.liff import liff_bp

        template_folder = Path(__file__).resolve().parents[2] / "templates"
        cls.app = Flask(__name__, template_folder=str(template_folder))
        cls.app.config.update(TESTING=True)
        cls.app.register_blueprint(liff_bp)

    def test_dev_preview_uses_adapter_and_read_only_transaction(self):
        from rewrite.handlers.liff import ocr_import_review as route

        session = _ReadOnlySession()
        adapter_result = ToolResult.success(data={
            "plan": {"status": "ready_for_create", "write_fields": {"name": "王小明"}},
            "customer_preview_id": "preview-1",
            "customer_preview_result_hash": "hash-1",
            "formal_tables_touched": "none",
        })
        with patch.object(route, "Session", return_value=session), patch.object(
            route.customer_apply_tools,
            "preview_customer_apply",
            return_value=adapter_result,
        ) as preview_mock:
            response = self.app.test_client().post(
                "/liff/ocr-import/review/customer-formal/preview?dev_skip_liff=1",
                json={"run_id": "run", "decision_id": "decision", "dev_skip_liff": "1"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["ok"])
        self.assertTrue(session.statements[0][0].startswith("SET TRANSACTION READ ONLY"))
        preview_mock.assert_called_once()

    def test_dev_skip_cannot_call_formal_apply(self):
        response = self.app.test_client().post(
            "/liff/ocr-import/review/customer-formal/apply?dev_skip_liff=1",
            json={"dev_skip_liff": "1"},
        )
        self.assertEqual(response.status_code, 403)
        self.assertIn("不允許", response.get_json()["error"])


if __name__ == "__main__":
    unittest.main()
