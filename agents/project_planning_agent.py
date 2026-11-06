import re
from typing import Dict, Any, List
from agents.base_agent import BaseAgent
from api.schemas.protocol import AgentRequest, AgentResponse
from utils.ollama_client import OllamaClient
from utils.unit_converter import UnitConverter
from engines.area_calculator import AreaCalculator
from utils.logging_config import logger

class ProjectPlanningAgent(BaseAgent):
    """
    Agent 1: Project Planning Agent.
    Converts customer natural language requirements and plot dimensions into a structured
    residential construction project specification with regulatory constraint checking.
    """
    def __init__(self):
        super().__init__(name="project_planning_agent")
        self.ollama = OllamaClient()

    def process(self, request: AgentRequest) -> AgentResponse:
        logger.info(f"ProjectPlanningAgent processing request for {request.project_id}")
        inp = request.input
        raw_text = inp.get("raw_requirements", "")

        # 1. Parse requirements (LLM with deterministic fallback)
        parsed = self._extract_requirements(raw_text, inp)

        # 2. Derive plot dimensions and units
        plot_area, length_ft, width_ft = UnitConverter.compute_plot_dimensions(
            area_sqft=parsed.get("plot_area_sqft", 1200.0),
            length_ft=parsed.get("plot_length_ft"),
            width_ft=parsed.get("plot_width_ft")
        )

        # 3. Calculate regulatory setbacks and coverage
        zoning_info = AreaCalculator.calculate_setbacks_and_coverage(plot_area, length_ft, width_ft)

        # 4. Determine required rooms based on BHK configuration
        bhk = parsed.get("bhk_configuration", "2BHK")
        rooms = self._generate_default_room_schedule(bhk, parsed)

        # 5. Validate fit against permissible footprint
        floors_count = parsed.get("floors", 1)
        fit_validation = AreaCalculator.validate_room_fit(
            rooms=rooms,
            permissible_footprint_sqft=zoning_info["actual_permissible_footprint_sqft"],
            floors=floors_count
        )

        # 6. Missing parameters checklist
        missing_info = []
        if not parsed.get("road_facing"):
            missing_info.append("Road facing direction (e.g., North, East) not specified; assuming North.")
        if not parsed.get("soil_type"):
            missing_info.append("Soil test report not provided; assuming medium bearing capacity (150 kN/m2).")

        result_payload = {
            "project_id": request.project_id,
            "bhk_configuration": bhk,
            "floors": parsed.get("floors", 1),
            "budget": parsed.get("budget", 3500000.0),
            "architectural_style": parsed.get("architectural_style", "Modern Contemporary"),
            "plot": {
                "area_sqft": plot_area,
                "area_sqm": UnitConverter.sqft_to_sqm(plot_area),
                "length_ft": length_ft,
                "width_ft": width_ft,
                "road_facing": parsed.get("road_facing", "North"),
            },
            "zoning_constraints": zoning_info,
            "rooms": rooms,
            "area_validation": fit_validation,
            "preferences": {
                "parking": parsed.get("parking", True),
                "balcony": parsed.get("balcony", True),
                "garden": parsed.get("garden", False),
                "open_kitchen": parsed.get("open_kitchen", True)
            },
            "missing_parameters": missing_info,
            "status": "PLAN_STRUCTURED"
        }

        warnings = []
        if not fit_validation["is_valid"]:
            warnings.append(f"Proposed rooms exceed permissible footprint by {abs(fit_validation['margin_sqft'])} sq ft. Consider adding a second floor.")
        warnings.append("Bylaws and setback figures are guidelines and require verification by an authorized municipal surveyor.")

        return AgentResponse(
            project_id=request.project_id,
            execution_id=request.execution_id,
            agent=self.name,
            status="completed",
            result=result_payload,
            warnings=warnings,
            requires_approval=False
        )

    def _extract_requirements(self, raw_text: str, fallback_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extracts structured entities using Ollama if connected, otherwise uses deterministic regex NLP.
        """
        extracted = {}

        # Attempt Ollama extraction
        if self.ollama.is_connected and raw_text:
            prompt = f"""
            Extract residential construction requirements from this description into JSON:
            Text: "{raw_text}"
            Return keys:
            - bhk_configuration (e.g. "1BHK", "2BHK", "3BHK", "4BHK")
            - plot_area_sqft (number)
            - budget (number in currency units)
            - floors (integer)
            - architectural_style (string)
            - parking (boolean)
            - balcony (boolean)
            """
            llm_res = self.ollama.generate_json(prompt)
            if llm_res and isinstance(llm_res, dict):
                extracted.update(llm_res)

        # Fallback regex heuristics if missing
        if not extracted.get("bhk_configuration"):
            bhk_match = re.search(r"(\d)\s*BHK", raw_text, re.IGNORECASE)
            extracted["bhk_configuration"] = f"{bhk_match.group(1)}BHK" if bhk_match else fallback_dict.get("bhk_configuration", "2BHK")

        if not extracted.get("plot_area_sqft"):
            area_match = re.search(r"(\d[\d,]*)\s*(?:sq(?:uare)?\.?\s*(?:ft|feet)|sqft)", raw_text, re.IGNORECASE)
            if area_match:
                extracted["plot_area_sqft"] = float(area_match.group(1).replace(",", ""))
            else:
                extracted["plot_area_sqft"] = float(fallback_dict.get("plot_area_sqft", 1200.0))

        if not extracted.get("budget"):
            budget_lakh_match = re.search(r"(?:₹|rs\.?|inr)?\s*(\d+)\s*(?:lakh|lac)", raw_text, re.IGNORECASE)
            if budget_lakh_match:
                extracted["budget"] = float(budget_lakh_match.group(1)) * 100000.0
            else:
                extracted["budget"] = float(fallback_dict.get("budget", 3500000.0))

        extracted["floors"] = int(fallback_dict.get("floors", 1))
        extracted["architectural_style"] = fallback_dict.get("architectural_style", "Modern")
        extracted["parking"] = "parking" in raw_text.lower() or fallback_dict.get("parking", True)
        extracted["balcony"] = "balcony" in raw_text.lower() or fallback_dict.get("balcony", True)
        extracted["garden"] = "garden" in raw_text.lower() or fallback_dict.get("garden", False)
        extracted["open_kitchen"] = "open kitchen" in raw_text.lower() or fallback_dict.get("open_kitchen", True)

        return extracted

    def _generate_default_room_schedule(self, bhk: str, parsed: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Creates standard residential room schedules compliant with National Building Code minimums
        and optimized for residential floor footprints.
        """
        bhk_num = 2
        try:
            bhk_num = int(bhk[0])
        except Exception:
            pass

        rooms = [
            {"name": "Living & Dining Room", "min_sqft": 180, "ideal_dim": "13' x 14'"},
            {"name": "Kitchen", "min_sqft": 90, "ideal_dim": "9' x 10'"},
            {"name": "Master Bedroom", "min_sqft": 140, "ideal_dim": "11'6\" x 12'"},
            {"name": "Master Bathroom", "min_sqft": 40, "ideal_dim": "5' x 8'"},
        ]

        if bhk_num >= 2:
            rooms.append({"name": "Bedroom 2", "min_sqft": 120, "ideal_dim": "10' x 12'"})
            rooms.append({"name": "Common Bathroom", "min_sqft": 40, "ideal_dim": "5' x 8'"})

        if bhk_num >= 3:
            rooms.append({"name": "Bedroom 3", "min_sqft": 110, "ideal_dim": "10' x 11'"})
            rooms.append({"name": "Attached Bathroom 3", "min_sqft": 35, "ideal_dim": "5' x 7'"})

        if bhk_num >= 4:
            rooms.append({"name": "Bedroom 4 / Study", "min_sqft": 100, "ideal_dim": "10' x 10'"})

        if parsed.get("balcony", True):
            rooms.append({"name": "Balcony / Utility", "min_sqft": 40, "ideal_dim": "4' x 10'"})

        return rooms
