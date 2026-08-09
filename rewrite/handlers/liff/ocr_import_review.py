"""LIFF endpoints for Prescription OCR review and preview-gated promotion.

The generic review preview/apply endpoints remain review/staging-only. Customer,
Drug, and ICD can reach formal tables only through the approved-only formal
adapter endpoints below. Drug-diagnosis relation promotion is hard-excluded.
"""
from __future__ import annotations

import logging
import os
from typing import Any

from flask import current_app, jsonify, render_template, request
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from database import Session
from rewrite.handlers.liff import liff_bp
from rewrite.handlers.liff.auth import verify_line_id_token
from rewrite.tools import prescription_ocr_review as review_tools
from rewrite.tools import prescription_ocr_customer_apply as customer_apply_tools
from rewrite.tools import prescription_ocr_medical_apply as medical_apply_tools

logger = logging.getLogger(__name__)


def _json_error(message: str, status: int = 400):
    return jsonify({"ok": False, "error": message}), status


def _is_local_request() -> bool:
    host = (request.host or "").split(":", 1)[0].strip().lower()
    remote_addr = (request.remote_addr or "").strip().lower()
    return host in {"127.0.0.1", "localhost", "::1"} or remote_addr in {
        "127.0.0.1",
        "localhost",
        "::1",
    }


def _dev_skip_liff_requested(body: dict[str, Any] | None = None) -> bool:
    if request.args.get("dev_skip_liff") == "1":
        return True
    if isinstance(body, dict) and str(body.get("dev_skip_liff") or "") == "1":
        return True
    return False


def _require_liff_or_local_dev(body: dict[str, Any] | None = None, *, allow_dev_skip: bool = False):
    if allow_dev_skip and _dev_skip_liff_requested(body) and _is_local_request():
        request.line_user_id = "dev_skip_liff"
        request.line_user_name = "Dev Skip LIFF"
        return None

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return _json_error("missing_bearer_token", 401)
    id_token = auth_header[len("Bearer ") :].strip()
    if not id_token:
        return _json_error("empty_id_token", 401)
    claims = verify_line_id_token(id_token)
    if not claims:
        return _json_error("invalid_id_token", 401)
    request.line_user_id = claims.get("sub")
    request.line_user_name = claims.get("name")
    return None


def _request_filters() -> dict[str, str]:
    return {
        "decision_type": (request.args.get("decision_type") or "").strip(),
        "suggested_action": (request.args.get("suggested_action") or "").strip(),
        "confidence_level": (request.args.get("confidence_level") or "").strip(),
        "existing_status": (request.args.get("existing_status") or "").strip(),
        "review_decision": (request.args.get("review_decision") or "").strip(),
    }


def _body_items(body: dict[str, Any]) -> list[dict[str, Any]]:
    items = body.get("decision_items")
    if isinstance(items, list):
        return [item for item in items if isinstance(item, dict)]
    # Compatibility with simpler clients.
    ids = body.get("decision_ids")
    if isinstance(ids, list):
        return [{"decision_id": str(decision_id)} for decision_id in ids]
    return []


@liff_bp.route("/ocr-import/review", methods=["GET"])
def ocr_import_review_form():
    """OCR import batch review form shell.

    The shell itself does not include decision data. The page fetches items from
    the authenticated JSON endpoint after LIFF init.
    """
    return render_template(
        "liff/ocr_import_review_form.html",
        liff_id=os.environ.get("LIFF_ID", ""),
        run_id=(request.args.get("run_id") or "").strip(),
        default_decision_type=(request.args.get("decision_type") or "all").strip() or "all",
        default_confidence_level=(request.args.get("confidence_level") or "all").strip() or "all",
        default_suggested_action=(request.args.get("suggested_action") or "all").strip() or "all",
        default_existing_status=(request.args.get("existing_status") or "all").strip() or "all",
    )


@liff_bp.route("/ocr-import/review/items", methods=["GET"])
def ocr_import_review_items():
    auth_error = _require_liff_or_local_dev(allow_dev_skip=True)
    if auth_error:
        return auth_error
    run_id = (request.args.get("run_id") or "").strip()
    result = review_tools.load_import_decision_items(run_id, filters=_request_filters())
    if not result.ok:
        return _json_error(result.error or "load failed")
    return jsonify({"ok": True, **result.data})


def _preview_or_apply(*, dry_run: bool, body: dict[str, Any] | None = None):
    body = body if body is not None else (request.get_json(silent=True) or {})
    run_id = (body.get("run_id") or "").strip()
    requested_action = (body.get("requested_action") or body.get("action") or "").strip()
    decision_items = _body_items(body)
    corrected_values = body.get("corrected_values") or {}
    review_note = (body.get("review_note") or "").strip()
    idempotency_key = (body.get("idempotency_key") or "").strip()
    preview_id = (body.get("preview_id") or "").strip()
    queue_revision = body.get("queue_revision") if isinstance(body.get("queue_revision"), dict) else None
    selected_rows_hash = (body.get("selected_rows_hash") or "").strip()
    preview_result_hash = (body.get("preview_result_hash") or "").strip()
    accept_skipped = bool(body.get("accept_skipped"))
    batch_mode = "dev_test" if current_app.config.get("TESTING") or _is_local_request() else "production"

    if not run_id:
        return _json_error("run_id 必填")
    if not requested_action:
        return _json_error("requested_action 必填")
    if not decision_items:
        return _json_error("decision_items 不可空")
    if corrected_values and not isinstance(corrected_values, dict):
        return _json_error("corrected_values 格式錯")

    session = Session()
    try:
        result = review_tools.apply_import_review_decisions(
            session=session,
            run_id=run_id,
            requested_action=requested_action,
            decision_items=decision_items,
            corrected_values=corrected_values,
            review_note=review_note,
            idempotency_key=idempotency_key,
            preview_id=preview_id,
            queue_revision=queue_revision,
            selected_rows_hash=selected_rows_hash,
            preview_result_hash=preview_result_hash,
            accept_skipped=accept_skipped,
            batch_mode=batch_mode,
            user_id=getattr(request, "line_user_id", None),
            user_name=getattr(request, "line_user_name", None),
            dry_run=dry_run,
            via="liff_ocr_import_review",
        )
    except SQLAlchemyError as exc:
        session.rollback()
        logger.exception("OCR import review failed")
        return _json_error(f"DB error: {exc}", 500)
    finally:
        session.close()

    if not result.ok:
        return _json_error(result.error or "review failed")
    if not dry_run and requested_action in {"approve", "corrected"}:
        formal_successes = [
            item for item in (result.data.get("per_item_result") or [])
            if item.get("decision_type") in {"customer", "drug", "icd"} and item.get("result") == "success"
        ]
        if formal_successes:
            # Generic /apply only persists review decisions. It cannot bypass
            # the formal preview/duplicate/postcheck adapter.
            result.data["formal_apply"] = {
                "required_adapter": "/liff/ocr-import/review/formal/preview",
                "decision_ids": [item.get("decision_id") for item in formal_successes],
                "formal_tables_touched": "none",
            }
    status = 200 if dry_run or result.data.get("idempotency_replay") else 201
    return jsonify({"ok": True, **result.data}), status


@liff_bp.route("/ocr-import/review/preview", methods=["POST"])
def ocr_import_review_preview():
    body = request.get_json(silent=True) or {}
    auth_error = _require_liff_or_local_dev(body, allow_dev_skip=True)
    if auth_error:
        return auth_error
    return _preview_or_apply(dry_run=True, body=body)


@liff_bp.route("/ocr-import/review/apply", methods=["POST"])
def ocr_import_review_apply():
    body = request.get_json(silent=True) or {}
    if _dev_skip_liff_requested(body):
        return _json_error("dev_skip_liff 不允許送出 apply", 403)
    auth_error = _require_liff_or_local_dev(body, allow_dev_skip=False)
    if auth_error:
        return auth_error
    return _preview_or_apply(dry_run=False, body=body)


@liff_bp.route("/ocr-import/review/customer-formal/preview", methods=["POST"])
def ocr_import_review_customer_formal_preview():
    """SELECT-only create/update plan for one persisted customer decision."""
    body = request.get_json(silent=True) or {}
    auth_error = _require_liff_or_local_dev(body, allow_dev_skip=True)
    if auth_error:
        return auth_error
    run_id = (body.get("run_id") or "").strip()
    decision_id = (body.get("decision_id") or "").strip()
    if not run_id or not decision_id:
        return _json_error("run_id 與 decision_id 必填")

    session = Session()
    try:
        # This must be the first DB statement in the preview transaction.
        session.execute(text("SET TRANSACTION READ ONLY"))
        result = customer_apply_tools.preview_customer_apply(
            session=session,
            run_id=run_id,
            decision_id=decision_id,
            reviewer_id=getattr(request, "line_user_id", "") or "",
            persist_artifact=True,
        )
        session.rollback()
    except SQLAlchemyError as exc:
        session.rollback()
        logger.exception("OCR customer formal preview failed")
        return _json_error(f"DB error: {exc}", 500)
    finally:
        session.close()

    if not result.ok:
        return _json_error(result.error or "customer formal preview failed")
    return jsonify({"ok": True, **result.data})


@liff_bp.route("/ocr-import/review/customer-formal/apply", methods=["POST"])
def ocr_import_review_customer_formal_apply():
    """Apply one customer only through the preview-gated generic adapter."""
    body = request.get_json(silent=True) or {}
    if _dev_skip_liff_requested(body):
        return _json_error("dev_skip_liff 不允許 customer formal apply", 403)
    auth_error = _require_liff_or_local_dev(body, allow_dev_skip=False)
    if auth_error:
        return auth_error
    run_id = (body.get("run_id") or "").strip()
    decision_id = (body.get("decision_id") or "").strip()
    preview_id = (body.get("customer_preview_id") or "").strip()
    result_hash = (body.get("customer_preview_result_hash") or "").strip()
    if not all((run_id, decision_id, preview_id, result_hash)):
        return _json_error("customer formal preview gate 欄位不完整")

    session = Session()
    try:
        result = customer_apply_tools.apply_customer_preview(
            session=session,
            run_id=run_id,
            decision_id=decision_id,
            customer_preview_id=preview_id,
            customer_preview_result_hash=result_hash,
        )
        if not result.ok:
            session.rollback()
            return _json_error(result.error or "customer formal apply failed")
        session.commit()
    except SQLAlchemyError as exc:
        session.rollback()
        logger.exception("OCR customer formal apply failed")
        return _json_error(f"DB error: {exc}", 500)
    finally:
        session.close()

    result.data["committed"] = True
    result.data["caller_must_commit"] = False
    return jsonify({"ok": True, **result.data}), 201


def _formal_decision_type(run_id: str, decision_id: str) -> str:
    _path, _fields, rows = review_tools._read_decision_queue(run_id)
    matches = [row for row in rows if (row.get("decision_id") or "").strip() == decision_id]
    if len(matches) != 1:
        raise ValueError("formal review row missing or duplicated")
    return (matches[0].get("decision_type") or "").strip()


def _normalize_customer_formal_preview(data: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(data)
    normalized.update({
        "formal_kind": "customer",
        "target_table": "customers",
        "formal_preview_id": data.get("customer_preview_id"),
        "formal_preview_result_hash": data.get("customer_preview_result_hash"),
    })
    return normalized


@liff_bp.route("/ocr-import/review/formal/preview", methods=["POST"])
def ocr_import_review_formal_preview():
    """SELECT-only formal plan for one approved Customer, Drug, or ICD row."""
    body = request.get_json(silent=True) or {}
    auth_error = _require_liff_or_local_dev(body, allow_dev_skip=True)
    if auth_error:
        return auth_error
    run_id = (body.get("run_id") or "").strip()
    decision_id = (body.get("decision_id") or "").strip()
    if not run_id or not decision_id:
        return _json_error("run_id 與 decision_id 必填")
    try:
        decision_type = _formal_decision_type(run_id, decision_id)
    except (FileNotFoundError, ValueError) as exc:
        return _json_error(str(exc))
    if decision_type not in {"customer", "drug", "icd"}:
        return _json_error("relation / unknown row 不允許 formal apply", 403)

    session = Session()
    try:
        session.execute(text("SET TRANSACTION READ ONLY"))
        if decision_type == "customer":
            result = customer_apply_tools.preview_customer_apply(
                session=session,
                run_id=run_id,
                decision_id=decision_id,
                reviewer_id=getattr(request, "line_user_id", "") or "",
                persist_artifact=True,
            )
        else:
            result = medical_apply_tools.preview_medical_apply(
                session=session,
                run_id=run_id,
                decision_id=decision_id,
                reviewer_id=getattr(request, "line_user_id", "") or "",
                persist_artifact=True,
            )
        session.rollback()
    except SQLAlchemyError as exc:
        session.rollback()
        logger.exception("OCR formal preview failed")
        return _json_error(f"DB error: {exc}", 500)
    finally:
        session.close()
    if not result.ok:
        return _json_error(result.error or "formal preview failed")
    data = _normalize_customer_formal_preview(result.data) if decision_type == "customer" else {
        **result.data,
        "formal_kind": decision_type,
    }
    return jsonify({"ok": True, **data})


def _fresh_verify_customer(result_data: dict[str, Any]) -> dict[str, Any]:
    customer_id = int(result_data.get("customer_id") or 0)
    fields = dict(result_data.get("written_fields") or {})
    session = Session()
    try:
        row = session.execute(
            text("SELECT * FROM public.customers WHERE id = :id"), {"id": customer_id}
        ).mappings().one_or_none()
        if row is None:
            raise ValueError("fresh customer postcheck row missing")
        actual = dict(row)
        for key, value in fields.items():
            if hasattr(value, "isoformat"):
                value = value.isoformat()
            actual_value = actual.get(key)
            if hasattr(actual_value, "isoformat"):
                actual_value = actual_value.isoformat()
            if actual_value != value:
                raise ValueError(f"fresh customer postcheck mismatch:{key}")
        keys = ("id", "name", "short_name", "birthday", "medical_record_no", "gender", "address", "category", "remarks")
        return {key: actual.get(key) for key in keys}
    finally:
        session.close()


@liff_bp.route("/ocr-import/review/formal/apply", methods=["POST"])
def ocr_import_review_formal_apply():
    """Apply one preview-gated Customer, Drug, or ICD row atomically."""
    body = request.get_json(silent=True) or {}
    if _dev_skip_liff_requested(body):
        return _json_error("dev_skip_liff 不允許 formal apply", 403)
    auth_error = _require_liff_or_local_dev(body, allow_dev_skip=False)
    if auth_error:
        return auth_error
    run_id = (body.get("run_id") or "").strip()
    decision_id = (body.get("decision_id") or "").strip()
    preview_id = (body.get("formal_preview_id") or "").strip()
    result_hash = (body.get("formal_preview_result_hash") or "").strip()
    if not all((run_id, decision_id, preview_id, result_hash)):
        return _json_error("formal preview gate 欄位不完整")
    try:
        decision_type = _formal_decision_type(run_id, decision_id)
    except (FileNotFoundError, ValueError) as exc:
        return _json_error(str(exc))
    if decision_type not in {"customer", "drug", "icd"}:
        return _json_error("relation / unknown row 不允許 formal apply", 403)

    session = Session()
    try:
        if decision_type == "customer":
            result = customer_apply_tools.apply_customer_preview(
                session=session,
                run_id=run_id,
                decision_id=decision_id,
                customer_preview_id=preview_id,
                customer_preview_result_hash=result_hash,
            )
        else:
            result = medical_apply_tools.apply_medical_preview(
                session=session,
                run_id=run_id,
                decision_id=decision_id,
                formal_preview_id=preview_id,
                formal_preview_result_hash=result_hash,
            )
        if not result.ok:
            session.rollback()
            return _json_error(result.error or "formal apply failed")
        session.commit()
    except SQLAlchemyError as exc:
        session.rollback()
        logger.exception("OCR formal apply failed")
        return _json_error(f"DB error: {exc}", 500)
    finally:
        session.close()

    try:
        if decision_type == "customer":
            fresh = _fresh_verify_customer(result.data)
            result.data.update({
                "target_table": "customers",
                "target_id": result.data.get("customer_id"),
                "fresh_postcheck": fresh,
            })
        else:
            fresh_session = Session()
            try:
                fresh_result = medical_apply_tools.verify_committed_medical_result(
                    session=fresh_session, result=result.data
                )
            finally:
                fresh_session.close()
            if not fresh_result.ok:
                return _json_error(f"committed but fresh postcheck failed: {fresh_result.error}", 500)
            result.data.update(fresh_result.data)
    except (SQLAlchemyError, ValueError) as exc:
        logger.exception("OCR formal fresh postcheck failed")
        return _json_error(f"committed but fresh postcheck failed: {exc}", 500)

    result.data["committed"] = True
    result.data["caller_must_commit"] = False
    result.data["formal_kind"] = decision_type
    return jsonify({"ok": True, **result.data}), 201
