"""Connection-rules compatibility matrix — type-level gate BEFORE solving.

``check_connection_allowed`` runs before ``DockingSolver.solve``: there is no
point computing transforms for module pairs that are mechanically or
logically forbidden. Engineering dimension checks (height/width/pitch) live
in ``validators.py``; this module answers "may type A dock to type B?".
"""

from __future__ import annotations

from typing import Any, Dict, Tuple

__all__ = [
    "COMPATIBILITY",
    "check_connection_allowed",
    "matrix_to_dict",
]

# (outlet_type, inlet_type) -> (allowed, note). Absent pair = forbidden.
COMPATIBILITY: Dict[Tuple[str, str], Tuple[bool, str]] = {
    ("Straight", "Straight"): (True, "collinear sections"),
    ("Straight", "Curved"): (True, "straight feeds curve inlet"),
    ("Curved", "Straight"): (True, "curve outlet feeds straight"),
    ("Curved", "Curved"): (True, "S-curves allowed; opposite hands need layout check"),
    ("Straight", "Merge"): (True, "merge main inlet"),
    ("Curved", "Merge"): (True, "merge main inlet"),
    ("Merge", "Straight"): (True, "merge outlet is straight-compatible"),
    ("Merge", "Curved"): (True, "merge outlet is straight-compatible"),
    ("Straight", "Transfer"): (True, "transfer is a short straight"),
    ("Transfer", "Straight"): (True, "transfer is a short straight"),
    ("Curved", "Transfer"): (True, "transfer is a short straight"),
    ("Transfer", "Curved"): (True, "transfer is a short straight"),
    ("Straight", "Incline"): (True, "level feeds incline foot"),
    ("Incline", "Straight"): (True, "incline head feeds level"),
    ("Incline", "Incline"): (True, "grades must be co-directional"),
    ("Straight", "Custom"): (True, "custom validated per-port"),
    ("Curved", "Custom"): (True, "custom validated per-port"),
    ("Custom", "Straight"): (True, "custom validated per-port"),
    ("Custom", "Custom"): (True, "custom validated per-port"),
    # Forbidden pairs (explicit so errors explain, not just KeyError):
    ("Merge", "Merge"): (False, "two merge outlets cannot chain directly"),
    ("Merge", "Incline"): (False, "merge outlet must settle before grade"),
    ("Incline", "Merge"): (False, "no merge on a grade"),
    ("Transfer", "Transfer"): (False, "transfers cannot chain; add a carrier section"),
    ("Transfer", "Merge"): (False, "transfer must discharge to a carrier first"),
    ("Transfer", "Incline"): (False, "transfer must discharge to a carrier first"),
}


def check_connection_allowed(
    outlet_type: str,
    inlet_type: str,
    outlet_rules: Dict[str, Any] | None = None,
    inlet_rules: Dict[str, Any] | None = None,
) -> Tuple[bool, str]:
    """Return ``(allowed, reason)`` for an outlet->inlet type pair.

    Per-port ``connection_rules`` overlays:
      - ``{"branch": True}`` on an inlet marks a merge branch inlet: allowed
        only when the outlet rules carry ``{"feeds_branch": True}``.
      - ``{"blocked": True}`` on either side forbids the connection.
    """
    outlet_rules = outlet_rules or {}
    inlet_rules = inlet_rules or {}
    if outlet_rules.get("blocked"):
        return False, "outlet port is blocked by connection_rules"
    if inlet_rules.get("blocked"):
        return False, "inlet port is blocked by connection_rules"
    if inlet_rules.get("branch") and not outlet_rules.get("feeds_branch"):
        return False, "branch inlet requires an outlet flagged feeds_branch"
    key = (str(outlet_type), str(inlet_type))
    if key in COMPATIBILITY:
        return COMPATIBILITY[key]
    return False, f"unsupported pair {outlet_type!r} -> {inlet_type!r}"


def matrix_to_dict() -> Dict[str, Dict[str, Any]]:
    """JSON-serializable view of the matrix (for reports / debug JSON)."""
    out: Dict[str, Dict[str, Any]] = {}
    for (a, b), (allowed, note) in sorted(COMPATIBILITY.items()):
        out[f"{a}->{b}"] = {"allowed": allowed, "note": note}
    return out
