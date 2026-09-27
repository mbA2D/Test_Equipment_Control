"""Stable profile identity and execution identifiers for battery tests."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping
from uuid import uuid4


PROFILE_RUNTIME_FIELDS = frozenset({
    "profile_id",
    "profile_version",
    "test_id",
    "session_id",
    "start_new_test",
    "institution_code",
    "directory",
    "cell_name",
    "eq_req_dict",
})


def new_profile_id() -> str:
    """Create an identifier for a reusable profile definition."""
    return f"profile-{uuid4()}"


def new_test_id() -> str:
    """Create an identifier for one test campaign."""
    return f"test-{uuid4()}"


def new_session_id() -> str:
    """Create an identifier for one execution attempt."""
    return f"session-{uuid4()}"


def profile_version(configuration: Mapping[str, Any]) -> str:
    """Return the deterministic version for the current profile settings."""
    payload = _profile_payload(configuration)
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return f"sha256:{hashlib.sha256(encoded.encode('utf-8')).hexdigest()}"


def _profile_payload(value: Any, key: str | None = None) -> Any:
    if key in PROFILE_RUNTIME_FIELDS:
        return None
    if isinstance(value, Mapping):
        return {
            str(item_key): _profile_payload(item_value, str(item_key))
            for item_key, item_value in sorted(value.items(), key=lambda item: str(item[0]))
            if str(item_key) not in PROFILE_RUNTIME_FIELDS
        }
    if isinstance(value, (list, tuple)):
        return [_profile_payload(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)
