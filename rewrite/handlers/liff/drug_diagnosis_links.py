"""LIFF endpoints for drug_diagnosis_links v3 skeleton.

Phase 1 scope:
- Serve a LIFF form.
- List existing links.
- Search drug_items and diagnosis_codes.
- Preview a new link and detect duplicates.
- Apply one manually reviewed link.
"""

import logging
import os
from typing import Any

from flask import jsonify, render_template, request
from sqlalchemy.exc import IntegrityError
from sqlalchemy import text

from database import Session
from rewrite.handlers.liff import liff_bp
from rewrite.handlers.liff.auth import liff_auth_required

logger = logging.getLogger(__name__)

MAX_LIMIT = 50
DEFAULT_LIMIT = 20
MAX_NOTE_TEXT_LENGTH = 500

ALLOWED_LINK_TYPES = {
    "commonly_used_for",
    "may_be_used_for",
    "monitor_for",
    "avoid_for",
    "contraindicated_for",
}
ALLOWED_ROLE_TYPES = {
    "primary_treatment",
    "adjunct_treatment",
    "symptom_relief",
    "prevention",
    "monitoring",
    "other",
}
ALLOWED_CONFIDENCE = {"high", "medium", "low"}


def _limit() -> int:
    try:
        value = int(request.args.get("limit", DEFAULT_LIMIT))
    except (TypeError, ValueError):
        value = DEFAULT_LIMIT
    return max(1, min(value, MAX_LIMIT))


def _clean_query() -> str:
    return (request.args.get("q") or "").strip()


def _fetch_one(session, sql: str, params: dict[str, Any]) -> dict[str, Any] | None:
    row = session.execute(text(sql), params).mappings().first()
    return dict(row) if row else None


def _json_error(message: str, status: int = 400):
    return jsonify({"ok": False, "error": message}), status


def _is_unique_constraint_error(exc: IntegrityError) -> bool:
    original = getattr(exc, "orig", None)
    pgcode = getattr(original, "pgcode", None) or getattr(original, "sqlstate", None)
    if pgcode == "23505":
        return True

    args = getattr(original, "args", ())
    if args and args[0] == 1062:
        return True

    message = str(original or exc).lower()
    return "unique constraint" in message or "duplicate key" in message


def _parse_preview_payload(body: dict) -> tuple[dict[str, Any], str | None]:
    try:
        drug_item_id = int(body.get("drug_item_id"))
    except (TypeError, ValueError):
        return {}, "drug_item_id 必須是整數"

    try:
        diagnosis_code_id = int(body.get("diagnosis_code_id"))
    except (TypeError, ValueError):
        return {}, "diagnosis_code_id 必須是整數"

    link_type = (body.get("link_type") or "commonly_used_for").strip()
    role_type = (body.get("role_type") or "primary_treatment").strip()
    confidence = (body.get("confidence") or "medium").strip()
    note_text = (body.get("note_text") or "").strip() or None
    if note_text and len(note_text) > MAX_NOTE_TEXT_LENGTH:
        return {}, f"note_text 最多 {MAX_NOTE_TEXT_LENGTH} 字"

    if link_type not in ALLOWED_LINK_TYPES:
        return {}, f"link_type 不支援：{link_type}"
    if role_type not in ALLOWED_ROLE_TYPES:
        return {}, f"role_type 不支援：{role_type}"
    if confidence not in ALLOWED_CONFIDENCE:
        return {}, f"confidence 不支援：{confidence}"

    is_primary = body.get("is_primary", True)
    if isinstance(is_primary, str):
        is_primary = is_primary.lower() in ("1", "true", "yes", "on")
    else:
        is_primary = bool(is_primary)

    sort_order_raw = body.get("sort_order")
    sort_order = 100
    if sort_order_raw not in (None, ""):
        try:
            sort_order = int(sort_order_raw)
        except (TypeError, ValueError):
            return {}, "sort_order 必須是整數"

    return {
        "drug_item_id": drug_item_id,
        "diagnosis_code_id": diagnosis_code_id,
        "link_type": link_type,
        "role_type": role_type,
        "confidence": confidence,
        "is_primary": is_primary,
        "sort_order": sort_order,
        "source_type": "manual",
        "note_text": note_text,
    }, None


def _validate_link_payload(session, body: dict) -> tuple[dict[str, Any] | None, str | None, int]:
    fields, err = _parse_preview_payload(body)
    if err:
        return None, err, 400

    drug = _fetch_one(
        session,
        """
        SELECT
            id,
            generic_name,
            brand_name,
            table_type,
            item_kind,
            category
        FROM drug_items
        WHERE id = :id
          AND COALESCE(is_active, TRUE) IS TRUE
        """,
        {"id": fields["drug_item_id"]},
    )
    if not drug:
        return None, "找不到指定的 drug_item_id", 404

    diagnosis = _fetch_one(
        session,
        """
        SELECT id, icd10_code, icd9_code, name_zh, name_en
        FROM diagnosis_codes
        WHERE id = :id
        """,
        {"id": fields["diagnosis_code_id"]},
    )
    if not diagnosis:
        return None, "找不到指定的 diagnosis_code_id", 404

    duplicate = _fetch_one(
        session,
        """
        SELECT id
        FROM drug_diagnosis_links
        WHERE drug_item_id = :drug_item_id
          AND diagnosis_code_id = :diagnosis_code_id
          AND link_type = :link_type
          AND role_type = :role_type
        """,
        {
            "drug_item_id": fields["drug_item_id"],
            "diagnosis_code_id": fields["diagnosis_code_id"],
            "link_type": fields["link_type"],
            "role_type": fields["role_type"],
        },
    )

    return {
        **fields,
        "drug": drug,
        "diagnosis": diagnosis,
        "duplicate": duplicate,
    }, None, 200


@liff_bp.route("/drug_diagnosis_links/form", methods=["GET"])
def drug_diagnosis_links_form():
    return render_template(
        "liff/drug_diagnosis_link_form.html",
        liff_id=os.environ.get("LIFF_ID", ""),
        link_types=sorted(ALLOWED_LINK_TYPES),
        role_types=sorted(ALLOWED_ROLE_TYPES),
        confidences=["high", "medium", "low"],
    )


@liff_bp.route("/drug_diagnosis_links", methods=["GET"])
@liff_auth_required
def drug_diagnosis_links_list():
    query = _clean_query()
    limit = _limit()
    params: dict[str, Any] = {"limit": limit}
    if query:
        params["like"] = f"%{query}%"
        sql = text(
            """
            SELECT
                ddl.id,
                ddl.drug_item_id,
                ddl.diagnosis_code_id,
                ddl.link_type,
                ddl.role_type,
                ddl.confidence,
                ddl.is_primary,
                ddl.sort_order,
                ddl.source_type,
                ddl.note_text,
                di.generic_name,
                di.brand_name,
                dc.icd10_code,
                dc.icd9_code,
                dc.name_zh
            FROM drug_diagnosis_links ddl
            JOIN drug_items di ON di.id = ddl.drug_item_id
            JOIN diagnosis_codes dc ON dc.id = ddl.diagnosis_code_id
            WHERE (
                di.generic_name ILIKE :like
                OR di.brand_name ILIKE :like
                OR di.aliases ILIKE :like
                OR dc.icd10_code ILIKE :like
                OR dc.icd9_code ILIKE :like
                OR dc.name_zh ILIKE :like
                OR dc.name_en ILIKE :like
            )
            ORDER BY ddl.id DESC
            LIMIT :limit
            """
        )
    else:
        sql = text(
            """
            SELECT
                ddl.id,
                ddl.drug_item_id,
                ddl.diagnosis_code_id,
                ddl.link_type,
                ddl.role_type,
                ddl.confidence,
                ddl.is_primary,
                ddl.sort_order,
                ddl.source_type,
                ddl.note_text,
                di.generic_name,
                di.brand_name,
                dc.icd10_code,
                dc.icd9_code,
                dc.name_zh
            FROM drug_diagnosis_links ddl
            JOIN drug_items di ON di.id = ddl.drug_item_id
            JOIN diagnosis_codes dc ON dc.id = ddl.diagnosis_code_id
            ORDER BY ddl.id DESC
            LIMIT :limit
            """
        )

    session = Session()
    try:
        rows = session.execute(sql, params).mappings().all()
    finally:
        session.close()

    return jsonify({"ok": True, "links": [dict(row) for row in rows]})


@liff_bp.route("/drug_diagnosis_links/search_drugs", methods=["GET"])
@liff_auth_required
def drug_diagnosis_links_search_drugs():
    query = _clean_query()
    if len(query) < 2:
        return jsonify({"ok": True, "items": []})

    session = Session()
    try:
        rows = session.execute(
            text(
                """
                SELECT
                    id,
                    generic_name,
                    brand_name,
                    table_type,
                    item_kind,
                    category,
                    supplier,
                    manufacturer
                FROM drug_items
                WHERE COALESCE(is_active, TRUE) IS TRUE
                  AND (
                    generic_name ILIKE :like
                    OR brand_name ILIKE :like
                    OR aliases ILIKE :like
                    OR category ILIKE :like
                    OR supplier ILIKE :like
                    OR manufacturer ILIKE :like
                    OR seq_no::text ILIKE :like
                  )
                ORDER BY
                    CASE
                        WHEN LOWER(COALESCE(generic_name, '')) = LOWER(:query) THEN 0
                        WHEN LOWER(COALESCE(brand_name, '')) = LOWER(:query) THEN 0
                        WHEN generic_name ILIKE :prefix THEN 1
                        WHEN brand_name ILIKE :prefix THEN 1
                        ELSE 2
                    END,
                    generic_name ASC NULLS LAST,
                    brand_name ASC NULLS LAST
                LIMIT :limit
                """
            ),
            {
                "query": query,
                "like": f"%{query}%",
                "prefix": f"{query}%",
                "limit": _limit(),
            },
        ).mappings().all()
    finally:
        session.close()

    return jsonify({"ok": True, "items": [dict(row) for row in rows]})


@liff_bp.route("/drug_diagnosis_links/search_diagnoses", methods=["GET"])
@liff_auth_required
def drug_diagnosis_links_search_diagnoses():
    query = _clean_query()
    if len(query) < 2:
        return jsonify({"ok": True, "items": []})

    session = Session()
    try:
        rows = session.execute(
            text(
                """
                SELECT
                    id,
                    icd10_code,
                    icd9_code,
                    name_zh,
                    name_en
                FROM diagnosis_codes
                WHERE
                    icd10_code ILIKE :like
                    OR icd9_code ILIKE :like
                    OR name_zh ILIKE :like
                    OR name_en ILIKE :like
                    OR aliases ILIKE :like
                ORDER BY
                    CASE
                        WHEN LOWER(COALESCE(icd10_code, '')) = LOWER(:query) THEN 0
                        WHEN LOWER(COALESCE(icd9_code, '')) = LOWER(:query) THEN 0
                        WHEN icd10_code ILIKE :prefix THEN 1
                        WHEN icd9_code ILIKE :prefix THEN 1
                        ELSE 2
                    END,
                    icd10_code ASC NULLS LAST,
                    icd9_code ASC NULLS LAST,
                    name_zh ASC
                LIMIT :limit
                """
            ),
            {
                "query": query,
                "like": f"%{query}%",
                "prefix": f"{query}%",
                "limit": _limit(),
            },
        ).mappings().all()
    finally:
        session.close()

    return jsonify({"ok": True, "items": [dict(row) for row in rows]})


@liff_bp.route("/drug_diagnosis_links/preview", methods=["POST"])
@liff_auth_required
def drug_diagnosis_links_preview():
    body = request.get_json(silent=True) or {}

    session = Session()
    try:
        validated, err, status = _validate_link_payload(session, body)
        if err:
            return _json_error(err, status)
    finally:
        session.close()

    duplicate = validated["duplicate"]
    return jsonify(
        {
            "ok": True,
            "can_apply": duplicate is None,
            "duplicate": duplicate,
            "preview": {
                key: value
                for key, value in validated.items()
                if key != "duplicate"
            },
            "message": "可新增" if duplicate is None else "此關聯已存在，不能重複新增",
        }
    )


@liff_bp.route("/drug_diagnosis_links/apply", methods=["POST"])
@liff_auth_required
def drug_diagnosis_links_apply():
    body = request.get_json(silent=True) or {}
    session = Session()
    try:
        with session.begin():
            validated, err, status = _validate_link_payload(session, body)
            if err:
                return _json_error(err, status)
            if validated["duplicate"]:
                return _json_error("此關聯已存在，不能重複新增", 409)

            inserted = _fetch_one(
                session,
                """
                INSERT INTO drug_diagnosis_links (
                    drug_item_id,
                    diagnosis_code_id,
                    link_type,
                    role_type,
                    confidence,
                    is_primary,
                    sort_order,
                    source_type,
                    note_text
                )
                VALUES (
                    :drug_item_id,
                    :diagnosis_code_id,
                    :link_type,
                    :role_type,
                    :confidence,
                    :is_primary,
                    :sort_order,
                    :source_type,
                    :note_text
                )
                RETURNING
                    id,
                    drug_item_id,
                    diagnosis_code_id,
                    link_type,
                    role_type,
                    confidence,
                    is_primary,
                    sort_order,
                    source_type,
                    note_text,
                    created_at,
                    updated_at
                """,
                {
                    "drug_item_id": validated["drug_item_id"],
                    "diagnosis_code_id": validated["diagnosis_code_id"],
                    "link_type": validated["link_type"],
                    "role_type": validated["role_type"],
                    "confidence": validated["confidence"],
                    "is_primary": validated["is_primary"],
                    "sort_order": validated["sort_order"],
                    "source_type": "manual",
                    "note_text": validated["note_text"],
                },
            )
    except IntegrityError as exc:
        if _is_unique_constraint_error(exc):
            return _json_error("這筆藥品與診斷碼關聯已存在，未新增。", 409)
        logger.exception("Failed to apply drug diagnosis link")
        return _json_error("新增藥品與診斷碼關聯失敗", 500)
    finally:
        session.close()

    return jsonify(
        {
            "ok": True,
            "link": inserted,
            "drug": validated["drug"],
            "diagnosis": validated["diagnosis"],
            "message": "新增成功",
        }
    ), 201
