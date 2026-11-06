from datetime import datetime, timedelta
from typing import Dict, Any, List
import networkx as nx
from utils.logging_config import logger

class SchedulingEngine:
    """
    Deterministic Construction Scheduling Engine.
    Implements the Critical Path Method (CPM) using Directed Acyclic Graphs (DAG),
    computes Early/Late schedules, activity float, and generates Gantt timelines.
    """

    DEFAULT_STAGES = [
        {"id": "ACT-01", "name": "Site Survey, Clearing & Soil Compaction", "base_days": 7, "predecessors": [], "stage": "Substructure"},
        {"id": "ACT-02", "name": "Earthwork & Foundation Pit Excavation", "base_days": 10, "predecessors": ["ACT-01"], "stage": "Substructure"},
        {"id": "ACT-03", "name": "PCC Bedding & Isolated Footing Casting", "base_days": 14, "predecessors": ["ACT-02"], "stage": "Substructure"},
        {"id": "ACT-04", "name": "Plinth Beam Construction & Soil Backfilling", "base_days": 12, "predecessors": ["ACT-03"], "stage": "Substructure"},
        {"id": "ACT-05", "name": "RCC Columns & First Floor Slab Casting", "base_days": 24, "predecessors": ["ACT-04"], "stage": "Superstructure"},
        {"id": "ACT-06", "name": "External & Internal Brick Masonry", "base_days": 20, "predecessors": ["ACT-05"], "stage": "Superstructure"},
        {"id": "ACT-07", "name": "Electrical Conduiting & Plumbing Rough-ins", "base_days": 15, "predecessors": ["ACT-06"], "stage": "Services"},
        {"id": "ACT-08", "name": "Internal Plastering & External Rendering", "base_days": 18, "predecessors": ["ACT-06"], "stage": "Finishes"},
        {"id": "ACT-09", "name": "Vitrified Floor & Bathroom Wall Tiling", "base_days": 14, "predecessors": ["ACT-08"], "stage": "Finishes"},
        {"id": "ACT-10", "name": "Door Frames, Windows & Glazing Installation", "base_days": 10, "predecessors": ["ACT-08"], "stage": "Joinery"},
        {"id": "ACT-11", "name": "Interior & Exterior Emulsion Painting", "base_days": 14, "predecessors": ["ACT-09", "ACT-10"], "stage": "Finishes"},
        {"id": "ACT-12", "name": "Electrical Switches & Sanitary Fixture Fitting", "base_days": 8, "predecessors": ["ACT-07", "ACT-11"], "stage": "Services"},
        {"id": "ACT-13", "name": "Final Quality Inspection, Snagging & Cleaning", "base_days": 6, "predecessors": ["ACT-12"], "stage": "Handover"},
        {"id": "ACT-14", "name": "Client Handover & Formal Key Ceremony", "base_days": 2, "predecessors": ["ACT-13"], "stage": "Handover"}
    ]

    @classmethod
    def calculate_cpm_schedule(
        cls,
        start_date_str: str = "2026-12-01",
        builtup_sqft: float = 950.0,
        floors: int = 1,
        custom_stages: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        stages = custom_stages or cls.DEFAULT_STAGES

        # Scale durations slightly for larger footprints (> 1500 sqft)
        scale_factor = 1.0 + max(0.0, (builtup_sqft - 1000.0) / 3000.0)

        # Build NetworkX DiGraph
        G = nx.DiGraph()
        duration_map = {}
        stage_details = {}

        for s in stages:
            task_id = s["id"]
            scaled_dur = max(2, round(s["base_days"] * scale_factor))
            duration_map[task_id] = scaled_dur
            stage_details[task_id] = s
            G.add_node(task_id, duration=scaled_dur, name=s["name"], stage=s.get("stage", "General"))

            for pred in s.get("predecessors", []):
                G.add_edge(pred, task_id)

        # Check for circular dependencies
        if not nx.is_directed_acyclic_graph(G):
            raise ValueError("Circular task dependency detected in construction schedule sequence!")

        # 1. Forward Pass (Early Start, Early Finish)
        es = {}
        ef = {}
        topo_order = list(nx.topological_sort(G))

        for task in topo_order:
            preds = list(G.predecessors(task))
            if not preds:
                es[task] = 0
            else:
                es[task] = max(ef[p] for p in preds)
            ef[task] = es[task] + duration_map[task]

        project_duration_days = max(ef.values()) if ef else 0

        # 2. Backward Pass (Late Start, Late Finish)
        ls = {}
        lf = {}
        for task in reversed(topo_order):
            succs = list(G.successors(task))
            if not succs:
                lf[task] = project_duration_days
            else:
                lf[task] = min(ls[s] for s in succs)
            ls[task] = lf[task] - duration_map[task]

        # 3. Float & Critical Path
        slack = {}
        critical_tasks = []
        for task in topo_order:
            slack[task] = ls[task] - es[task]
            if slack[task] == 0:
                critical_tasks.append(task)

        # 4. Map Calendar Dates
        try:
            start_dt = datetime.strptime(start_date_str, "%Y-%m-%d")
        except Exception:
            start_dt = datetime(2026, 12, 1)

        end_dt = start_dt + timedelta(days=project_duration_days)

        scheduled_tasks = []
        for task in topo_order:
            task_start_dt = start_dt + timedelta(days=es[task])
            task_end_dt = start_dt + timedelta(days=ef[task])
            is_crit = slack[task] == 0

            scheduled_tasks.append({
                "id": task,
                "name": stage_details[task]["name"],
                "stage": stage_details[task]["stage"],
                "duration_days": duration_map[task],
                "predecessors": stage_details[task]["predecessors"],
                "early_start_day": es[task],
                "early_finish_day": ef[task],
                "start_date": task_start_dt.strftime("%Y-%m-%d"),
                "end_date": task_end_dt.strftime("%Y-%m-%d"),
                "slack_days": slack[task],
                "is_critical": is_crit
            })

        return {
            "start_date": start_dt.strftime("%Y-%m-%d"),
            "estimated_completion_date": end_dt.strftime("%Y-%m-%d"),
            "total_duration_calendar_days": project_duration_days,
            "total_tasks_count": len(scheduled_tasks),
            "critical_path_tasks": critical_tasks,
            "tasks": scheduled_tasks
        }
