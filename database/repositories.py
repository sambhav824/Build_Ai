import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from database.models import (
    Project, AgentExecution, Design, Quotation, InventoryItem,
    Schedule, SiteObservation, ApprovalRecord
)
from utils.logging_config import logger

def utc_now():
    return datetime.now(timezone.utc)

class ProjectRepository:
    @staticmethod
    def create_project(db: Session, project_id: str, name: str, client_name: Optional[str] = None, **kwargs) -> Project:
        project = Project(
            id=project_id,
            name=name,
            client_name=client_name or "Residential Client",
            **kwargs
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        logger.info(f"Created project: {project.id} - {project.name}")
        return project

    @staticmethod
    def get_project(db: Session, project_id: str) -> Optional[Project]:
        return db.query(Project).filter(Project.id == project_id).first()

    @staticmethod
    def list_projects(db: Session) -> List[Project]:
        return db.query(Project).order_by(Project.created_at.desc()).all()

    @staticmethod
    def update_project(db: Session, project_id: str, **kwargs) -> Optional[Project]:
        proj = db.query(Project).filter(Project.id == project_id).first()
        if proj:
            for k, v in kwargs.items():
                setattr(proj, k, v)
            proj.updated_at = utc_now()
            db.commit()
            db.refresh(proj)
        return proj

class ExecutionRepository:
    @staticmethod
    def log_execution_start(db: Session, exec_id: str, project_id: str, agent_name: str, action: str, input_payload: Dict[str, Any]) -> AgentExecution:
        record = AgentExecution(
            id=exec_id,
            project_id=project_id,
            agent_name=agent_name,
            action=action,
            status="REQUESTED",
            input_payload=input_payload,
            created_at=utc_now()
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return record

    @staticmethod
    def log_execution_finish(db: Session, exec_id: str, status: str, output_payload: Dict[str, Any], warnings: List[str] = None, requires_approval: bool = False, error_message: str = None) -> Optional[AgentExecution]:
        record = db.query(AgentExecution).filter(AgentExecution.id == exec_id).first()
        if record:
            record.status = status
            record.output_payload = output_payload
            record.warnings = warnings or []
            record.requires_approval = requires_approval
            record.error_message = error_message
            record.completed_at = utc_now()
            db.commit()
            db.refresh(record)
        return record

class ApprovalRepository:
    @staticmethod
    def record_approval(db: Session, project_id: str, item_type: str, item_version: int, approved_by: str, status: str = "APPROVED", comments: Optional[str] = None) -> ApprovalRecord:
        record = ApprovalRecord(
            id=f"APP-{uuid.uuid4().hex[:8].upper()}",
            project_id=project_id,
            item_type=item_type,
            item_version=item_version,
            approved_by=approved_by,
            status=status,
            comments=comments,
            timestamp=utc_now()
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        logger.info(f"Approval recorded: {record.id} for {item_type} v{item_version} [{status}] on project {project_id}")
        return record

    @staticmethod
    def check_approval(db: Session, project_id: str, item_type: str, item_version: int) -> bool:
        record = db.query(ApprovalRecord).filter(
            ApprovalRecord.project_id == project_id,
            ApprovalRecord.item_type == item_type,
            ApprovalRecord.item_version == item_version,
            ApprovalRecord.status == "APPROVED"
        ).first()
        return record is not None

