"""
診斷碼查詢服務

三層搜尋策略：
  L1 精確查碼    — icd9_code / icd10_code 精確匹配
  L2 關鍵字搜尋  — ILIKE + 章節/高頻過濾
  L3 （未來）    — pg_trgm / pgvector
"""
import re
import logging
from typing import List, Dict, Any

from sqlalchemy import text

from modules.models.base import db
from modules.models.diagnosis import (
    DiagnosisCode, DiagnosisChapter, DiagnosisCodeChapter,
    DiagnosisCodeNote,
)

logger = logging.getLogger(__name__)

CHAPTER_KEYWORDS = {
    '皮膚': 1,
    '骨關節': 2, '肌肉': 2, '骨骼': 2, '關節': 2,
    '泌尿': 3, '腎臟': 3, '腎': 3, '攝護腺': 3, '膀胱': 3,
    '癌': 4, '癌症': 4, '腫瘤': 4,
    '血液': 5, '代謝': 5, '貧血': 5, '電解質': 5, '血脂': 5,
    '感染': 6,
    '肝': 7, '膽': 7, '肝膽': 7, '胰臟': 7,
    '神經': 8, '阿茲海默': 8,
    '高血壓': 9,
}

NOISE_WORDS = [
    '碼', '診斷碼', '的', '有哪些', '列出', '查詢', '查', '是什麼',
    '什麼', '相關', '所有', '全部', '幫我', '請問',
]


class DiagnosisQueryService:

    @staticmethod
    def search(query_text: str) -> Dict[str, Any]:
        query = query_text.strip()
        if not query:
            return {'type': 'error', 'message': '請輸入查詢內容'}

        if re.match(r'^[\d\+\.\/\s]+$', query):
            return DiagnosisQueryService.lookup_code(query.replace(' ', ''))

        if re.match(r'^[A-Za-z]\d', query):
            return DiagnosisQueryService.lookup_code(query)

        return DiagnosisQueryService.smart_search(query)

    # ----- L1：精確碼查詢 -----

    @staticmethod
    def lookup_code(code: str) -> Dict[str, Any]:
        results = DiagnosisCode.query.filter(
            db.or_(
                DiagnosisCode.icd9_code == code,
                DiagnosisCode.icd10_code == code,
            )
        ).all()

        if not results:
            results = DiagnosisCode.query.filter(
                db.or_(
                    DiagnosisCode.icd9_code.ilike(f'%{code}%'),
                    DiagnosisCode.icd10_code.ilike(f'%{code}%'),
                )
            ).limit(20).all()

        if not results:
            return {'type': 'empty', 'message': f'找不到診斷碼 {code}', 'query': code}

        enriched = [DiagnosisQueryService._enrich(dc) for dc in results]
        has_additional = any(c.get('additional_codes') for c in enriched)

        if len(enriched) == 1 and not has_additional:
            return {'type': 'single', 'codes': enriched, 'total': 1, 'query': code}

        if has_additional:
            notes = DiagnosisQueryService._get_chapter_notes(enriched)
            return {'type': 'table', 'codes': enriched, 'chapter_notes': notes,
                    'total': len(enriched), 'query': code}

        return {'type': 'list', 'codes': enriched, 'total': len(enriched), 'query': code}

    # ----- L2：智能關鍵字搜尋 -----

    @staticmethod
    def smart_search(text: str) -> Dict[str, Any]:
        wants_high_freq = any(kw in text for kw in ('高頻', '常用', '最常'))
        wants_handwritten = '手寫' in text

        target_chapter = None
        for kw, ch_num in sorted(CHAPTER_KEYWORDS.items(), key=lambda x: -len(x[0])):
            if kw in text:
                target_chapter = ch_num
                break

        search_terms = text
        for kw in list(CHAPTER_KEYWORDS.keys()) + NOISE_WORDS + ['高頻', '常用', '最常', '手寫']:
            search_terms = search_terms.replace(kw, '')
        search_terms = search_terms.strip()

        query = DiagnosisCode.query

        if target_chapter:
            query = query.join(DiagnosisCodeChapter).join(DiagnosisChapter).filter(
                DiagnosisChapter.chapter_number == target_chapter
            )

        if wants_high_freq:
            query = query.filter(DiagnosisCode.is_high_frequency.is_(True))
        if wants_handwritten:
            query = query.filter(DiagnosisCode.is_handwritten.is_(True))

        if search_terms:
            like = f'%{search_terms}%'
            query = query.filter(
                db.or_(
                    DiagnosisCode.name_zh.ilike(like),
                    DiagnosisCode.name_en.ilike(like),
                    DiagnosisCode.aliases.ilike(like),
                    DiagnosisCode.description.ilike(like),
                    DiagnosisCode.subcategory.ilike(like),
                    DiagnosisCode.icd9_code.ilike(like),
                    DiagnosisCode.icd10_code.ilike(like),
                )
            )

        results = query.distinct().limit(30).all()

        if not results and search_terms:
            parts = list(search_terms)
            if len(parts) >= 2:
                conditions = [
                    db.or_(
                        DiagnosisCode.name_zh.ilike(f'%{ch}%'),
                        DiagnosisCode.name_en.ilike(f'%{ch}%'),
                    )
                    for ch in parts if ch.strip()
                ]
                if conditions:
                    results = DiagnosisCode.query.filter(
                        db.and_(*conditions)
                    ).limit(20).all()

        if not results:
            return {'type': 'empty', 'message': f'找不到「{text}」相關的診斷碼', 'query': text}

        enriched = [DiagnosisQueryService._enrich(dc) for dc in results]
        has_additional = any(c.get('additional_codes') for c in enriched)

        if len(enriched) == 1:
            return {'type': 'single', 'codes': enriched, 'total': 1, 'query': text}

        if has_additional:
            notes = DiagnosisQueryService._get_chapter_notes(enriched)
            return {'type': 'table', 'codes': enriched, 'chapter_notes': notes,
                    'total': len(enriched), 'query': text}

        return {'type': 'list', 'codes': enriched, 'total': len(enriched), 'query': text}

    # ----- 特殊查詢 -----

    @staticmethod
    def list_chapters() -> List[Dict]:
        chapters = DiagnosisChapter.query.order_by(DiagnosisChapter.chapter_number).all()
        result = []
        for ch in chapters:
            count = DiagnosisCodeChapter.query.filter_by(chapter_id=ch.id).count()
            result.append({'number': ch.chapter_number, 'name': ch.name, 'code_count': count})
        return result

    # ----- Helpers -----

    @staticmethod
    def _enrich(dc: DiagnosisCode) -> Dict[str, Any]:
        chapters = []
        for link in dc.chapter_links:
            ch = db.session.get(DiagnosisChapter, link.chapter_id)
            if ch:
                chapters.append(ch.name)

        components = [
            {'code': comp.component_code, 'name_zh': comp.component_name_zh, 'order': comp.component_order}
            for comp in (dc.components or [])
        ]

        notes = [n.note_text for n in DiagnosisCodeNote.query.filter_by(diagnosis_code_id=dc.id).all()]
        related_drugs = DiagnosisQueryService._get_related_drugs(dc.id)

        return {
            'id': dc.id,
            'icd9_code': dc.icd9_code,
            'icd10_code': dc.icd10_code,
            'name_zh': dc.name_zh,
            'name_en': dc.name_en,
            'aliases': dc.aliases,
            'subcategory': dc.subcategory,
            'chapters': chapters,
            'is_high_frequency': dc.is_high_frequency,
            'is_handwritten': dc.is_handwritten,
            'is_deprecated': dc.is_deprecated,
            'description': dc.description,
            'additional_codes': dc.additional_codes,
            'components': components,
            'notes': notes,
            'related_drugs': related_drugs,
        }

    @staticmethod
    def _get_related_drugs(diagnosis_code_id: int) -> List[Dict[str, Any]]:
        rows = db.session.execute(
            text("""
                SELECT
                    di.id AS drug_item_id,
                    di.generic_name,
                    di.brand_name,
                    ddl.link_type,
                    ddl.role_type,
                    ddl.confidence,
                    ddl.source_type,
                    ddl.note_text,
                    ddl.is_primary,
                    ddl.sort_order
                FROM drug_diagnosis_links ddl
                JOIN drug_items di ON di.id = ddl.drug_item_id
                WHERE ddl.diagnosis_code_id = :diagnosis_code_id
                  AND di.is_active IS TRUE
                ORDER BY
                    ddl.is_primary DESC,
                    CASE ddl.confidence
                        WHEN 'high' THEN 1
                        WHEN 'medium' THEN 2
                        WHEN 'low' THEN 3
                        ELSE 4
                    END ASC,
                    ddl.sort_order ASC,
                    di.generic_name ASC,
                    di.brand_name ASC
                LIMIT 30
            """),
            {'diagnosis_code_id': diagnosis_code_id},
        ).mappings().all()

        return [dict(row) for row in rows]

    @staticmethod
    def _get_chapter_notes(enriched: List[Dict]) -> List[str]:
        chapter_names = set()
        for c in enriched:
            for ch_name in (c.get('chapters') or []):
                chapter_names.add(ch_name)

        if not chapter_names:
            return []

        chs = DiagnosisChapter.query.filter(DiagnosisChapter.name.in_(list(chapter_names))).all()
        chapter_ids = {ch.id for ch in chs}

        notes = DiagnosisCodeNote.query.filter(
            DiagnosisCodeNote.chapter_id.in_(list(chapter_ids)),
        ).all()

        clean = []
        for n in notes:
            txt = n.note_text.replace('**', '').strip()
            if txt.endswith('：') or txt.endswith(':'):
                continue
            if txt.startswith('1.') or txt.startswith('2.'):
                continue
            if txt not in clean:
                clean.append(txt)
        return clean[:8]
