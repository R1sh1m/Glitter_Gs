"""Docking subsystem — ports, 6-DOF solver, validators, debug, apply.

Pipeline: ``connection_rules.check_connection_allowed`` (type-level gate)
-> ``solver.DockingSolver.solve`` (transform) -> ``validators`` (engineering
gates raising ``DockingError`` with required corrections).
"""

__all__ = [
    "port",
    "connection_rules",
    "solver",
    "validators",
    "debug",
    "apply",
]
