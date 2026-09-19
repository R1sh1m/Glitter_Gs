# Automation Platform — Phases 2–6 (Graph, Manufacturing, Intelligence, Fusion)

> Companion to `Docs/COORDINATE_SYSTEM.md` (frames/ports/transforms, normative),
> `Docs/ENGINEERING.md` (sizing/taper), `Docs/ASSEMBLY.md` (Part-doc rule).

## ConveyorGraph (`conveyor_addin/graph/layout.py`)

- `add_module(module)` — first module roots the layout at identity; later
  modules are unplaced ghosts (excluded from collision) until docked.
- `connect_modules(outlet_id, inlet_id)` — compatibility matrix → 6-DOF
  solve → height/width/pitch gates → AABB collision vs all placed modules
  (butt contact at the joint plane passes; volume overlap raises).
- `remove_module(id)` — drops node + edges, sets `dirty` (downstream
  placements may be stale; `validate_layout` reports it).
- `validate_layout()` → `{valid, dirty, edges, collisions}`.
- `generate_assembly()` → placed modules (world 4×4, AABB, world ports),
  joints, numeric BOM roll-up, validation snapshot.
- Curve collision uses the arc-sweep box (`local_aabb_mm`), not the
  centerline length.

## Manufacturing (`conveyor_addin/manufacturing/`)

- `bom.py` — fabrication rows (rails in m, rollers/shafts/6002 bearings in
  pcs, posts/plates/boards/guards); `line_bom` rolls up a line.
- `cutlist.py` — saw cuts (rail L, leg H−40, tube W−60, shaft W+24, guards).
- `instructions.py` — canonical 4 steps + taper/grade/branch/guard extras.
- `report.py` — `build_report` → JSON + Markdown + BOM CSV + cut CSV.

## Intelligence (`conveyor_addin/intelligence/`, recommend-only)

Pipeline: `recommender` (spec DATA + reasoning + gate findings, `cad_actions: []`)
→ `rules_engine.gate` (deterministic SPEC/P-3ROLLERS/W-MARGIN checks)
→ `optimizer` (legacy duty heuristic as data) → validated spec →
`modules.*` factory → Fusion generator. The recommender cannot import or
call CAD (source-scan + subprocess import test). Baseline scorer
`knowledge_base.score_spec` is the bar a future local model must beat.

## Fusion (`conveyor_addin/fusion/`, Objective 6)

- `generators.py` — module → legacy `ConveyorInput`/`CurveInput` + ordered
  build-plan ops (pure, tested). Live builders stay in the legacy engines.
- `viz.py` — RGB triad / joint overlay specs (pure) + guarded `adsk`
  sketch presenter (offline-safe `False`).
- `commands.py` — six Conveyor Intelligence actions as pure functions over
  `ConveyorGraph`; `register_panel(app)` is the one-line wiring point for
  `conveyor_addin.py run()` (no-op outside Fusion). The live dialog file was
  deliberately not edited (parallel uncommitted work).

## Demo line (`examples/build_demo_line.py` → `out/demo_line/`)

Straight 2000 + Curve90 Ri800 + Straight 3000 auto-docked: `demo_line_assembly.json`
(world matrices, joints, validation), `demo_line_report.{json,md}`,
`demo_line_bom.csv`, `demo_line_cutlist.csv`, per-joint `*_dock_debug.json`.
Final outlet: `(3025, 4250, 750)` heading +Y. (3000mm exceeds the straight
spec range, so the carrier is composed as straight-geometry explicitly.)

## Test map

`test_units_strict`, `test_serialization`, `test_docking_math` (9-case gate),
`test_regression_legacy` (deletion gate for root engines), `test_debug_export`,
`test_graph`, `test_manufacturing`, `test_intelligence`, `test_fusion_commands`
— all in `run_ci.py` Stage 8.
