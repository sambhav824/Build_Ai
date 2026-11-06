"""
studio.modification
===================
Advanced AI Conversational Architectural Modification Engine.
"""

from studio.modification.room_library import RoomLibrary, RoomDimensionSpec, DEFAULT_ROOM_LIBRARY
from studio.modification.nlp_interpreter import NLPInterpreter, ModificationIntent, ModificationOperation
from studio.modification.layout_planner import LayoutPlanner
from studio.modification.floor_generator import FloorGenerator
from studio.modification.revision_manager import RevisionManager
from studio.modification.modification_engine import ModificationEngine

__all__ = [
    "RoomLibrary",
    "RoomDimensionSpec",
    "DEFAULT_ROOM_LIBRARY",
    "NLPInterpreter",
    "ModificationIntent",
    "ModificationOperation",
    "LayoutPlanner",
    "FloorGenerator",
    "RevisionManager",
    "ModificationEngine",
]
