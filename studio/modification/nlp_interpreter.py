"""
studio.modification.nlp_interpreter
===================================
Natural Language Architectural Command Interpreter.
Leverages Ollama Llama 3.2 with structured JSON output constraints,
complemented by a deterministic regex parser fallback for offline/instant evaluation.
"""

import re
import json
from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from utils.ollama_client import OllamaClient
from utils.logging_config import logger


class ModificationOperation(str, Enum):
    ADD_FLOOR = "add_floor"
    ADD_ROOMS = "add_rooms"
    ADD_ATTACHED_BATH = "add_attached_bath"
    RESIZE_ROOM = "resize_room"
    REMOVE_ROOM = "remove_room"
    MOVE_ROOM = "move_room"
    ADD_STAIRCASE = "add_staircase"
    MOVE_STAIRCASE = "move_staircase"
    ADD_BALCONY = "add_balcony"
    CHANGE_HEIGHT = "change_height"
    UNKNOWN = "unknown"


class RequestedRoomItem(BaseModel):
    """Room type and count requested by user."""
    type: str = Field(..., description="bedroom, master_bedroom, washroom, kitchen, living_room, balcony")
    count: int = Field(1, ge=1, le=10)
    target_width_m: Optional[float] = None
    target_length_m: Optional[float] = None
    target_floor_index: Optional[int] = None


class ModificationIntent(BaseModel):
    """Structured architectural interpretation of natural language instruction."""
    raw_prompt: str
    operation: ModificationOperation
    floor_count: int = Field(0, description="Number of additional floors to add")
    floor_name: Optional[str] = None
    target_floor_index: Optional[int] = None
    rooms: List[RequestedRoomItem] = Field(default_factory=list)
    target_room_name: Optional[str] = None
    target_dimensions: Optional[Dict[str, float]] = None
    add_staircase_connection: bool = True
    preserve_existing_floors: bool = True
    notes: Optional[str] = None
    confidence: float = Field(1.0, ge=0.0, le=1.0)
    clarification_needed: Optional[str] = None


class NLPInterpreter:
    """
    Translates architectural user prompts into structured ModificationIntent.
    Uses LLM (Ollama Llama 3.2) when online, and deterministic architectural grammar parser as robust fallback.
    """

    WORD_TO_NUM = {
        "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
        "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
        "a": 1, "an": 1, "single": 1, "first": 1, "second": 2, "third": 3
    }

    def __init__(self):
        self.ollama = OllamaClient()

    def interpret(self, prompt: str, current_floor_count: int = 1) -> ModificationIntent:
        """Main interpretation pipeline with LLM prioritization and deterministic fallback."""
        clean_prompt = prompt.strip()
        logger.info(f"Interpreting architectural modification prompt: '{clean_prompt}'")

        # 1. Attempt deterministic rule parser first (instant, exact, zero hallucination)
        rule_intent = self._parse_deterministic(clean_prompt, current_floor_count)
        if rule_intent and rule_intent.operation != ModificationOperation.UNKNOWN:
            logger.info(f"Deterministic parser matched intent: {rule_intent.operation.value}")
            return rule_intent

        # 2. If prompt is complex, query LLM
        if self.ollama.is_available():
            llm_intent = self._query_llm(clean_prompt, current_floor_count)
            if llm_intent and llm_intent.operation != ModificationOperation.UNKNOWN:
                return llm_intent

        # 3. Fallback generic intent
        return ModificationIntent(
            raw_prompt=clean_prompt,
            operation=ModificationOperation.UNKNOWN,
            clarification_needed="Could not determine architectural operation. Try: 'Add 1 floor with 3 bedrooms and 1 washroom' or 'Increase master bedroom to 4.5 by 4 meters'."
        )

    def _parse_deterministic(self, prompt: str, current_floor_count: int) -> Optional[ModificationIntent]:
        """Deterministic NLP regex rules covering standard architectural requests."""
        p_lower = prompt.lower()

        # Rule 1: "Add [N] floor(s) with [rooms]..."
        floor_match = re.search(r"add\s+(\d+|one|two|three|a|an)\s+(?:additional\s+|more\s+)?floor", p_lower)
        if floor_match or ("add" in p_lower and "floor" in p_lower and ("bedroom" in p_lower or "washroom" in p_lower or "room" in p_lower)):
            num_floors = 1
            if floor_match:
                token = floor_match.group(1)
                num_floors = int(token) if token.isdigit() else self.WORD_TO_NUM.get(token, 1)

            rooms_requested = self._extract_room_counts(p_lower)
            target_floor_idx = current_floor_count
            floor_name = f"Level {target_floor_idx + 1}" if target_floor_idx > 0 else "Ground Floor"
            if target_floor_idx == 1:
                floor_name = "First Floor"
            elif target_floor_idx == 2:
                floor_name = "Second Floor"

            return ModificationIntent(
                raw_prompt=prompt,
                operation=ModificationOperation.ADD_FLOOR,
                floor_count=num_floors,
                floor_name=floor_name,
                target_floor_index=target_floor_idx,
                rooms=rooms_requested,
                add_staircase_connection=True,
                preserve_existing_floors=True,
                confidence=0.98
            )

        # Rule 2: "Increase [Room] [size] to [W] by [L] meters / feet" or "Resize [Room]..."
        resize_match = re.search(r"(?:increase|resize|enlarge|make|expand)\s+(?:the\s+)?([a-z0-9_\s]+?)\s+(?:size\s+)?to\s+(\d+(?:\.\d+)?)\s*(?:x|by|\*)\s*(\d+(?:\.\d+)?)\s*(?:m|meter|meters|ft|feet)?", p_lower)
        if resize_match:
            room_name = resize_match.group(1).strip()
            dim1 = float(resize_match.group(2))
            dim2 = float(resize_match.group(3))
            return ModificationIntent(
                raw_prompt=prompt,
                operation=ModificationOperation.RESIZE_ROOM,
                target_room_name=room_name,
                target_dimensions={"width": dim1, "length": dim2},
                confidence=0.95
            )

        # Rule 3: "Add [N] bedroom(s) / washroom(s) / attached bathroom" (to existing floor)
        if ("attached" in p_lower and ("washroom" in p_lower or "bathroom" in p_lower or "bath" in p_lower)) or (re.search(r"add\s+(?:\d+|one|two|three|a|an)\s+(?:bedroom|washroom|bathroom|attached|balcony|kitchen|living)", p_lower) and "floor" not in p_lower):
            rooms_requested = self._extract_room_counts(p_lower)
            if not rooms_requested and ("washroom" in p_lower or "bath" in p_lower):
                rooms_requested = [RequestedRoomItem(type="washroom", count=1)]
            op = ModificationOperation.ADD_ATTACHED_BATH if "attached" in p_lower else ModificationOperation.ADD_ROOMS
            return ModificationIntent(
                raw_prompt=prompt,
                operation=op,
                target_floor_index=0,
                rooms=rooms_requested,
                notes=prompt,
                confidence=0.92
            )

        # Rule 4: "Add staircase..." / "Connect staircase..."
        if "staircase" in p_lower or "stair" in p_lower:
            if "move" in p_lower or "shift" in p_lower:
                side = "left" if "left" in p_lower else "right" if "right" in p_lower else "center"
                return ModificationIntent(
                    raw_prompt=prompt,
                    operation=ModificationOperation.MOVE_STAIRCASE,
                    notes=f"Move staircase to {side} side",
                    confidence=0.90
                )
            if "add" in p_lower or "connect" in p_lower:
                return ModificationIntent(
                    raw_prompt=prompt,
                    operation=ModificationOperation.ADD_STAIRCASE,
                    add_staircase_connection=True,
                    notes=prompt,
                    confidence=0.95
                )

        # Rule 5: "Add balcony..."
        if "balcony" in p_lower and "add" in p_lower:
            return ModificationIntent(
                raw_prompt=prompt,
                operation=ModificationOperation.ADD_BALCONY,
                rooms=[RequestedRoomItem(type="balcony", count=1)],
                confidence=0.95
            )

        # Rule 6: "Remove [Room]..." / "Delete [Room]..."
        remove_match = re.search(r"(?:remove|delete|eliminate)\s+(?:one\s+|a\s+|the\s+)?([a-z0-9_\s]+)", p_lower)
        if remove_match:
            target = remove_match.group(1).strip()
            return ModificationIntent(
                raw_prompt=prompt,
                operation=ModificationOperation.REMOVE_ROOM,
                target_room_name=target,
                confidence=0.90
            )

        # Rule 7: "Increase height of building..."
        if "height" in p_lower and ("increase" in p_lower or "higher" in p_lower or "raise" in p_lower):
            return ModificationIntent(
                raw_prompt=prompt,
                operation=ModificationOperation.CHANGE_HEIGHT,
                target_dimensions={"height_increment_m": 0.5},
                confidence=0.90
            )

        return None

    def _extract_room_counts(self, text: str) -> List[RequestedRoomItem]:
        """Extract requested room types and integer counts from text."""
        items: List[RequestedRoomItem] = []
        room_patterns = [
            ("master_bedroom", r"(\d+|one|two|three|a|an)\s+(?:attached\s+)?master\s+bed(?:room)?s?"),
            ("bedroom", r"(\d+|one|two|three|four|five|a|an)\s+bed(?:room)?s?"),
            ("attached_bathroom", r"(\d+|one|two|three|a|an)\s+attached\s+(?:bath|washroom|bathroom)s?"),
            ("washroom", r"(\d+|one|two|three|four|a|an)\s+(?:common\s+)?(?:washroom|bathroom|toilet|wc|bath)s?"),
            ("kitchen", r"(\d+|one|a|an)\s+kitchens?"),
            ("living_room", r"(\d+|one|a|an)\s+(?:living|hall|lounge)s?"),
            ("balcony", r"(\d+|one|a|an)\s+balcon(?:y|ies)"),
        ]

        # Prevent double-counting "master bedroom" as "bedroom"
        matched_spans = []

        for r_type, pat in room_patterns:
            for m in re.finditer(pat, text):
                # Check overlapping spans
                if any(m.start() >= s and m.end() <= e for s, e in matched_spans):
                    continue
                token = m.group(1)
                count = int(token) if token.isdigit() else self.WORD_TO_NUM.get(token, 1)
                items.append(RequestedRoomItem(type=r_type, count=count))
                matched_spans.append((m.start(), m.end()))

        # Fallback: if user specified rooms without numbers, e.g. "three bedrooms and one washroom"
        if not items:
            if "bedroom" in text:
                items.append(RequestedRoomItem(type="bedroom", count=1))
            if "washroom" in text or "bath" in text:
                items.append(RequestedRoomItem(type="washroom", count=1))

        return items

    def _query_llm(self, prompt: str, current_floor_count: int) -> Optional[ModificationIntent]:
        """Structured LLM call with system prompt enforcing JSON schema."""
        system_prompt = (
            "You are an expert AI Architectural Assistant. Your job is to convert natural-language "
            "building modification instructions into strict JSON matching this schema:\n"
            "{\n"
            '  "operation": "add_floor" | "add_rooms" | "resize_room" | "remove_room" | "move_room" | "add_staircase" | "add_balcony" | "change_height",\n'
            '  "floor_count": int,\n'
            '  "floor_name": string,\n'
            '  "rooms": [{"type": "bedroom"|"master_bedroom"|"washroom"|"kitchen"|"living_room"|"balcony", "count": int}],\n'
            '  "target_room_name": string or null,\n'
            '  "target_dimensions": {"width": float, "length": float} or null,\n'
            '  "add_staircase_connection": boolean,\n'
            '  "preserve_existing_floors": boolean\n'
            "}\n"
            "Respond ONLY with valid JSON. Never output conversational remarks."
        )

        user_content = f"Current building floor count: {current_floor_count}. User request: '{prompt}'"

        try:
            raw_response = self.ollama.generate(
                prompt=f"{system_prompt}\n\nUser: {user_content}\n\nAssistant JSON:",
                temperature=0.0
            )
            # Clean JSON fences if present
            cleaned = re.sub(r"```json\s*", "", raw_response)
            cleaned = re.sub(r"```\s*", "", cleaned).strip()
            data = json.loads(cleaned)
            data["raw_prompt"] = prompt
            return ModificationIntent.model_validate(data)
        except Exception as e:
            logger.warning(f"LLM natural language parsing fell back: {e}")
            return None
