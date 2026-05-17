"""
藥名查詢服務

資料來源只使用正式表 drug_items：
  L1 精確查詢    — generic_name / brand_name / aliases
  L2 模糊查詢    — generic_name / brand_name / aliases / 其他可用文字欄位
"""
import logging
from typing import Any, Dict, List

from sqlalchemy import text

from modules.models.base import db

logger = logging.getLogger(__name__)

CORE_COLUMNS = [
    'id',
    'seq_no',
    'table_type',
    'item_kind',
    'generic_name',
    'brand_name',
    'aliases',
]

OPTIONAL_DISPLAY_COLUMNS = [
    'normalized_name',
    'raw_name',
    'original_name',
    'source_name',
    'spec',
    'specification',
    'strength',
    'dosage',
    'dose',
    'unit',
    'category',
    'supplier',
    'manufacturer',
    'source',
    'source_photo',
    'source_version',
]

SEARCH_CANDIDATE_COLUMNS = [
    'generic_name',
    'brand_name',
    'aliases',
    'normalized_name',
    'raw_name',
    'original_name',
    'source_name',
    'seq_no',
    'category',
    'supplier',
    'manufacturer',
]


class DrugQueryService:

    @staticmethod
    def search(query_text: str) -> Dict[str, Any]:
        query = query_text.strip()
        if not query:
            return {'type': 'error', 'message': '請輸入藥名查詢內容'}

        try:
            columns = DrugQueryService._get_drug_items_columns()
            if not columns:
                return {'type': 'error', 'message': '找不到正式藥名表 drug_items'}

            search_columns = [c for c in SEARCH_CANDIDATE_COLUMNS if c in columns]
            if not search_columns:
                return {'type': 'error', 'message': 'drug_items 缺少可查詢的藥名欄位'}

            rows = DrugQueryService._query_rows(query, columns, search_columns)
        except Exception:
            logger.exception("藥名查詢失敗")
            return {'type': 'error', 'message': '藥名查詢失敗，請稍後再試'}

        if not rows:
            return {'type': 'empty', 'message': f'找不到「{query}」相關的藥名', 'query': query}

        visible = rows[:10]
        return {
            'type': 'list',
            'items': [DrugQueryService._normalize_row(row) for row in visible],
            'total': len(visible),
            'has_more': len(rows) > 10,
            'query': query,
        }

    @staticmethod
    def _get_drug_items_columns() -> set:
        sql = text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = 'drug_items'
        """)
        return {row[0] for row in db.session.execute(sql).all()}

    @staticmethod
    def _query_rows(query: str, columns: set, search_columns: List[str]) -> List[Dict[str, Any]]:
        select_columns = []
        for column in CORE_COLUMNS + OPTIONAL_DISPLAY_COLUMNS:
            if column in columns and column not in select_columns:
                select_columns.append(column)

        if 'id' not in select_columns and 'id' in columns:
            select_columns.insert(0, 'id')

        select_sql = ', '.join(DrugQueryService._q(column) for column in select_columns)
        exact_conditions = [
            f"LOWER(COALESCE({DrugQueryService._q(column)}::text, '')) = LOWER(:query)"
            for column in search_columns
        ]
        fuzzy_conditions = [
            f"{DrugQueryService._q(column)}::text ILIKE :like"
            for column in search_columns
        ]
        prefix_conditions = [
            f"{DrugQueryService._q(column)}::text ILIKE :prefix"
            for column in search_columns
        ]

        exact_sql = ' OR '.join(exact_conditions)
        fuzzy_sql = ' OR '.join(fuzzy_conditions)
        prefix_sql = ' OR '.join(prefix_conditions)
        active_sql = ''
        if 'is_active' in columns:
            active_sql = ' AND COALESCE("is_active", TRUE) IS TRUE'

        order_parts = [
            f"CASE WHEN {exact_sql} THEN 0 ELSE 1 END",
            f"CASE WHEN {prefix_sql} THEN 0 ELSE 1 END",
        ]
        if 'table_type' in columns:
            order_parts.append('"table_type" NULLS LAST')
        if 'seq_no' in columns:
            order_parts.append('"seq_no" NULLS LAST')
        order_sql = ', '.join(order_parts)

        sql = text(f"""
            SELECT {select_sql}
            FROM drug_items
            WHERE ({exact_sql} OR {fuzzy_sql}){active_sql}
            ORDER BY {order_sql}
            LIMIT 11
        """)

        params = {
            'query': query,
            'like': f'%{query}%',
            'prefix': f'{query}%',
        }
        return [dict(row) for row in db.session.execute(sql, params).mappings().all()]

    @staticmethod
    def _normalize_row(row: Dict[str, Any]) -> Dict[str, Any]:
        drug_id = row.get('id')
        return {
            'id': drug_id,
            'seq_no': row.get('seq_no'),
            'table_type': row.get('table_type'),
            'item_kind': row.get('item_kind'),
            'generic_name': row.get('generic_name'),
            'brand_name': row.get('brand_name'),
            'aliases': row.get('aliases'),
            'normalized_name': row.get('normalized_name'),
            'raw_name': row.get('raw_name') or row.get('original_name') or row.get('source_name'),
            'spec': row.get('spec') or row.get('specification') or row.get('strength'),
            'dosage': row.get('dosage') or row.get('dose'),
            'unit': row.get('unit'),
            'category': row.get('category'),
            'supplier': row.get('supplier'),
            'manufacturer': row.get('manufacturer'),
            'source': row.get('source') or row.get('source_photo') or row.get('source_version'),
            'related_diagnoses': DrugQueryService._get_related_diagnoses(drug_id) if drug_id else [],
        }

    @staticmethod
    def _get_related_diagnoses(drug_item_id: int) -> List[Dict[str, Any]]:
        rows = db.session.execute(
            text("""
                SELECT
                    dc.id AS diagnosis_code_id,
                    dc.icd10_code,
                    dc.icd9_code,
                    dc.name_zh,
                    ddl.link_type,
                    ddl.role_type,
                    ddl.confidence,
                    ddl.source_type,
                    ddl.note_text,
                    ddl.is_primary,
                    ddl.sort_order
                FROM drug_diagnosis_links ddl
                JOIN diagnosis_codes dc ON dc.id = ddl.diagnosis_code_id
                WHERE ddl.drug_item_id = :drug_item_id
                ORDER BY
                    ddl.is_primary DESC,
                    CASE ddl.confidence
                        WHEN 'high' THEN 1
                        WHEN 'medium' THEN 2
                        WHEN 'low' THEN 3
                        ELSE 4
                    END ASC,
                    ddl.sort_order ASC,
                    dc.icd10_code ASC NULLS LAST,
                    dc.icd9_code ASC NULLS LAST
                LIMIT 5
            """),
            {'drug_item_id': drug_item_id},
        ).mappings().all()

        return [dict(row) for row in rows]

    @staticmethod
    def _q(identifier: str) -> str:
        return '"' + identifier.replace('"', '""') + '"'
