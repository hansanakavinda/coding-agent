"""Session persistence manager for saving and resuming conversation histories."""

from dataclasses import asdict, dataclass
import datetime
import json
from pathlib import Path
from typing import Any
import uuid


@dataclass
class SessionData:
    """Stored representation of an agent session."""

    session_id: str
    created_at: str
    updated_at: str
    task: str
    messages: list[dict[str, Any]]
    iterations: int

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SessionData":
        return cls(
            session_id=data.get("session_id", ""),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            task=data.get("task", ""),
            messages=data.get("messages", []),
            iterations=data.get("iterations", 0),
        )


import hashlib

DEFAULT_CENTRAL_SESSIONS_DIR = Path.home() / ".free-coding-agent" / "sessions"


class SessionManager:
    """Handles saving, loading, and listing session checkpoints in centralized storage.

    Never stores session data in the user's project directory.
    """

    def __init__(
        self,
        project_root: Path,
        base_sessions_dir: Path | None = None,
    ) -> None:
        self.project_root = Path(project_root).resolve()
        base_dir = Path(base_sessions_dir) if base_sessions_dir else DEFAULT_CENTRAL_SESSIONS_DIR

        # Compute a unique, collision-free slug based on project name and canonical path hash
        norm_path = str(self.project_root).lower().replace("\\", "/")
        path_hash = hashlib.sha256(norm_path.encode("utf-8")).hexdigest()[:12]
        workspace_slug = f"{self.project_root.name}_{path_hash}"

        self.storage_dir = base_dir / workspace_slug
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        # Store workspace info mapping for inspection
        meta_file = self.storage_dir / "workspace.json"
        if not meta_file.exists():
            meta = {
                "project_name": self.project_root.name,
                "project_path": str(self.project_root),
                "slug": workspace_slug,
            }
            try:
                meta_file.write_text(json.dumps(meta, indent=2), encoding="utf-8")
            except Exception:
                pass

    def generate_session_id(self) -> str:
        """Create a compact, timestamped session identifier."""
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        rand = uuid.uuid4().hex[:6]
        return f"sess_{ts}_{rand}"

    def save_session(
        self,
        session_id: str,
        task: str,
        messages: list[dict[str, Any]],
        iterations: int,
    ) -> Path:
        """Persist session state to a JSON checkpoint file."""
        now = datetime.datetime.now().isoformat()
        filepath = self.storage_dir / f"{session_id}.json"

        # Check for existing creation timestamp and initial task title
        created_at = now
        task_title = task
        if filepath.exists():
            try:
                existing = json.loads(filepath.read_text(encoding="utf-8"))
                created_at = existing.get("created_at", now)
                task_title = existing.get("task") or task
            except Exception:
                pass

        session = SessionData(
            session_id=session_id,
            created_at=created_at,
            updated_at=now,
            task=task_title,
            messages=messages,
            iterations=iterations,
        )

        temp_file = self.storage_dir / f"{session_id}.tmp"
        temp_file.write_text(json.dumps(asdict(session), indent=2), encoding="utf-8")
        temp_file.replace(filepath)
        return filepath

    def load_session(self, session_id: str) -> SessionData | None:
        """Load an existing session by its session ID."""
        clean_id = session_id.strip()
        if not clean_id.endswith(".json"):
            filename = f"{clean_id}.json"
        else:
            filename = clean_id

        filepath = self.storage_dir / filename
        if not filepath.exists():
            return None

        try:
            data = json.loads(filepath.read_text(encoding="utf-8"))
            return SessionData.from_dict(data)
        except Exception:
            return None

    def list_sessions(self) -> list[dict[str, Any]]:
        """List all saved sessions ordered by most recently modified."""
        sessions: list[dict[str, Any]] = []
        if not self.storage_dir.exists():
            return sessions

        for path in self.storage_dir.glob("*.json"):
            if path.name == "workspace.json":
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                sessions.append(
                    {
                        "session_id": data.get("session_id", path.stem),
                        "updated_at": data.get("updated_at", ""),
                        "task": data.get("task", "(unknown)"),
                        "message_count": len(data.get("messages", [])),
                        "iterations": data.get("iterations", 0),
                    }
                )
            except Exception:
                continue

        # Sort descending by updated_at
        sessions.sort(key=lambda s: s["updated_at"], reverse=True)
        return sessions
