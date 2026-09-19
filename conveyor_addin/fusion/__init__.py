"""Fusion boundary — thin adapters + guarded presenters (OBJECTIVE 6).

Nothing here owns math. ``generators`` maps intelligent modules back to
legacy engine inputs (pure, tested). ``viz`` computes viewport overlay
specs (pure) with a best-effort ``adsk`` presenter (guarded).
``commands`` exposes the six Conveyor Intelligence panel actions as pure
functions over ``ConveyorGraph``; ``register_panel`` wires them into the
Add-In toolbar when Fusion is present (otherwise ``False``).

NOTE: the live ``conveyor_addin.py`` dialog file is intentionally NOT
edited by this phase (parallel uncommitted work lives there); ``commands``
documents the one-line wiring point in ``register_panel``.
"""

__all__ = ["generators", "viz", "commands"]
