import os
from datetime import datetime, timedelta
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from utils.logging_config import logger

class QuotationGenerator:
    """
    Produces publication-grade, professional PDF construction quotations and BOQ schedules.
    """

    @staticmethod
    def generate_pdf(
        project_id: str,
        client_name: str,
        project_name: str,
        builtup_area_sqft: float,
        cost_data: dict,
        output_path: str = None
    ) -> str:
        if not output_path:
            os.makedirs("generated_reports", exist_ok=True)
            output_path = f"generated_reports/Quotation_{project_id}.pdf"

        doc = SimpleDocTemplate(
            output_path,
            pagesize=letter,
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=36
        )

        styles = getSampleStyleSheet()
        
        # Custom palette: Deep Navy, Construction Orange, Charcoal, Clean White
        PRIMARY_NAVY = colors.HexColor("#0f172a")
        ACCENT_ORANGE = colors.HexColor("#ea580c")
        BORDER_GREY = colors.HexColor("#cbd5e1")
        BG_ROW = colors.HexColor("#f8fafc")

        title_style = ParagraphStyle(
            'DocTitle',
            parent=styles['Heading1'],
            fontName='Helvetica-Bold',
            fontSize=22,
            textColor=PRIMARY_NAVY,
            spaceAfter=4
        )
        subtitle_style = ParagraphStyle(
            'DocSubtitle',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=10,
            textColor=colors.HexColor("#64748b"),
            spaceAfter=15
        )
        section_style = ParagraphStyle(
            'SectionHeader',
            parent=styles['Heading2'],
            fontName='Helvetica-Bold',
            fontSize=13,
            textColor=PRIMARY_NAVY,
            spaceBefore=12,
            spaceAfter=6
        )
        normal_style = ParagraphStyle(
            'RegularText',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#334155")
        )
        bold_style = ParagraphStyle(
            'RegularBold',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#0f172a")
        )

        elements = []

        # Header Title
        elements.append(Paragraph("BUILDSMARTAI ESTIMATION & QUOTATION", title_style))
        elements.append(Paragraph("Intelligent Residential Construction Management & Cost Engineering", subtitle_style))

        # Project & Client Meta Table
        today_str = datetime.now().strftime("%d %b %Y")
        valid_until_str = (datetime.now() + timedelta(days=30)).strftime("%d %b %Y")

        meta_data = [
            [Paragraph("<b>Project ID:</b>", normal_style), Paragraph(project_id, bold_style),
             Paragraph("<b>Date of Issue:</b>", normal_style), Paragraph(today_str, normal_style)],
            [Paragraph("<b>Project Name:</b>", normal_style), Paragraph(project_name, bold_style),
             Paragraph("<b>Valid Until:</b>", normal_style), Paragraph(valid_until_str, normal_style)],
            [Paragraph("<b>Client Name:</b>", normal_style), Paragraph(client_name, bold_style),
             Paragraph("<b>Built-up Area:</b>", normal_style), Paragraph(f"{builtup_area_sqft:,.1f} sq ft", bold_style)],
            [Paragraph("<b>Status:</b>", normal_style), Paragraph("<font color='#ea580c'><b>Awaiting Client Approval</b></font>", bold_style),
             Paragraph("<b>Currency:</b>", normal_style), Paragraph("INR (₹)", bold_style)]
        ]
        meta_table = Table(meta_data, colWidths=[90, 180, 90, 180])
        meta_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), BG_ROW),
            ('BOX', (0,0), (-1,-1), 1, BORDER_GREY),
            ('INNERGRID', (0,0), (-1,-1), 0.5, BORDER_GREY),
            ('TOPPADDING', (0,0), (-1,-1), 5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ]))
        elements.append(meta_table)
        elements.append(Spacer(1, 15))

        # Itemized Bill of Quantities (BOQ) Table
        elements.append(Paragraph("1. Material Bill of Quantities (BOQ)", section_style))

        boq_items = cost_data.get("itemized_boq", [])
        table_rows = [
            [
                Paragraph("<b>#</b>", bold_style),
                Paragraph("<b>Item Description</b>", bold_style),
                Paragraph("<b>Qty</b>", bold_style),
                Paragraph("<b>Unit</b>", bold_style),
                Paragraph("<b>Rate (₹)</b>", bold_style),
                Paragraph("<b>Total Amount (₹)</b>", bold_style)
            ]
        ]

        for idx, it in enumerate(boq_items, start=1):
            table_rows.append([
                Paragraph(str(idx), normal_style),
                Paragraph(it.get("name", ""), normal_style),
                Paragraph(f"{it.get('quantity', 0):,}", normal_style),
                Paragraph(it.get("unit", ""), normal_style),
                Paragraph(f"₹{it.get('unit_rate', 0):,.2f}", normal_style),
                Paragraph(f"₹{it.get('total_amount', 0):,.2f}", bold_style),
            ])

        boq_table = Table(table_rows, colWidths=[24, 230, 50, 45, 80, 111])
        boq_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#e2e8f0")),
            ('BOX', (0,0), (-1,-1), 1, BORDER_GREY),
            ('INNERGRID', (0,0), (-1,-1), 0.5, BORDER_GREY),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ]))
        elements.append(boq_table)
        elements.append(Spacer(1, 15))

        # Comprehensive Cost Summary Table
        elements.append(Paragraph("2. Financial Summary & Grand Total", section_style))
        cb = cost_data.get("cost_breakdown", {})
        
        summary_rows = [
            [Paragraph("Material Subtotal", normal_style), Paragraph(f"₹{cb.get('material_cost', 0):,.2f}", normal_style)],
            [Paragraph("Direct Civil Labour (Turnkey RCC & Masonry)", normal_style), Paragraph(f"₹{cb.get('labour_cost', 0):,.2f}", normal_style)],
            [Paragraph("Finishing & Fixtures Installation Labour", normal_style), Paragraph(f"₹{cb.get('finishing_labour_cost', 0):,.2f}", normal_style)],
            [Paragraph("Machinery, Scaffolding & Equipment Rentals", normal_style), Paragraph(f"₹{cb.get('equipment_cost', 0):,.2f}", normal_style)],
            [Paragraph("Logistics, Transportation & Unloading", normal_style), Paragraph(f"₹{cb.get('transport_cost', 0):,.2f}", normal_style)],
            [Paragraph("<b>Subtotal (Net Construction Cost)</b>", bold_style), Paragraph(f"<b>₹{cb.get('subtotal', 0):,.2f}</b>", bold_style)],
            [Paragraph("Contingency & Escalation Buffer (5.0%)", normal_style), Paragraph(f"₹{cb.get('contingency', 0):,.2f}", normal_style)],
            [Paragraph("Goods & Services Tax (GST 12.0%)", normal_style), Paragraph(f"₹{cb.get('taxes', 0):,.2f}", normal_style)],
            [Paragraph("<b>GRAND ESTIMATED TOTAL</b>", ParagraphStyle('GT', parent=bold_style, fontSize=11, textColor=ACCENT_ORANGE)),
             Paragraph(f"<b>₹{cb.get('grand_total', 0):,.2f}</b>", ParagraphStyle('GTV', parent=bold_style, fontSize=11, textColor=ACCENT_ORANGE))]
        ]

        summary_table = Table(summary_rows, colWidths=[360, 180])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), BG_ROW),
            ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor("#ffedd5")), # Light orange highlight for grand total
            ('BOX', (0,0), (-1,-1), 1, BORDER_GREY),
            ('INNERGRID', (0,0), (-1,-1), 0.5, BORDER_GREY),
            ('TOPPADDING', (0,0), (-1,-1), 5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ]))
        elements.append(summary_table)
        elements.append(Spacer(1, 15))

        # Regulatory & Professional Approvals Footer
        elements.append(Paragraph("3. Engineering Terms & Approvals", section_style))
        terms_text = (
            "• This quotation is generated based on standard architectural dimensions and regional price indexes.<br/>"
            "• Actual construction costs may vary based on site soil conditions, plumbing/finishing brand selections, and foundation depth.<br/>"
            "• Material procurement and contract award will commence strictly upon mutual written authorization."
        )
        elements.append(Paragraph(terms_text, normal_style))
        elements.append(Spacer(1, 20))

        sign_data = [
            [Paragraph("<b>Prepared By:</b> BuildSmartAI Quantity Engine", normal_style),
             Paragraph("<b>Client / Architect Approval:</b>", normal_style)],
            [Paragraph("Date: " + today_str, normal_style),
             Paragraph("Signature: _______________________ (Date: _________)", normal_style)]
        ]
        sign_table = Table(sign_data, colWidths=[270, 270])
        sign_table.setStyle(TableStyle([
            ('TOPPADDING', (0,0), (-1,-1), 8),
            ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ]))
        elements.append(sign_table)

        # Build document
        doc.build(elements)
        logger.info(f"Generated quotation PDF: {output_path}")
        return output_path
