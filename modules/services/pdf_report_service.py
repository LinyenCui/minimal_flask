"""PDF 報表渲染（與 xlsx 同一份 DataFrame，數字保證一致）。

設計：A4 橫式請款單 — 深藍報頭 + 摘要卡 + 斑馬紋明細 + 司機統計/領款人簽名 + 頁碼。
字型：需要中文 TTF。解析順序：
  1. env PDF_FONT_PATH / PDF_FONT_BOLD_PATH
  2. repo assets/fonts/ 下的 .ttf（部署 Render 用，需自帶開源中文字型）
  3. macOS 系統字型（本機開發 fallback）
找不到會 raise，避免默默輸出豆腐字。
"""
import logging
import os
import re
from xml.sax.saxutils import escape as _xml_escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as _canvas
from reportlab.platypus import (
    BaseDocTemplate, Frame, KeepTogether, NextPageTemplate, PageTemplate,
    Paragraph, Spacer, Table, TableStyle,
)

logger = logging.getLogger(__name__)

# ── 色票（報頭深藍 + 橘色金額 accent，內文低飽和灰）──
INK = colors.HexColor('#1F3A52')
INK_LIGHT = colors.HexColor('#2E5471')
ACCENT = colors.HexColor('#F57C00')
ZEBRA = colors.HexColor('#F5F7FA')
GRID = colors.HexColor('#D9DEE4')
MUTED = colors.HexColor('#7A8794')
TEXT = colors.HexColor('#222A31')

FONT = 'CJK'
FONT_BOLD = 'CJK-Bold'

_FONT_READY = False

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))


def _resolve_fonts() -> tuple:
    """回 (regular_path, bold_path, subfont_index)。找不到 raise。"""
    env_r = os.environ.get('PDF_FONT_PATH')
    env_b = os.environ.get('PDF_FONT_BOLD_PATH')
    if env_r and os.path.exists(env_r):
        return env_r, (env_b if env_b and os.path.exists(env_b) else env_r), None

    fonts_dir = os.path.join(_ROOT, 'assets', 'fonts')
    if os.path.isdir(fonts_dir):
        ttfs = sorted(f for f in os.listdir(fonts_dir) if f.lower().endswith('.ttf'))
        reg = next((f for f in ttfs if 'bold' not in f.lower()), None)
        bold = next((f for f in ttfs if 'bold' in f.lower()), None)
        if reg:
            return (os.path.join(fonts_dir, reg),
                    os.path.join(fonts_dir, bold or reg), None)

    # macOS 本機 fallback（.ttc 用 subfontIndex 0）
    for reg, bold in (
        ('/System/Library/Fonts/STHeiti Light.ttc', '/System/Library/Fonts/STHeiti Medium.ttc'),
        ('/System/Library/Fonts/PingFang.ttc', '/System/Library/Fonts/PingFang.ttc'),
    ):
        if os.path.exists(reg):
            return reg, (bold if os.path.exists(bold) else reg), 0

    raise RuntimeError(
        "找不到中文字型：請放 TTF 到 assets/fonts/ 或設 PDF_FONT_PATH"
    )


def _ensure_fonts():
    global _FONT_READY
    if _FONT_READY:
        return
    reg, bold, idx = _resolve_fonts()
    kw = {} if idx is None else {'subfontIndex': idx}
    pdfmetrics.registerFont(TTFont(FONT, reg, **kw))
    pdfmetrics.registerFont(TTFont(FONT_BOLD, bold, **kw))
    logger.info(f"[PDF] fonts: {reg} / {bold}")
    _FONT_READY = True


class _NumberedCanvas(_canvas.Canvas):
    """兩段式頁碼：第 X 頁／共 N 頁。"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved = []

    def showPage(self):
        self._saved.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved)
        for state in self._saved:
            self.__dict__.update(state)
            self.setFont(FONT, 7.5)
            self.setFillColor(MUTED)
            w, _h = self._pagesize
            self.drawRightString(w - 12 * mm, 8 * mm, f"第 {self._pageNumber} 頁／共 {total} 頁")
            self.drawString(12 * mm, 8 * mm, "本表由派班系統自動產生")
            super().showPage()
        super().save()


def _fmt_money(v) -> str:
    try:
        return f"{int(round(float(v))):,}"
    except (TypeError, ValueError):
        return '—'


def _num(v):
    """→ float 或 None（NULL/NaN/非數字）。"""
    try:
        n = float(v)
    except (TypeError, ValueError):
        return None
    return None if n != n else n


def _fare_cells(meter, extra) -> tuple:
    """(錶價, 加成, 實收) 顯示字串 — 逐欄語意：
    錶價 0/NULL = 未記錄 →「—」；加成 0 = 常態 → 留白；
    實收：兩欄都沒記 →「—」，有記（含折抵成 0）→ 誠實顯示數字。"""
    m, e = _num(meter), _num(extra)
    m_s = _fmt_money(m) if m else '—'
    e_s = _fmt_money(e) if e else ''
    recorded = bool(m) or bool(e)
    a_s = _fmt_money((m or 0) + (e or 0)) if recorded else '—'
    return m_s, e_s, a_s


def _p_text(s) -> str:
    """給 Paragraph 用的文字：XML escape（& < > 會炸 reportlab）+ 換行轉 <br/>。"""
    if s is None:
        return ''
    return _xml_escape(str(s)).replace('\n', '<br/>')


def _fmt_id(v) -> str:
    """司機編號等 ID 顯示：pandas groupby 會把 int 變 float（5386.0）→ 轉回整數字串。
    None / NaN（欄內有 NULL 時整欄變 float64，NaN 是 truthy）→ 空字串。"""
    if v is None or v != v:
        return ''
    try:
        f = float(v)
        if f == int(f):
            return str(int(f))
    except (TypeError, ValueError, OverflowError):
        pass
    return str(v)


def _clean_note(s: str) -> str:
    """說明欄顯示層清理：去 [N] 前綴、None→空。不動原始資料。"""
    if not s:
        return ''
    s = re.sub(r'\[\d+\]\s*', '', str(s))
    s = s.replace('None→', '').replace('→None', '→空').replace('None', '')
    return s.strip()


def render_report_pdf(
    df, driver_stats, *,
    filename: str,
    title: str,
    start_date, end_date,
    category: str = None,
) -> str:
    """df/driver_stats（與 xlsx 同源）→ PDF 檔。回傳 filename。

    df 欄位：ID 日期 星期 起點 途經點 終點 司機編號 錶價 加成 實收 說明
    driver_stats 欄位：司機編號 班次數 金額

    版面：A4 直式（使用者要求可直接列印）。
    """
    _ensure_fonts()
    # legacy title 常帶「(YYYY/MM/DD - YYYY/MM/DD)」尾綴，報頭已另示期間 → 去重
    title = re.sub(r'\s*[（(].*[）)]\s*$', '', str(title)).strip() or str(title)
    page_w, page_h = A4
    M = 12 * mm

    doc = BaseDocTemplate(
        filename, pagesize=A4,
        leftMargin=M, rightMargin=M, topMargin=M, bottomMargin=14 * mm,
        title=title,
    )

    period = f"{start_date.strftime('%Y/%m/%d')} — {end_date.strftime('%Y/%m/%d')}"
    cat_text = category if category and category != '全部' else '全部類別'
    from modules.utils.taiwan_time import get_taiwan_time   # Render 是 UTC，要用台灣時間
    gen_time = get_taiwan_time().strftime('%Y-%m-%d %H:%M')

    def _header(cv, _doc):
        """每頁報頭：第一頁大帶、續頁細帶。"""
        cv.saveState()
        if cv.getPageNumber() == 1:
            h = 22 * mm
            cv.setFillColor(INK)
            cv.rect(0, page_h - h, page_w, h, stroke=0, fill=1)
            cv.setFillColor(colors.white)
            cv.setFont(FONT_BOLD, 17)
            cv.drawString(M, page_h - 11.2 * mm, title)
            cv.setFont(FONT, 9.5)
            cv.setFillColor(colors.HexColor('#C8D6E2'))
            cv.drawString(M, page_h - 17.5 * mm, f"期間 {period}　·　類別 {cat_text}　·　產表 {gen_time}")
            # 右上角圓形計程車標記
            cv.setFillColor(ACCENT)
            cv.circle(page_w - M - 6 * mm, page_h - h / 2, 5.2 * mm, stroke=0, fill=1)
            cv.setFillColor(colors.white)
            cv.setFont(FONT_BOLD, 10)
            cv.drawCentredString(page_w - M - 6 * mm, page_h - h / 2 - 3.4, "派班")
        else:
            h = 9 * mm
            cv.setFillColor(INK)
            cv.rect(0, page_h - h, page_w, h, stroke=0, fill=1)
            cv.setFillColor(colors.white)
            cv.setFont(FONT_BOLD, 9)
            cv.drawString(M, page_h - 6.2 * mm, f"{title}　{period}")
        cv.restoreState()

    frame_first = Frame(M, 14 * mm, page_w - 2 * M, page_h - 22 * mm - 16 * mm, id='f1')
    frame_later = Frame(M, 14 * mm, page_w - 2 * M, page_h - 9 * mm - 17 * mm, id='f2')
    doc.addPageTemplates([
        PageTemplate(id='first', frames=[frame_first], onPage=_header),
        PageTemplate(id='later', frames=[frame_later], onPage=_header),
    ])

    story = [NextPageTemplate('later'), Spacer(0, 2 * mm)]

    # ── 摘要卡 ──
    total_meter = df['錶價'].fillna(0).sum()
    total_extra = df['加成'].fillna(0).sum()
    total_actual = df['實收'].fillna(0).sum()
    n_trips = len(df)
    n_drivers = df['司機編號'].nunique()

    def _card(label, value, value_color=TEXT, big=False):
        return [
            Paragraph(label, ParagraphStyle('cl', fontName=FONT, fontSize=8, textColor=MUTED, alignment=1)),
            Paragraph(value, ParagraphStyle(
                'cv', fontName=FONT_BOLD, fontSize=17 if big else 13,
                textColor=value_color, alignment=1, leading=20 if big else 16, spaceBefore=2)),
        ]

    cards = Table(
        [[
            _card("合計金額", f"{_fmt_money(total_actual)} 元", ACCENT, big=True),
            _card("總筆數", f"{n_trips} 筆"),
            _card("錶價小計", f"{_fmt_money(total_meter)} 元"),
            _card("加成小計", f"{_fmt_money(total_extra):s} 元"),
            _card("出勤司機", f"{n_drivers} 位"),
        ]],
        colWidths=[(page_w - 2 * M) * w for w in (0.28, 0.18, 0.18, 0.18, 0.18)],
        style=TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.white),
            ('BOX', (0, 0), (0, 0), 0.8, ACCENT),
            ('BOX', (1, 0), (1, 0), 0.6, GRID),
            ('BOX', (2, 0), (2, 0), 0.6, GRID),
            ('BOX', (3, 0), (3, 0), 0.6, GRID),
            ('BOX', (4, 0), (4, 0), 0.6, GRID),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ]),
    )
    story += [cards, Spacer(0, 5 * mm)]

    # ── 明細表 ──
    cell = ParagraphStyle('cell', fontName=FONT, fontSize=7.3, textColor=TEXT, leading=9)
    cell_note = ParagraphStyle('note', parent=cell, fontSize=7, textColor=MUTED)

    # A4 直式：日期+星期併欄（06-22 一），10 欄塞進 186mm
    head = ['ID', '日期', '起點', '途經', '終點', '司機', '錶價', '加成', '實收', '說明']
    rows = [head]
    for i, (_, r) in enumerate(df.iterrows(), start=1):
        rows.append([
            str(r['ID']),
            f"{str(r['日期'])[5:]} {r['星期']}",   # MM-DD 週（年份報頭已示）
            Paragraph(_p_text(r['起點'] or ''), cell),
            Paragraph(_p_text(r['途經點'] or '') if str(r['途經點']) != 'None' else '', cell),
            Paragraph(_p_text(r['終點'] or ''), cell),
            _fmt_id(r['司機編號']),
            *_fare_cells(r['錶價'], r['加成']),
            Paragraph(_p_text(_clean_note(r['說明'])), cell_note),
        ])
    # 總計列
    rows.append(['', '', '', '', '總計', '',
                 _fmt_money(total_meter), _fmt_money(total_extra), _fmt_money(total_actual), ''])

    W = page_w - 2 * M
    col_w = [w * W for w in (0.052, 0.098, 0.163, 0.128, 0.163, 0.058, 0.072, 0.066, 0.078, 0.122)]

    tstyle = [
        ('FONTNAME', (0, 0), (-1, 0), FONT_BOLD),
        ('FONTNAME', (0, 1), (-1, -1), FONT),
        ('FONTSIZE', (0, 0), (-1, 0), 7.6),
        ('FONTSIZE', (0, 1), (-1, -1), 7.3),
        ('BACKGROUND', (0, 0), (-1, 0), INK_LIGHT),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (1, -1), 'CENTER'),
        ('ALIGN', (5, 0), (5, -1), 'CENTER'),
        ('ALIGN', (6, 0), (8, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TEXTCOLOR', (0, 1), (-1, -2), TEXT),
        ('GRID', (0, 0), (-1, -1), 0.4, GRID),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
        ('LEFTPADDING', (0, 0), (-1, -1), 2.5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        # 總計列
        ('FONTNAME', (0, -1), (-1, -1), FONT_BOLD),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#FFF3E0')),
        ('TEXTCOLOR', (6, -1), (8, -1), ACCENT),
        ('LINEABOVE', (0, -1), (-1, -1), 0.9, ACCENT),
    ]
    # 一律斑馬紋（曾對週六日鋪淡橘底,用戶回饋像印壞/變質 → 拿掉;星期欄已標 六/日）
    for i in range(1, len(rows) - 1):
        if i % 2 == 0:
            tstyle.append(('BACKGROUND', (0, i), (-1, i), ZEBRA))

    story.append(Table(rows, colWidths=col_w, style=TableStyle(tstyle), repeatRows=1))
    story.append(Spacer(0, 7 * mm))

    # ── 司機統計 + 領款人簽名 ──
    sec_title = Paragraph("司機統計與領款簽收", ParagraphStyle(
        'sec', fontName=FONT_BOLD, fontSize=11.5, textColor=INK, spaceAfter=4))
    drows = [['司機編號', '班次數', '金額', '領款人簽名']]
    for _, r in driver_stats.iterrows():
        drows.append([_fmt_id(r['司機編號']), f"{int(r['班次數'])} 班",
                      f"{_fmt_money(r['金額'])} 元", ''])
    # 合計列（簽收總額須與上方合計金額對帳）
    drows.append(['合計', f"{int(driver_stats['班次數'].sum())} 班",
                  f"{_fmt_money(driver_stats['金額'].sum())} 元", ''])
    dW = W * 0.72
    dtab = Table(
        drows,
        colWidths=[dW * w for w in (0.16, 0.14, 0.22, 0.48)],
        rowHeights=[8 * mm] + [11 * mm] * (len(drows) - 2) + [8 * mm],
        hAlign='LEFT',
        style=TableStyle([
            ('FONTNAME', (0, 0), (-1, 0), FONT_BOLD),
            ('FONTNAME', (0, 1), (-1, -1), FONT),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('FONTSIZE', (0, 1), (-1, -1), 9.5),
            ('BACKGROUND', (0, 0), (-1, 0), INK_LIGHT),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (1, -1), 'CENTER'),
            ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.4, GRID),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('RIGHTPADDING', (2, 0), (2, -1), 6),
            # 簽名欄底線感：淡色底
            ('BACKGROUND', (3, 1), (3, -2), colors.HexColor('#FBFCFD')),
            # 合計列
            ('FONTNAME', (0, -1), (-1, -1), FONT_BOLD),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#FFF3E0')),
            ('TEXTCOLOR', (2, -1), (2, -1), ACCENT),
            ('LINEABOVE', (0, -1), (-1, -1), 0.9, ACCENT),
        ]),
    )
    note = Paragraph("※ 請領款司機於簽名欄親簽；金額以「實收（錶價＋加成）」計。",
                     ParagraphStyle('n', fontName=FONT, fontSize=8, textColor=MUTED, spaceBefore=3))
    story.append(KeepTogether([sec_title, dtab, note]))

    doc.build(story, canvasmaker=_NumberedCanvas)
    logger.info(f"[PDF] rendered: {filename}")
    return filename


def render_monthly_stats_pdf(
    df, *,
    filename: str,
    start_date, end_date,
    category: str = None,
) -> str:
    """月度統計 PDF（對應 xlsx 的 月度總覽 + 司機績效 + 每日趨勢）。

    df 欄位：日期(datetime) 起點 終點 錶價 加成 實收 司機編號

    版面：A4 直式。重點段 = 每日統計表（使用者指定的核心內容，橘框強調）。
    """
    _ensure_fonts()
    page_w, page_h = A4
    M = 12 * mm

    if category == '東洋':
        title = '東洋班次月度統計報表'
    elif category == '診所':
        title = '診所班次月度統計報表'
    else:
        title = '班次月度統計報表'

    doc = BaseDocTemplate(
        filename, pagesize=A4,
        leftMargin=M, rightMargin=M, topMargin=M, bottomMargin=14 * mm, title=title,
    )
    period = f"{start_date.strftime('%Y/%m/%d')} — {end_date.strftime('%Y/%m/%d')}"
    cat_text = category if category and category != '全部' else '全部類別'
    from modules.utils.taiwan_time import get_taiwan_time
    gen_time = get_taiwan_time().strftime('%Y-%m-%d %H:%M')

    def _header(cv, _doc):
        cv.saveState()
        if cv.getPageNumber() == 1:
            h = 22 * mm
            cv.setFillColor(INK)
            cv.rect(0, page_h - h, page_w, h, stroke=0, fill=1)
            cv.setFillColor(colors.white)
            cv.setFont(FONT_BOLD, 17)
            cv.drawString(M, page_h - 11.2 * mm, title)
            cv.setFont(FONT, 9.5)
            cv.setFillColor(colors.HexColor('#C8D6E2'))
            cv.drawString(M, page_h - 17.5 * mm, f"期間 {period}　·　類別 {cat_text}　·　產表 {gen_time}")
            cv.setFillColor(ACCENT)
            cv.circle(page_w - M - 6 * mm, page_h - h / 2, 5.2 * mm, stroke=0, fill=1)
            cv.setFillColor(colors.white)
            cv.setFont(FONT_BOLD, 10)
            cv.drawCentredString(page_w - M - 6 * mm, page_h - h / 2 - 3.4, "派班")
        else:
            h = 9 * mm
            cv.setFillColor(INK)
            cv.rect(0, page_h - h, page_w, h, stroke=0, fill=1)
            cv.setFillColor(colors.white)
            cv.setFont(FONT_BOLD, 9)
            cv.drawString(M, page_h - 6.2 * mm, f"{title}　{period}")
        cv.restoreState()

    doc.addPageTemplates([
        PageTemplate(id='first', frames=[Frame(M, 14 * mm, page_w - 2 * M, page_h - 38 * mm, id='f1')], onPage=_header),
        PageTemplate(id='later', frames=[Frame(M, 14 * mm, page_w - 2 * M, page_h - 26 * mm, id='f2')], onPage=_header),
    ])
    story = [NextPageTemplate('later'), Spacer(0, 2 * mm)]
    W = page_w - 2 * M

    # ── 統計 ──
    total_trips = len(df)
    total_rev = df['實收'].fillna(0).sum()
    days = max((end_date - start_date).days, 1)
    n_drivers = df['司機編號'].nunique()
    daily = df.groupby(df['日期'].dt.date).agg({'實收': ['count', 'sum']})
    daily.columns = ['班次數', '總金額']
    daily = daily.reset_index().rename(columns={'日期': 'date'})
    drivers = df.groupby('司機編號').agg({'實收': ['count', 'sum', 'mean']}).round(0)
    drivers.columns = ['班次數', '總金額', '平均車資']
    drivers = drivers.reset_index().sort_values('總金額', ascending=False)

    def _card(label, value, value_color=TEXT, big=False):
        return [
            Paragraph(label, ParagraphStyle('cl', fontName=FONT, fontSize=8, textColor=MUTED, alignment=1)),
            Paragraph(value, ParagraphStyle(
                'cv', fontName=FONT_BOLD, fontSize=17 if big else 13,
                textColor=value_color, alignment=1, leading=20 if big else 16, spaceBefore=2)),
        ]

    cards = Table(
        [[
            _card("總車資", f"{_fmt_money(total_rev)} 元", ACCENT, big=True),
            _card("總班次", f"{total_trips} 趟"),
            _card("平均車資", f"{_fmt_money(df['實收'].fillna(0).mean())} 元"),
            _card("日均班次", f"{total_trips / days:.1f} 趟"),
            _card("參與司機", f"{n_drivers} 位"),
        ]],
        colWidths=[W * w for w in (0.28, 0.18, 0.18, 0.18, 0.18)],
        style=TableStyle([
            ('BOX', (0, 0), (0, 0), 0.8, ACCENT),
            ('BOX', (1, 0), (1, 0), 0.6, GRID),
            ('BOX', (2, 0), (2, 0), 0.6, GRID),
            ('BOX', (3, 0), (3, 0), 0.6, GRID),
            ('BOX', (4, 0), (4, 0), 0.6, GRID),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 5), ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]),
    )
    story += [cards, Spacer(0, 6 * mm)]

    # ── 每日統計（重點段：使用者指定的核心內容，橘框強調）──
    wk = ['一', '二', '三', '四', '五', '六', '日']
    dsec0 = Paragraph("每日統計", ParagraphStyle(
        'sec0', fontName=FONT_BOLD, fontSize=11.5, textColor=ACCENT, spaceAfter=4))
    drows0 = [['日期', '班次數', '總金額']]
    for _, r in daily.iterrows():
        d = r['date']
        drows0.append([f"{d.strftime('%m/%d')}（{wk[d.weekday()]}）",
                       f"{int(r['班次數'])}", f"{_fmt_money(r['總金額'])}"])
    drows0.append(['總計', f"{int(daily['班次數'].sum())}",
                   f"{_fmt_money(daily['總金額'].sum())}"])
    dstyle0 = [
        ('FONTNAME', (0, 0), (-1, 0), FONT_BOLD), ('FONTNAME', (0, 1), (-1, -2), FONT),
        ('FONTNAME', (0, -1), (-1, -1), FONT_BOLD),
        ('FONTSIZE', (0, 0), (-1, -1), 8.6),
        ('BACKGROUND', (0, 0), (-1, 0), ACCENT), ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (0, -1), 'CENTER'), ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.4, GRID),
        ('BOX', (0, 0), (-1, -1), 1.2, ACCENT),   # 橘框 = 把重點「圈」起來
        ('TOPPADDING', (0, 0), (-1, -1), 2.6), ('BOTTOMPADDING', (0, 0), (-1, -1), 2.6),
        ('RIGHTPADDING', (1, 0), (-1, -1), 8),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#FFF3E0')),
        ('TEXTCOLOR', (2, -1), (2, -1), ACCENT),
        ('LINEABOVE', (0, -1), (-1, -1), 0.9, ACCENT),
    ]
    for i in range(1, len(drows0) - 1):
        if i % 2 == 0:
            dstyle0.append(('BACKGROUND', (0, i), (-1, i), ZEBRA))
    dtab0 = Table(drows0, colWidths=[W * 0.52 * w for w in (0.42, 0.24, 0.34)],
                  hAlign='LEFT', style=TableStyle(dstyle0), repeatRows=1)
    story += [dsec0, dtab0, Spacer(0, 6 * mm)]

    # ── 每日車資長條圖 ──
    from reportlab.graphics.shapes import Drawing
    from reportlab.graphics.charts.barcharts import VerticalBarChart
    chart_h = 52 * mm
    dr = Drawing(W, chart_h)
    bc = VerticalBarChart()
    bc.x, bc.y = 14, 16
    bc.width, bc.height = W - 30, chart_h - 26
    bc.data = [list(daily['總金額'])]
    bc.categoryAxis.categoryNames = [d.strftime('%m/%d') for d in daily['date']]
    bc.bars[0].fillColor = ACCENT
    bc.bars[0].strokeColor = None
    bc.valueAxis.valueMin = 0
    bc.valueAxis.labels.fontName = FONT
    bc.valueAxis.labels.fontSize = 6.5
    bc.valueAxis.strokeColor = GRID
    bc.categoryAxis.labels.fontName = FONT
    bc.categoryAxis.labels.fontSize = 6 if len(daily) > 20 else 7
    bc.categoryAxis.labels.angle = 45 if len(daily) > 14 else 0
    bc.categoryAxis.labels.dy = -8 if len(daily) > 14 else -4
    bc.categoryAxis.strokeColor = GRID
    dr.add(bc)
    chart_title = Paragraph("每日車資趨勢", ParagraphStyle(
        'ct', fontName=FONT_BOLD, fontSize=11.5, textColor=INK, spaceAfter=2))
    story += [KeepTogether([chart_title, dr]), Spacer(0, 5 * mm)]

    # ── 司機績效表 ──
    dsec = Paragraph("司機績效統計", ParagraphStyle(
        'sec2', fontName=FONT_BOLD, fontSize=11.5, textColor=INK, spaceAfter=4))
    drows = [['司機編號', '班次數', '總金額', '平均車資', '佔比']]
    for _, r in drivers.iterrows():
        pct = (r['總金額'] / total_rev * 100) if total_rev else 0
        drows.append([_fmt_id(r['司機編號']), f"{int(r['班次數'])} 趟",
                      f"{_fmt_money(r['總金額'])} 元", f"{_fmt_money(r['平均車資'])} 元",
                      f"{pct:.1f}%"])
    drows.append(['合計', f"{total_trips} 趟", f"{_fmt_money(total_rev)} 元", '', ''])
    dstyle = [
        ('FONTNAME', (0, 0), (-1, 0), FONT_BOLD), ('FONTNAME', (0, 1), (-1, -2), FONT),
        ('FONTNAME', (0, -1), (-1, -1), FONT_BOLD),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BACKGROUND', (0, 0), (-1, 0), INK_LIGHT), ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (0, -1), 'CENTER'), ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.4, GRID),
        ('TOPPADDING', (0, 0), (-1, -1), 3.5), ('BOTTOMPADDING', (0, 0), (-1, -1), 3.5),
        ('RIGHTPADDING', (1, 0), (-1, -1), 6),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#FFF3E0')),
        ('TEXTCOLOR', (2, -1), (2, -1), ACCENT),
        ('LINEABOVE', (0, -1), (-1, -1), 0.9, ACCENT),
    ]
    for i in range(1, len(drows) - 1):
        if i % 2 == 0:
            dstyle.append(('BACKGROUND', (0, i), (-1, i), ZEBRA))
    dtab = Table(drows, colWidths=[W * 0.55 * w for w in (0.22, 0.18, 0.24, 0.22, 0.14)],
                 hAlign='LEFT', style=TableStyle(dstyle), repeatRows=1)
    story.append(KeepTogether([dsec, dtab]))

    doc.build(story, canvasmaker=_NumberedCanvas)
    logger.info(f"[PDF] rendered monthly: {filename}")
    return filename
