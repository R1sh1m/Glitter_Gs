"""Formal port data model — every module exposes inlet/outlet ConveyorPorts.

Terminology (``Docs/COORDINATE_SYSTEM.md`` §3): ``direction`` (flow, x),
``lateral_axis`` (y = up × direction), ``up`` (z). The legacy dict key
``"normal"`` is accepted ONLY via ``from_legacy_dict()`` and maps to
``lateral_axis`` — new code must never emit ``"normal"``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict

try:  # pytest / Add-In dir on sys.path (repo convention)
    from core.errors import PortDefinitionError
except ImportError:  # Fusion: repo root on sys.path
    from conveyor_addin.core.errors import PortDefinitionError  # type: ignore[no-redef]

try:
    from core import frames as _frames
except ImportError:
    from conveyor_addin.core import frames as _frames  # type: ignore[no-redef]

try:
    from core.invariants import SCHEMA_VERSION
except ImportError:
    from conveyor_addin.core.invariants import SCHEMA_VERSION  # type: ignore[no-redef]

try:
    from core import serialization as _ser
except ImportError:
    from conveyor_addin.core import serialization as _ser  # type: ignore[no-redef]

__all__ = ["ConveyorPort"]


def _vec(value: Any, name: str) -> _frames.Vec3:
    try:
        x, y, z = value
    except Exception:
        raise PortDefinitionError(f"Port {name} must be (x, y, z), got {value!r}")
    return (float(x), float(y), float(z))


@dataclass(frozen=True)
class ConveyorPort:
    """Intelligent docking endpoint (units: mm / unit vectors)."""

    id: str
    origin: _frames.Vec3
    direction: _frames.Vec3
    lateral_axis: _frames.Vec3
    up: _frames.Vec3
    width: float
    height: float
    roller_pitch: float
    conveyor_type: str = "Straight"
    connection_rules: Dict[str, Any] = field(default_factory=dict)
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "origin", _vec(self.origin, "origin"))
        object.__setattr__(self, "direction", _vec(self.direction, "direction"))
        object.__setattr__(self, "lateral_axis", _vec(self.lateral_axis, "lateral_axis"))
        object.__setattr__(self, "up", _vec(self.up, "up"))
        for key in ("width", "height", "roller_pitch"):
            object.__setattr__(self, key, float(getattr(self, key)))
        if self.width <= 0 or self.height <= 0 or self.roller_pitch <= 0:
            raise PortDefinitionError(
                f"Port {self.id!r}: width/height/pitch must be positive, got "
                f"{self.width}/{self.height}/{self.roller_pitch}"
            )

    # -- geometry -----------------------------------------------------------
    def normalized(self) -> "ConveyorPort":
        """Copy with unit direction/lateral/up (raises on zero-length)."""
        import dataclasses

        try:
            d = _frames.vnorm(self.direction)
            lat = _frames.vnorm(self.lateral_axis)
            u = _frames.vnorm(self.up)
        except ValueError as exc:
            raise PortDefinitionError(f"Port {self.id!r}: {exc}") from exc
        return dataclasses.replace(self, direction=d, lateral_axis=lat, up=u)

    def basis(self) -> _frames.Mat3:
        """Right-handed port basis rows [x=dir, y=lateral, z=up]-as-columns.

        Uses Gram-Schmidt (``frames.orthonormal_basis``) so incline ports
        with ``direction.z != 0`` still produce valid frames.
        """
        return _frames.orthonormal_basis(self.direction, self.up)

    def validate(self) -> None:
        """Raise ``PortDefinitionError`` when the triad is degenerate."""
        n = self.normalized()
        ang_du = _frames.vangle_deg(n.direction, n.up)
        if ang_du < 1.0 or ang_du > 179.0:
            raise PortDefinitionError(
                f"Port {self.id!r}: direction/up near-parallel ({ang_du:.2f}°)"
            )
        y_want = _frames.vnorm(_frames.vcross(n.up, n.direction))
        if _frames.vangle_deg(y_want, n.lateral_axis) > 5.0:
            raise PortDefinitionError(
                f"Port {self.id!r}: lateral_axis not right-handed "
                f"(off by {_frames.vangle_deg(y_want, n.lateral_axis):.2f}°)"
            )

    # -- serialization ------------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "origin_mm": [self.origin[0], self.origin[1], self.origin[2]],
            "direction": [self.direction[0], self.direction[1], self.direction[2]],
            "lateral_axis": [
                self.lateral_axis[0],
                self.lateral_axis[1],
                self.lateral_axis[2],
            ],
            "up": [self.up[0], self.up[1], self.up[2]],
            "width_mm": self.width,
            "height_mm": self.height,
            "pitch_mm": self.roller_pitch,
            "conveyor_type": self.conveyor_type,
            "connection_rules": dict(self.connection_rules),
            "schema_version": self.schema_version,
        }

    @staticmethod
    def from_dict(payload: Dict[str, Any]) -> "ConveyorPort":
        data = _ser.migrate_port_dict(dict(payload))
        return ConveyorPort(
            id=str(data.get("id", "port")),
            origin=_vec(data["origin_mm"], "origin_mm"),
            direction=_vec(data["direction"], "direction"),
            lateral_axis=_vec(data["lateral_axis"], "lateral_axis"),
            up=_vec(data.get("up", (0.0, 0.0, 1.0)), "up"),
            width=float(data["width_mm"]),
            height=float(data["height_mm"]),
            roller_pitch=float(data["pitch_mm"]),
            conveyor_type=str(data.get("conveyor_type", "Straight")),
            connection_rules=dict(data.get("connection_rules", {})),
            schema_version=str(data.get("schema_version", SCHEMA_VERSION)),
        )

    @staticmethod
    def from_legacy_dict(port_id: str, payload: Dict[str, Any]) -> "ConveyorPort":
        """Build from a legacy ``get_module_ports`` dict (``"normal"`` key).

        This is the ONLY place the legacy ``"normal"`` key is read.
        """
        data = dict(payload)
        if "lateral_axis" not in data and "normal" in data:
            data["lateral_axis"] = data.pop("normal")
        return ConveyorPort.from_dict(
            {
                "id": port_id,
                "origin_mm": list(data["origin_mm"]),
                "direction": list(data["direction"]),
                "lateral_axis": list(data["lateral_axis"]),
                "up": list(data.get("up", (0.0, 0.0, 1.0))),
                "width_mm": float(data["width_mm"]),
                "height_mm": float(data["height_mm"]),
                "pitch_mm": float(data["pitch_mm"]),
                "conveyor_type": str(data.get("conveyor_type", "Straight")),
                "connection_rules": dict(data.get("connection_rules", {})),
            }
        )

    def to_legacy_dict(self) -> Dict[str, Any]:
        """Export legacy-shaped dict (for old consumers; key ``"normal"``)."""
        return {
            "origin_mm": tuple(self.origin),
            "direction": tuple(self.direction),
            "normal": tuple(self.lateral_axis),
            "up": tuple(self.up),
            "width_mm": self.width,
            "height_mm": self.height,
            "pitch_mm": self.roller_pitch,
        }
