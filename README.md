# BuildSmartAI 🏗️

> **AI-Powered Multi-Agent Residential Construction Planning, Design & Site Intelligence Platform**

BuildSmartAI transforms unstructured customer requirements into a fully managed residential construction project using five specialised AI agents coordinated by a central orchestrator.

---

## Architecture

```
Builder / Contractor / Customer
          │
          ▼
BuildSmartAI Web Dashboard  (frontend/index.html — Tailwind + Three.js)
          │
          ▼
FastAPI Backend (main.py)   ←── REST API + Static asset serving
          │
          ▼
Central AI Orchestrator     ←── Routes requests, prevents loops, logs executions
     ┌────┴──────────────────────────────┐
     ▼           ▼           ▼           ▼           ▼
 Agent 1      Agent 2      Agent 3   Agent 4      Agent 5
 Project      Estimation   Design    Scheduling   Site Monitoring
 Planning    &Procurement  Agent     Agent        & Progress Agent
 Agent        Agent
     │           │           │           │           │
     └───────────┴───────────┴───────────┴───────────┘
                               │
                               ▼
                    Shared SQLite Database  (buildsmart.db)
                    + JSON data files       (data/)
                    + Generated artifacts   (generated_designs/, generated_reports/)
```

### Five AI Agents

| # | Agent | Responsibility |
|---|-------|----------------|
| 1 | **Project Planning Agent** | Parses natural-language requirements → structured project brief |
| 2 | **Estimation & Procurement Agent** | IS 1200 BOQ calculations → cost quotation PDF + Excel |
| 3 | **Design Agent** | Parametric 2D floor plan + OBJ 3D mesh; supports blueprint upload (CV Mode B) |
| 4 | **Scheduling Agent** | Critical Path Method (CPM/PERT) timeline with monsoon advisory |
| 5 | **Site Monitoring & Progress Agent** | Computer Vision worker & PPE detection; delay analysis |

---

### BuildSmart 3D Studio (AI Architectural 2D-to-3D Conversion & Modification)

BuildSmart 3D Studio converts 2D architectural drawings into editable, interactive, multi-floor 3D building models:
- **Formats Accepted**: CAD DXF, DWG pipeline, multi-page architectural PDF, high-resolution PNG/JPG drawings.
- **Architectural Element Extraction**: Parallel wall pairing, door/window detection, room polygon extraction, and automatic scale calibration.
- **Interactive 3D WebGL Viewport**: 360° orbit controls, pan/zoom, visual styles (Realistic PBR, Wireframe, X-Ray), view gizmo, exploded multi-story view, and BIM component property inspector.
- **AI Conversational Modification Engine**: Natural-language architectural commands (e.g., *"Add 1 floor with 3 bedrooms and 1 washroom"*, *"Increase Master Bedroom to 4.5 by 4.0 meters"*, *"Add staircase connecting ground floor to first floor"*) translated deterministically into spatial geometry with circulation passages, door/window openings, and staircase alignments.
- **Revision History**: Non-destructive snapshot manager with real-time Undo and Redo.
- **3D Model Export**: Native export to `.glb` (glTF 2.0 binary) and `.obj` / `.mtl`.

---

## Technology Stack

| Component | Technology |
|-----------|-----------|
| Backend API | Python 3.14+, FastAPI, Uvicorn |
| AI / NLP | Ollama + Llama 3.2 (graceful offline fallback) |
| Database | SQLAlchemy 2 + SQLite (dev) / PostgreSQL (prod) |
| Data Validation | Pydantic v2 |
| Computer Vision | OpenCV 5, Ultralytics YOLO (optional) |
| Calculations | IS 1200 deterministic Python engines (no ML for numbers) |
| Scheduling | NetworkX (CPM graph) |
| PDF Reports | ReportLab |
| Excel BOQ | openpyxl |
| 3D Viewer | Three.js + OrbitControls |
| Frontend | HTML5 + Tailwind CSS (single-page dashboard) |

---

## Quick Start

### 1 — Prerequisites

```powershell
# Python 3.11+ required (tested on 3.14.6)
python --version

# Install dependencies
pip install -r requirements.txt
```

### 2 — Configuration

```powershell
# Copy and edit the environment file
copy .env.example .env
# Edit .env — set JWT_SECRET_KEY to a long random string
```

### 3 — Initialise Database

```powershell
python -c "from database.connection import init_db; init_db()"
```

### 4 — (Optional) Set up Ollama for LLM NLP

> When Ollama is unavailable the system falls back to deterministic regex parsing — all agents still work.

```bash
# Install Ollama from https://ollama.ai
ollama pull llama3.2

# Start the Ollama server (runs on port 11434 by default)
ollama serve
```

### 5 — (Optional) YOLO Worker Detection

Download `yolov8n.pt` from [Ultralytics](https://github.com/ultralytics/assets/releases) and place it in the project root.  
When the file is absent the system uses contour-based silhouette detection automatically.

### 6 — Run the Server

```powershell
python main.py
# or
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Open **http://127.0.0.1:8000** in your browser.

---

## API Endpoints (Quick Reference)

### Projects

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/projects` | Create a new project |
| `GET`  | `/api/projects` | List all projects |
| `GET`  | `/api/projects/{id}` | Full project details |
| `POST` | `/api/projects/{id}/orchestrate-all` | Run full pipeline (all 5 agents) |

### Planning

| `POST` | `/api/projects/{id}/plan` | Planning Agent — parse requirements |

### Design

| Method | Endpoint |
|--------|----------|
| `POST` | `/api/projects/{id}/design/generate` |
| `GET`  | `/api/projects/{id}/design` |
| `POST` | `/api/projects/{id}/design/revise` |
| `POST` | `/api/projects/{id}/design/approve` |

### Estimation

| `POST` | `/api/projects/{id}/estimate` | Generate BOQ + Quotation |
| `GET`  | `/api/projects/{id}/boq` | Retrieve BOQ |
| `POST` | `/api/projects/{id}/quotation/approve` | Approve quotation |

### Procurement

| `GET`  | `/api/projects/{id}/procurement` | Shortage analysis + purchase orders |
| `POST` | `/api/projects/{id}/procurement/order` | Record a confirmed PO (human approval required) |

### Scheduling

| `POST` | `/api/projects/{id}/schedule` | CPM schedule generation |
| `GET`  | `/api/projects/{id}/schedule` | Retrieve schedule |

### Site Monitoring

| `POST` | `/api/projects/{id}/monitoring/upload` | Upload site image for CV analysis |
| `GET`  | `/api/projects/{id}/monitoring` | Latest observations |
| `GET`  | `/api/projects/{id}/monitoring/progress` | Delay analysis |

### Reports

| `GET`  | `/api/projects/{id}/reports` | List available reports |
| `GET`  | `/api/projects/{id}/reports/quotation-pdf` | Download PDF quotation |
| `GET`  | `/api/projects/{id}/reports/boq-excel` | Download Excel BOQ |
| `GET`  | `/api/projects/{id}/reports/floorplan-svg` | Download 2D SVG floor plan |

### Health

| `GET`  | `/api/health` | Platform health + agent list |

Interactive API docs: **http://127.0.0.1:8000/docs**

---

## Demo Workflow (curl)

```bash
# 1. Create project
curl -X POST http://127.0.0.1:8000/api/projects \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Modern 2BHK Villa",
    "client_name": "Mr. Sharma",
    "plot_area_sqft": 1200,
    "plot_length_ft": 40,
    "plot_width_ft": 30,
    "bhk_configuration": "2BHK",
    "floors": 1,
    "budget": 3500000,
    "raw_requirements": "2BHK on 1200 sqft with modern design"
  }'

# (Use returned project_id, e.g. BS-XXXX, in subsequent calls)

# 2. Run planning
curl -X POST http://127.0.0.1:8000/api/projects/BS-XXXX/plan

# 3. Generate design
curl -X POST http://127.0.0.1:8000/api/projects/BS-XXXX/design/generate

# 4. Approve design
curl -X POST http://127.0.0.1:8000/api/projects/BS-XXXX/design/approve

# 5. Generate BOQ + Quotation
curl -X POST http://127.0.0.1:8000/api/projects/BS-XXXX/estimate

# 6. Approve quotation
curl -X POST http://127.0.0.1:8000/api/projects/BS-XXXX/quotation/approve

# 7. Create CPM schedule
curl -X POST http://127.0.0.1:8000/api/projects/BS-XXXX/schedule \
  -H "Content-Type: application/json" \
  -d '{"start_date": "2026-12-01"}'

# 8. Download PDF quotation
curl -o quotation.pdf http://127.0.0.1:8000/api/projects/BS-XXXX/reports/quotation-pdf
```

---

## Running Tests

```powershell
# Full test suite (22 unit tests)
python -m pytest tests/ -v --tb=short

# Individual test modules
python -m pytest tests/test_planning.py -v
python -m pytest tests/test_design.py -v
python -m pytest tests/test_estimation.py -v
python -m pytest tests/test_scheduling.py -v
python -m pytest tests/test_monitoring.py -v
python -m pytest tests/test_orchestrator.py -v

# Full system integration test (requires FastAPI TestClient)
python -m pytest tests/test_full_system.py -v --tb=short
```

---

## Project Structure

```
BuildSmartAI/
├── main.py                        # FastAPI entrypoint + lifespan
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
│
├── agents/                        # AI Agent implementations
│   ├── base_agent.py
│   ├── orchestrator.py            # Central AI Orchestrator
│   ├── project_planning_agent.py  # Agent 1
│   ├── estimation_procurement_agent.py  # Agent 2
│   ├── scheduling_agent.py        # Agent 4
│   ├── site_monitoring_agent.py   # Agent 5
│   └── design_agent/             # Agent 3 (sub-package)
│       ├── design_agent.py
│       ├── design_planner.py
│       ├── constraint_validator.py
│       ├── floorplan_generator.py
│       └── design_revision.py
│
├── engines/                       # Deterministic calculation engines
│   ├── area_calculator.py         # Setbacks, zoning, permissible area
│   ├── quantity_calculator.py     # IS 1200 material quantities
│   ├── cost_calculator.py         # Cost estimation with GST
│   ├── geometry_engine.py         # 2D room geometry
│   ├── scheduling_engine.py       # NetworkX CPM/PERT
│   └── progress_analyzer.py      # Schedule vs actual comparison
│
├── vision/                        # Computer Vision pipeline
│   ├── model_loader.py            # YOLO / contour fallback
│   ├── worker_detection.py        # Personnel detection + annotation
│   └── ppe_detection.py           # Helmet & vest HSV analysis
│
├── design/                        # Design file processing
│   ├── plan_parser.py             # OpenCV blueprint contour extraction
│   ├── model_exporter.py          # OBJ/MTL + Three.js scene JSON
│   └── blender_generator.py       # Blender render script generator
│
├── reports/                       # Document generators
│   ├── quotation_generator.py     # ReportLab PDF quotation
│   ├── boq_generator.py           # openpyxl Excel BOQ
│   └── progress_report.py         # Site intelligence PDF
│
├── database/
│   ├── connection.py              # SQLAlchemy engine + session
│   ├── models.py                  # ORM models
│   └── repositories.py           # Data access layer
│
├── api/
│   ├── schemas/
│   │   ├── protocol.py            # AgentRequest / AgentResponse schemas
│   │   └── project_schemas.py    # Request/Response Pydantic models
│   └── routes/
│       ├── projects.py
│       ├── planning.py
│       ├── design.py
│       ├── estimation.py
│       ├── procurement.py         # ← Procurement API
│       ├── scheduling.py
│       ├── monitoring.py
│       └── reports.py
│
├── utils/
│   ├── logging_config.py
│   ├── ollama_client.py
│   ├── unit_converter.py
│   ├── security.py                # JWT scaffold
│   └── file_handler.py           # Upload validation
│
├── data/
│   ├── inventory.json             # Material catalogue with supplier info
│   ├── suppliers.json             # Supplier records
│   ├── sample_projects.json       # Demo project seed data
│   ├── project_tasks.json         # 14 canonical CPM construction tasks
│   └── expenses.json              # Sample cost breakdown (BS-1001)
│
├── frontend/
│   └── index.html                 # Single-page dashboard (Tailwind + Three.js)
│
├── tests/
│   ├── test_planning.py
│   ├── test_design.py
│   ├── test_estimation.py
│   ├── test_scheduling.py
│   ├── test_monitoring.py
│   ├── test_plan_parser.py
│   ├── test_orchestrator.py
│   └── test_full_system.py
│
├── uploads/                       # Uploaded site images (runtime)
├── generated_designs/             # SVG floor plans, OBJ models (runtime)
└── generated_reports/             # PDF quotations, Excel BOQ (runtime)
```

---

## Important Limitations & Disclaimers

> [!IMPORTANT]
> - **Regulatory values** (setbacks, FSI, ground coverage) are **indicative only**. Always verify with the relevant local municipal authority (MCGM, BBMP, HMDA, etc.) and a licensed architect before construction.
> - **Material quantities and costs** are calculated using IS 1200 engineering formulas and are **illustrative estimates**. Obtain quotations from actual suppliers before budgeting.
> - **Safety alerts** from the Site Monitoring Agent are **advisory indicators** for on-site safety officers. They do not constitute professional safety certification.
> - **Worker counts** reflect detected personnel in a single image frame and are not measures of labour productivity.
> - **No automatic payments or orders** are made by this system. All procurement actions require explicit human approval.
> - **Ollama / LLM** is used only for natural-language parsing. All structural and financial calculations use deterministic Python engines.

---

## Licence

BuildSmartAI is a proprietary platform. All rights reserved.  
Sample data and generated reports are for demonstration purposes only.
