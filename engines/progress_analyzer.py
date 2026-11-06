from datetime import datetime
from typing import Dict, Any, List

class ProgressAnalyzer:
    """
    Construction Site Progress & Delay Analytics Engine.
    Correlates actual visual stage observations with the CPM baseline schedule,
    distinguishing between:
    - Observed Delay: Physical stage completion behind planned finish date.
    - Reported Delay: Field blocker reported by site engineers (e.g. rain, labour strike).
    - Predicted Delay: Downstream critical path slippage projected from current variance.
    """

    STAGE_ORDER = [
        "Site Survey & Clearing",
        "Excavation",
        "Foundation",
        "Plinth Beam",
        "Structural RCC Columns & Slab",
        "Brick Masonry",
        "Plumbing & Electrical Rough-ins",
        "Plastering",
        "Flooring & Tiling",
        "Doors & Windows",
        "Painting & Finishing",
        "Handover"
    ]

    @classmethod
    def compare_planned_vs_actual(
        cls,
        planned_tasks: List[Dict[str, Any]],
        observed_stage: str,
        current_date_str: str = None,
        reported_blockers: List[str] = None
    ) -> Dict[str, Any]:
        today_dt = datetime.strptime(current_date_str, "%Y-%m-%d") if current_date_str else datetime.now()

        # Identify which planned task corresponds to current date
        current_planned_task = None
        for t in planned_tasks:
            t_start = datetime.strptime(t["start_date"], "%Y-%m-%d")
            t_end = datetime.strptime(t["end_date"], "%Y-%m-%d")
            if t_start <= today_dt <= t_end:
                current_planned_task = t
                break

        if not current_planned_task and planned_tasks:
            # Fallback to nearest task
            current_planned_task = planned_tasks[min(len(planned_tasks) - 1, 4)]

        # Index comparison between observed stage and planned task
        obs_idx = 4 # Default Structural
        for idx, s in enumerate(cls.STAGE_ORDER):
            if s.lower() in observed_stage.lower():
                obs_idx = idx
                break

        planned_idx = 4
        planned_name = current_planned_task["name"] if current_planned_task else "Structural RCC Columns & Slab"
        for idx, s in enumerate(cls.STAGE_ORDER):
            if s.lower() in planned_name.lower():
                planned_idx = idx
                break

        stage_variance = obs_idx - planned_idx
        # Estimate days variance
        variance_days = stage_variance * 12 # approx 12 days per stage

        if stage_variance == 0:
            schedule_health = "ON_TRACK"
        elif stage_variance > 0:
            schedule_health = "AHEAD_OF_SCHEDULE"
        else:
            schedule_health = "DELAYED"

        observed_delay_days = max(0, -variance_days)
        reported_blockers = reported_blockers or []
        reported_delay_days = len(reported_blockers) * 3 # 3 days impact per major blocker
        predicted_delay_days = observed_delay_days + reported_delay_days

        delay_analysis = {
            "current_evaluation_date": today_dt.strftime("%Y-%m-%d"),
            "planned_active_stage": planned_name,
            "visually_observed_stage": observed_stage,
            "schedule_health": schedule_health,
            "observed_delay_days": observed_delay_days,
            "reported_delay_days": reported_delay_days,
            "predicted_critical_path_delay_days": predicted_delay_days,
            "reported_blockers": reported_blockers,
            "recommended_mitigation": (
                "Deploy additional masonry shift and expedite plastering mortar batching."
                if predicted_delay_days > 0 else "Maintain current planned pace and weekly site safety inspections."
            )
        }

        return delay_analysis
