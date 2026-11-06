"""
api.routes.studio
=================
FastAPI route collection for BuildSmart 3D Studio:
Architectural Drawing to Interactive 3D Building Conversion.
"""

import os
import json
import shutil
from pathlib import Path
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Response
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel, Field

from studio.models.project import (
    ArchitecturalProject,
    Building,
    FloorLevel,
    DrawingFormat,
    MeasurementUnit,
)
from studio.models.elements import Wall, Door, Window, Room, Staircase, Column, Slab, WallType, RoomType
from studio.models.geometry import Point2D
from studio.models.materials import STANDARD_MATERIALS
from studio.recognition.plan_analyzer import PlanAnalyzer
from studio.geometry.scene_compiler import SceneCompiler
from studio.parsers.scale_calibrator import ScaleCalibrator
from studio.parsers.dwg_handler import DWGHandler
from studio.parsers.pdf_processor import PDFProcessor
from studio.modification import ModificationEngine, RoomLibrary
from utils.logging_config import logger

router = APIRouter(prefix="/api/studio", tags=["BuildSmart 3D Studio"])
modification_engine = ModificationEngine()
room_library = RoomLibrary()

BASE_DIR = Path(__file__).resolve().parent.parent.parent
STUDIO_DATA_DIR = BASE_DIR / "data" / "studio_projects"
STUDIO_DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOADS_DIR = BASE_DIR / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
EXPORTS_DIR = BASE_DIR / "generated_designs" / "studio_exports"
EXPORTS_DIR.mkdir(parents=True, exist_ok=True)


class CreateStudioProjectRequest(BaseModel):
    project_name: str = Field("Modern 2BHK Architectural Model")
    source_filename: str = Field("sample_plan.dxf")
    source_format: DrawingFormat = Field(DrawingFormat.DXF)
    units: MeasurementUnit = Field(MeasurementUnit.METERS)


class CalibrateScaleRequest(BaseModel):
    point1: List[float] = Field(..., description="[x1, y1] pixel coords")
    point2: List[float] = Field(..., description="[x2, y2] pixel coords")
    known_length_meters: float = Field(..., ge=0.1, le=100.0)


class UpdateMaterialRequest(BaseModel):
    material_id: str


def _get_project_path(project_id: str) -> Path:
    return STUDIO_DATA_DIR / f"{project_id}.json"


def _save_project(proj: ArchitecturalProject) -> None:
    p = _get_project_path(proj.project_id)
    with open(p, "w", encoding="utf-8") as f:
        f.write(proj.model_dump_json(indent=2))


def _load_project(project_id: str) -> Optional[ArchitecturalProject]:
    p = _get_project_path(project_id)
    if not p.exists():
        return None
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
            return ArchitecturalProject.model_validate(data)
    except Exception as e:
        logger.error(f"Error loading studio project {project_id}: {e}")
        return None


@router.get("/health")
def studio_health_check():
    """Verify 3D Studio subsystem health and CAD/Mesh parser availability."""
    ezdxf_available = False
    try:
        import ezdxf
        ezdxf_available = True
    except ImportError:
        pass

    trimesh_available = False
    try:
        import trimesh
        trimesh_available = True
    except ImportError:
        pass

    return {
        "status": "healthy",
        "subsystem": "BuildSmart 3D Studio",
        "version": "1.0.0",
        "parsers": {
            "dxf": ezdxf_available,
            "trimesh": trimesh_available,
            "opencv": True,
            "pymupdf": True,
        },
        "supported_formats": ["DXF", "DWG", "PDF", "PNG", "JPG", "JPEG"]
    }


@router.get("/materials")
def get_studio_materials():
    """Return available PBR architectural materials for inspector customization."""
    return {
        mat_id: {
            "material_id": mat.material_id,
            "name": mat.name,
            "category": mat.category.value,
            "color_hex": mat.color_hex,
            "roughness": mat.roughness,
            "metalness": mat.metalness,
            "opacity": mat.opacity,
            "is_transparent": mat.is_transparent,
            "unit_cost_inr": mat.unit_cost_inr,
        }
        for mat_id, mat in STANDARD_MATERIALS.items()
    }


@router.get("/projects")
def list_studio_projects():
    """List all saved 3D Studio architectural projects."""
    projects = []
    for f in STUDIO_DATA_DIR.glob("*.json"):
        try:
            with open(f, "r", encoding="utf-8") as fp:
                data = json.load(fp)
                projects.append({
                    "project_id": data.get("project_id", f.stem),
                    "project_name": data.get("project_name", "Untitled"),
                    "source_filename": data.get("source_filename", ""),
                    "source_format": data.get("source_format", "DXF"),
                    "levels_count": len(data.get("building", {}).get("levels", [])),
                    "created_at": data.get("created_at", ""),
                })
        except Exception:
            continue
    return projects


@router.post("/projects", status_code=201)
def create_studio_project(payload: CreateStudioProjectRequest):
    """Initialize a new architectural 3D Studio project."""
    proj = ArchitecturalProject(
        project_name=payload.project_name,
        source_filename=payload.source_filename,
        source_format=payload.source_format,
        units=payload.units,
    )
    _save_project(proj)
    logger.info(f"Created Studio Architectural Project: {proj.project_id} ({proj.project_name})")
    return {
        "status": "success",
        "project_id": proj.project_id,
        "project": proj.model_dump()
    }


@router.post("/upload")
async def upload_drawing(
    file: UploadFile = File(...),
    project_name: Optional[str] = Form("Residential Building Plan"),
    num_floors: Optional[int] = Form(1),
    floor_height_m: Optional[float] = Form(3.0),
    pixels_per_meter: Optional[float] = Form(100.0)
):
    """
    Ingest architectural drawing (DXF, DWG, PDF, PNG, JPG),
    analyze architectural elements, construct 3D geometry, and store project.
    """
    filename = file.filename or "drawing.dxf"
    ext = Path(filename).suffix.lower()

    if ext not in [".dxf", ".dwg", ".pdf", ".png", ".jpg", ".jpeg"]:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported format '{ext}'. Must be DXF, DWG, PDF, PNG, or JPG."
        )

    saved_path = UPLOADS_DIR / filename
    with open(saved_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    analyzer = PlanAnalyzer(project_name=project_name or Path(filename).stem)

    try:
        if ext == ".dxf":
            proj = analyzer.analyze_dxf(saved_path, num_floors=num_floors or 1, floor_height_m=floor_height_m or 3.0)
        elif ext == ".dwg":
            handler = DWGHandler(saved_path)
            if handler.is_converter_available():
                dxf_file = handler.convert_to_dxf(UPLOADS_DIR)
                proj = analyzer.analyze_dxf(dxf_file, num_floors=num_floors or 1, floor_height_m=floor_height_m or 3.0)
            else:
                header = handler.inspect_dwg_header()
                raise HTTPException(
                    status_code=422,
                    detail=(
                        f"Native DWG detected ({header['version']}). "
                        f"ODA File Converter is not installed. Please export as DXF from your CAD software, "
                        f"or upload a 2D floor plan image/PDF."
                    )
                )
        elif ext == ".pdf":
            pdf_proc = PDFProcessor(saved_path)
            rendered_png = pdf_proc.render_page_to_image(page_index=0, dpi=200, output_dir=UPLOADS_DIR)
            pdf_proc.close()
            proj = analyzer.analyze_raster(
                rendered_png,
                pixels_per_meter=pixels_per_meter or 100.0,
                num_floors=num_floors or 1,
                floor_height_m=floor_height_m or 3.0
            )
            proj.source_filename = filename
            proj.source_format = DrawingFormat.PDF
            _save_project(proj)
        else:
            # PNG / JPG / JPEG
            proj = analyzer.analyze_raster(
                saved_path,
                pixels_per_meter=pixels_per_meter or 100.0,
                num_floors=num_floors or 1,
                floor_height_m=floor_height_m or 3.0
            )

        return {
            "status": "success",
            "project_id": proj.project_id,
            "project_name": proj.project_name,
            "source_format": proj.source_format.value,
            "total_builtup_sqm": proj.building.total_builtup_area_sqm,
            "levels_count": len(proj.building.levels),
            "bim_tree": proj.to_bim_tree_json()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to process drawing {filename}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Drawing processing failed: {str(e)}")


@router.get("/projects/{project_id}")
def get_studio_project(project_id: str):
    """Retrieve complete architectural intermediate representation for a project."""
    proj = _load_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail=f"Studio Project {project_id} not found")
    return proj.model_dump()


@router.get("/projects/{project_id}/bim-tree")
def get_studio_bim_tree(project_id: str):
    """Retrieve BIM element tree hierarchy powering the Left Studio Panel."""
    proj = _load_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail=f"Studio Project {project_id} not found")
    return proj.to_bim_tree_json()


@router.get("/projects/{project_id}/scene")
def get_studio_scene(project_id: str):
    """Retrieve compiled Three.js scene graph JSON for 360° interactive rendering."""
    proj = _load_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail=f"Studio Project {project_id} not found")
    return SceneCompiler.compile_threejs_scene(proj)


@router.patch("/projects/{project_id}/elements/{element_id}/material")
def update_element_material(project_id: str, element_id: str, payload: UpdateMaterialRequest):
    """Update material assignment for an element in the 3D building."""
    proj = _load_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail=f"Studio Project {project_id} not found")

    updated = False
    for lvl in proj.building.levels:
        for w in lvl.walls:
            if w.wall_id == element_id:
                w.material_id = payload.material_id
                updated = True
                break
        for s in lvl.slabs:
            if s.slab_id == element_id:
                s.material_id = payload.material_id
                updated = True
                break
        for r in lvl.rooms:
            if r.room_id == element_id:
                r.floor_material_id = payload.material_id
                updated = True
                break

    if not updated:
        raise HTTPException(status_code=404, detail=f"Element {element_id} not found in project {project_id}")

    _save_project(proj)
    return {"status": "success", "element_id": element_id, "material_id": payload.material_id}


@router.get("/projects/{project_id}/export/obj")
def export_project_obj(project_id: str):
    """Export building as Wavefront OBJ file."""
    proj = _load_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail=f"Studio Project {project_id} not found")

    obj_content = SceneCompiler.export_to_obj(proj)
    filename = f"{proj.project_name.lower().replace(' ', '_')}_{proj.project_id}.obj"
    return Response(
        content=obj_content,
        media_type="text/plain",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@router.get("/projects/{project_id}/export/glb")
def export_project_glb(project_id: str):
    """Export building as binary glTF (GLB) file."""
    proj = _load_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail=f"Studio Project {project_id} not found")

    filename = f"{proj.project_name.lower().replace(' ', '_')}_{proj.project_id}.glb"
    target_path = EXPORTS_DIR / filename
    SceneCompiler.export_to_glb(proj, target_path)

    return FileResponse(
        path=str(target_path),
        filename=filename,
        media_type="model/gltf-binary"
    )


@router.post("/seed-sample")
def seed_sample_studio_project():
    """Seed a high-fidelity 2-story contemporary residential villa project."""
    # Ground Floor
    gf_walls = [
        # Exterior perimeter (12m x 9m)
        Wall(
            wall_id="GF_W_FRONT",
            name="Front Facade Wall",
            wall_type=WallType.EXTERIOR,
            start=Point2D(x=0.0, y=0.0),
            end=Point2D(x=12.0, y=0.0),
            thickness_m=0.23,
            height_m=3.0,
            openings=[
                Door(opening_id="GF_D_MAIN", name="Grand Entrance Door", width_m=1.2, height_m=2.2, offset_along_wall_m=3.5),
                Window(opening_id="GF_W_LIV1", name="Living Room Window A", width_m=1.8, height_m=1.4, sill_height_m=0.8, offset_along_wall_m=8.0)
            ],
            material_id="MAT-PLAS-01"
        ),
        Wall(
            wall_id="GF_W_RIGHT",
            name="East Exterior Wall",
            wall_type=WallType.EXTERIOR,
            start=Point2D(x=12.0, y=0.0),
            end=Point2D(x=12.0, y=9.0),
            thickness_m=0.23,
            height_m=3.0,
            openings=[
                Window(opening_id="GF_W_KIT", name="Kitchen Window", width_m=1.5, height_m=1.2, sill_height_m=1.0, offset_along_wall_m=4.5)
            ],
            material_id="MAT-BRK-01"
        ),
        Wall(
            wall_id="GF_W_BACK",
            name="Rear Exterior Wall",
            wall_type=WallType.EXTERIOR,
            start=Point2D(x=12.0, y=9.0),
            end=Point2D(x=0.0, y=9.0),
            thickness_m=0.23,
            height_m=3.0,
            openings=[
                Window(opening_id="GF_W_BED_G", name="Guest Bedroom Window", width_m=1.5, height_m=1.2, sill_height_m=0.9, offset_along_wall_m=3.0),
                Door(opening_id="GF_D_PATIO", name="Patio Door", width_m=1.0, height_m=2.1, offset_along_wall_m=8.5)
            ],
            material_id="MAT-PLAS-01"
        ),
        Wall(
            wall_id="GF_W_LEFT",
            name="West Exterior Wall",
            wall_type=WallType.EXTERIOR,
            start=Point2D(x=0.0, y=9.0),
            end=Point2D(x=0.0, y=0.0),
            thickness_m=0.23,
            height_m=3.0,
            material_id="MAT-PLAS-01"
        ),
        # Interior partitions
        Wall(
            wall_id="GF_W_DIV1",
            name="Living / Kitchen Partition",
            wall_type=WallType.INTERIOR,
            start=Point2D(x=6.5, y=0.0),
            end=Point2D(x=6.5, y=5.5),
            thickness_m=0.15,
            height_m=3.0,
            openings=[
                Door(opening_id="GF_D_KIT", name="Kitchen Archway", width_m=1.0, height_m=2.1, offset_along_wall_m=2.8)
            ],
            material_id="MAT-PLAS-02"
        ),
        Wall(
            wall_id="GF_W_DIV2",
            name="Guest Bedroom Partition",
            wall_type=WallType.INTERIOR,
            start=Point2D(x=0.0, y=5.5),
            end=Point2D(x=6.5, y=5.5),
            thickness_m=0.15,
            height_m=3.0,
            openings=[
                Door(opening_id="GF_D_GBED", name="Guest Bedroom Door", width_m=0.9, height_m=2.1, offset_along_wall_m=4.5)
            ],
            material_id="MAT-PLAS-02"
        )
    ]

    gf_rooms = [
        Room(
            room_id="GF_R_LIVING",
            name="Living & Dining Hall",
            room_type=RoomType.LIVING,
            boundary_polygon=[Point2D(x=0, y=0), Point2D(x=6.5, y=0), Point2D(x=6.5, y=5.5), Point2D(x=0, y=5.5)],
            floor_material_id="MAT-TILE-01"
        ),
        Room(
            room_id="GF_R_KITCHEN",
            name="Modular Kitchen",
            room_type=RoomType.KITCHEN,
            boundary_polygon=[Point2D(x=6.5, y=0), Point2D(x=12.0, y=0), Point2D(x=12.0, y=5.5), Point2D(x=6.5, y=5.5)],
            floor_material_id="MAT-GRAN-01"
        ),
        Room(
            room_id="GF_R_BED1",
            name="Guest Bedroom",
            room_type=RoomType.BEDROOM,
            boundary_polygon=[Point2D(x=0, y=5.5), Point2D(x=6.5, y=5.5), Point2D(x=6.5, y=9.0), Point2D(x=0, y=9.0)],
            floor_material_id="MAT-WOOD-01"
        ),
    ]

    gf_slab = Slab(
        slab_id="GF_SLAB_01",
        name="Ground Floor Foundation Slab",
        boundary_polygon=[Point2D(x=0, y=0), Point2D(x=12, y=0), Point2D(x=12, y=9), Point2D(x=0, y=9)],
        thickness_m=0.20,
        elevation_m=0.0,
        material_id="MAT-CONC-01"
    )

    gf_stair = Staircase(
        stair_id="GF_STAIR_01",
        start=Point2D(x=7.5, y=6.0),
        end=Point2D(x=7.5, y=8.8),
        width_m=1.0,
        total_rise_m=3.0,
        num_steps=16,
        material_id="MAT-WOOD-01"
    )

    level_0 = FloorLevel(
        level_id="lvl_ground",
        name="Ground Floor",
        elevation_m=0.0,
        floor_to_floor_height_m=3.0,
        walls=gf_walls,
        rooms=gf_rooms,
        slabs=[gf_slab],
        stairs=[gf_stair]
    )

    # First Floor (Level 2)
    ff_walls = [
        Wall(
            wall_id="FF_W_FRONT",
            name="First Floor Front Wall",
            wall_type=WallType.EXTERIOR,
            start=Point2D(x=0.0, y=0.0),
            end=Point2D(x=12.0, y=0.0),
            thickness_m=0.23,
            height_m=3.0,
            openings=[
                Window(opening_id="FF_W_MBR", name="Master Bedroom French Window", width_m=2.4, height_m=2.1, sill_height_m=0.0, offset_along_wall_m=4.0)
            ],
            material_id="MAT-PLAS-01"
        ),
        Wall(
            wall_id="FF_W_RIGHT",
            name="First Floor East Wall",
            wall_type=WallType.EXTERIOR,
            start=Point2D(x=12.0, y=0.0),
            end=Point2D(x=12.0, y=9.0),
            thickness_m=0.23,
            height_m=3.0,
            material_id="MAT-PLAS-01"
        ),
        Wall(
            wall_id="FF_W_BACK",
            name="First Floor Back Wall",
            wall_type=WallType.EXTERIOR,
            start=Point2D(x=12.0, y=9.0),
            end=Point2D(x=0.0, y=9.0),
            thickness_m=0.23,
            height_m=3.0,
            openings=[
                Window(opening_id="FF_W_BED2", name="Bedroom 2 Window", width_m=1.6, height_m=1.2, sill_height_m=0.9, offset_along_wall_m=6.0)
            ],
            material_id="MAT-PLAS-01"
        ),
        Wall(
            wall_id="FF_W_LEFT",
            name="First Floor West Wall",
            wall_type=WallType.EXTERIOR,
            start=Point2D(x=0.0, y=9.0),
            end=Point2D(x=0.0, y=0.0),
            thickness_m=0.23,
            height_m=3.0,
            material_id="MAT-PLAS-01"
        ),
    ]

    ff_rooms = [
        Room(
            room_id="FF_R_MBR",
            name="Master Bedroom Suite",
            room_type=RoomType.MASTER_BEDROOM,
            boundary_polygon=[Point2D(x=0, y=0), Point2D(x=7, y=0), Point2D(x=7, y=5.5), Point2D(x=0, y=5.5)],
            floor_material_id="MAT-WOOD-01"
        ),
        Room(
            room_id="FF_R_TERRACE",
            name="Covered Open Balcony",
            room_type=RoomType.BALCONY,
            boundary_polygon=[Point2D(x=7, y=0), Point2D(x=12, y=0), Point2D(x=12, y=5.5), Point2D(x=7, y=5.5)],
            floor_material_id="MAT-TILE-01"
        ),
    ]

    ff_slab = Slab(
        slab_id="FF_SLAB_01",
        name="First Floor Inter-story Slab",
        boundary_polygon=[Point2D(x=0, y=0), Point2D(x=12, y=0), Point2D(x=12, y=9), Point2D(x=0, y=9)],
        thickness_m=0.15,
        elevation_m=3.0,
        material_id="MAT-CONC-01"
    )

    roof_slab = Slab(
        slab_id="ROOF_SLAB_01",
        name="Roof Terrace Slab",
        boundary_polygon=[Point2D(x=0, y=0), Point2D(x=12, y=0), Point2D(x=12, y=9), Point2D(x=0, y=9)],
        thickness_m=0.15,
        elevation_m=6.0,
        material_id="MAT-CONC-01"
    )

    level_1 = FloorLevel(
        level_id="lvl_first",
        name="Level 02 (First Floor)",
        elevation_m=3.0,
        floor_to_floor_height_m=3.0,
        walls=ff_walls,
        rooms=ff_rooms,
        slabs=[ff_slab, roof_slab]
    )

    building = Building(
        name="Contemporary 2-Story Residential Villa",
        levels=[level_0, level_1]
    )

    project = ArchitecturalProject(
        project_id="STU-SAMPLE-2BHK",
        project_name="Contemporary 2-Story Villa (Seed Model)",
        source_filename="villa_canonical.dxf",
        source_format=DrawingFormat.DXF,
        units=MeasurementUnit.METERS,
        scale_verified=True,
        building=building,
        metadata={"seed": True, "architect": "BuildSmartAI Studio"}
    )

    _save_project(project)
    logger.info("Seeded canonical sample 3D Studio project STU-SAMPLE-2BHK.")
    return {
        "status": "success",
        "project_id": project.project_id,
        "message": "Sample 3D Studio model seeded successfully.",
        "bim_tree": project.to_bim_tree_json()
    }


# ---------------------------------------------------------------------------
# Conversational Architectural Modification Endpoints
# ---------------------------------------------------------------------------

class ModificationRequest(BaseModel):
    prompt: str = Field(..., json_schema_extra={"example": "Add 1 floor with 3 bedrooms and 1 washroom"})
    custom_dimensions: Optional[Dict[str, Any]] = None


@router.get("/room-library")
def get_room_library():
    """Retrieve configurable architectural room dimensions and building standards."""
    return room_library.to_dict()


@router.post("/projects/{project_id}/preview-modification")
def preview_project_modification(project_id: str, payload: ModificationRequest):
    """
    Stage 1: Generate architectural modification proposal before applying.
    Calculates space requirements, footprint boundaries, and validation results.
    """
    proj = _load_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail=f"Studio Project {project_id} not found")

    result = modification_engine.preview_modification(proj, payload.prompt)
    return result


@router.post("/projects/{project_id}/apply-modification")
def apply_project_modification(project_id: str, payload: ModificationRequest):
    """
    Stage 2: Deterministically apply the modification to the building model,
    regenerate 3D geometry, commit to revision history, and return updated project.
    """
    proj = _load_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail=f"Studio Project {project_id} not found")

    updated_proj, result = modification_engine.apply_modification(
        project=proj,
        user_prompt=payload.prompt,
        custom_dimensions=payload.custom_dimensions
    )
    _save_project(updated_proj)
    return result


@router.get("/projects/{project_id}/revisions")
def get_project_revisions(project_id: str):
    """Retrieve revision history stack for project."""
    history = modification_engine.revision_manager.get_revision_history(project_id)
    return {"project_id": project_id, "revisions": history}


@router.post("/projects/{project_id}/undo")
def undo_project_modification(project_id: str):
    """Roll back to previous valid architectural building revision."""
    restored_proj = modification_engine.revision_manager.undo(project_id)
    if not restored_proj:
        raise HTTPException(status_code=400, detail="Cannot undo: already at earliest revision or no history.")

    _save_project(restored_proj)
    scene = SceneCompiler.compile_threejs_scene(restored_proj)
    bim_tree = restored_proj.to_bim_tree_json()
    history = modification_engine.revision_manager.get_revision_history(project_id)
    return {
        "status": "success",
        "message": "Project rolled back to previous revision.",
        "scene": scene,
        "bim_tree": bim_tree,
        "history": history
    }


@router.post("/projects/{project_id}/redo")
def redo_project_modification(project_id: str):
    """Redo previously undone architectural building revision."""
    restored_proj = modification_engine.revision_manager.redo(project_id)
    if not restored_proj:
        raise HTTPException(status_code=400, detail="Cannot redo: already at latest revision.")

    _save_project(restored_proj)
    scene = SceneCompiler.compile_threejs_scene(restored_proj)
    bim_tree = restored_proj.to_bim_tree_json()
    history = modification_engine.revision_manager.get_revision_history(project_id)
    return {
        "status": "success",
        "message": "Project advanced to next revision.",
        "scene": scene,
        "bim_tree": bim_tree,
        "history": history
    }
