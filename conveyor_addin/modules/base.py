"""ConveyorModule — the intelligent engineering object (OBJECTIVE 1).

Every conveyor is a connected equipment item with identity, envelope,
local frame, ports, engineering parameters, manufacturing metadata, and
BOM data. CAD bodies are views of this object, never the object itself.
"""

from __future__ import annotations

import copy
import dataclasses
from dataclasses import dataclass, field
from typing import Any, Dict

try:  # pytest / Add-In dir on sys.path (repo convention)
    from core import frames as _frames
except ImportError:  # Fusion: repo root on sys.path
    from conveyor_addin.core import frames as _frames  # type: ignore[no-redef]

try:
    from core.invariants import SCHEMA_VERSION
except ImportError:
    from conveyor_addin.core.invariants import SCHEMA_VERSION  # type: ignore[no-redef]

try:
    from core import serialization as _ser
except ImportError:
    from conveyor_addin.core import serialization as _ser  # type: ignore[no-redef]

try:
    from core.params import MODULE_TYPES
except ImportError:
    from conveyor_addin.core.params import MODULE_TYPES  # type: ignore[no-redef]

try:
    from docking.port import ConveyorPort
except ImportError:
    from conveyor_addin.docking.port import ConveyorPort  # type: ignore[no-redef]

__all__ = ["ConveyorModule", "IDENTITY_FRAME"]


def IDENTITY_FRAME() -> Dict[str, Any]:
    """Default local frame: origin at inlet floor-center, axes aligned."""
    return {
        "origin_mm": [0.0, 0.0, 0.0],
        "rotation_3x3": [list(row) for row in _frames.mat_identity()],
    }


@dataclass
class ConveyorModule:
    """Intelligent conveyor module (lengths in mm, see COORD §2)."""

    module_id: str
    module_type: str
    length: float
    width: float
    height: float
    coordinate_frame: Dict[str, Any] = field(default_factory=IDENTITY_FRAME)
    inlet_port: ConveyorPort | None = None
    outlet_port: ConveyorPort | None = None
    engineering_parameters: Dict[str, Any] = field(default_factory=dict)
    manufacturing_metadata: Dict[str, Any] = field(default_factory=dict)
    bom_data: Dict[str, Any] = field(default_factory=dict)
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.module_type not in MODULE_TYPES:
            raise ValueError(
                f"module_type {self.module_type!r} not in {list(MODULE_TYPES)}"
            )
        self.length = float(self.length)
        self.width = float(self.width)
        self.height = float(self.height)
        if self.length <= 0 or self.width <= 0 or self.height <= 0:
            raise ValueError(
                f"Module {self.module_id!r}: L/W/H must be positive, got "
                f"{self.length}/{self.width}/{self.height}"
            )
        frame = dict(self.coordinate_frame or IDENTITY_FRAME())
        frame.setdefault("origin_mm", [0.0, 0.0, 0.0])
        frame.setdefault(
            "rotation_3x3", [list(r) for r in _frames.mat_identity()]
        )
        object.__setattr__(self, "coordinate_frame", frame)

    # -- placement ----------------------------------------------------------
    def with_world_transform(
        self, rotation: _frames.Mat3, translation_mm: _frames.Vec3
    ) -> "ConveyorModule":
        """Copy placed by rigid ``(R, t)``: frame composed, ports moved."""
        new_frame = {
            "origin_mm": list(
                _frames.apply_transform(
                    rotation,
                    translation_mm,
                    tuple(self.coordinate_frame["origin_mm"]),
                )
            ),
            "rotation_3x3": [
                list(row)
                for row in _frames.mat_mul(
                    rotation, self.coordinate_frame["rotation_3x3"]
                )
            ],
        }

        def _move(port: ConveyorPort | None) -> ConveyorPort | None:
            if port is None:
                return None
            p = port.normalized()
            return dataclasses.replace(
                p,
                origin=_frames.apply_transform(rotation, translation_mm, p.origin),
                direction=_frames.mat_vec(rotation, p.direction),
                lateral_axis=_frames.mat_vec(rotation, p.lateral_axis),
                up=_frames.mat_vec(rotation, p.up),
            )

        return dataclasses.replace(
            self,
            coordinate_frame=new_frame,
            inlet_port=_move(self.inlet_port),
            outlet_port=_move(self.outlet_port),
        )

    # -- serialization ------------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        return {
            "module_id": self.module_id,
            "module_type": self.module_type,
            "length": self.length,
            "width": self.width,
            "height": self.height,
            "coordinate_frame": copy.deepcopy(self.coordinate_frame),
            "inlet_port": self.inlet_port.to_dict() if self.inlet_port else None,
            "outlet_port": self.outlet_port.to_dict() if self.outlet_port else None,
            "engineering_parameters": copy.deepcopy(self.engineering_parameters),
            "manufacturing_metadata": copy.deepcopy(self.manufacturing_metadata),
            "bom_data": dict(self.bom_data),
            "schema_version": self.schema_version,
        }

    @staticmethod
    def from_dict(payload: Dict[str, Any]) -> "ConveyorModule":
        data = _ser.migrate_module_dict(dict(payload))

        def _port(key: str) -> ConveyorPort | None:
            raw = data.get(key)
            if raw is None:
                return None
            return ConveyorPort.from_dict(raw)

        return ConveyorModule(
            module_id=str(data["module_id"]),
            module_type=str(data["module_type"]),
            length=float(data["length"]),
            width=float(data["width"]),
            height=float(data["height"]),
            coordinate_frame=dict(
                data.get("coordinate_frame", IDENTITY_FRAME())
            ),
            inlet_port=_port("inlet_port"),
            outlet_port=_port("outlet_port"),
            engineering_parameters=dict(data.get("engineering_parameters", {})),
            manufacturing_metadata=dict(data.get("manufacturing_metadata", {})),
            bom_data=dict(data.get("bom_data", {})),
            schema_version=str(data.get("schema_version", SCHEMA_VERSION)),
        )

    def to_json(self) -> str:
        return _ser.dumps(self.to_dict())

    @staticmethod
    def from_json(text: str) -> "ConveyorModule":
        return ConveyorModule.from_dict(_ser.loads(text))
