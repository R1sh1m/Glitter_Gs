"""Serialization + schema migration for ConveyorModule / ConveyorPort.

Schema versions:
    ``"0"``   — legacy pre-schema dicts (raw ``get_module_ports`` /
                ``get_curve_module_ports`` dicts with ``"normal"`` key and
                no ``schema_version``). Read-only; auto-migrated on load.
    ``"1.0"`` — current: ``lateral_axis`` naming, ``schema_version`` field,
                typed module envelope (see ``modules/base.py``).

``migrate_dict`` upgrades any readable version to current. ``dumps``/``loads``
round-trip through JSON. Unknown future versions raise ``ValueError`` —
never silently misread.
"""

from __future__ import annotations

import copy
import json
from typing import Any, Dict

try:  # pytest / Add-In dir on sys.path (repo convention)
    from core.invariants import READABLE_SCHEMA_VERSIONS, SCHEMA_VERSION
except ImportError:  # Fusion: repo root on sys.path
    from conveyor_addin.core.invariants import READABLE_SCHEMA_VERSIONS, SCHEMA_VERSION  # type: ignore[no-redef]

__all__ = [
    "CURRENT_SCHEMA_VERSION",
    "migrate_dict",
    "migrate_port_dict",
    "migrate_module_dict",
    "dumps",
    "loads",
    "is_current",
]

CURRENT_SCHEMA_VERSION = SCHEMA_VERSION

_LEGACY_NORMAL_TO_LATERAL = "lateral_axis"


def is_current(payload: Dict[str, Any]) -> bool:
    return payload.get("schema_version", "0") == CURRENT_SCHEMA_VERSION


def migrate_port_dict(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Migrate a single port dict to the current schema (pure, non-mutating)."""
    data = copy.deepcopy(payload)
    version = str(data.get("schema_version", "0"))
    if version not in READABLE_SCHEMA_VERSIONS:
        raise ValueError(
            f"Unsupported port schema_version {version!r}; "
            f"readable: {list(READABLE_SCHEMA_VERSIONS)}"
        )
    if "normal" in data and "lateral_axis" not in data:
        data[_LEGACY_NORMAL_TO_LATERAL] = data.pop("normal")
    data["schema_version"] = CURRENT_SCHEMA_VERSION
    migrated_from = payload.get("schema_version", "0")
    if str(migrated_from) != CURRENT_SCHEMA_VERSION:
        data["migrated_from"] = str(migrated_from)
    return data


def migrate_module_dict(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Migrate a module dict to the current schema (pure, non-mutating)."""
    data = copy.deepcopy(payload)
    version = str(data.get("schema_version", "0"))
    if version not in READABLE_SCHEMA_VERSIONS:
        raise ValueError(
            f"Unsupported module schema_version {version!r}; "
            f"readable: {list(READABLE_SCHEMA_VERSIONS)}"
        )
    for key in ("inlet_port", "outlet_port"):
        if isinstance(data.get(key), dict):
            data[key] = migrate_port_dict(data[key])
    data["schema_version"] = CURRENT_SCHEMA_VERSION
    migrated_from = payload.get("schema_version", "0")
    if str(migrated_from) != CURRENT_SCHEMA_VERSION:
        data["migrated_from"] = str(migrated_from)
    return data


def migrate_dict(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Auto-detect port vs module payload and migrate to current schema."""
    if not isinstance(payload, dict):
        raise TypeError(f"migrate_dict expects a dict, got {type(payload)!r}")
    if "inlet_port" in payload or "module_type" in payload:
        return migrate_module_dict(payload)
    if "origin_mm" in payload or "direction" in payload:
        return migrate_port_dict(payload)
    raise ValueError(
        "Unrecognized payload: needs module keys "
        "('inlet_port'/'module_type') or port keys ('origin_mm'/'direction')"
    )


def dumps(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True)


def loads(text: str) -> Dict[str, Any]:
    """Parse JSON and migrate to current schema (records ``migrated_from``)."""
    data = json.loads(text)
    return migrate_dict(data)
