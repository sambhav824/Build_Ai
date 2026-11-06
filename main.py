import os
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from database.connection import init_db, SessionLocal
from database.repositories import ProjectRepository
from database.models import Project
from utils.logging_config import logger

# Import API routes
from api.routes import projects, planning, design, estimation, scheduling, monitoring, reports, procurement, studio

BASE_DIR = Path(__file__).resolve().parent
UPLOADS_DIR = BASE_DIR / "uploads"
DESIGNS_DIR = BASE_DIR / "generated_designs"
REPORTS_DIR = BASE_DIR / "generated_reports"
ASSETS_DIR = BASE_DIR / "frontend" / "assets"

# Ensure directories exist immediately at startup
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
DESIGNS_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
ASSETS_DIR.mkdir(parents=True, exist_ok=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize shared database
    init_db()
    logger.info("BuildSmartAI database initialized.")

    # Seed initial test sample project BS-1001 if not already present
    db = SessionLocal()
    try:
        sample = db.query(Project).filter(Project.id == "BS-1001").first()
        if not sample:
            ProjectRepository.create_project(
                db=db,
                project_id="BS-1001",
                name="Modern 2BHK Residential Villa",
                client_name="Mr. Rushikesh K.",
                plot_area_sqft=1200.0,
                plot_length_ft=40.0,
                plot_width_ft=30.0,
                bhk_configuration="2BHK",
                floors=1,
                budget=3500000.0,
                architectural_style="Modern Contemporary",
                raw_requirements=(
                    "I want a modern 2BHK residential house on a 1,200 sq. ft. plot with two bedrooms, "
                    "two bathrooms, living room, kitchen, dining space, balcony and parking. My budget is ₹35 lakh."
                )
            )
            logger.info("Seeded canonical sample project BS-1001.")
    finally:
        db.close()

    yield

app = FastAPI(
    title="BuildSmartAI Platform",
    description="AI-Powered Multi-Agent Residential Construction Planning, Design & Site Intelligence Platform",
    version="1.0.0",
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers
app.include_router(projects.router)
app.include_router(planning.router)
app.include_router(design.router)
app.include_router(estimation.router)
app.include_router(scheduling.router)
app.include_router(monitoring.router)
app.include_router(reports.router)
app.include_router(procurement.router)
app.include_router(studio.router)

# Mount Static Asset Directories using verified absolute paths
app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")
app.mount("/generated_designs", StaticFiles(directory=str(DESIGNS_DIR)), name="generated_designs")
app.mount("/generated_reports", StaticFiles(directory=str(REPORTS_DIR)), name="generated_reports")
app.mount("/assets", StaticFiles(directory=str(ASSETS_DIR)), name="assets")
app.mount("/frontend", StaticFiles(directory=str(BASE_DIR / "frontend")), name="frontend")
app.mount("/js", StaticFiles(directory=str(BASE_DIR / "frontend" / "js")), name="js")

# Serve Web Dashboard
@app.get("/")
def serve_dashboard():
    index_path = BASE_DIR / "frontend" / "index.html"
    return FileResponse(str(index_path))

@app.get("/studio")
def serve_studio():
    studio_path = BASE_DIR / "frontend" / "studio.html"
    if studio_path.exists():
        return FileResponse(str(studio_path))
    return FileResponse(str(BASE_DIR / "frontend" / "index.html"))

@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "platform": "BuildSmartAI",
        "version": "1.0.0",
        "agents": [
            "project_planning_agent",
            "estimation_procurement_agent",
            "design_agent",
            "scheduling_agent",
            "site_monitoring_agent"
        ]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
