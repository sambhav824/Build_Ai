"""
studio.modification.revision_manager
===================================
Project Revision Control & Undo/Redo Manager.
Maintains an immutable snapshot history of architectural project states,
enabling non-destructive modifications, rollbacks, and redo operations.
"""

from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from studio.models.project import ArchitecturalProject, Building
from utils.logging_config import logger


class RevisionRecord:
    """A snapshot of project state at a particular revision version."""
    def __init__(self, version: int, prompt: str, summary: Dict[str, Any], snapshot_json: str):
        self.version = version
        self.timestamp = datetime.now(timezone.utc).isoformat()
        self.prompt = prompt
        self.summary = summary
        self.snapshot_json = snapshot_json

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "timestamp": self.timestamp,
            "prompt": self.prompt,
            "summary": self.summary
        }


class RevisionManager:
    """
    Manages undo/redo stacks and revision records for ArchitecturalProjects.
    """

    def __init__(self):
        # Maps project_id -> list of snapshots
        self._history: Dict[str, List[Dict[str, Any]]] = {}
        # Maps project_id -> current index in history
        self._pointers: Dict[str, int] = {}

    def initialize_project(self, project: ArchitecturalProject):
        """Register the baseline revision (v1) for a project."""
        p_id = project.project_id
        if p_id not in self._history:
            snapshot = project.model_dump_json()
            initial_record = {
                "version": 1,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "prompt": "Original Base Model",
                "summary": {"operation": "baseline", "notes": "Initial drawing model loaded."},
                "snapshot": snapshot
            }
            self._history[p_id] = [initial_record]
            self._pointers[p_id] = 0

    def record_revision(self, project: ArchitecturalProject, prompt: str, summary: Dict[str, Any]):
        """Commit a new validated modification to the project revision history."""
        p_id = project.project_id
        self.initialize_project(project)

        # Truncate any redo branch if we commit a new change from a middle state
        cur_ptr = self._pointers[p_id]
        self._history[p_id] = self._history[p_id][:cur_ptr + 1]

        next_version = len(self._history[p_id]) + 1
        snapshot = project.model_dump_json()

        entry = {
            "version": next_version,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "prompt": prompt,
            "summary": summary,
            "snapshot": snapshot
        }
        self._history[p_id].append(entry)
        self._pointers[p_id] = len(self._history[p_id]) - 1

        logger.info(f"Recorded revision v{next_version} for project {p_id}: '{prompt}'")

    def undo(self, project_id: str) -> Optional[ArchitecturalProject]:
        """Undo last modification, restoring previous valid project snapshot."""
        if project_id not in self._history:
            return None
        cur_ptr = self._pointers[project_id]
        if cur_ptr <= 0:
            logger.warning(f"Project {project_id} is already at earliest revision.")
            return None

        self._pointers[project_id] -= 1
        prev_entry = self._history[project_id][self._pointers[project_id]]
        logger.info(f"Undoing project {project_id} to revision v{prev_entry['version']}")
        return ArchitecturalProject.model_validate_json(prev_entry["snapshot"])

    def redo(self, project_id: str) -> Optional[ArchitecturalProject]:
        """Redo previously undone modification."""
        if project_id not in self._history:
            return None
        cur_ptr = self._pointers[project_id]
        if cur_ptr >= len(self._history[project_id]) - 1:
            logger.warning(f"Project {project_id} is at latest revision.")
            return None

        self._pointers[project_id] += 1
        next_entry = self._history[project_id][self._pointers[project_id]]
        logger.info(f"Redoing project {project_id} to revision v{next_entry['version']}")
        return ArchitecturalProject.model_validate_json(next_entry["snapshot"])

    def get_revision_history(self, project_id: str) -> List[Dict[str, Any]]:
        """Return list of revisions without full snapshot bodies."""
        if project_id not in self._history:
            return []
        cur_ptr = self._pointers.get(project_id, 0)
        return [
            {
                "version": item["version"],
                "timestamp": item["timestamp"],
                "prompt": item["prompt"],
                "summary": item["summary"],
                "is_active": idx == cur_ptr
            }
            for idx, item in enumerate(self._history[project_id])
        ]
