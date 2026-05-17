"""
診斷碼查詢 LINE Bot 處理器

觸發方式：
  dx 2749        → 精確碼查詢
  碼 痛風        → 關鍵字搜尋
  dx 泌尿高頻碼  → 章節 + 高頻篩選
  /dx ...        → 群組相容
"""
import logging
from modules.utils.line_bot import reply_text
from modules.services.diagnosis_query_service import DiagnosisQueryService

logger = logging.getLogger(__name__)

PREFIXES = ['dx ', 'dx', '碼 ', '碼', '/dx ', '/dx', '/碼 ', '/碼']


def is_diagnosis_trigger(text: str) -> bool:
    lower = text.lower().strip()
    for p in PREFIXES:
        if lower.startswith(p.lower()):
            return True
    return False


def extract_query(text: str) -> str:
    lower = text.lower().strip()
    for p in sorted(PREFIXES, key=len, reverse=True):
        if lower.startswith(p.lower()):
            return text[len(p):].strip()
    return text.strip()


def handle_diagnosis_message(event):
    text = event.message.text.strip()
    reply_token = event.reply_token

    query = extract_query(text)

    if not query or query in ('help', '幫助', '說明'):
        reply_text(reply_token, _help_text())
        return

    if query in ('章節', '目錄', 'chapters'):
        chapters = DiagnosisQueryService.list_chapters()
        reply_text(reply_token, _format_chapters(chapters))
        return

    try:
        result = DiagnosisQueryService.search(query)
        reply_text(reply_token, _format_result(result))
    except Exception as e:
        logger.error(f"診斷碼查詢失敗: {e}", exc_info=True)
        reply_text(reply_token, "❌ 查詢失敗，請稍後再試")


# ---------------------------------------------------------------------------
# 格式化
# ---------------------------------------------------------------------------

def _format_result(result: dict) -> str:
    if result['type'] == 'error':
        return f"❌ {result['message']}"
    if result['type'] == 'empty':
        return f"🔍 {result['message']}\n\n💡 試試：dx 章節 查看所有分類"
    if result['type'] == 'single':
        return _format_single(result['codes'][0])
    if result['type'] == 'table':
        return _format_table(result)
    return _format_list(result['codes'], result['total'], result.get('query', ''))


def _format_single(c: dict) -> str:
    lines = []

    en = f" ({c['name_en']})" if c.get('name_en') else ''
    code_display = c.get('icd9_code') or c.get('icd10_code') or ''
    lines.append(f"📋 {code_display} — {c['name_zh']}{en}")
    lines.append('━' * 20)

    if c.get('icd10_code') and c.get('icd9_code'):
        lines.append(f"📁 ICD-10: {c['icd10_code']}  |  ICD-9: {c['icd9_code']}")
    elif c.get('icd10_code'):
        lines.append(f"📁 ICD-10: {c['icd10_code']}")
    elif c.get('icd9_code'):
        lines.append(f"📁 ICD-9: {c['icd9_code']}")

    if c.get('chapters'):
        lines.append(f"📂 {' / '.join(c['chapters'])}")

    tags = []
    if c.get('is_high_frequency'):
        tags.append('🔸 高頻碼')
    if c.get('is_handwritten'):
        tags.append('✏️ 手寫新增')
    if c.get('is_deprecated'):
        tags.append('✗ 不常用')
    if tags:
        lines.append(' '.join(tags))

    if c.get('subcategory'):
        lines.append(f"🏷️ {c['subcategory']}")

    if c.get('additional_codes'):
        lines.append(f"＋另加：{c['additional_codes']}")

    if c.get('components'):
        comp_str = ' + '.join(
            f"{comp['code']}({comp['name_zh']})" if comp.get('name_zh') else comp['code']
            for comp in sorted(c['components'], key=lambda x: x['order'])
        )
        lines.append(f"🔗 組合碼：{comp_str}")

    if c.get('description'):
        desc = c['description']
        if '另加' not in desc and len(desc) <= 60:
            lines.append(f"📝 {desc}")

    if c.get('notes'):
        lines.append('')
        for note in c['notes'][:3]:
            note_short = note if len(note) <= 80 else note[:77] + '...'
            lines.append(f"💡 {note_short}")

    related = _format_related_drugs(c)
    if related:
        lines.append('')
        lines.extend(related)

    return '\n'.join(lines)


def _format_table(result: dict) -> str:
    codes = result['codes']
    notes = result.get('chapter_notes', [])
    query = result.get('query', '')

    lines = [f'📋 {query} — 對照表', '━' * 22, '']

    for c in codes[:15]:
        lines.append(f'▸ {c["name_zh"]}')
        if c.get('icd10_code') and c.get('icd9_code'):
            lines.append(f'  ICD-10: {c["icd10_code"]}')
            lines.append(f'  ICD-9:  {c["icd9_code"]}')
        elif c.get('icd10_code'):
            lines.append(f'  ICD-10: {c["icd10_code"]}')
        elif c.get('icd9_code'):
            lines.append(f'  ICD-9:  {c["icd9_code"]}')

        if c.get('additional_codes'):
            lines.append(f'  ＋另加：{c["additional_codes"]}')
        elif c.get('description') and '另加' not in (c.get('description') or ''):
            desc = c['description']
            if len(desc) <= 40:
                lines.append(f'  📝 {desc}')
        related = _format_related_drugs(c, prefix='  ')
        if related:
            lines.extend(related)
        lines.append('')

    if notes:
        lines.append('📝 簡單記法：')
        for n in notes:
            lines.append(f'  • {n}')

    return '\n'.join(lines)


def _format_list(codes: list, total: int, query: str) -> str:
    lines = [f"📋 找到 {total} 筆「{query}」相關診斷碼", '']

    for c in codes[:15]:
        prefix = '🔸' if c.get('is_high_frequency') else '  '
        en = f" ({c['name_en']})" if c.get('name_en') else ''
        ch_str = f" [{'/'.join(c['chapters'])}]" if c.get('chapters') else ''

        icd9 = c.get('icd9_code') or ''
        icd10 = c.get('icd10_code') or ''
        if icd10 and icd9:
            code_str = f"{icd9} | {icd10}"
        else:
            code_str = icd9 or icd10

        lines.append(f"{prefix} {code_str} {c['name_zh']}{en}{ch_str}")
        related = _format_related_drugs(c, prefix='   ')
        if related:
            lines.extend(related)

    if total > 15:
        lines.append(f"\n... 還有 {total - 15} 筆，請縮小查詢範圍")

    lines.append(f"\n💡 輸入 dx <碼號> 查看詳情")
    return '\n'.join(lines)


def _format_related_drugs(c: dict, prefix: str = '') -> list:
    related = c.get('related_drugs') or []
    if not related:
        return []

    lines = [f'{prefix}相關藥名']
    for drug in related[:5]:
        drug_name = f"{drug.get('generic_name') or ''} / {drug.get('brand_name') or ''}".strip()
        meta = '；'.join(
            part for part in [
                drug.get('link_type'),
                drug.get('role_type'),
                drug.get('confidence'),
                drug.get('source_type'),
            ]
            if part
        )
        line = f'{prefix}- {drug_name}'
        if meta:
            line += f'（{meta}）'
        lines.append(line)
        if drug.get('note_text'):
            lines.append(f"{prefix}  {drug['note_text']}")
    return lines


def _format_chapters(chapters: list) -> str:
    lines = ['📚 診斷碼章節目錄', '━' * 20, '']
    for ch in chapters:
        lines.append(f"第{ch['number']}章 {ch['name']}（{ch['code_count']} 筆）")
    lines.append('')
    lines.append('💡 輸入 dx <章節名> 查看該章碼')
    lines.append('   例：dx 皮膚、dx 泌尿高頻碼')
    return '\n'.join(lines)


def _help_text() -> str:
    return """📋 診斷碼查詢系統
━━━━━━━━━━━━━━━━━━━━

🔍 查詢方式：

  dx 2749          精確碼查詢
  dx I13.10        ICD-10 查詢
  dx 痛風          名稱搜尋
  dx 泌尿高頻碼    章節 + 高頻篩選
  dx 洗腎 貧血     多關鍵字搜尋
  碼 肝炎          中文前綴
  dx 章節          查看所有章節

📁 支援章節：
  皮膚、骨關節、泌尿腎臟、
  癌症、血液代謝、感染、
  肝膽、神經、高血壓

🔸 = 醫師高頻使用碼
✏️ = 手寫新增碼
📁 ICD-10 欄位隨時可擴充"""
