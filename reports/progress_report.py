import os
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from utils.logging_config import logger

class ProgressReportGenerator:
    """
    Generates structured PDF Daily Site Intelligence & Progress Monitoring Reports.
    """

    @staticmethod
    def generate_pdf(
        project_id: str,
        project_name: str,
        vision_data: dict,
        progress_data: dict,
        output_path: str = None
    ) -> str:
        if not output_path:
            os.makedirs("generated_reports", exist_ok=True)
            output_path = f"generated_reports/SiteReport_{project_id}.pdf"

        doc = SimpleDocTemplate(
            output_path,
            pagesize=letter,
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=36
        )

        styles = getSampleStyleSheet()
        PRIMARY_NAVY = colors.HexColor("#0f172a")
        ACCENT_ORANGE = colors.HexColor("#ea580c")
        BORDER_GREY = colors.HexColor("#cbd5e1")
        BG_ROW = colors.HexColor("#f8fafc")

        title_style = ParagraphStyle('RepTitle', parent=styles['Heading1'], fontSize=20, fontName='Helvetica-Bold', textColor=PRIMARY_NAVY, spaceAfter=4)
        subtitle_style = ParagraphStyle('RepSub', parent=styles['Normal'], fontSize=9.5, fontName='Helvetica', textColor=colors.HexColor("#64748b"), spaceAfter=14)
        sec_style = ParagraphStyle('RepSec', parent=styles['Heading2'], fontSize=12, fontName='Helvetica-Bold', textColor=PRIMARY_NAVY, spaceBefore=10, spaceAfter=5)
        normal = ParagraphStyle('RepNorm', parent=styles['Normal'], fontSize=8.5, leading=11, textColor=colors.HexColor("#334155"))
        bold = ParagraphStyle('RepBold', parent=styles['Normal'], fontSize=8.5, leading=11, fontName='Helvetica-Bold', textColor=PRIMARY_NAVY)

        elements = []

        elements.append(Paragraph("BUILDSMARTAI SITE INTELLIGENCE REPORT", title_style))
        elements.append(Paragraph("Automated Computer Vision Site Monitoring & Delay Analysis", subtitle_style))

        # Meta Table
        today_str = datetime.now().strftime("%d %b %Y, %H:%M")
        meta_data = [
            [Paragraph("<b>Project ID:</b>", normal), Paragraph(project_id, bold),
             Paragraph("<b>Report Generated:</b>", normal), Paragraph(today_str, normal)],
            [Paragraph("<b>Project Name:</b>", normal), Paragraph(project_name, bold),
             Paragraph("<b>Observed Stage:</b>", normal), Paragraph(f"<b>{progress_data.get('visually_observed_stage', 'Structural')}</b>", bold)],
            [Paragraph("<b>Schedule Status:</b>", normal), Paragraph(f"<font color='#0284c7'><b>{progress_data.get('schedule_health', 'ON_TRACK')}</b></font>", bold),
             Paragraph("<b>Workers Detected:</b>", normal), Paragraph(f"{vision_data.get('total_workers_detected', 0)} active", bold)],
            [Paragraph("<b>PPE Compliance:</b>", normal), Paragraph(f"{vision_data.get('ppe_compliance_rate_pct', 90)}%", bold),
             Paragraph("<b>Predicted Delay:</b>", normal), Paragraph(f"{progress_data.get('predicted_critical_path_delay_days', 0)} days", bold)]
        ]
        meta_t = Table(meta_data, colWidths=[95, 175, 95, 175])
        meta_t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), BG_ROW),
            ('BOX', (0,0), (-1,-1), 1, BORDER_GREY),
            ('INNERGRID', (0,0), (-1,-1), 0.5, BORDER_GREY),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ]))
        elements.append(meta_t)
        elements.append(Spacer(1, 12))

        # Safety Alerts Section
        elements.append(Paragraph("1. Site Safety & PPE Observations", sec_style))
        alerts = vision_data.get("safety_alerts", [])
        if not alerts:
            elements.append(Paragraph("No critical safety violations observed during latest image inspection.", normal))
        else:
            alert_rows = [[Paragraph("<b>Severity</b>", bold), Paragraph("<b>Alert Type</b>", bold), Paragraph("<b>Observation Details</b>", bold)]]
            for a in alerts:
                sev_color = "#dc2626" if a.get("severity") == "HIGH" else "#ea580c"
                alert_rows.append([
                    Paragraph(f"<font color='{sev_color}'><b>{a.get('severity')}</b></font>", bold),
                    Paragraph(a.get("type", "SAFETY_ALERT"), normal),
                    Paragraph(a.get("message", ""), normal)
                ])
            alert_t = Table(alert_rows, colWidths=[70, 140, 330])
            alert_t.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#f1f5f9")),
                ('BOX', (0,0), (-1,-1), 1, BORDER_GREY),
                ('INNERGRID', (0,0), (-1,-1), 0.5, BORDER_GREY),
                ('TOPPADDING', (0,0), (-1,-1), 4),
                ('BOTTOMPADDING', (0,0), (-1,-1), 4),
            ]))
            elements.append(alert_t)
        elements.append(Spacer(1, 12))

        # Progress & Delay Analysis
        elements.append(Paragraph("2. Schedule Progress & Delay Breakdown", sec_style))
        prog_rows = [
            [Paragraph("Planned Stage (Baseline CPM)", normal), Paragraph(progress_data.get("planned_active_stage", ""), bold)],
            [Paragraph("Visually Confirmed Stage", normal), Paragraph(progress_data.get("visually_observed_stage", ""), bold)],
            [Paragraph("Observed Physical Variance", normal), Paragraph(f"{progress_data.get('observed_delay_days', 0)} days", normal)],
            [Paragraph("Reported Field Blocker Variance", normal), Paragraph(f"{progress_data.get('reported_delay_days', 0)} days", normal)],
            [Paragraph("<b>Projected Critical Path Slippage</b>", bold), Paragraph(f"<b>{progress_data.get('predicted_critical_path_delay_days', 0)} days</b>", bold)],
            [Paragraph("Recommended Action", normal), Paragraph(progress_data.get("recommended_mitigation", ""), normal)]
        ]
        prog_t = Table(prog_rows, colWidths=[200, 340])
        prog_t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), BG_ROW),
            ('BOX', (0,0), (-1,-1), 1, BORDER_GREY),
            ('INNERGRID', (0,0), (-1,-1), 0.5, BORDER_GREY),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ]))
        elements.append(prog_t)

        doc.build(elements)
        logger.info(f"Generated site progress PDF report: {output_path}")
        return output_path
