"""BDF row construction, fixed CSV output, and metadata sidecars."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import pandas as pd


REQUIRED_COLUMNS = (
    "Test Time / s",
    "Voltage / V",
    "Current / A",
)

RECOMMENDED_COLUMNS = (
    "Unix Time / s",
    "Cycle Count / 1",
    "Step Count / 1",
)

OPTIONAL_COLUMNS = (
    "Step ID",
    "Step Time / s",
    "Step Type",
    "Surface Temperature T1 / degC",
    "Surface Temperature T2 / degC",
    "Surface Temperature T3 / degC",
    "Surface Temperature T4 / degC",
    "Surface Temperature T5 / degC",
    "Cycle Charging Capacity / Ah",
    "Cycle Discharging Capacity / Ah",
    "Cycle Charging Energy / Wh",
    "Cycle Discharging Energy / Wh",
)

BDF_COLUMNS = REQUIRED_COLUMNS + RECOMMENDED_COLUMNS + OPTIONAL_COLUMNS

TEMPERATURE_COLUMNS = tuple(
    column for column in OPTIONAL_COLUMNS if column.startswith("Surface Temperature")
)

CAPACITY_ENERGY_COLUMNS = (
    "Cycle Charging Capacity / Ah",
    "Cycle Discharging Capacity / Ah",
    "Cycle Charging Energy / Wh",
    "Cycle Discharging Energy / Wh",
)

METADATA_SCHEMA = "test_equipment_control.bdf_metadata"
METADATA_VERSION = "0.1"


def metadata_path(data_path: str | Path) -> Path:
    """Return the JSON-LD sidecar path paired with a BDF CSV file."""
    return Path(data_path).with_suffix(".meta.jsonld")


def temperature_source_map(equipment: Mapping[str, Any]) -> dict[str, str]:
    """Map configured temperature equipment to BDF surface-temperature slots."""
    source_keys: list[str] = []
    if equipment.get("dmm_t") is not None:
        source_keys.append("Temperature")
    for index in range(100):
        source_key = f"dmm_t{index}"
        if equipment.get(source_key) is None:
            break
        source_keys.append(source_key)

    return {
        TEMPERATURE_COLUMNS[index]: source_key
        for index, source_key in enumerate(source_keys[:len(TEMPERATURE_COLUMNS)])
    }


def build_bdf_row(
        measurement: Mapping[str, Any],
        *,
        test_time_s: float,
        cycle_count: int,
        step_count: int,
        step_id: int,
        step_time_s: float,
        step_type: str,
        temperature_sources: Mapping[str, str],
    ) -> dict[str, Any]:
    """Convert an internal measurement into one fixed-schema BDF row."""
    row = {column: None for column in BDF_COLUMNS}
    row.update({
        "Test Time / s": test_time_s,
        "Voltage / V": measurement.get("Voltage"),
        "Current / A": measurement.get("Current"),
        "Unix Time / s": measurement.get("Unix_Timestamp"),
        "Cycle Count / 1": cycle_count,
        "Step Count / 1": step_count,
        "Step ID": step_id,
        "Step Time / s": step_time_s,
        "Step Type": step_type,
    })

    for bdf_column, source_key in temperature_sources.items():
        row[bdf_column] = measurement.get(source_key)

    for column in CAPACITY_ENERGY_COLUMNS:
        row[column] = measurement.get(column, 0.0)

    return row


def build_temperature_metadata(
        temperature_sources: Mapping[str, str],
) -> dict[str, dict[str, str]]:
    """Describe temperature columns and their logical surface locations."""
    metadata = {}
    for column, source_key in temperature_sources.items():
        slot = column.removeprefix("Surface Temperature ").removesuffix(" / degC")
        metadata[column] = {
            "source_equipment_key": source_key,
            "measurement_kind": "surface_temperature",
            "placement": slot,
            "physical_location": "unspecified",
        }
    return metadata


def validate_bdf_dataframe(
        dataframe: pd.DataFrame,
        *,
        require_fixed_headers: bool = True,
) -> dict[str, Any]:
    """Validate the project's fixed BDF CSV schema and sequence semantics.

    ``batterydf`` remains the authoritative package-level validator.  This
    project check covers the fixed headers and the cycle/step fields that are
    intentionally project-specific or newer than the installed package's
    canonical field registry.
    """
    errors: list[str] = []
    actual_columns = tuple(str(column) for column in dataframe.columns)
    if require_fixed_headers and actual_columns != BDF_COLUMNS:
        missing = [column for column in BDF_COLUMNS if column not in actual_columns]
        unexpected = [column for column in actual_columns if column not in BDF_COLUMNS]
        if missing:
            errors.append(f"missing columns: {', '.join(missing)}")
        if unexpected:
            errors.append(f"unexpected columns: {', '.join(unexpected)}")
        if not missing and not unexpected:
            errors.append("columns are not in the fixed BDF order")

    numeric_columns = (
        "Test Time / s",
        "Voltage / V",
        "Current / A",
        "Unix Time / s",
        "Cycle Count / 1",
        "Step Count / 1",
        "Step ID",
        "Step Time / s",
        *CAPACITY_ENERGY_COLUMNS,
        *TEMPERATURE_COLUMNS,
    )
    for column in numeric_columns:
        if column not in dataframe.columns:
            continue
        values = pd.to_numeric(dataframe[column], errors="coerce")
        if values.notna().any() and values.isna().any():
            errors.append(f"{column} contains non-numeric values")

    monotonic_columns = (
        "Test Time / s",
        "Unix Time / s",
        "Cycle Count / 1",
        "Step Count / 1",
        "Step ID",
    )
    for column in monotonic_columns:
        if column not in dataframe.columns:
            continue
        values = pd.to_numeric(dataframe[column], errors="coerce").dropna()
        if not values.is_monotonic_increasing:
            errors.append(f"{column} must be monotonic non-decreasing")

    if {"Step Count / 1", "Step Time / s"}.issubset(dataframe.columns):
        step_counts = pd.to_numeric(dataframe["Step Count / 1"], errors="coerce")
        step_times = pd.to_numeric(dataframe["Step Time / s"], errors="coerce")
        for step_count, values in step_times.groupby(step_counts):
            if not values.is_monotonic_increasing:
                errors.append(
                    f"Step Time / s must be monotonic within Step Count / 1={step_count}"
                )

    for column in ("Cycle Count / 1", "Step Count / 1", "Step ID"):
        if column in dataframe.columns:
            values = pd.to_numeric(dataframe[column], errors="coerce").dropna()
            if (values < 1).any():
                errors.append(f"{column} must contain positive values")

    return {"ok": not errors, "errors": errors}


def build_cycle_metadata(
        *,
        data_path: str | Path,
        institution_code: str,
        cell_name: str,
        cycle_count: int,
        cycle_settings: list[Mapping[str, Any]],
        equipment: Mapping[str, Any],
        temperature_sources: Mapping[str, str],
        start_time_utc: str,
        status: str = "running",
        end_time_utc: str | None = None,
        profile_id: str | None = None,
        profile_version: str | None = None,
        test_id: str | None = None,
        session_id: str | None = None,
        continued_from_test_id: str | None = None,
) -> dict[str, Any]:
    """Build project metadata that is embedded in the official JSON-LD sidecar."""
    steps = []
    for step_id, settings in enumerate(cycle_settings, start=1):
        steps.append({
            "step_id": step_id,
            "step_type": settings["bdf_step_type"],
            "display_name": settings.get("cycle_display"),
            "settings": _json_safe(settings),
        })

    equipment_metadata = {}
    for role, device in equipment.items():
        if device is not None:
            identification = getattr(device, "eq_idn", None) or getattr(device, "inst_idn", None)
            parts = [part.strip() for part in identification.split(",")] if isinstance(identification, str) else []
            manufacturer = getattr(device, "manufacturer", None)
            model = getattr(device, "model_number", None) or getattr(device, "model", None)
            serial = getattr(device, "serial_number", None)
            firmware = getattr(device, "firmware_version", None)
            if len(parts) >= 3:
                manufacturer = manufacturer or parts[0]
                model = model or parts[1]
                serial = serial or parts[2]
            if len(parts) >= 4:
                firmware = firmware or parts[3]
            equipment_metadata[role] = {
                "driver": type(device).__name__,
                "class_name": getattr(device, "class_name", None),
                "manufacturer": manufacturer,
                "instrument_model": model,
                "serial_number": serial,
                "firmware_version": firmware,
                "identification": identification,
                "equipment_id": getattr(device, "equipment_id", None),
                "resource_id": getattr(device, "resource_id", None)
                or getattr(getattr(device, "inst", None), "resource_name", None),
                "instrument_channel": getattr(device, "instrument_channel", None),
            }

    return {
        "metadata_schema": METADATA_SCHEMA,
        "metadata_version": METADATA_VERSION,
        "data_file": Path(data_path).name,
        "institution_code": institution_code,
        "identity": {
            "profile_id": profile_id,
            "profile_version": profile_version,
            "test_id": test_id,
            "session_id": session_id,
            "continued_from_test_id": continued_from_test_id,
        },
        "cell": {
            "name": cell_name,
        },
        "test": {
            "cycle_count": cycle_count,
            "type": cycle_settings[0].get("cycle_display") if cycle_settings else "UNKNOWN",
            "status": status,
            "start_time_utc": start_time_utc,
            "end_time_utc": end_time_utc,
            "steps": steps,
        },
        "equipment": equipment_metadata,
        "temperature_sensors": build_temperature_metadata(temperature_sources),
        "measurement": {
            "current_sign_convention": "positive_charge_negative_discharge",
            "capacity_energy_integration": "right_endpoint_current_voltage_times_delta_time",
            "time_reference": "Test Time / s is elapsed from test start",
        },
    }


def write_metadata(data_path: str | Path, metadata: Mapping[str, Any]) -> Path:
    """Write official BDF JSON-LD metadata with project-specific details."""
    output_path = metadata_path(data_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        from bdf.metadata import Creator, DataDownload, Dataset
    except ImportError:
        _write_fallback_jsonld(output_path, data_path, metadata)
        return output_path

    institution_code = str(metadata.get("institution_code", "LOCAL"))
    cell_name = str(metadata.get("cell", {}).get("name", "UNKNOWN"))
    dataset = Dataset(
        title=f"Battery test {cell_name} cycle {metadata.get('test', {}).get('cycle_count', 'UNKNOWN')}",
        creators=[Creator(name=institution_code, type="Organization")],
        description="Battery cycling time-series data in the Battery Data Format.",
        version=METADATA_VERSION,
        variable_measured=list(REQUIRED_COLUMNS + RECOMMENDED_COLUMNS + OPTIONAL_COLUMNS),
    )
    dataset.save_jsonld(
        output_path,
        distributions=[DataDownload(
            url=Path(data_path).name,
            name=Path(data_path).name,
            encoding_format="text/csv",
        )],
        extra_fields={"testEquipmentControl": dict(metadata)},
    )
    return output_path


def read_metadata(data_path: str | Path) -> dict[str, Any]:
    """Read the project metadata payload from a BDF sidecar."""
    path = metadata_path(data_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload.get("testEquipmentControl", payload)


def utc_now() -> str:
    """Return an ISO-8601 UTC timestamp for metadata."""
    return datetime.now(timezone.utc).isoformat()


def _json_safe(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return str(value)


def _write_fallback_jsonld(
        output_path: Path,
        data_path: str | Path,
        metadata: Mapping[str, Any],
) -> None:
    """Write a compatible sidecar when optional batterydf is unavailable."""
    payload = {
        "@context": ["https://schema.org/", "http://www.w3.org/ns/csvw"],
        "@type": "schema:Dataset",
        "schema:name": Path(data_path).name,
        "schema:distribution": [{
            "@type": "schema:DataDownload",
            "schema:contentUrl": Path(data_path).name,
            "schema:encodingFormat": "text/csv",
        }],
        "testEquipmentControl": _json_safe(metadata),
    }
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
