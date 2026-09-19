"""Core engineering layer — single source of truth for units, frames, tolerances.

Import convention (works both under pytest with repo-root on ``sys.path``
and inside Fusion where the Add-In parent dir is inserted, see
``conveyor_addin.py``)::

    try:
        from conveyor_addin.core.units import mm_to_cm
    except ImportError:  # Add-In directory itself on sys.path
        from core.units import mm_to_cm

New code MUST import from here — never redefine ranges, tolerances, or
unit conversions. See ``Docs/COORDINATE_SYSTEM.md`` (normative).
"""

__all__ = [
    "units",
    "frames",
    "errors",
    "invariants",
    "params",
    "serialization",
]
