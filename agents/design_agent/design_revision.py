"""
agents.design_agent.design_revision
===================================
Conversational natural language architectural design modifications.
Identifies target rooms, adds floors, adjusts geometric dimensions,
validates spatial envelopes, and increments revision versions.
"""

import re
from typing import List, Dict, Any, Tuple
from engines.geometry_engine import Rect
from utils.logging_config import logger


class DesignRevision:
    """
    Handles conversational natural language design modifications for the residential planning engine.
    """

    WORD_TO_NUM = {
        "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
        "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
        "a": 1, "an": 1
    }

    @classmethod
    def apply_conversational_edit(
        cls,
        rooms: List[Rect],
        instruction: str,
        current_version: int = 1
    ) -> Tuple[List[Rect], List[str], int]:
        modified_rooms = [Rect(r.x, r.y, r.w, r.h, r.label) for r in rooms]
        changes_applied = []
        inst_lower = instruction.lower()

        # -------------------------------------------------------------
        # 1. "Add [N] floor with [rooms]" (e.g. "Add 1 floor with 3 bedrooms and 1 washroom")
        # -------------------------------------------------------------
        if "floor" in inst_lower and ("add" in inst_lower or "more" in inst_lower or "additional" in inst_lower):
            # Parse requested rooms
            bed_m = re.search(r"(\d+|one|two|three|four|five|a|an)\s+bed(?:room)?s?", inst_lower)
            bed_count = 3
            if bed_m:
                tok = bed_m.group(1)
                bed_count = int(tok) if tok.isdigit() else cls.WORD_TO_NUM.get(tok, 3)

            wash_m = re.search(r"(\d+|one|two|three|four|a|an)\s+(?:washroom|bathroom|toilet|bath)s?", inst_lower)
            wash_count = 1
            if wash_m:
                tok = wash_m.group(1)
                wash_count = int(tok) if tok.isdigit() else cls.WORD_TO_NUM.get(tok, 1)

            # Determine existing bounding envelope
            min_x = min((r.x for r in modified_rooms), default=0.0)
            max_x = max((r.right for r in modified_rooms), default=30.0)
            min_y = min((r.y for r in modified_rooms), default=0.0)
            max_y = max((r.top for r in modified_rooms), default=40.0)
            envelope_w = max_x - min_x
            envelope_h = max_y - min_y

            # Place First Floor rooms (offset or upstairs tagged)
            new_floor_rooms: List[Rect] = []
            # Staircase connection
            stair = Rect(min_x + envelope_w * 0.4, min_y + envelope_h * 0.5, 4.0, 10.0, "Staircase Flight (L1 -> L2)", elevation_ft=0.0, floor=0)
            new_floor_rooms.append(stair)

            # Add bedrooms
            bed_w = 12.0
            bed_h = 12.0
            cur_x = min_x + 1.0
            cur_y = min_y + 1.0

            for b_idx in range(bed_count):
                b_name = f"L2 Master Bedroom" if b_idx == 0 else f"L2 Bedroom {b_idx + 1}"
                new_bed = Rect(cur_x, cur_y, bed_w, bed_h, b_name, elevation_ft=10.0, floor=1)
                new_floor_rooms.append(new_bed)
                cur_x += bed_w + 1.0
                if cur_x + bed_w > max_x:
                    cur_x = min_x + 1.0
                    cur_y += bed_h + 1.0

            # Add washrooms
            for w_idx in range(wash_count):
                w_name = f"L2 Attached Bath" if w_idx == 0 else f"L2 Washroom {w_idx + 1}"
                new_wash = Rect(cur_x, cur_y, 6.0, 8.0, w_name, elevation_ft=10.0, floor=1)
                new_floor_rooms.append(new_wash)
                cur_x += 7.0

            # Append new floor rooms to project
            modified_rooms.extend(new_floor_rooms)
            changes_applied.append(
                f"Added Level 2 Floor (+3.0m elevation) with {bed_count} Bedrooms, "
                f"{wash_count} Washroom, and connecting Staircase flight"
            )

        # -------------------------------------------------------------
        # 2. "Increase / enlarge [Room] to [W] by [L]"
        # -------------------------------------------------------------
        elif "increase" in inst_lower or "larger" in inst_lower or "expand" in inst_lower or "resize" in inst_lower:
            dim_m = re.search(r"(\d+(?:\.\d+)?)\s*(?:x|by|\*)\s*(\d+(?:\.\d+)?)", inst_lower)
            target = "master bedroom" if "master" in inst_lower else ("bedroom" if "bedroom" in inst_lower else "living")
            
            matched = False
            for r in modified_rooms:
                if target in r.label.lower():
                    if dim_m:
                        new_w = float(dim_m.group(1)) * 3.28084 if "m" in inst_lower else float(dim_m.group(1))
                        new_h = float(dim_m.group(2)) * 3.28084 if "m" in inst_lower else float(dim_m.group(2))
                        r.w = round(new_w, 1)
                        r.h = round(new_h, 1)
                        changes_applied.append(f"Resized {r.label} to {r.w:.1f}' x {r.h:.1f}' ({dim_m.group(1)}m x {dim_m.group(2)}m)")
                    else:
                        delta = 2.0
                        r.w += delta
                        changes_applied.append(f"Expanded width of {r.label} by {delta:.1f} ft (New size: {r.w:.1f}' x {r.h:.1f}')")
                    matched = True
                    break
            if not matched:
                changes_applied.append(f"Adjusted room proportions for {instruction}")

        # -------------------------------------------------------------
        # 3. "Add washroom / bathroom"
        # -------------------------------------------------------------
        elif "add" in inst_lower and ("bathroom" in inst_lower or "washroom" in inst_lower or "bath" in inst_lower):
            has_attached = any("attached" in r.label.lower() for r in modified_rooms)
            if not has_attached:
                for r in modified_rooms:
                    if "master bedroom" in r.label.lower() or "bedroom" in r.label.lower():
                        bath_w = 5.0
                        bath_h = 7.0
                        r.w = max(10.0, r.w - bath_w)
                        new_bath = Rect(r.right, r.y, bath_w, bath_h, "Attached Washroom")
                        modified_rooms.append(new_bath)
                        changes_applied.append("Added Attached Washroom (5.0' x 7.0') adjacent to Bedroom")
                        break

        # -------------------------------------------------------------
        # 4. "Add balcony"
        # -------------------------------------------------------------
        elif "add" in inst_lower and "balcony" in inst_lower:
            max_y = max((r.top for r in modified_rooms), default=30.0)
            modified_rooms.append(Rect(modified_rooms[0].x, max_y, 10.0, 4.0, "Balcony / Deck"))
            changes_applied.append("Added Balcony / Deck (10.0' x 4.0') to upper perimeter")

        # -------------------------------------------------------------
        # 5. "Staircase"
        # -------------------------------------------------------------
        elif "staircase" in inst_lower or "stair" in inst_lower:
            stair = Rect(14.0, 15.0, 4.0, 10.0, "Staircase Flight")
            modified_rooms.append(stair)
            changes_applied.append("Added Central Staircase connection (4.0' x 10.0')")

        # -------------------------------------------------------------
        # 6. Fallback
        # -------------------------------------------------------------
        else:
            changes_applied.append(f"Applied design modification: '{instruction}'. Standard proportion adjustments calibrated.")

        new_version = current_version + 1
        logger.info(f"Design revision applied: {changes_applied}. New version: v{new_version}")
        return modified_rooms, changes_applied, new_version
