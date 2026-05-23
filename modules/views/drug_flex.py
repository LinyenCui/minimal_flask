"""
Read-only drug Flex Message renderer.

The layout follows the existing fixed schedule Flex style: one entity per
bubble, carousel for multiple results, compact label/value rows, and no write
actions.
"""

from typing import Any


PRIMARY = "#6A1B9A"
ACCENT = "#06C755"
MUTED = "#999999"
BLACK = "#333333"
SUCCESS = "#2E7D32"
LIGHT_BG = "#F5F5F5"
MAX_BUBBLES = 10


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
                "color": "#666666",
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


def _diagnosis_row(dx: dict) -> dict:
    code_parts = [
        part
        for part in (
            dx.get("icd10_code"),
            dx.get("icd9_code"),
            dx.get("name_zh"),
        )
        if part
    ]
    title = " / ".join(code_parts) or "—"
    meta = " / ".join(
        part
        for part in (
            dx.get("confidence"),
            dx.get("source_type"),
            dx.get("role_type"),
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
                "text": _short(title, 76),
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


def _title(item: dict) -> str:
    return (
        item.get("brand_name")
        or item.get("generic_name")
        or item.get("raw_name")
        or f"藥品 #{item.get('id')}"
    )


def render_drug_bubble(item: dict) -> dict:
    """Render one drug item as a read-only Flex bubble."""
    body: list[dict] = []

    generic = item.get("generic_name")
    brand = item.get("brand_name")
    title = _title(item)

    if generic:
        body.append(_row("成分", _short(generic, 96), value_weight="bold"))
    if brand and brand != generic:
        body.append(_row("藥名", _short(brand, 96), value_weight="bold"))
    if item.get("nhi_drug_code"):
        body.append(
            _row(
                "健保碼",
                _short(item["nhi_drug_code"], 32),
                value_color=PRIMARY,
                value_weight="bold",
            )
        )

    type_parts = [part for part in (item.get("table_type"), item.get("item_kind")) if part]
    if type_parts or item.get("category"):
        body.append(_separator())
        if type_parts:
            body.append(_row("類型", " / ".join(type_parts), value_color=PRIMARY))
        if item.get("category"):
            body.append(_row("分類", item["category"]))

    supplier = item.get("supplier")
    manufacturer = item.get("manufacturer")
    if supplier or manufacturer:
        body.append(_separator())
        if supplier:
            body.append(_row("供應商", _short(supplier, 72), value_color=MUTED))
        if manufacturer:
            body.append(_row("製造商", _short(manufacturer, 72), value_color=MUTED))

    related = item.get("related_diagnoses") or []
    if related:
        body.append(_separator())
        body.append(
            {
                "type": "text",
                "text": "相關診斷碼",
                "weight": "bold",
                "size": "sm",
                "color": SUCCESS,
                "margin": "sm",
            }
        )
        for dx in related[:5]:
            body.append(_diagnosis_row(dx))

    return {
        "type": "bubble",
        "size": "kilo",
        "header": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": PRIMARY,
            "paddingAll": "md",
            "contents": [
                {
                    "type": "text",
                    "text": _short(title, 40),
                    "weight": "bold",
                    "size": "lg",
                    "color": "#ffffff",
                    "wrap": True,
                },
                {
                    "type": "text",
                    "text": f"drug_items #{item.get('id')}" if item.get("id") else "drug_items",
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
            "contents": body or [_row("藥品", _short(title, 96))],
        },
    }


def render_drug_results(items: list[dict]) -> dict:
    """Render one or more drug items. One result returns a bubble; many return carousel."""
    bubbles = [render_drug_bubble(item) for item in items[:MAX_BUBBLES]]
    if len(bubbles) == 1:
        return bubbles[0]
    return {"type": "carousel", "contents": bubbles}
