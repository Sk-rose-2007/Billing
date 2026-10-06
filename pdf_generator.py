import os
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# Attempt to register Arial for Indian Rupee symbol support; fallback gracefully
FONT_NAME = 'Helvetica'
BOLD_FONT = 'Helvetica-Bold'
CURRENCY_PREFIX = 'Rs. '

try:
    if os.path.exists('C:/Windows/Fonts/arial.ttf'):
        pdfmetrics.registerFont(TTFont('AppFont', 'C:/Windows/Fonts/arial.ttf'))
        if os.path.exists('C:/Windows/Fonts/arialbd.ttf'):
            pdfmetrics.registerFont(TTFont('AppFont-Bold', 'C:/Windows/Fonts/arialbd.ttf'))
            BOLD_FONT = 'AppFont-Bold'
        else:
            BOLD_FONT = 'AppFont'
        FONT_NAME = 'AppFont'
        CURRENCY_PREFIX = '₹'
except Exception:
    pass

def generate_pdf_invoice(bill, items, output_dir=None):
    """
    Generate a clean, professional, printable PDF invoice using ReportLab.
    
    Args:
        bill: sqlite3.Row or dict containing bill fields
        items: list of sqlite3.Row or dict containing bill item fields
        output_dir: directory path where PDF is saved
    Returns:
        str: Absolute path to the generated PDF file
    """
    if output_dir is None:
        output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'invoices')
    os.makedirs(output_dir, exist_ok=True)

    filename = f"{bill['bill_number']}.pdf"
    filepath = os.path.join(output_dir, filename)

    doc = SimpleDocTemplate(
        filepath,
        pagesize=A4,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    story = []
    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        'StoreTitle',
        parent=styles['Normal'],
        fontName=BOLD_FONT,
        fontSize=22,
        leading=26,
        textColor=colors.HexColor('#0F172A'),
        alignment=1 # Center
    )
    subtitle_style = ParagraphStyle(
        'StoreSubtitle',
        parent=styles['Normal'],
        fontName=FONT_NAME,
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#475569'),
        alignment=1 # Center
    )
    meta_label = ParagraphStyle(
        'MetaLabel',
        parent=styles['Normal'],
        fontName=BOLD_FONT,
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#334155')
    )
    meta_val = ParagraphStyle(
        'MetaValue',
        parent=styles['Normal'],
        fontName=FONT_NAME,
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#0F172A')
    )
    th_style = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontName=BOLD_FONT,
        fontSize=9,
        leading=11,
        textColor=colors.white,
        alignment=0
    )
    th_style_r = ParagraphStyle(
        'TableHeaderR',
        parent=styles['Normal'],
        fontName=BOLD_FONT,
        fontSize=9,
        leading=11,
        textColor=colors.white,
        alignment=2 # Right
    )
    td_style = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName=FONT_NAME,
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#1E293B')
    )
    td_style_r = ParagraphStyle(
        'TableCellR',
        parent=styles['Normal'],
        fontName=FONT_NAME,
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#1E293B'),
        alignment=2 # Right
    )
    total_label_style = ParagraphStyle(
        'TotalLabel',
        parent=styles['Normal'],
        fontName=BOLD_FONT,
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#1E293B'),
        alignment=2
    )
    total_val_style = ParagraphStyle(
        'TotalVal',
        parent=styles['Normal'],
        fontName=FONT_NAME,
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#0F172A'),
        alignment=2
    )
    grand_label_style = ParagraphStyle(
        'GrandLabel',
        parent=styles['Normal'],
        fontName=BOLD_FONT,
        fontSize=12,
        leading=16,
        textColor=colors.HexColor('#0F172A'),
        alignment=2
    )
    grand_val_style = ParagraphStyle(
        'GrandVal',
        parent=styles['Normal'],
        fontName=BOLD_FONT,
        fontSize=12,
        leading=16,
        textColor=colors.HexColor('#1E40AF'),
        alignment=2
    )
    footer_style = ParagraphStyle(
        'FooterText',
        parent=styles['Normal'],
        fontName=FONT_NAME,
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#64748B'),
        alignment=1 # Center
    )

    # 1. Header Section
    story.append(Paragraph("DEPARTMENT STORE", title_style))
    story.append(Spacer(1, 4))
    story.append(Paragraph("123 Main Market Street, Central Bazaar | Contact: +91 98765 43210", subtitle_style))
    story.append(Paragraph("Retail Invoice / Cash Bill", subtitle_style))
    story.append(Spacer(1, 12))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#0F172A'), spaceBefore=2, spaceAfter=12))

    # 2. Bill & Customer Metadata
    c_type_display = "Account Customer" if bill['customer_type'] == 'existing' else "Walk-in Customer"
    meta_data = [
        [
            Paragraph("<b>Bill No:</b>", meta_label),
            Paragraph(f"<b>{bill['bill_number']}</b>", meta_val),
            Paragraph("<b>Customer Name:</b>", meta_label),
            Paragraph(str(bill['customer_name']), meta_val)
        ],
        [
            Paragraph("<b>Date:</b>", meta_label),
            Paragraph(str(bill['bill_date']), meta_val),
            Paragraph("<b>Phone:</b>", meta_label),
            Paragraph(str(bill['customer_phone'] or 'N/A'), meta_val)
        ],
        [
            Paragraph("<b>Payment Status:</b>", meta_label),
            Paragraph("Paid in Full" if bill['balance'] <= 0 else "Balance Due", meta_val),
            Paragraph("<b>Customer Type:</b>", meta_label),
            Paragraph(c_type_display, meta_val)
        ]
    ]

    meta_table = Table(meta_data, colWidths=[80, 175, 95, 175])
    meta_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 2),
        ('RIGHTPADDING', (0,0), (-1,-1), 2),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 14))

    # 3. Items Table
    item_rows = [
        [
            Paragraph("#", th_style),
            Paragraph("Product Description", th_style),
            Paragraph("Quantity", th_style_r),
            Paragraph("Unit Price", th_style_r),
            Paragraph("Total", th_style_r)
        ]
    ]

    for idx, it in enumerate(items, 1):
        item_rows.append([
            Paragraph(str(idx), td_style),
            Paragraph(str(it['product_name']), td_style),
            Paragraph(f"{it['quantity']:g}", td_style_r),
            Paragraph(f"{CURRENCY_PREFIX}{it['price']:.2f}", td_style_r),
            Paragraph(f"{CURRENCY_PREFIX}{it['total']:.2f}", td_style_r)
        ])

    items_table = Table(item_rows, colWidths=[25, 230, 80, 95, 95])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E293B')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#FFFFFF'), colors.HexColor('#F8FAFC')]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
    ]))
    story.append(items_table)
    story.append(Spacer(1, 10))

    # 4. Summary Table (Subtotal, Discount, Grand Total, Paid, Balance)
    summary_data = [
        [Paragraph("Subtotal:", total_label_style), Paragraph(f"{CURRENCY_PREFIX}{bill['subtotal']:.2f}", total_val_style)],
        [Paragraph("Discount:", total_label_style), Paragraph(f"- {CURRENCY_PREFIX}{bill['discount']:.2f}", total_val_style)],
        [Paragraph("Grand Total:", grand_label_style), Paragraph(f"{CURRENCY_PREFIX}{bill['grand_total']:.2f}", grand_val_style)],
        [Paragraph("Paid Amount:", total_label_style), Paragraph(f"{CURRENCY_PREFIX}{bill['paid_amount']:.2f}", total_val_style)],
        [Paragraph("Balance Remaining:", total_label_style), Paragraph(f"{CURRENCY_PREFIX}{bill['balance']:.2f}", total_val_style)]
    ]

    summary_table = Table(summary_data, colWidths=[385, 140])
    summary_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LINEBELOW', (0, 2), (-1, 2), 1, colors.HexColor('#1E293B')),
        ('LINEABOVE', (0, 2), (-1, 2), 1, colors.HexColor('#1E293B')),
    ]))
    story.append(summary_table)

    story.append(Spacer(1, 25))
    story.append(HRFlowable(width="100%", thickness=0.75, color=colors.HexColor('#94A3B8'), spaceBefore=5, spaceAfter=10))

    # 5. Footer & Terms
    story.append(Paragraph("<b>Thank You For Shopping With Us!</b>", ParagraphStyle('Thanks', parent=footer_style, fontName=BOLD_FONT, fontSize=11, textColor=colors.HexColor('#0F172A'))))
    story.append(Spacer(1, 4))
    story.append(Paragraph("Goods once sold can be exchanged within 7 days with this bill.", footer_style))
    story.append(Paragraph("This is a computer-generated invoice. No signature required.", footer_style))

    doc.build(story)
    return filepath
