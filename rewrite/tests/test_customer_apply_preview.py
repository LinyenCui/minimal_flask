from __future__ import annotations

import unittest
from datetime import date

from rewrite.tools.base import ToolResult
from rewrite.tools.customer import prepare_create_customer
from rewrite.tools.prescription_ocr_customer_apply import (
    classify_apply_plan,
    duplicate_details,
)


class _Result:
    def __init__(self, row=None):
        self.row = row

    def fetchone(self):
        return self.row


class _ReadOnlyFakeSession:
    def __init__(self, duplicate_id=None):
        self.duplicate_id = duplicate_id
        self.statements = []

    def execute(self, statement, params):
        sql = str(statement).strip()
        self.statements.append((sql, params))
        if not sql.upper().startswith("SELECT"):
            raise AssertionError(f"mutation SQL was issued: {sql}")
        return _Result((self.duplicate_id,) if self.duplicate_id else None)


def candidate(**overrides):
    result = {
        "run_id": "old_20260715_003300",
        "decision_id": "old_20260715_003300:row:test",
        "preview_id": "preview-test",
        "review_action": "approve",
        "source_image": "fixture_customer.jpg",
        "confirmed_name": "測試顧客",
        "short_name": "測試顧客",
        "birthday": "",
        "medical_record_no": "000123",
        "phone": "",
        "identity_markers": ["榮民", "榮保"],
        "identity_raw": ["身份:荣保", "份:榮民"],
    }
    result.update(overrides)
    return result


def existing(customer_id, **overrides):
    result = {
        "id": customer_id,
        "name": "測試顧客",
        "short_name": "測試顧客",
        "birthday": None,
        "medical_record_no": None,
        "contact_phone": None,
        "address": "既有地址",
        "category": "既有分類",
        "remarks": "既有註記",
    }
    result.update(overrides)
    return result


class PrepareCreateCustomerTest(unittest.TestCase):
    def test_prepare_is_select_only_and_returns_formal_payload(self):
        session = _ReadOnlyFakeSession()
        result = prepare_create_customer(
            session=session,
            name="測試顧客",
            short_name="測試顧客",
            address="門診",
            category="診所",
            medical_record_no="000123",
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.data["medical_record_no"], "000123")
        self.assertEqual(len(session.statements), 1)
        self.assertTrue(session.statements[0][0].upper().startswith("SELECT"))

    def test_prepare_reuses_exact_short_name_duplicate_contract(self):
        result = prepare_create_customer(
            session=_ReadOnlyFakeSession(duplicate_id=42),
            name="測試顧客",
            short_name="測試顧客",
            address="門診",
        )
        self.assertFalse(result.ok)
        self.assertIn("customer #42", result.error)


class CustomerApplyClassificationTest(unittest.TestCase):
    def test_no_match_is_ready_for_create(self):
        item = candidate()
        details = duplicate_details(item, [])
        prepared = ToolResult.success(data={"name": item["confirmed_name"], "remarks": "provenance only"})
        plan = classify_apply_plan(item, details, prepared)
        self.assertEqual(plan["status"], "ready_for_create")

    def test_same_medical_record_with_different_name_is_blocked(self):
        item = candidate()
        details = duplicate_details(
            item,
            [existing(11, name="不同姓名", short_name="不同", medical_record_no="000123")],
        )
        plan = classify_apply_plan(item, details, ToolResult.success(data={}))
        self.assertEqual(plan["status"], "blocked")
        self.assertIn("medical_record_no_match_name_conflict:customer#11", plan["reasons"])

    def test_same_name_with_different_medical_record_is_blocked(self):
        item = candidate()
        details = duplicate_details(item, [existing(12, medical_record_no="009999")])
        plan = classify_apply_plan(item, details, ToolResult.fail("short name exists"))
        self.assertEqual(plan["status"], "blocked")
        self.assertIn("same_name_medical_record_no_conflict:customer#12", plan["reasons"])

    def test_consistent_existing_with_blank_medical_record_is_update_preview(self):
        item = candidate(birthday="1950-01-02")
        details = duplicate_details(item, [existing(13)])
        plan = classify_apply_plan(item, details, ToolResult.fail("short name exists"))
        self.assertEqual(plan["status"], "ready_for_update")
        self.assertEqual(plan["target_customer_id"], 13)
        self.assertEqual(plan["write_fields"]["medical_record_no"], "000123")
        self.assertEqual(plan["write_fields"]["birthday"], "1950-01-02")
        self.assertNotIn("patient_identity_markers", plan["write_fields"])
        self.assertNotIn("榮民", plan["write_fields"]["remarks"])
        self.assertNotIn("address", plan["write_fields"])
        self.assertNotIn("category", plan["write_fields"])

    def test_same_name_with_different_birthday_is_blocked(self):
        item = candidate(birthday="1950-01-02", medical_record_no="")
        details = duplicate_details(item, [existing(14, birthday=date(1951, 1, 2))])
        plan = classify_apply_plan(item, details, ToolResult.fail("short name exists"))
        self.assertEqual(plan["status"], "blocked")
        self.assertIn("same_name_birthday_conflict:customer#14", plan["reasons"])

    def test_fully_applied_existing_customer_is_already_exists(self):
        item = candidate()
        provenance = (
            "Prescription OCR run=old_20260715_003300; source_image=fixture_customer.jpg; "
            "review_action=approve; decision_id=old_20260715_003300:row:test"
        )
        details = duplicate_details(
            item,
            [existing(15, medical_record_no="000123", remarks=provenance)],
        )
        plan = classify_apply_plan(item, details, ToolResult.fail("short name exists"))
        self.assertEqual(plan["status"], "already_exists")
        self.assertEqual(plan["write_fields"], {})


if __name__ == "__main__":
    unittest.main()
