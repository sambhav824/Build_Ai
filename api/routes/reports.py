import os
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from database.connection import get_db
from database.models import Quotation, Project

router = APIRouter(prefix="/api/projects/{project_id}/reports", tags=["Reports & Document Downloads"])

@router.get("")
def list_available_reports(project_id: str, db: Session = Depends(get_db)):
    reports = []

    # Check for Quotation PDF
    quote_pdf = f"generated_reports/Quotation_{project_id}.pdf"
    if os.path.exists(quote_pdf):
        reports.append({
            "type": "QUOTATION_PDF",
            "name": f"Quotation_{project_id}.pdf",
            "download_url": f"/api/projects/{project_id}/reports/quotation-pdf",
            "format": "PDF"
        })

    # Check for BOQ Excel
    boq_xlsx = f"generated_reports/BOQ_{project_id}.xlsx"
    if os.path.exists(boq_xlsx):
        reports.append({
            "type": "BOQ_EXCEL",
            "name": f"BOQ_{project_id}.xlsx",
            "download_url": f"/api/projects/{project_id}/reports/boq-excel",
            "format": "XLSX"
        })

    # Check for Site Progress Report PDF
    site_pdf = f"generated_reports/SiteReport_{project_id}.pdf"
    if os.path.exists(site_pdf):
        reports.append({
            "type": "SITE_REPORT_PDF",
            "name": f"SiteReport_{project_id}.pdf",
            "download_url": f"/api/projects/{project_id}/reports/site-pdf",
            "format": "PDF"
        })

    # Check for 2D SVG Blueprint
    svg_plan = f"generated_designs/{project_id}_floorplan.svg"
    if os.path.exists(svg_plan):
        reports.append({
            "type": "FLOORPLAN_SVG",
            "name": f"{project_id}_floorplan.svg",
            "download_url": f"/api/projects/{project_id}/reports/floorplan-svg",
            "format": "SVG"
        })

    return {"project_id": project_id, "reports": reports}

@router.get("/quotation-pdf")
def download_quotation_pdf(project_id: str):
    file_path = f"generated_reports/Quotation_{project_id}.pdf"
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Quotation PDF not yet generated")
    return FileResponse(file_path, media_type="application/pdf", filename=f"Quotation_{project_id}.pdf")

@router.get("/boq-excel")
def download_boq_excel(project_id: str):
    file_path = f"generated_reports/BOQ_{project_id}.xlsx"
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="BOQ Excel not yet generated")
    return FileResponse(
        file_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=f"BOQ_{project_id}.xlsx"
    )

@router.get("/site-pdf")
def download_site_pdf(project_id: str):
    file_path = f"generated_reports/SiteReport_{project_id}.pdf"
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Site Intelligence Report PDF not yet generated")
    return FileResponse(file_path, media_type="application/pdf", filename=f"SiteReport_{project_id}.pdf")

@router.get("/floorplan-svg")
def download_floorplan_svg(project_id: str):
    file_path = f"generated_designs/{project_id}_floorplan.svg"
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Floorplan SVG not found")
    return FileResponse(file_path, media_type="image/svg+xml", filename=f"{project_id}_floorplan.svg")
