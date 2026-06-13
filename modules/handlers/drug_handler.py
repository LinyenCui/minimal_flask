"""
藥名查詢 LINE Bot 處理器

觸發方式：
  /drug Concor
  /藥名 立普妥
  drug Metformin
  !drug 胰島素
"""
import logging

from modules.services.drug_query_service import DrugQueryService
from modules.utils.line_bot import reply_message, reply_text
from modules.views.drug_flex import render_drug_results

logger = logging.getLogger(__name__)

# 觸發前綴：裸字「藥」「藥名」已移除(中文常用字,群聊易誤觸,如「藥師/藥膏/藥局」)
# 查藥名請用 /藥名、/drug、!drug 等明確前綴;英文 drug 裸字保留(中文群聊幾乎不誤觸)
PREFIXES = ['/藥名 ', '/藥名', '/drug ', '/drug', 'drug ', 'drug', '!drug ', '!drug', '！drug ', '！drug']


def is_drug_trigger(text: str) -> bool:
    lower = text.lower().strip()
    for prefix in PREFIXES:
        if lower.startswith(prefix.lower()):
            return True
    return False


def extract_query(text: str) -> str:
    lower = text.lower().strip()
    for prefix in sorted(PREFIXES, key=len, reverse=True):
        if lower.startswith(prefix.lower()):
            return text[len(prefix):].strip()
    return text.strip()


def handle_drug_message(event):
    text = event.message.text.strip()
    reply_token = event.reply_token
    query = extract_query(text)

    if not query or query in ('help', '幫助', '說明'):
        reply_text(reply_token, _help_text())
        return

    try:
        result = DrugQueryService.search(query)
        _reply_result(reply_token, result)
    except Exception as exc:
        logger.error(f"藥名查詢失敗: {exc}", exc_info=True)
        reply_text(reply_token, "❌ 藥名查詢失敗，請稍後再試")


def _reply_result(reply_token: str, result: dict) -> None:
    """Reply with read-only Flex for drug results, falling back to text."""
    text_fallback = _format_result(result)

    if result.get('type') != 'list' or not result.get('items'):
        reply_text(reply_token, text_fallback)
        return

    try:
        items = result.get('items') or []
        flex = render_drug_results(items)
        ok = reply_message(reply_token, {
            'type': 'flex',
            'altText': f"藥名查詢：{result.get('query') or 'drug'}（{len(items)} 筆）",
            'contents': flex,
        })
        if not ok:
            logger.warning("藥名 Flex 發送失敗，改用文字 fallback")
            reply_text(reply_token, text_fallback)
    except Exception as exc:
        logger.warning(f"藥名 Flex 建立失敗，改用文字 fallback: {exc}", exc_info=True)
        reply_text(reply_token, text_fallback)


def _format_result(result: dict) -> str:
    if result['type'] == 'error':
        return f"❌ {result['message']}"
    if result['type'] == 'empty':
        return (
            f"🔍 {result['message']}\n\n"
            "💡 試試：/drug Concor、/藥名 立普妥、!drug 胰島素"
        )
    return _format_list(result)


def _format_list(result: dict) -> str:
    items = result.get('items') or []
    query = result.get('query', '')
    lines = [f"💊 找到 {len(items)} 筆「{query}」相關藥名", '']

    for idx, item in enumerate(items, start=1):
        title = item.get('brand_name') or item.get('generic_name') or item.get('raw_name') or f"藥品 #{item.get('id')}"
        lines.append(f"{idx}. {title}")

        if item.get('generic_name') and item.get('generic_name') != title:
            lines.append(f"   成分：{item['generic_name']}")
        if item.get('brand_name') and item.get('brand_name') != title:
            lines.append(f"   藥名：{item['brand_name']}")
        if item.get('nhi_drug_code'):
            lines.append(f"   健保碼：{item['nhi_drug_code']}")

        type_parts = [part for part in (item.get('table_type'), item.get('item_kind')) if part]
        if type_parts:
            lines.append(f"   類型：{' / '.join(type_parts)}")

        extra_parts = []
        for label, key in (
            ('規格', 'spec'),
            ('劑量', 'dosage'),
            ('單位', 'unit'),
            ('標準名', 'normalized_name'),
            ('原始名', 'raw_name'),
            ('分類', 'category'),
            ('來源', 'source'),
        ):
            if item.get(key):
                extra_parts.append(f"{label}：{item[key]}")
        for part in extra_parts[:5]:
            lines.append(f"   {part}")

        related = _format_related_diagnoses(item)
        if related:
            lines.extend(related)

        lines.append('')

    if result.get('has_more'):
        lines.append('... 可能還有更多結果，請縮小查詢範圍')
        lines.append('')

    lines.append('💡 輸入 /drug <藥名> 查詢正式 drug_items')
    return '\n'.join(lines).rstrip()


def _help_text() -> str:
    return """💊 藥名查詢
━━━━━━━━━━━━━━━━━━━━

查詢方式：
  /drug Concor
  /藥名 立普妥
  drug Metformin
  !drug 胰島素

資料來源：正式表 drug_items
最多顯示 10 筆結果"""


def _format_related_diagnoses(item: dict) -> list:
    related = item.get('related_diagnoses') or []
    if not related:
        return []

    lines = ['   相關診斷碼']
    for dx in related[:5]:
        icd10 = dx.get('icd10_code') or ''
        icd9 = dx.get('icd9_code') or ''
        name = dx.get('name_zh') or ''
        code_parts = [part for part in (icd10, icd9, name) if part]
        meta = '；'.join(
            part for part in [
                dx.get('link_type'),
                dx.get('role_type'),
                dx.get('confidence'),
                dx.get('source_type'),
            ]
            if part
        )
        line = f"   - {' / '.join(code_parts)}"
        if meta:
            line += f"（{meta}）"
        lines.append(line)
        if dx.get('note_text'):
            lines.append(f"     {dx['note_text']}")
    return lines
