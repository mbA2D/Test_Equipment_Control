"""Persistent per-cell allocation state for BDF test continuation."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


MANIFEST_FILENAME = "cell_manifest.json"
MANIFEST_VERSION = 1


def manifest_path(cell_directory: str | Path) -> Path:
    """Return the manifest path inside a cell's output directory."""
    return Path(cell_directory) / MANIFEST_FILENAME


def load_manifest(cell_directory: str | Path) -> dict[str, Any]:
    """Load a manifest, treating a missing or invalid one as recoverable."""
    path = manifest_path(cell_directory)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
    return payload if isinstance(payload, dict) else {}


def save_manifest(cell_directory: str | Path, manifest: Mapping[str, Any]) -> Path:
    """Atomically replace the cell manifest with a JSON-serializable payload."""
    directory = Path(cell_directory)
    directory.mkdir(parents=True, exist_ok=True)
    path = manifest_path(directory)
    temporary_path = path.with_name(f".{path.name}.tmp")
    temporary_path.write_text(
        json.dumps(dict(manifest), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    os.replace(temporary_path, path)
    return path


def manifest_timestamped_update(manifest: Mapping[str, Any], **updates: Any) -> dict[str, Any]:
    """Return manifest data with a refreshed update timestamp."""
    result = dict(manifest)
    result.update(updates)
    result["updated_at_utc"] = utc_now()
    return result


def utc_now() -> str:
    """Return an ISO-8601 UTC timestamp for manifest state."""
    return datetime.now(timezone.utc).isoformat()
