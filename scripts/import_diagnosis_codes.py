#!/usr/bin/env python3
"""
匯入診斷碼 MD → PostgreSQL

用法：python scripts/import_diagnosis_codes.py [MD_FILE_PATH]
預設路徑：../zhuosuo/00_醫師常用診斷碼整理_NotebookLM.md
"""
import sys
import os
import re
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

CHINESE_NUMS = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
                '六': 6, '七': 7, '八': 8, '九': 9, '十': 10}


def chinese_to_int(s):
    s = s.strip()
    if s.isdigit():
        return int(s)
    return CHINESE_NUMS.get(s, 0)


# ---------------------------------------------------------------------------
# MD Parser
# ---------------------------------------------------------------------------

def parse_md(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    raw_sections = re.split(r'\n(?=## )', content)
    chapters = []
    for section in raw_sections:
        if re.match(r'## 第.+章', section):
            ch = _parse_chapter(section)
            if ch:
                chapters.append(ch)
    return chapters


def _parse_chapter(text):
    header = re.match(r'## 第(.+?)章[：:](.+)', text)
    if not header:
        return None

    ch_num = chinese_to_int(header.group(1))
    ch_name = header.group(2).strip()

    source_match = re.search(r'來源照片[：:](.+?)(?:\n|$)', text)
    source_photos = source_match.group(1).strip() if source_match else None

    subsections = re.split(r'\n(?=### )', text)

    codes = {}
    notes = []

    for sub in subsections:
        sub_title = sub.split('\n', 1)[0] if sub else ''

        if '高頻項目' in sub_title or '螢光筆標記' in sub_title:
            _parse_standard_table(sub, codes, force_high_freq=True)
        elif '完整診斷碼列表' in sub_title:
            _parse_standard_table(sub, codes)
        elif '常見對照表' in sub_title and ch_num == 9:
            _parse_chapter9_table(sub, codes)
        elif '手寫補充' in sub_title:
            _parse_handwritten_table(sub, codes)
        elif '補充說明' in sub_title or '簡單記法' in sub_title:
            _parse_notes_section(sub, notes)

    return {
        'number': ch_num,
        'name': ch_name,
        'source_photos': source_photos,
        'codes': codes,
        'notes': notes,
    }


def _parse_standard_table(text, codes, force_high_freq=False):
    current_subcat = None
    for line in text.split('\n'):
        line = line.strip()

        subcat_m = re.match(r'\*\*(.+?)\*\*[：:]', line)
        if subcat_m:
            current_subcat = subcat_m.group(1).strip()
            continue

        if not line.startswith('|') or '---' in line:
            continue
        parts = [p.strip() for p in line.split('|')]
        parts = [p for p in parts if p != '']
        if len(parts) < 2 or parts[0] in ('診斷碼',):
            continue

        code_cell = parts[0]
        name_zh = parts[1] if len(parts) > 1 else ''
        name_en = parts[2] if len(parts) > 2 else ''

        is_highlighted = '🔸' in code_cell
        is_handwritten_mark = '✏️' in code_cell
        is_deprecated = '✗' in code_cell

        code_clean = re.sub(r'[🔸✏️✗\s]', '', code_cell).strip()
        if not code_clean or code_clean == '—':
            continue

        if name_en in ('—', ''):
            name_en = None

        hi = is_highlighted or force_high_freq

        if code_clean in codes:
            if hi:
                codes[code_clean]['is_high_frequency'] = True
            if is_handwritten_mark:
                codes[code_clean]['is_handwritten'] = True
            if name_en and not codes[code_clean].get('name_en'):
                codes[code_clean]['name_en'] = name_en
            if current_subcat and not codes[code_clean].get('subcategory'):
                codes[code_clean]['subcategory'] = current_subcat
        else:
            codes[code_clean] = {
                'icd9_code': code_clean,
                'icd10_code': None,
                'name_zh': name_zh,
                'name_en': name_en,
                'subcategory': current_subcat,
                'is_high_frequency': hi,
                'is_handwritten': is_handwritten_mark,
                'is_deprecated': is_deprecated,
                'confidence': 'confirmed',
                'additional_codes': None,
            }


def _parse_chapter9_table(text, codes):
    """第九章：| 中文名稱 | ICD-10-CM | ICD-9-CM | 補充說明 |"""
    for line in text.split('\n'):
        line = line.strip()
        if not line.startswith('|') or '---' in line:
            continue
        parts = [p.strip() for p in line.split('|')]
        parts = [p for p in parts if p != '']
        if len(parts) < 3 or parts[0] in ('中文名稱',):
            continue

        name_zh = parts[0]
        icd10 = parts[1] if len(parts) > 1 else ''
        icd9_raw = parts[2] if len(parts) > 2 else ''
        desc = parts[3] if len(parts) > 3 else ''

        icd9_codes = [c.strip() for c in re.split(r'[\/,]', icd9_raw) if c.strip()]
        icd9_str = ' / '.join(icd9_codes) if icd9_codes else None

        additional = None
        if '另加' in desc:
            m = re.search(r'另加\s*(.+?)(?:。|$)', desc)
            if m:
                additional = m.group(1).strip().rstrip('。')

        key = name_zh
        if key not in codes:
            codes[key] = {
                'icd9_code': icd9_str,
                'icd10_code': icd10 if icd10 else None,
                'name_zh': name_zh,
                'name_en': None,
                'subcategory': None,
                'is_high_frequency': False,
                'is_handwritten': False,
                'is_deprecated': False,
                'confidence': 'confirmed',
                'description': desc if desc else None,
                'additional_codes': additional,
            }


def _parse_handwritten_table(text, codes):
    for line in text.split('\n'):
        line = line.strip()
        if not line.startswith('|') or '---' in line:
            continue
        parts = [p.strip() for p in line.split('|')]
        parts = [p for p in parts if p != '']
        if len(parts) < 2 or parts[0] in ('診斷碼',):
            continue

        code_cell = parts[0]
        name_zh = parts[1] if len(parts) > 1 else ''
        conf_text = parts[2] if len(parts) > 2 else '已確認'

        code_clean = re.sub(r'[✏️\s]', '', code_cell).strip()
        if not code_clean or code_clean == '—':
            continue

        confidence = 'confirmed' if '已確認' in conf_text else 'pending'

        if code_clean in codes:
            codes[code_clean]['is_handwritten'] = True
            codes[code_clean]['confidence'] = confidence
        else:
            codes[code_clean] = {
                'icd9_code': code_clean,
                'icd10_code': None,
                'name_zh': name_zh,
                'name_en': None,
                'subcategory': None,
                'is_high_frequency': False,
                'is_handwritten': True,
                'is_deprecated': False,
                'confidence': confidence,
                'additional_codes': None,
            }


def _parse_notes_section(text, notes_list):
    for line in text.split('\n'):
        line = line.strip()
        if not line.startswith('-'):
            continue
        note_text = line.lstrip('- ').strip()
        if note_text:
            notes_list.append(note_text)


# ---------------------------------------------------------------------------
# Database Import
# ---------------------------------------------------------------------------

def import_to_db(chapters):
    from modules.models.base import db
    from modules.models.diagnosis import (
        DiagnosisChapter, DiagnosisCode, DiagnosisCodeChapter,
        DiagnosisCodeComponent, DiagnosisCodeNote,
    )

    # 警告：之前這裡的 db.drop_all() 會刪除整個資料庫的所有資料表！
    # 現在改為只針對診斷碼相關表進行清理（或保留 db.create_all() 確保表存在）
    db.create_all()
    
    # 清空原本的診斷碼資料（如果需要重新匯入）
    db.session.query(DiagnosisCodeComponent).delete()
    db.session.query(DiagnosisCodeNote).delete()
    db.session.query(DiagnosisCodeChapter).delete()
    db.session.query(DiagnosisCode).delete()
    db.session.query(DiagnosisChapter).delete()
    db.session.commit()

    code_objects = {}
    chapter_objects = {}

    for ch in chapters:
        ch_obj = DiagnosisChapter(
            chapter_number=ch['number'],
            name=ch['name'],
            source_photos=ch.get('source_photos'),
        )
        db.session.add(ch_obj)
        db.session.flush()
        chapter_objects[ch['number']] = ch_obj
        logger.info(f"  章節 {ch['number']}: {ch['name']} ({len(ch['codes'])} 筆)")

        for code_key, info in ch['codes'].items():
            lookup = info['name_zh']

            if lookup not in code_objects:
                dc = DiagnosisCode(
                    icd9_code=info.get('icd9_code'),
                    icd10_code=info.get('icd10_code'),
                    name_zh=info['name_zh'],
                    name_en=info.get('name_en'),
                    aliases=info.get('aliases'),
                    subcategory=info.get('subcategory'),
                    is_high_frequency=info.get('is_high_frequency', False),
                    is_handwritten=info.get('is_handwritten', False),
                    is_deprecated=info.get('is_deprecated', False),
                    confidence=info.get('confidence', 'confirmed'),
                    description=info.get('description'),
                    usage_note=info.get('usage_note'),
                    additional_codes=info.get('additional_codes'),
                )
                db.session.add(dc)
                db.session.flush()
                code_objects[lookup] = dc
            else:
                dc = code_objects[lookup]
                if info.get('is_high_frequency'):
                    dc.is_high_frequency = True
                if info.get('is_handwritten'):
                    dc.is_handwritten = True
                if info.get('name_en') and not dc.name_en:
                    dc.name_en = info['name_en']
                if info.get('subcategory') and not dc.subcategory:
                    dc.subcategory = info['subcategory']
                if info.get('icd10_code') and not dc.icd10_code:
                    dc.icd10_code = info['icd10_code']
                if info.get('additional_codes') and not dc.additional_codes:
                    dc.additional_codes = info['additional_codes']

            exists = DiagnosisCodeChapter.query.filter_by(
                diagnosis_code_id=dc.id, chapter_id=ch_obj.id
            ).first()
            if not exists:
                db.session.add(DiagnosisCodeChapter(
                    diagnosis_code_id=dc.id, chapter_id=ch_obj.id
                ))

            icd9 = info.get('icd9_code') or ''
            if '+' in icd9:
                parts = icd9.split('+')
                for idx, part in enumerate(parts):
                    existing_comp = DiagnosisCodeComponent.query.filter_by(
                        combined_code_id=dc.id, component_code=part
                    ).first()
                    if not existing_comp:
                        db.session.add(DiagnosisCodeComponent(
                            combined_code_id=dc.id,
                            component_code=part,
                            component_order=idx + 1,
                        ))

        for note_text in ch.get('notes', []):
            linked_code_id = None
            code_refs = re.findall(r'\b(\d{3,5})\b', note_text)
            if code_refs:
                for ref in code_refs:
                    for obj in code_objects.values():
                        if obj.icd9_code and ref in obj.icd9_code:
                            linked_code_id = obj.id
                            break
                    if linked_code_id:
                        break

            db.session.add(DiagnosisCodeNote(
                diagnosis_code_id=linked_code_id,
                chapter_id=ch_obj.id,
                note_type='supplement',
                note_text=note_text,
            ))

    db.session.commit()

    total_codes = DiagnosisCode.query.count()
    with_icd10 = DiagnosisCode.query.filter(DiagnosisCode.icd10_code.isnot(None)).count()
    total_links = DiagnosisCodeChapter.query.count()
    total_notes = DiagnosisCodeNote.query.count()
    total_components = DiagnosisCodeComponent.query.count()

    logger.info(f"\n匯入完成:")
    logger.info(f"  診斷碼: {total_codes} 筆（{with_icd10} 筆含 ICD-10）")
    logger.info(f"  碼-章節關聯: {total_links}")
    logger.info(f"  補充說明: {total_notes}")
    logger.info(f"  組合碼拆解: {total_components}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    default_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        '..', 'zhuosuo', '00_醫師常用診斷碼整理_NotebookLM.md'
    )
    md_path = sys.argv[1] if len(sys.argv) > 1 else default_path
    md_path = os.path.abspath(md_path)

    if not os.path.exists(md_path):
        logger.error(f"找不到檔案: {md_path}")
        sys.exit(1)

    logger.info(f"解析 MD 檔案: {md_path}")
    chapters = parse_md(md_path)
    logger.info(f"解析到 {len(chapters)} 個章節")

    from modules import create_app
    app = create_app()
    with app.app_context():
        logger.info("匯入資料庫...")
        import_to_db(chapters)

    logger.info("完成!")


if __name__ == '__main__':
    main()
