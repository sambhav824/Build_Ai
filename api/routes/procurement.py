"""
procurement.py — Procurement API Routes for BuildSmartAI
=========================================================
Exposes material shortage analysis, purchase order planning, and
procurement approval endpoints.

All procurement actions require human approval — no automatic orders are placed.
"""

import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from database.connection import get_db
from database.models import Quotation, InventoryItem
from database.repositories import ProjectRepository, ApprovalRepository
from agents.orchestrator import Orchestrator
import json, os

router = APIRouter(prefix="/api/projects/{project_id}/procurement", tags=["Procurement"])
orchestrator = Orchestrator()

_INVENTORY_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "data", "inventory.json")
_SUPPLIERS_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "data", "suppliers.json")


def _load_inventory() -> list:
    try:
        with open(_INVENTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data.get("inventory", [])
            return data if isinstance(data, list) else []
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _load_suppliers() -> list:
    try:
        with open(_SUPPLIERS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data.get("suppliers", [])
            return data if isinstance(data, list) else []
    except (FileNotFoundError, json.JSONDecodeError):
        return []


@router.get("")
def get_procurement_status(project_id: str, db: Session = Depends(get_db)):
    """
    Return material shortage analysis and procurement status for a project.

    Compares the latest approved BOQ quantities against available inventory
    to generate a shortage list and recommended purchase orders.
    """
    proj = ProjectRepository.get_project(db, project_id)
    if not proj:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    # Latest quotation
    quotation = (
        db.query(Quotation)
        .filter(Quotation.project_id == project_id)
        .order_by(Quotation.version.desc())
        .first()
    )
    if not quotation:
        raise HTTPException(
            status_code=404,
            detail="No BOQ/Quotation found for project. Run /estimate first."
        )

    inventory = _load_inventory()
    suppliers = _load_suppliers()

    inv_map = {}
    for inv_item in inventory:
        if isinstance(inv_item, dict):
            if "id" in inv_item:
                inv_map[inv_item["id"]] = inv_item
            if "material_name" in inv_item:
                inv_map[inv_item["material_name"]] = inv_item
            if "material" in inv_item:
                inv_map[inv_item["material"]] = inv_item

    boq_items = quotation.boq_items or []
    shortages = []
    purchase_orders = []
    total_procurement_cost = 0.0

    for item in boq_items:
        item_code = item.get("item_code") or item.get("id")
        material = item.get("name") or item.get("item") or item.get("material", "Unknown Material")
        required_qty = float(item.get("quantity", 0.0))
        unit = item.get("unit", "")

        inv = inv_map.get(item_code) or inv_map.get(material) or {}
        available = float(inv.get("available_qty", 0.0))
        unit_cost = float(inv.get("unit_cost", item.get("unit_rate", 0.0)))
        lead_days = int(inv.get("lead_time_days", 7))
        supplier = inv.get("supplier_name", inv.get("supplier", "To Be Sourced"))

        shortage_qty = max(0.0, required_qty - available)
        if shortage_qty > 0:
            order_cost = round(shortage_qty * unit_cost, 2)
            total_procurement_cost += order_cost
            shortages.append({
                "material": material,
                "unit": unit,
                "required_quantity": round(required_qty, 2),
                "available_in_stock": round(available, 2),
                "shortage_quantity": round(shortage_qty, 2),
                "unit_cost_inr": unit_cost,
                "estimated_order_cost_inr": order_cost,
                "lead_time_days": lead_days,
                "recommended_supplier": supplier,
            })
            purchase_orders.append({
                "po_ref": f"PO-{uuid.uuid4().hex[:6].upper()}",
                "material": material,
                "quantity": round(shortage_qty, 2),
                "unit": unit,
                "supplier": supplier,
                "estimated_cost_inr": order_cost,
                "lead_time_days": lead_days,
                "status": "PENDING_APPROVAL",
            })

    is_approved = ApprovalRepository.check_approval(db, project_id, "PROCUREMENT", 1)

    return {
        "project_id": project_id,
        "quotation_id": quotation.id,
        "quotation_version": quotation.version,
        "quotation_status": quotation.status,
        "procurement_approved": is_approved,
        "total_shortages": len(shortages),
        "total_procurement_cost_inr": round(total_procurement_cost, 2),
        "shortages": shortages,
        "purchase_orders": purchase_orders,
        "suppliers": suppliers,
        "disclaimer": (
            "ILLUSTRATIVE / SAMPLE DATA. All quantities, costs and lead times are "
            "derived from the BOQ and sample inventory data. Verify with actual "
            "suppliers before placing orders."
        ),
    }


@router.post("/order")
def record_purchase_order(
    project_id: str,
    db: Session = Depends(get_db),
    body: dict = Body(...)
):
    """
    Record a manually confirmed purchase order.

    Requires ``approved_by`` field. This endpoint does NOT place any automatic
    order — it records the human decision for audit and schedule tracking.

    Body fields
    -----------
    material : str
        Material name matching BOQ item.
    quantity : float
        Quantity to order.
    unit : str
        Unit of measure.
    supplier : str
        Supplier name.
    unit_cost_inr : float
        Agreed unit price in INR.
    approved_by : str
        Name / role of person authorising the order.
    notes : str, optional
        Any additional notes or reference numbers.
    """
    proj = ProjectRepository.get_project(db, project_id)
    if not proj:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    approved_by = body.get("approved_by", "").strip()
    if not approved_by:
        raise HTTPException(
            status_code=422,
            detail="'approved_by' is required. No procurement order can be placed without human authorisation."
        )

    material = body.get("material", "")
    quantity = float(body.get("quantity", 0))
    unit = body.get("unit", "")
    supplier = body.get("supplier", "TBD")
    unit_cost = float(body.get("unit_cost_inr", 0.0))
    notes = body.get("notes", "")

    if quantity <= 0:
        raise HTTPException(status_code=422, detail="'quantity' must be a positive number.")

    po_id = f"PO-{uuid.uuid4().hex[:8].upper()}"
    order_cost = round(quantity * unit_cost, 2)

    # Record approval in audit trail
    approval = ApprovalRepository.record_approval(
        db=db,
        project_id=project_id,
        item_type="PROCUREMENT",
        item_version=1,
        approved_by=approved_by,
        status="APPROVED",
        comments=(
            f"Purchase order {po_id}: {quantity} {unit} of '{material}' "
            f"from {supplier} @ INR {unit_cost}/unit. Total: INR {order_cost:,.2f}. "
            f"Notes: {notes}"
        ),
    )

    return {
        "status": "recorded",
        "message": (
            f"Purchase order {po_id} recorded successfully. "
            "This is an internal record — please coordinate with the supplier directly."
        ),
        "purchase_order": {
            "po_id": po_id,
            "project_id": project_id,
            "material": material,
            "quantity": quantity,
            "unit": unit,
            "supplier": supplier,
            "unit_cost_inr": unit_cost,
            "total_cost_inr": order_cost,
            "approved_by": approved_by,
            "approval_record_id": approval.id,
            "notes": notes,
            "status": "CONFIRMED",
        },
        "disclaimer": (
            "BuildSmartAI records this order for project tracking only. "
            "No payment or automatic supplier communication is made by this system."
        ),
    }
