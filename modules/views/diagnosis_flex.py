"""
Read-only diagnosis Flex Message renderer.

The layout follows the existing customer detail Flex style:
header + label/value rows + separators. It is intentionally pure and does
not send messages or access the database.
"""

from typing import Any


PRIMARY = "#1565C0"
ACCENT = "#FF6D00"
MUTED = "#999999"
BLACK = "#333333"
SUCCESS = "#2E7D32"
DANGER = "#D32F2F"
LIGHT_BG = "#F5F5F5"


def _short(text: Any, limit: int = 80) -> str:
    value = "" if text is None else str(text).strip()
    if len(value) <= limit:
        return value
    return value[: limit - 1] + "..."


def _row(
    label: str,
    value: str,
    *,
    value_color: str = BLACK,
    value_weight: str = "regular",
    label_color: str = "#666666",
) -> dict:
    return {
        "type": "box",
        "layout": "horizontal",
        "spacing": "sm",
        "contents": [
            {
                "type": "text",
                "text": label,
                "size": "sm",
                "color": label_color,
                "flex": 2,
            },
            {
                "type": "text",
                "text": value or "—",
                "size": "sm",
                "color": value_color,
                "weight": value_weight,
                "flex": 5,
                "wrap": True,
            },
        ],
    }


def _separator(margin: str = "md") -> dict:
    return {"type": "separator", "margin": margin}


def _tag(text: str, color: str = PRIMARY) -> dict:
    return {
        "type": "text",
        "text": text,
        "size": "xs",
        "color": color,
        "weight": "bold",
        "wrap": True,
    }


def _drug_row(drug: dict) -> dict:
    generic = drug.get("generic_name") or ""
    brand = drug.get("brand_name") or ""
    name = " / ".join(part for part in (generic, brand) if part) or "—"
    meta = " / ".join(
        part
        for part in (
            drug.get("confidence"),
            drug.get("source_type"),
            drug.get("role_type"),
        )
        if part
    )
    return {
        "type": "box",
        "layout": "vertical",
        "spacing": "xs",
        "paddingAll": "sm",
        "backgroundColor": LIGHT_BG,
        "cornerRadius": "md",
        "contents": [
            {
                "type": "text",
                "text": _short(name, 72),
                "size": "sm",
                "color": BLACK,
                "weight": "bold",
                "wrap": True,
            },
            {
                "type": "text",
                "text": meta or "—",
                "size": "xs",
                "color": MUTED,
                "wrap": True,
            },
        ],
    }


def render_diagnosis_detail(c: dict) -> dict:
    """Render one enriched diagnosis result as a Flex bubble."""
    body: list[dict] = []

    icd10 = c.get("icd10_code") or ""
    icd9 = c.get("icd9_code") or ""
    name_zh = c.get("name_zh") or "診斷碼"

    if icd10:
        body.append(_row("ICD-10", icd10, value_color=PRIMARY, value_weight="bold"))
    if icd9:
        body.append(_row("ICD-9", icd9, value_color=PRIMARY, value_weight="bold"))

    body.append(_row("中文名", name_zh, value_weight="bold"))
    if c.get("name_en"):
        body.append(_row("英文名", _short(c["name_en"], 96), value_color=MUTED))

    tags = []
    if c.get("is_high_frequency"):
        tags.append(_tag("高頻碼", ACCENT))
    if c.get("is_handwritten"):
        tags.append(_tag("手寫新增", PRIMARY))
    if c.get("is_deprecated"):
        tags.append(_tag("不常用", DANGER))
    if tags:
        body.append(
            {
                "type": "box",
                "layout": "horizontal",
                "spacing": "md",
                "margin": "sm",
                "contents": tags,
            }
        )

    if c.get("chapters") or c.get("subcategory"):
        body.append(_separator())
        if c.get("chapters"):
            body.append(_row("章節", " / ".join(c["chapters"])))
        if c.get("subcategory"):
            body.append(_row("分類", c["subcategory"]))

    if c.get("additional_codes") or c.get("components"):
        body.append(_separator())
        if c.get("additional_codes"):
            body.append(_row("另加", c["additional_codes"], value_color=ACCENT))
        if c.get("components"):
            comp_text = " + ".join(
                f"{comp.get('code')}({comp.get('name_zh')})"
                if comp.get("name_zh")
                else str(comp.get("code") or "")
                for comp in sorted(c["components"], key=lambda x: x.get("order") or 0)
            )
            body.append(_row("組合碼", _short(comp_text, 96), value_color=ACCENT))

    note_items = []
    if c.get("description") and "另加" not in c["description"]:
        note_items.append(c["description"])
    note_items.extend(c.get("notes") or [])
    note_items = [_short(note, 72) for note in note_items if note][:2]
    if note_items:
        body.append(_separator())
        for idx, note in enumerate(note_items, start=1):
            body.append(_row(f"備註{idx}", note, value_color=MUTED))

    related = c.get("related_drugs") or []
    if related:
        body.append(_separator())
        body.append(
            {
                "type": "text",
                "text": "相關藥名",
                "weight": "bold",
                "size": "sm",
                "color": SUCCESS,
                "margin": "sm",
            }
        )
        for drug in related[:5]:
            body.append(_drug_row(drug))

    header_code = icd10 or icd9 or f"#{c.get('id') or ''}".strip()
    return {
        "type": "bubble",
        "size": "mega",
        "header": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": PRIMARY,
            "paddingAll": "md",
            "contents": [
                {
                    "type": "text",
                    "text": _short(name_zh, 40),
                    "weight": "bold",
                    "size": "lg",
                    "color": "#ffffff",
                    "wrap": True,
                },
                {
                    "type": "text",
                    "text": header_code or "診斷碼",
                    "size": "xs",
                    "color": "#E0E0E0",
                    "margin": "sm",
                    "wrap": True,
                },
            ],
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": body,
        },
    }

