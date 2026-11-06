from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Float, Boolean, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from database.connection import Base

def utc_now():
    return datetime.now(timezone.utc)

class Project(Base):
    __tablename__ = "projects"

    id = Column(String(64), primary_key=True, index=True) # e.g. "BS-1001"
    name = Column(String(255), nullable=False)
    client_name = Column(String(255), nullable=True)
    status = Column(String(64), default="PLANNING") # PLANNING, DESIGN_APPROVED, ESTIMATION_DONE, SCHEDULED, IN_PROGRESS, COMPLETED
    plot_area_sqft = Column(Float, nullable=True)
    plot_length_ft = Column(Float, nullable=True)
    plot_width_ft = Column(Float, nullable=True)
    bhk_configuration = Column(String(32), nullable=True)
    floors = Column(Integer, default=1)
    budget = Column(Float, nullable=True)
    architectural_style = Column(String(64), default="Modern")
    raw_requirements = Column(Text, nullable=True)
    structured_requirements = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    # Relationships
    executions = relationship("AgentExecution", back_populates="project", cascade="all, delete-orphan")
    designs = relationship("Design", back_populates="project", cascade="all, delete-orphan")
    quotations = relationship("Quotation", back_populates="project", cascade="all, delete-orphan")
    schedules = relationship("Schedule", back_populates="project", cascade="all, delete-orphan")
    site_observations = relationship("SiteObservation", back_populates="project", cascade="all, delete-orphan")
    approvals = relationship("ApprovalRecord", back_populates="project", cascade="all, delete-orphan")

class AgentExecution(Base):
    __tablename__ = "agent_executions"

    id = Column(String(64), primary_key=True, index=True) # e.g. "EXEC-001"
    project_id = Column(String(64), ForeignKey("projects.id"), index=True)
    agent_name = Column(String(64), nullable=False) # planning, design, estimation, scheduling, monitoring
    action = Column(String(64), nullable=False)
    status = Column(String(32), default="REQUESTED") # REQUESTED, COMPLETED, FAILED, AWAITING_APPROVAL
    input_payload = Column(JSON, nullable=True)
    output_payload = Column(JSON, nullable=True)
    warnings = Column(JSON, nullable=True)
    requires_approval = Column(Boolean, default=False)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now)
    completed_at = Column(DateTime, nullable=True)

    project = relationship("Project", back_populates="executions")

class Design(Base):
    __tablename__ = "designs"

    id = Column(String(64), primary_key=True, index=True)
    project_id = Column(String(64), ForeignKey("projects.id"), index=True)
    version = Column(Integer, default=1)
    status = Column(String(32), default="PROPOSED") # PROPOSED, APPROVED, REVISED, REJECTED
    layout_2d = Column(JSON, nullable=False) # Rooms, walls, dimensions, doors, windows
    model_3d_meta = Column(JSON, nullable=True) # 3D mesh details, camera, heights
    model_3d_file = Column(String(255), nullable=True) # Path to GLB / OBJ
    preview_2d_svg = Column(Text, nullable=True) # SVG representation for quick rendering
    total_builtup_area = Column(Float, default=0.0)
    validation_status = Column(JSON, nullable=True) # Setbacks, bylaws, room sizes validation
    created_at = Column(DateTime, default=utc_now)

    project = relationship("Project", back_populates="designs")

class Quotation(Base):
    __tablename__ = "quotations"

    id = Column(String(64), primary_key=True, index=True)
    project_id = Column(String(64), ForeignKey("projects.id"), index=True)
    version = Column(Integer, default=1)
    status = Column(String(32), default="DRAFT") # DRAFT, APPROVED, SUPERSEDED
    material_cost = Column(Float, default=0.0)
    labour_cost = Column(Float, default=0.0)
    transport_cost = Column(Float, default=0.0)
    equipment_cost = Column(Float, default=0.0)
    finishing_cost = Column(Float, default=0.0)
    taxes = Column(Float, default=0.0)
    contingency = Column(Float, default=0.0)
    grand_total = Column(Float, default=0.0)
    boq_items = Column(JSON, nullable=False) # List of calculated items
    assumptions = Column(JSON, nullable=True)
    pdf_report_path = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=utc_now)

    project = relationship("Project", back_populates="quotations")

class InventoryItem(Base):
    __tablename__ = "inventory"

    id = Column(String(64), primary_key=True)
    material_name = Column(String(128), nullable=False)
    category = Column(String(64), nullable=True)
    unit = Column(String(32), nullable=False)
    available_qty = Column(Float, default=0.0)
    minimum_stock = Column(Float, default=0.0)
    unit_cost = Column(Float, default=0.0)
    supplier_name = Column(String(128), nullable=True)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

class Schedule(Base):
    __tablename__ = "schedules"

    id = Column(String(64), primary_key=True, index=True)
    project_id = Column(String(64), ForeignKey("projects.id"), index=True)
    version = Column(Integer, default=1)
    status = Column(String(32), default="PLANNED")
    start_date = Column(String(32), nullable=False)
    estimated_end_date = Column(String(32), nullable=False)
    critical_path = Column(JSON, nullable=True)
    tasks = Column(JSON, nullable=False) # List of tasks with dependencies, durations, early/late dates
    created_at = Column(DateTime, default=utc_now)

    project = relationship("Project", back_populates="schedules")

class SiteObservation(Base):
    __tablename__ = "site_observations"

    id = Column(String(64), primary_key=True, index=True)
    project_id = Column(String(64), ForeignKey("projects.id"), index=True)
    media_url = Column(String(255), nullable=False)
    detected_workers = Column(Integer, default=0)
    ppe_compliance_rate = Column(Float, default=100.0)
    safety_alerts = Column(JSON, nullable=True)
    inferred_stage = Column(String(64), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now)

    project = relationship("Project", back_populates="site_observations")

class ApprovalRecord(Base):
    __tablename__ = "approval_records"

    id = Column(String(64), primary_key=True, index=True)
    project_id = Column(String(64), ForeignKey("projects.id"), index=True)
    item_type = Column(String(64), nullable=False) # DESIGN, QUOTATION, SCHEDULE, PROCUREMENT
    item_version = Column(Integer, default=1)
    approved_by = Column(String(128), default="Project Owner")
    status = Column(String(32), default="APPROVED") # APPROVED, REJECTED
    comments = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=utc_now)

    project = relationship("Project", back_populates="approvals")

