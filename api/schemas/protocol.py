from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class AgentRequest(BaseModel):
    project_id: str = Field(..., description="Unique Project ID e.g. BS-1001")
    execution_id: str = Field(..., description="Unique execution transaction ID e.g. EXEC-001")
    agent: str = Field(..., description="Target specialized agent name")
    action: str = Field(..., description="Specific action for the agent to execute")
    input: Dict[str, Any] = Field(default_factory=dict, description="Structured input parameters")
    status: str = Field(default="requested", description="Request status")

class AgentResponse(BaseModel):
    project_id: str = Field(..., description="Unique Project ID")
    execution_id: str = Field(..., description="Unique execution transaction ID")
    agent: str = Field(..., description="Executing agent name")
    status: str = Field(..., description="Execution status: completed, failed, awaiting_approval")
    result: Dict[str, Any] = Field(default_factory=dict, description="Structured output payload")
    warnings: List[str] = Field(default_factory=list, description="Validation or assumption warnings")
    requires_approval: bool = Field(default=False, description="Whether human approval is required before proceeding")
    error: Optional[str] = Field(default=None, description="Detailed error message if failed")

class ApprovalRequestSchema(BaseModel):
    project_id: str
    item_type: str # DESIGN, QUOTATION, SCHEDULE, PROCUREMENT
    item_version: int = 1
    approved_by: str = "Authorized Professional / Client"
    status: str = "APPROVED" # APPROVED, REJECTED
    comments: Optional[str] = None
