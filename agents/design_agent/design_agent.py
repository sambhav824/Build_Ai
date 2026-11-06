import os
from typing import Dict, Any, List
from agents.base_agent import BaseAgent
from api.schemas.protocol import AgentRequest, AgentResponse
from engines.geometry_engine import Rect
from agents.design_agent.design_planner import DesignPlanner
from agents.design_agent.constraint_validator import ConstraintValidator
from agents.design_agent.floorplan_generator import FloorplanGenerator
from agents.design_agent.design_revision import DesignRevision
from design.model_exporter import ModelExporter
from design.blender_generator import BlenderGenerator
from design.plan_parser import PlanParser
from utils.logging_config import logger

class DesignAgent(BaseAgent):
    """
    Agent 3: AI Residential Design Agent.
    Transforms project constraints and parameters into dimensioned 2D floor plans,
    validates municipal bylaws & setbacks, generates interactive 3D WebGL meshes,
    parses uploaded blueprints via Computer Vision, and supports conversational design revisions.
    """
    def __init__(self):
        super().__init__(name="design_agent")

    def process(self, request: AgentRequest) -> AgentResponse:
        logger.info(f"DesignAgent processing action '{request.action}' for project {request.project_id}")
        inp = request.input

        # Action: Mode B - Parse Uploaded Blueprint
        if request.action in ["upload_and_parse_plan", "parse_uploaded_plan"]:
            image_path = inp.get("image_path", "uploads/sample_floorplan.png")
            parsed_cv = PlanParser.parse_image_plan(image_path)
            extracted = parsed_cv["extracted_rooms"]

            rooms = [Rect(r["x"], r["y"], r["w"], r["h"], r["name"]) for r in extracted]
            svg_file = FloorplanGenerator.render_svg(rooms, 40.0, 30.0, request.project_id)
            model_3d_info = ModelExporter.export_3d_obj(rooms, request.project_id)

            return AgentResponse(
                project_id=request.project_id,
                execution_id=request.execution_id,
                agent=self.name,
                status="completed",
                result={
                    "project_id": request.project_id,
                    "mode": "MODE_B_UPLOADED_DRAWING",
                    "cv_analysis": parsed_cv,
                    "extracted_rooms": extracted,
                    "preview_2d_svg_file": svg_file.replace("\\", "/"),
                    "model_3d_obj": model_3d_info["obj_path"],
                    "scene_3d_json": model_3d_info["scene_json"],
                    "requires_confirmation": len(parsed_cv["uncertain_regions"]) > 0
                },
                warnings=["Please confirm detected room dimensions before proceeding to structural estimation."],
                requires_approval=True
            )

        # 1. Project Parameters & Plot Data
        plot = inp.get("plot", {})
        plot_length = float(plot.get("length_ft", inp.get("plot_length_ft", 40.0)))
        plot_width = float(plot.get("width_ft", inp.get("plot_width_ft", 30.0)))
        bhk = inp.get("bhk_configuration", inp.get("bhk", "2BHK"))
        style = inp.get("architectural_style", inp.get("style", "Modern Contemporary"))
        version = int(inp.get("version", 1))

        zoning = inp.get("zoning_constraints", {})
        setbacks = zoning.get("setbacks", {
            "front_ft": 5.0,
            "rear_ft": 3.0,
            "side_left_ft": 3.0,
            "side_right_ft": 3.0
        })

        # 2. Check if this is a Revision Request
        revision_instruction = inp.get("revision_prompt")
        existing_rooms_data = inp.get("rooms")

        if request.action == "revise_design" and revision_instruction:
            if not existing_rooms_data:
                # Generate baseline layout first so the conversational revision has an actual building to modify
                existing_rects = DesignPlanner.generate_layout(
                    plot_length_ft=plot_length,
                    plot_width_ft=plot_width,
                    setbacks=setbacks,
                    bhk=bhk,
                    style=style
                )
            else:
                existing_rects = [
                    Rect(
                        r["x"],
                        r["y"],
                        r["w"],
                        r["h"],
                        r.get("name", r.get("label", "")),
                        elevation_ft=r.get("elevation_ft", 0.0),
                        floor=r.get("floor", 0)
                    )
                    for r in existing_rooms_data
                ]
            rooms, revision_notes, version = DesignRevision.apply_conversational_edit(
                rooms=existing_rects,
                instruction=revision_instruction,
                current_version=version
            )
        else:
            # Generate fresh layout
            rooms = DesignPlanner.generate_layout(
                plot_length_ft=plot_length,
                plot_width_ft=plot_width,
                setbacks=setbacks,
                bhk=bhk,
                style=style
            )
            revision_notes = ["Initial algorithmic layout generated."]

        # 3. Geometric & Statutory Constraint Validation
        validation_results = ConstraintValidator.validate_layout(
            rooms=rooms,
            plot_length_ft=plot_length,
            plot_width_ft=plot_width,
            setbacks=setbacks
        )

        # 4. Generate Dimensioned 2D SVG Drawing
        svg_file = FloorplanGenerator.render_svg(
            rooms=rooms,
            plot_length_ft=plot_length,
            plot_width_ft=plot_width,
            project_id=request.project_id
        )

        with open(svg_file, "r", encoding="utf-8") as f:
            svg_content = f.read()

        # 5. Generate Procedural 3D Model Mesh (.obj, .mtl, scene.json)
        model_3d_info = ModelExporter.export_3d_obj(
            rooms=rooms,
            project_id=request.project_id
        )

        # 6. Generate Optional Offline Blender Python Script
        blender_script = BlenderGenerator.generate_blender_script(
            rooms=rooms,
            project_id=request.project_id
        )

        total_builtup_sqft = sum(r.area for r in rooms)

        result_payload = {
            "project_id": request.project_id,
            "version": version,
            "architectural_style": style,
            "total_builtup_sqft": round(total_builtup_sqft, 2),
            "rooms": [r.to_dict() for r in rooms],
            "validation": validation_results,
            "revision_notes": revision_notes,
            "preview_2d_svg_file": svg_file.replace("\\", "/"),
            "preview_2d_svg": svg_content,
            "model_3d_obj": model_3d_info["obj_path"],
            "model_3d_mtl": model_3d_info["mtl_path"],
            "scene_3d_json": model_3d_info["scene_json"],
            "blender_script": blender_script.replace("\\", "/"),
            "requires_customer_approval": True
        }

        warnings = []
        if not validation_results["is_valid"]:
            warnings.extend(validation_results["violations"])
        warnings.append("Conceptual 3D visualization is not an engineering structural working drawing.")

        return AgentResponse(
            project_id=request.project_id,
            execution_id=request.execution_id,
            agent=self.name,
            status="completed",
            result=result_payload,
            warnings=warnings,
            requires_approval=True # Residential designs strictly require human approval
        )
