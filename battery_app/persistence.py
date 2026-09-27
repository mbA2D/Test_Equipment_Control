"""Versioned, queue-free persistence for GUI configuration."""

import json
from pathlib import Path
from typing import Any


class ConfigurationStore:
    """Read and write serializable test and equipment configurations."""

    schema_version = 3

    def save_json(self, payload: dict[str, Any], filename: str | Path) -> Path:
        path = Path(filename)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return path

    def load_json(self, filename: str | Path) -> dict[str, Any]:
        payload = json.loads(Path(filename).read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Configuration file must contain a JSON object")
        return payload

    def save_test_configuration(self, configuration: dict[str, Any], filename: str | Path) -> Path:
        return self.save_json(
            {"schema_version": self.schema_version, "test_configuration": configuration},
            filename,
        )

    def load_test_configuration(self, filename: str | Path) -> dict[str, Any]:
        payload = self.load_json(filename)
        schema_version = payload.get("schema_version")
        if schema_version != self.schema_version:
            raise ValueError(
                "Test profiles require schema version "
                f"{self.schema_version}; got {schema_version!r}"
            )
        unexpected_fields = sorted(set(payload) - {"schema_version", "test_configuration"})
        if unexpected_fields:
            raise ValueError(
                "Test profile envelope contains unsupported fields: "
                + ", ".join(unexpected_fields)
            )
        configuration = payload.get("test_configuration")
        if not isinstance(configuration, dict):
            raise ValueError("Test profile envelope requires an object test_configuration")
        return configuration

    def save_equipment_assignment(
        self,
        connected_equipment: list[dict[str, Any]],
        assignments: dict[int, dict[str, Any] | None],
        filename: str | Path,
    ) -> Path:
        equipment = {
            str(item["local_id"]): {
                key: value
                for key, value in item.items()
                if key not in {"queue_in", "response_queue", "response_routes", "owners"}
            }
            for item in connected_equipment
        }
        serializable_assignments = {}
        for channel, assignment in assignments.items():
            serializable_assignments[str(channel)] = self._remove_queue_handles(assignment)
        self._validate_equipment_identities(
            {int(local_id): descriptor for local_id, descriptor in equipment.items()},
            {int(channel): assignment for channel, assignment in serializable_assignments.items()},
        )
        return self.save_json(
            {
                "schema_version": self.schema_version,
                "connected_equipment_dict": equipment,
                "res_ids_dict": serializable_assignments,
            },
            filename,
        )

    def load_equipment_assignment(self, filename: str | Path) -> dict[str, Any]:
        payload = self.load_json(filename)
        schema_version = payload.get("schema_version")
        if schema_version != self.schema_version:
            raise ValueError(
                "Equipment assignments require schema version "
                f"{self.schema_version}; got {schema_version!r}"
            )

        connected_equipment = {
            int(key): value for key, value in payload["connected_equipment_dict"].items()
        }
        assignments = {
            int(key): value for key, value in payload["res_ids_dict"].items()
        }
        self._validate_equipment_identities(connected_equipment, assignments)
        return {
            "connected_equipment_dict": connected_equipment,
            "res_ids_dict": assignments,
        }

    @staticmethod
    def _validate_equipment_identities(
        connected_equipment: dict[int, dict[str, Any]],
        assignments: dict[int, dict[str, Any] | None],
    ) -> None:
        """Require stable identities and canonical channels for every assignment."""
        equipment_ids = {}
        for local_id, descriptor in connected_equipment.items():
            equipment_id = descriptor.get("equipment_id") if isinstance(descriptor, dict) else None
            if not isinstance(equipment_id, str) or not equipment_id:
                raise ValueError(f"Connected equipment {local_id} is missing equipment_id")
            if equipment_id in equipment_ids:
                raise ValueError(f"Duplicate equipment_id in connected equipment: {equipment_id}")
            channels = descriptor.get("instrument_channels") if isinstance(descriptor, dict) else None
            if not isinstance(channels, list) or not channels:
                raise ValueError(f"Connected equipment {local_id} is missing instrument_channels")
            if any(
                not isinstance(channel, int) or isinstance(channel, bool) or channel < 0
                for channel in channels
            ):
                raise ValueError(f"Connected equipment {local_id} has invalid instrument_channels")
            if channels != [0] and channels != list(range(1, len(channels) + 1)):
                raise ValueError(
                    f"Connected equipment {local_id} must use canonical instrument channels"
                )
            equipment_ids[equipment_id] = channels

        for battery_channel, assignment in assignments.items():
            if assignment is None:
                continue
            if not isinstance(assignment, dict):
                raise ValueError(f"Assignment for battery channel {battery_channel} must be an object")
            for role, descriptor in assignment.items():
                if descriptor is None:
                    continue
                res_id = descriptor.get("res_id") if isinstance(descriptor, dict) else None
                equipment_id = res_id.get("equipment_id") if isinstance(res_id, dict) else None
                if equipment_id not in equipment_ids:
                    raise ValueError(
                        f"Assignment for channel {battery_channel}, role {role} "
                        "does not reference a connected equipment_id"
                    )
                eq_ch = res_id.get("eq_ch") if isinstance(res_id, dict) else None
                if (
                    not isinstance(eq_ch, int)
                    or isinstance(eq_ch, bool)
                    or eq_ch not in equipment_ids[equipment_id]
                ):
                    raise ValueError(
                        f"Assignment for channel {battery_channel}, role {role} "
                        "must reference a valid canonical eq_ch"
                    )

    @classmethod
    def _remove_queue_handles(cls, value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: cls._remove_queue_handles(item)
                for key, item in value.items()
                if key not in {"queue_in", "response_queue", "client_id"}
            }
        if isinstance(value, list):
            return [cls._remove_queue_handles(item) for item in value]
        return value
