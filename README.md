# Roller Conveyor Engineering Automation Platform

![Python](https://img.shields.io/badge/python-3.12%2B-blue)
![Platform](https://img.shields.io/badge/Fusion_360-2026_COM-lightgrey)
![OS](https://img.shields.io/badge/OS-Windows_%7C_macOS-green)
![Tests](https://img.shields.io/badge/pytest-130%2B_passing-brightgreen)
![Local](https://img.shields.io/badge/network-100%25_local-orange)

A companion engineering tool for Autodesk Fusion 360 that designs, docks,
validates, and documents industrial roller conveyor lines — from a single
parametric module to a fully docked factory layout with fabrication BOM,
cut lists, and assembly instructions.

Deterministic engineering calculations govern every output. The optional
recommendation layer proposes specifications only; it never generates CAD.

---

## Capabilities

**Parametric module generation**

- Straight modules driven entirely by native Fusion user parameters
  (`ConvLength`, `ConvWidth`, `FrameHeight`, `RollerDia`, `RollerSpacing`,
  `LegSpacing`, `GuardHeight`); roller and leg counts are Fusion formula
  parameters, so editing values in *Modify → Change Parameters* reconfigures
  the model in place via `computeAll()` — no rebuilds.
- Tapered curve modules (15–180°) with surface-speed-matched rollers
  (`d_outer = d_inner · Ro/Ri`) and a 5° adjacent-roller angular cap.
- Merge, Transfer, Incline, and Custom module types with formal port geometry.

**6-DOF docking solver**

- Every module exposes intelligent inlet/outlet ports (origin, flow
  direction, lateral axis, up vector, width, carry height, pitch).
- The solver computes the rigid transform (rotation matrix, quaternion,
  translation) aligning any outlet to any inlet, including incline grades
  the legacy yaw-only method could not represent.
- Engineering gates verify carry-height agreement (±1.0 mm, with riser
  correction sizing on failure), width agreement, pitch continuity, and
  footprint collision. Failures return the cause and the required fix.

**Layout graph**

- `ConveyorGraph` models the factory line: modules as nodes, docking joints
  as edges. Operations: `add_module`, `remove_module`, `connect_modules`,
  `validate_layout`, `generate_assembly` (world transforms, joint record,
  rolled-up BOM, validation snapshot).

**Manufacturing output**

- Fabrication BOM (frame extrusion in metres; rollers, shafts, and 6002
  bearings in pieces), saw cut lists, ordered assembly instructions, and a
  combined shop-floor report (JSON, Markdown, CSV).

**Digital twin**

- OPC-UA (IEC 62541) NodeSet metadata per module: drive commands, telemetry,
  photoeye states, rated capacity, and safety factor.

**Verification**

- Physical CAD B-Rep bounding-box gate (±5.0 mm), pre-export sketch hygiene,
  STEP export gated on validation pass, and a Fusion-independent test suite
  covering all docking mathematics before any geometry is built.

---

## Repository layout

```
├── fusion_conveyor_generator.py   # Straight-module engine (proven, adapter-wrapped)
├── fusion_curve_module.py         # Tapered-curve engine (proven, adapter-wrapped)
├── fusion_docking_system.py       # Legacy yaw-only docking (superseded by docking/solver.py)
├── conveyor_addin/
│   ├── core/                      # Single source of truth: units, frames, tolerances,
│   │                              # errors, parameter ranges, serialization/migration
│   ├── docking/                   # Port model, compatibility matrix, 6-DOF solver,
│   │                              # validators, debug export, Fusion occurrence applier
│   ├── graph/                     # ConveyorGraph layout model
│   ├── modules/                   # Intelligent module factories (adapters + new types)
│   ├── manufacturing/             # BOM, cut lists, instructions, reports
│   ├── intelligence/              # Recommend-only layer: knowledge base, rules engine,
│   │                              # optimizer, recommender (no CAD access by construction)
│   ├── fusion/                    # Generator adapters, viewport overlay specs,
│   │                              # Conveyor Intelligence panel actions
│   ├── conveyor_addin.py          # Persistent Fusion dialog (live preview, export)
│   └── presets.json               # Standard module presets
├── examples/
│   └── build_demo_line.py         # End-to-end demo: Straight 2000 + Curve 90° + Straight 3000
├── tests/                         # Offline suites incl. docking-math gate and fixtures
├── out/demo_line/                 # Generated demo deliverables (assembly, BOM, report)
└── Docs/                          # Normative engineering documentation (see below)
```

---

## Install and run in Fusion 360

The `conveyor_addin/` folder is a self-contained Fusion add-in
(manifest + dialog + engines + presets). Install once, then run it
from inside Fusion.

### 1. Prerequisites

- Autodesk Fusion 360 (2026 build recommended), Desktop, signed in.
- This repo cloned / downloaded locally.
- No extra Python packages needed inside Fusion — Fusion ships its own interpreter.

### 2. Install the add-in

**Option A — automatic (recommended)**

```bash
python install_addin.py
```

This copies `conveyor_addin/` to Fusion's Add-Ins folder(s):

- Windows: `%APPDATA%\Autodesk\Autodesk Fusion 360\API\AddIns\conveyor_addin`
- macOS: `~/Library/Application Support/Autodesk/Autodesk Fusion 360/API/AddIns/conveyor_addin`

You should see `Successfully installed to: ...` for each location found.

**Option B — manual copy**

1. Locate Fusion's Add-Ins folder:
   - Windows: `%APPDATA%\Autodesk\Autodesk Fusion 360\API\AddIns\`
   - macOS: `~/Library/Application Support/Autodesk/Autodesk Fusion 360/API/AddIns/`
2. Copy the whole repo `conveyor_addin/` folder there, so you end up with:
   `.../AddIns/conveyor_addin/conveyor_addin.manifest` plus
   `conveyor_addin.py`, `presets.json`, `fusion_conveyor_generator.py`,
   `fusion_curve_module.py`, etc.
3. Restart Fusion if it was already open.

### 3. Enable the add-in

1. In Fusion: **Utilities → Scripts and Add-Ins** (or `Shift + S`).
2. Switch to the **Add-Ins** tab → select `conveyor_addin`
   (shows as **Parametric Conveyor Generator**).
3. Click **Run**, and tick **Run on Startup** so it stays available.
4. If the version / OS in the panel looks stale after a repo update,
   re-run `python install_addin.py` (or re-copy), then restart Fusion.

### 4. Run it — build your first conveyor

1. Open or create a **Design** document (one module = one document).
2. Go to the toolbar panel where the add-in registered its commands
   (`Solid → Create` / `Scripts and Add-Ins` panel):
   - **Parametric Conveyor Generator** — build straight or curved modules.
   - **Dock Next Conveyor Module** — snap the next module to an existing line outlet.
3. In the dialog:
   - Pick **Module Type**: `Straight Section` or `Curved 30° / 45° / 60° / 90° Section`.
   - Pick a **Preset** (e.g. `C2: Medium Standard (With Guards)`), or choose
     `Custom (Manual)` and type millimetre values.
   - Watch the **Live Engineering Preview** (roller count, pitch, steel mass,
     rated load) and the **Status / Export Log**.
   - Click **Build / Apply**. Re-clicking reconfigures the same model in
     place — no duplicate solids.
4. Tweak any time via **Modify → Change Parameters**
   (`ConvLength`, `ConvWidth`, `FrameHeight`, `RollerDia`, `RollerSpacing`,
   `LegSpacing`, `GuardHeight`, `C_CurveAngle`).

### 5. Where your files go

When **Export STEP + BOM + OPC-UA on Apply** is ticked, each build writes to:

- Windows: `~/ConveyorGenerator_Output/`
- macOS: `~/ConveyorGenerator_Output/`

You get per-module `.step`, `BOM.csv` with masses, `validation_report.txt`,
and OPC-UA NodeSet JSONs. Offline demo outputs instead go to `out/demo_line/`
(see below).

### 6. Updating / uninstalling

- Update: pull the repo, re-run `python install_addin.py`, restart Fusion.
- Uninstall: in **Scripts and Add-Ins → Add-Ins**, select `conveyor_addin` →
  **Stop**, untick **Run on Startup**, then delete the
  `.../AddIns/conveyor_addin` folder.

### 7. Troubleshooting

- Add-in not listed → check the folder contains `conveyor_addin.manifest`
  one level down (`AddIns/conveyor_addin/conveyor_addin.manifest`), then restart Fusion.
- `Part Design documents can only contain one component` → expected: keep one
  module per document and assemble lines in a separate assembly doc via
  `addExistingComponent` (see `Docs/ASSEMBLY.md`).
- Stale dialog / old preset → you ran from a cached copy; reinstall + restart.
- Dialog errors are appended to `~/ConveyorGenerator_Output/dialog_errors.log`.

Full click-through script: `Docs/DEMO_RUNBOOK.md`.

---

## Quick start

### In Fusion 360 — Add-In (recommended)

See **Install and run in Fusion 360** above for the full guide. Short version:
`python install_addin.py`, then in Fusion **Scripts and Add-Ins → Add-Ins**
→ Run `conveyor_addin` with **Run on Startup**, then use the toolbar
**Parametric Conveyor Generator** command.

### In Fusion 360 — Script

1. **Utilities → Scripts and Add-Ins** (or `Shift + S`), add
   `fusion_conveyor_generator.py` under *My Scripts*, and run it.
2. Choose the automated multi-configuration pipeline or interactive
   custom-parameter entry.

### Offline — demo line (no Fusion required)

```bash
python examples/build_demo_line.py
```

Docks Straight 2000 mm + 90° curve (Ri 800) + Straight 3000 mm, validates
both joints, and writes `out/demo_line/`: assembly description
(`demo_line_assembly.json`), fabrication BOM and cut list (CSV), the
manufacturing report (JSON + Markdown), and per-joint transform debug files.

### Offline — tests

```bash
python -m pytest tests/ -q
python run_ci.py     # full pipeline: syntax, AST, lint, types, all suites
```

---

## Design envelope

| Parameter | Symbol | Range | Typical |
| :--- | :---: | :---: | :---: |
| Conveyor length | `L` | 800 – 2000 mm | 1400 mm |
| Conveyor width | `W` | 300 – 600 mm | 450 mm |
| Frame height | `H` | 500 – 900 mm | 750 mm |
| Roller diameter | `D` | 40 – 80 mm | 60 mm |
| Roller spacing (c-to-c) | `P` | 80 – 150 mm | 110 mm |
| Support-leg spacing | `S` | 500 – 1000 mm | 700 mm |
| Side-guard height | `G` | 0 – 150 mm | 100 mm |
| Side guards | — | Yes / No | Yes |

Key relations: roller end margin `D/2 + 10`; fixed-pitch floor counts
(`RollerCount`, `LegCount` as Fusion formulas); curve pitch cap 5°;
joint acceptance carry ±1.0 mm, pitch step within the slack band.
Full derivations: `Docs/ENGINEERING.md`.

---

## Documentation

All non-code engineering knowledge lives in `Docs/`; code implements it and
never redefines it. Start here, not in code comments.

- `Docs/COORDINATE_SYSTEM.md` — normative frames, port definitions, unit
  boundaries, and transform conventions (single source of truth).
- `Docs/PLATFORM_PHASES.md` — graph, manufacturing, intelligence, and
  Fusion panel guide with the demo-line outputs.
- `Docs/ENGINEERING.md` — sizing math, taper theory, advisory rules,
  assumptions ledger.
- `Docs/INTEGRATION.md` — hardware interface gates IF-010…IF-060
  (rail bores, roller assemblies, drives, supports, sensors, docking).
- `Docs/STANDARDS.md` — normative index (CEMA, ISO, IEC) with committed
  source material under `Docs/standards/`.
- `Docs/ASSEMBLY.md` — one-module-per-document rule and the
  `addExistingComponent` assembly flow.
- `Docs/SIMULATION.md` — analytic capacity loop and manual study recipes.
- `Docs/VISION_PRODUCTION_LINES.md` — roadmap from modules to
  interlockable production lines.
- `Docs/FUSION_API_REFERENCE.md`, `Docs/FUSION_SCRIPT_WORKFLOW.md` —
  Fusion API detail and the script-to-CAD execution flow.

---

## Quality gates and conventions

1. **One source of truth** — dimensions, ranges, and tolerances live in
   `conveyor_addin/core/`; nothing else redefines them.
2. **Adapter-first evolution** — new layers wrap the proven generators;
   root engine files are never deleted until the regression suite
   (`tests/test_regression_legacy.py`) passes.
3. **Math before geometry** — the docking solver passes its
   Fusion-independent suite (straight, curve, reversed-flow, height/width
   rejection, rotation hygiene, full-line chain) before any CAD integration.
4. **Deterministic over heuristic** — ML proposes, engineering rules
   dispose; every recommendation passes `rules_engine.gate` or is rejected.
5. **No silent unit conversions** — all mm↔cm and deg↔rad conversions go
   through `core/units.py` (CI-enforced).

## Requirements

- Autodesk Fusion 360 (2026 build recommended) for CAD generation.
- Python 3.12+ with `pytest` for the offline suite (`pip install -r requirements.txt`).
- No network access required; no external services are used.
