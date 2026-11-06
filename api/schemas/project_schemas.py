from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class CreateProjectRequest(BaseModel):
    name: str = Field(..., json_schema_extra={"example": "Modern 2BHK Residential Villa"})
    client_name: Optional[str] = Field("Mr. Rushikesh K.", json_schema_extra={"example": "Mr. Rushikesh K."})
    plot_area_sqft: Optional[float] = Field(1200.0, json_schema_extra={"example": 1200.0})
    plot_length_ft: Optional[float] = Field(40.0, json_schema_extra={"example": 40.0})
    plot_width_ft: Optional[float] = Field(30.0, json_schema_extra={"example": 30.0})
    bhk_configuration: Optional[str] = Field("2BHK", json_schema_extra={"example": "2BHK"})
    floors: Optional[int] = Field(1, json_schema_extra={"example": 1})
    budget: Optional[float] = Field(3500000.0, json_schema_extra={"example": 3500000.0})
    architectural_style: Optional[str] = Field("Modern Contemporary", json_schema_extra={"example": "Modern Contemporary"})
    raw_requirements: Optional[str] = Field(
        "I want a modern 2BHK house on a 1,200 sq. ft. plot with two bedrooms, two bathrooms, living room, kitchen, dining space, balcony and parking. My budget is ₹35 lakh.",
        json_schema_extra={"example": "I want a modern 2BHK house on a 1,200 sq. ft. plot with two bedrooms, two bathrooms, living room, kitchen, dining space, balcony and parking. My budget is ₹35 lakh."}
    )

class PlanRequirementsRequest(BaseModel):
    raw_requirements: Optional[str] = None
    plot_area_sqft: Optional[float] = None
    plot_length_ft: Optional[float] = None
    plot_width_ft: Optional[float] = None
    bhk_configuration: Optional[str] = None
    floors: Optional[int] = None
    budget: Optional[float] = None

class DesignReviseRequest(BaseModel):
    revision_prompt: str = Field(..., json_schema_extra={"example": "Increase the master bedroom size by two feet"})

class ScheduleGenerateRequest(BaseModel):
    start_date: Optional[str] = Field("2026-12-01", json_schema_extra={"example": "2026-12-01"})

class ApprovalActionRequest(BaseModel):
    item_type: str = Field(..., json_schema_extra={"example": "DESIGN"}) # DESIGN, QUOTATION, SCHEDULE, PROCUREMENT
    item_version: int = Field(1, json_schema_extra={"example": 1})
    status: str = Field("APPROVED", json_schema_extra={"example": "APPROVED"})
    comments: Optional[str] = Field("Design validated against local municipal setback bylaws.", json_schema_extra={"example": "Approved"})
    approved_by: Optional[str] = Field("Authorized Client / Architect", json_schema_extra={"example": "Authorized Client / Architect"})
