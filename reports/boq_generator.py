import os
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from utils.logging_config import logger

class BOQGenerator:
    """
    Exports itemized Bill of Quantities into standardized, styled Excel workbooks (.xlsx).
    """

    @staticmethod
    def generate_excel(project_id: str, project_name: str, boq_items: list, output_path: str = None) -> str:
        if not output_path:
            os.makedirs("generated_reports", exist_ok=True)
            output_path = f"generated_reports/BOQ_{project_id}.xlsx"

        wb = Workbook()
        ws = wb.active
        ws.title = "Bill of Quantities"

        # Theme Colors
        navy_fill = PatternFill(start_color="0F172A", end_color="0F172A", fill_type="solid")
        header_fill = PatternFill(start_color="E2E8F0", end_color="E2E8F0", fill_type="solid")
        zebra_fill = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")

        white_bold = Font(name="Calibri", size=14, bold=True, color="FFFFFF")
        dark_bold = Font(name="Calibri", size=11, bold=True, color="0F172A")
        regular_font = Font(name="Calibri", size=11, color="334155")

        thin_side = Side(border_style="thin", color="CBD5E1")
        border = Border(left=thin_side, right=thin_side, top=thin_side, bottom=thin_side)

        # Title Block
        ws.merge_cells("A1:G1")
        ws["A1"] = f"BUILDSMARTAI — BILL OF QUANTITIES: {project_name.upper()} ({project_id})"
        ws["A1"].font = white_bold
        ws["A1"].fill = navy_fill
        ws["A1"].alignment = Alignment(horizontal="center", vertical="center")
        ws.row_dimensions[1].height = 35

        # Table Column Headers
        headers = ["Item #", "Item Code", "Material / Service Description", "Category", "Quantity", "Unit", "Measurement Formula"]
        for col_idx, header in enumerate(headers, start=1):
            cell = ws.cell(row=3, column=col_idx, value=header)
            cell.font = dark_bold
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center" if col_idx in [1, 5, 6] else "left", vertical="center")
            cell.border = border
        ws.row_dimensions[3].height = 25

        # Populate Items
        current_row = 4
        for idx, it in enumerate(boq_items, start=1):
            row_data = [
                idx,
                it.get("item_code", f"ITEM-{idx:02d}"),
                it.get("name", ""),
                it.get("category", "General"),
                it.get("quantity", 0),
                it.get("unit", ""),
                it.get("formula", "Standard Estimation")
            ]
            for col_idx, val in enumerate(row_data, start=1):
                cell = ws.cell(row=current_row, column=col_idx, value=val)
                cell.font = regular_font
                cell.border = border
                if current_row % 2 == 0:
                    cell.fill = zebra_fill
                if col_idx in [1, 5, 6]:
                    cell.alignment = Alignment(horizontal="center", vertical="center")
            ws.row_dimensions[current_row].height = 20
            current_row += 1

        # Adjust Column Widths
        col_widths = {1: 10, 2: 15, 3: 45, 4: 25, 5: 15, 6: 12, 7: 45}
        for col_idx, width in col_widths.items():
            col_letter = chr(64 + col_idx)
            ws.column_dimensions[col_letter].width = width

        wb.save(output_path)
        logger.info(f"Generated BOQ Excel sheet: {output_path}")
        return output_path
