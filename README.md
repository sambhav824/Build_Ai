# 🏗️ BuildSmartAI

> **Your AI-powered construction crew — from a simple idea to blueprints, budgets, 3D models, and site monitoring.**

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Three.js](https://img.shields.io/badge/Three.js-WebGL-black?style=flat&logo=three.js&logoColor=white)](https://threejs.org/)
[![OpenCV](https://img.shields.io/badge/OpenCV-Computer_Vision-5C3EE8?style=flat&logo=opencv&logoColor=white)](https://opencv.org/)
[![Repository](https://img.shields.io/badge/GitHub-sambhav824%2FBuild__Ai-blue?style=flat&logo=github)](https://github.com/sambhav824/Build_Ai)

---

## 💡 What is BuildSmartAI?

Building a home is exciting, but coordinating between architects, contractors, quantity estimators, and site supervisors can quickly become overwhelming.

**BuildSmartAI** solves this by acting as your complete digital construction team. Simply type what you want in everyday language—for example:

> *"I want a modern 2BHK villa on a 30x40 ft plot with a spacious living room, open kitchen, parking, and a budget of ₹35 lakh."*

Within moments, BuildSmartAI coordinates a team of **5 specialized AI agents** to plan your rooms, draw 2D floor plans, generate interactive 3D models, compute precise material and cost estimates (BOQ), map out a day-by-day construction timeline, and even inspect site photos for safety gear.

---

## 🤖 Meet Your AI Construction Crew

Instead of relying on a single generic AI, BuildSmartAI uses dedicated agents that each specialize in one crucial phase of construction:

```
                          You (Client / Builder / Architect)
                                          │
                                          ▼
                       BuildSmartAI Web Dashboard & 3D Studio
                                          │
                                          ▼
                             Central AI Coordinator
                   ┌──────────────┬───────────────┬──────────────┐
                   ▼              ▼               ▼              ▼
            📋 Planning     💰 Estimation   🎨 3D Design   📅 Scheduling
               Agent           & Buying        Agent           Agent
                   │              │               │              │
                   └──────────────┴───────┬───────┴──────────────┘
                                          ▼
                                🦺 Site Monitoring
                                       Agent
```

| Agent | Role | How It Helps You |
|---|---|---|
| **1. 📋 Planning Agent** | Requirements Interpreter | Listens to your vision, checks local setback & zoning guidelines, and structures your dream home into an actionable project brief. |
| **2. 💰 Estimation & Procurement Agent** | Quantity Surveyor | Calculates required cement, sand, bricks, and steel using **IS 1200** standards. Produces instant PDF quotations and Excel spreadsheets. *(No AI hallucination for math!)* |
| **3. 🎨 Design & 3D Studio Agent** | Digital Architect | Draws 2D floor plans and renders interactive 3D WebGL models. Can also read uploaded blueprint drawings or PDFs. |
| **4. 📅 Scheduling Agent** | Project Manager | Computes the Critical Path Method (CPM) construction schedule, sets milestones, and warns you in advance about monsoon season delays. |
| **5. 🦺 Site Monitoring Agent** | Safety & Progress Inspector | Scans real construction site photos using Computer Vision to count workers, check for helmets/reflective vests, and flag schedule delays. |

---

## 🏢 BuildSmart 3D Studio: Walk Through Your Plan

BuildSmartAI includes **3D Studio**, a web-based architectural workspace right in your browser:

- **Upload Real Drawings**: Drop in CAD DXF files, architectural PDFs, or clear blueprint images.
- **Interactive 3D Viewport**: Orbit, pan, zoom, view exploded multi-story levels, or inspect room dimensions.
- **Talk to Your Model**: Give instructions in plain English (e.g., *"Add a first floor with 2 bedrooms"*, *"Make the master bedroom 4x5 meters"*), and see the 3D model update automatically.
- **Export Anytime**: Download ready-to-use `.glb` (3D web model) or `.obj` files to open in Blender or AutoCAD.

---

## ⚡ Quick Start

You can run BuildSmartAI on your laptop in just a few minutes.

### 1. Clone the Repository
```bash
git clone https://github.com/sambhav824/Build_Ai.git
cd Build_Ai
```

### 2. Install Dependencies
Make sure you have **Python 3.11+** installed:
```bash
pip install -r requirements.txt
```

### 3. Set Up Environment & Database
```bash
# Copy example environment file
cp .env.example .env

# Initialize the local database (creates sample project BS-1001)
python -c "from database.connection import init_db; init_db()"
```

### 4. Start the Application
```bash
python main.py
```

Now open **[http://localhost:8000](http://localhost:8000)** in your browser! 🎉

- **Main Dashboard**: [http://localhost:8000](http://localhost:8000)
- **Interactive 3D Studio**: [http://localhost:8000/studio](http://localhost:8000/studio)
- **API Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 🔌 Optional Add-ons

BuildSmartAI is designed to work completely out of the box with zero external services required. If you'd like extra capabilities, you can enable these optional extras:

- **Local LLM via Ollama**:
  If you want rich conversational responses with local AI:
  ```bash
  ollama pull llama3.2
  ollama serve
  ```
  *(If Ollama is not running, BuildSmartAI automatically falls back to built-in deterministic parsers so everything keeps working smoothly.)*

- **Advanced Site AI with YOLO**:
  For deep neural-network PPE and worker detection, drop `yolov8n.pt` into the root directory. If absent, the built-in computer vision engine handles detection automatically.

---

## 🛠️ Tech Stack at a Glance

- **Backend**: FastAPI, Python 3.11+, Uvicorn
- **Frontend**: Clean HTML5, Tailwind CSS, Three.js (WebGL 3D Viewer)
- **Data & Storage**: SQLAlchemy 2, SQLite (dev) / PostgreSQL (prod)
- **Engineering Engines**:
  - Deterministic IS 1200 building material calculation formulas
  - NetworkX for CPM/PERT critical path project scheduling
  - ReportLab for PDF quotes & openpyxl for Excel spreadsheets
- **Vision Pipeline**: OpenCV & Ultralytics YOLO

---

## 🧪 Running Tests

A complete automated test suite is included:

```bash
# Run all tests
python -m pytest tests/ -v
```

---

## 📁 Project Layout

```
BuildSmartAI/
├── main.py               # FastAPI application entry point
├── api/                  # REST API endpoints (projects, design, estimation, etc.)
├── agents/               # The 5 specialized AI construction agents
├── engines/              # Deterministic math engines (IS 1200 formulas, CPM graphs)
├── vision/               # Computer vision for worker & PPE safety inspection
├── reports/              # Automatic PDF & Excel export generators
├── database/             # SQLite database models and queries
├── frontend/
│   ├── index.html        # Main interactive web dashboard
│   ├── studio.html       # BuildSmart 3D Studio viewer & modifier
│   └── js/               # Frontend logic and Three.js 3D renderers
└── tests/                # Test suite
```

---

## 🤝 Responsible Engineering

- **Real Math, Not Guesswork**: Material quantities, structural setbacks, and financial calculations are derived using deterministic formulas (IS 1200) rather than generative text guesses.
- **Human-in-the-Loop**: Generated purchase orders and final design revisions require your review and explicit approval.
- **Safety First**: Site monitoring alerts are advisory tools designed to assist on-site engineers and safety officers.

---

## 📄 License & Contributing

Built with ❤️ for architects, builders, and aspiring home owners.  
Contributions, issues, and ideas are warmly welcome! Feel free to open an issue or pull request on [GitHub](https://github.com/sambhav824/Build_Ai).
