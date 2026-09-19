"""Local ML preparation — recommend-only intelligence (no external APIs).

Architecture (enforced)::
    AI Recommendation -> Engineering Rules -> Validation -> Fusion Generator

``recommender`` proposes SPEC DATA ONLY (never CAD handles, never builder
calls — enforced by ``tests/test_intelligence.py`` source scan).
``rules_engine`` gates every recommendation deterministically.
``optimizer`` wraps the proven legacy duty-class heuristic as data.
"""

__all__ = ["knowledge_base", "rules_engine", "optimizer", "recommender"]
