"""
monthly_pdf.py – Professional Monthly Customer Statement PDF Generator
Uses ReportLab to produce a clean A4 ledger-style monthly statement.
All financial data comes from database functions – nothing is hardcoded.
"""
import os
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether
)
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ── Font registration ─────────────────────────────────────────────────────────
_FONT_NORMAL = 'Helvetica'
_FONT_BOLD   = 'Helvetica-Bold'
_CURRENCY    = 'Rs.'

try:
    _arial_path = 'C:/Windows/Fonts/arial.ttf'
    _arialb_path = 'C:/Windows/Fonts/arialbd.ttf'
    if os.path.exists(_arial_path):
        pdfmetrics.registerFont(TTFont('AppFont',      _arial_path))
        pdfmetrics.registerFont(TTFont('AppFont-Bold', _arialb_path))
        _FONT_NORMAL = 'AppFont'
        _FONT_BOLD   = 'AppFont-Bold'
        _CURRENCY    = '\u20b9'   # ₹
except Exception:
    pass   # Fall back to Helvetica + Rs.

# ── Colour palette ────────────────────────────────────────────────────────────
_BLACK      = colors.HexColor('#000000')
_DARK_GREY  = colors.HexColor('#1E293B')
_MID_GREY   = colors.HexColor('#64748B')
_LIGHT_GREY = colors.HexColor('#F1F5F9')
_STRIPE     = colors.HexColor('#F8FAFC')
_WHITE      = colors.white
_BORDER     = colors.HexColor('#CBD5E1')

PAGE_W, PAGE_H = A4
_MARGIN = 15 * mm


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ps(name, size=9, leading=None, align=0, bold=False, color=None, italic=False):
    """Create a ParagraphStyle."""
    font = _FONT_BOLD if bold else _FONT_NORMAL
    return ParagraphStyle(
        name,
        fontName=font,
        fontSize=size,
        leading=leading or (size + 4),
        alignment=align,
        textColor=color or _BLACK,
    )


def _fmt(amount):
    """Format amount as currency string."""
    return '{}\u00a0{:,.2f}'.format(_CURRENCY, float(amount))


def _qty(q):
    """Smart quantity display: integer if whole, else decimal."""
    f = float(q)
    if f == int(f):
        return str(int(f))
    return '{:g}'.format(f)


# ── Main PDF function ─────────────────────────────────────────────────────────

def generate_monthly_statement_pdf(data, shop_settings, output_dir):
    """
    Generate a monthly account statement PDF.

    Parameters
    ----------
    data          : dict returned by database.get_monthly_bill_data() or
                    database.get_monthly_bill_data_alltime()
    shop_settings : dict returned by database.get_shop_settings()
    output_dir    : directory to write the PDF

    Returns
    -------
    str : absolute path to the generated PDF file
    """
    os.makedirs(output_dir, exist_ok=True)

    customer     = data['customer']
    month_name   = data.get('month_name', 'All Time')
    year         = data.get('year')
    month_int    = data.get('month')
    transactions = data.get('transactions', [])
    is_alltime   = data.get('is_alltime', False)

    # Build output filename
    cust_slug  = customer['name'].replace(' ', '_')
    if is_alltime:
        period_slug = 'COMPLETE_STATEMENT'
    else:
        period_slug = '{}_{:04d}'.format(month_name.upper(), year)
    filename = 'STMT_{}_{}.pdf'.format(cust_slug, period_slug)
    filepath = os.path.join(output_dir, filename)

    usable_w = PAGE_W - 2 * _MARGIN

    doc = SimpleDocTemplate(
        filepath,
        pagesize=A4,
        leftMargin=_MARGIN, rightMargin=_MARGIN,
        topMargin=_MARGIN,  bottomMargin=_MARGIN + 4 * mm,
        title='Monthly Account Statement',
        author=shop_settings.get('shop_name', 'FRUITS SHOP'),
    )

    story = []

    # ── SHOP HEADER ───────────────────────────────────────────────────────────
    shop_name    = shop_settings.get('shop_name', 'FRUITS SHOP').upper()
    shop_address = shop_settings.get('shop_address', '').strip()
    shop_phone   = shop_settings.get('shop_phone', '').strip()
    shop_gst     = shop_settings.get('shop_gst', '').strip()

    story.append(Paragraph(
        shop_name,
        _ps('ShopTitle', size=22, leading=28, align=1, bold=True)
    ))

    sub_parts = []
    if shop_address:
        sub_parts.append(shop_address)
    if shop_phone:
        sub_parts.append('Tel: {}'.format(shop_phone))
    if shop_gst:
        sub_parts.append('GST: {}'.format(shop_gst))
    if sub_parts:
        story.append(Paragraph(
            '  |  '.join(sub_parts),
            _ps('ShopSub', size=8, align=1, color=_MID_GREY)
        ))

    story.append(Spacer(1, 3 * mm))
    story.append(HRFlowable(width='100%', thickness=2, color=_BLACK, spaceAfter=4))

    # Statement title
    if is_alltime:
        stmt_title = 'COMPLETE ACCOUNT STATEMENT'
    else:
        stmt_title = 'MONTHLY ACCOUNT STATEMENT  \u2013  {} {}'.format(
            month_name.upper(), year
        )
    story.append(Paragraph(
        stmt_title,
        _ps('StmtTitle', size=11, leading=16, align=1, bold=True)
    ))
    story.append(Spacer(1, 4 * mm))

    # Customer info band
    cname = customer.get('name', '')
    cphone = customer.get('phone') or '\u2013'
    caddr  = customer.get('address') or ''

    cust_rows = [[
        Paragraph('<b>Customer :</b> {}'.format(cname), _ps('CL', size=10)),
        Paragraph('<b>Phone :</b> {}'.format(cphone),   _ps('CR', size=10, align=2)),
    ]]
    if caddr:
        cust_rows.append([
            Paragraph('<b>Address :</b> {}'.format(caddr), _ps('CA', size=9, color=_MID_GREY)),
            Paragraph('', _ps('CRA', size=9)),
        ])
    cust_tbl = Table(cust_rows, colWidths=[usable_w * 0.65, usable_w * 0.35])
    cust_tbl.setStyle(TableStyle([
        ('VALIGN',       (0,0),(-1,-1),'MIDDLE'),
        ('TOPPADDING',   (0,0),(-1,-1), 3),
        ('BOTTOMPADDING',(0,0),(-1,-1), 3),
    ]))
    story.append(cust_tbl)
    story.append(Spacer(1, 3 * mm))
    story.append(HRFlowable(width='100%', thickness=0.75, color=_BORDER, spaceAfter=4))

    # ── TRANSACTION TABLE ─────────────────────────────────────────────────────
    col_sno  = 12 * mm
    col_date = 26 * mm
    col_prod = usable_w - col_sno - col_date - 22 * mm - 26 * mm
    col_qty  = 22 * mm
    col_amt  = 26 * mm
    col_ws   = [col_sno, col_date, col_prod, col_qty, col_amt]

    def _th(txt, align=1):
        return Paragraph(txt, _ps('TH_{}'.format(txt), size=9, bold=True,
                                  align=align, color=_WHITE))
    def _td(txt, align=0, bold=False):
        return Paragraph(str(txt), _ps('TD_{}'.format(txt[:6]),
                                       size=9, align=align, bold=bold))

    header = [
        _th('S.No', 1), _th('Date', 1), _th('Product Name', 0),
        _th('Qty', 1),  _th('Amount', 2),
    ]
    rows = [header]
    sno = 0

    for txn in transactions:
        sno += 1
        items = txn.get('items', [])
        n = len(items)
        for i, item in enumerate(items):
            first = (i == 0)
            last  = (i == n - 1)
            rows.append([
                _td(str(sno) if first else '', align=1),
                _td(txn['date_str'] if first else '', align=1),
                _td(item['product_name']),
                _td(_qty(item['quantity']), align=1),
                _td(_fmt(txn['bill_total']) if last else '', align=2, bold=last),
            ])

    if not transactions:
        rows.append([
            _td('\u2013', align=1),
            _td('No transactions found for this period', align=0),
            _td(''), _td(''), _td(''),
        ])

    tbl = Table(rows, colWidths=col_ws, repeatRows=1)
    n_rows = len(rows)
    stripe_colors = []
    for ri in range(1, n_rows):
        bg = _STRIPE if ri % 2 == 0 else _WHITE
        stripe_colors.append(('BACKGROUND', (0, ri), (-1, ri), bg))

    tbl.setStyle(TableStyle([
        # Header
        ('BACKGROUND',    (0, 0), (-1, 0), _DARK_GREY),
        ('FONTNAME',      (0, 0), (-1, 0), _FONT_BOLD),
        ('FONTSIZE',      (0, 0), (-1, 0), 9),
        ('TEXTCOLOR',     (0, 0), (-1, 0), _WHITE),
        ('ROWBACKGROUNDS',(0, 1), (-1,-1), [_WHITE, _STRIPE]),
        # Fonts and sizes for data
        ('FONTNAME',      (0, 1), (-1,-1), _FONT_NORMAL),
        ('FONTSIZE',      (0, 1), (-1,-1), 9),
        # Alignment columns
        ('ALIGN',         (0, 0), (0,-1), 'CENTER'),   # S.No
        ('ALIGN',         (1, 0), (1,-1), 'CENTER'),   # Date
        ('ALIGN',         (3, 0), (3,-1), 'CENTER'),   # Qty
        ('ALIGN',         (4, 0), (4,-1), 'RIGHT'),    # Amount
        # Padding
        ('TOPPADDING',    (0, 0), (-1,-1), 5),
        ('BOTTOMPADDING', (0, 0), (-1,-1), 5),
        ('LEFTPADDING',   (0, 0), (-1,-1), 4),
        ('RIGHTPADDING',  (0, 0), (-1,-1), 4),
        # Grid
        ('GRID',          (0, 0), (-1,-1), 0.4, _BORDER),
        ('LINEBELOW',     (0, 0), (-1, 0), 1.5, _BLACK),
        ('VALIGN',        (0, 0), (-1,-1), 'MIDDLE'),
    ] + stripe_colors))

    story.append(tbl)
    story.append(Spacer(1, 6 * mm))

    # ── SUMMARY SECTION ───────────────────────────────────────────────────────
    lbl_ps  = _ps('SumLbl', size=10, align=2)
    lbl_bps = _ps('SumLblB', size=10, align=2, bold=True)
    val_ps  = _ps('SumVal', size=10, align=2)
    val_bps = _ps('SumValB', size=10, align=2, bold=True)

    prev_pending    = data.get('previous_pending', 0.0)
    current_total   = data.get('current_total', 0.0)
    grand_total     = data.get('grand_total', 0.0)
    paid_this_month = data.get('payments_this_month', 0.0)
    amount_payable  = data.get('amount_payable', 0.0)

    def _srow(label, value, bold=False):
        lp = lbl_bps if bold else lbl_ps
        vp = val_bps if bold else val_ps
        return [Paragraph('', _ps('SP')),
                Paragraph(label, lp),
                Paragraph(value, vp)]

    sum_rows = [
        _srow('Current Month Total', _fmt(current_total)),
        _srow('Previous Pending',    _fmt(prev_pending)),
        _srow('Grand Total',         _fmt(grand_total), bold=True),
    ]
    if paid_this_month > 0:
        sum_rows.append(_srow('Paid This Month', _fmt(paid_this_month)))
    sum_rows.append(_srow('Amount Payable', _fmt(amount_payable), bold=True))

    sw = [usable_w * 0.30, usable_w * 0.44, usable_w * 0.26]
    sum_tbl = Table(sum_rows, colWidths=sw)

    grand_idx   = 2   # "Grand Total" row
    payable_idx = len(sum_rows) - 1

    sum_style = [
        ('FONTNAME',     (0,0),(-1,-1), _FONT_NORMAL),
        ('FONTSIZE',     (0,0),(-1,-1), 10),
        ('VALIGN',       (0,0),(-1,-1), 'MIDDLE'),
        ('TOPPADDING',   (0,0),(-1,-1), 4),
        ('BOTTOMPADDING',(0,0),(-1,-1), 4),
        # Grand Total separator lines
        ('LINEABOVE',    (1, grand_idx), (-1, grand_idx),   1.0, _BLACK),
        ('LINEBELOW',    (1, grand_idx), (-1, grand_idx),   1.0, _BLACK),
        ('FONTNAME',     (1, grand_idx), (-1, grand_idx),   _FONT_BOLD),
        # Amount Payable styling
        ('BACKGROUND',   (0, payable_idx), (-1, payable_idx), _LIGHT_GREY),
        ('FONTNAME',     (1, payable_idx), (-1, payable_idx), _FONT_BOLD),
        ('LINEABOVE',    (1, payable_idx), (-1, payable_idx), 0.75, _MID_GREY),
    ]
    sum_tbl.setStyle(TableStyle(sum_style))

    story.append(KeepTogether([sum_tbl]))
    story.append(Spacer(1, 8 * mm))

    # Footer
    story.append(HRFlowable(width='100%', thickness=0.4, color=_BORDER, spaceAfter=3))
    gen_time = datetime.now().strftime('%d %b %Y %I:%M %p')
    story.append(Paragraph(
        'This is a computer-generated account statement. Generated on: {}'.format(gen_time),
        _ps('Footer', size=8, align=1, color=_MID_GREY)
    ))

    doc.build(story)
    return filepath
