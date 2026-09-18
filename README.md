# Glitter_Gs — Parametric Adjustable Roller Conveyor Generator
### Autodesk Fusion × Standards: Industry Hackathon (Problem Statement A)

A production-grade Autodesk Fusion API solution that generates and parametrically controls an **Adjustable Roller Conveyor Module** satisfying all requirements from Problem Statement A (sections 2.1 – 2.6).

<<<<<<< HEAD
## Implemented Scope
- User-driven configuration input through Fusion UI:
  - `length_mm` (L): 800–2000
  - `width_mm` (W): 300–600
  - `height_mm` (H): 500–900
  - `roller_diameter_mm` (D): 40–80
  - `roller_spacing_mm` (P): 80–150
  - `support_spacing_mm` (S): 500–1000
  - `side_guard_height_mm` (G): 0–150
  - `side_guards`: Yes/No
- Automated generation of:
  - frame
  - rollers
  - support legs
  - optional side guards
- Repeated component logic:
  - roller count/positions computed from selected length, diameter, and max spacing
  - support-leg pair count/positions computed from selected length and max spacing
- Deterministic output:
  - identical inputs produce identical derived layout/signature
- Idempotent regeneration:
  - stale generated components with `GG_` prefix are removed before rebuild
- Automatic verification:
  - overall dimensions and feature consistency
  - roller/support spacing constraints and computed positions
- BOM/component summary generated for each configuration.
- Fusion parameter persistence:
  - active dimensions are written to named `GG_` user parameters
  - the generated module stores its configuration signature and BOM as Fusion attributes
- Regeneration safety:
  - support-leg pair centres stay inside the selected conveyor length
  - rollers are centred across the conveyor width
=======
---
>>>>>>> origin/main

## 🌟 Key Innovations & Salient Architectural Features

1. **Genuine Native Parametric CAD Modeling (Section 2.4)**
   - Unlike static B-rep solid generators, the CAD model is **fully driven by native Autodesk Fusion User Parameters** (`ConvLength`, `ConvWidth`, `FrameHeight`, `RollerDia`, `RollerSpacing`, `LegSpacing`, `GuardHeight`).
   - Every sketch line and extrusion dimension is parametrically tied via `.parameter.expression`.

2. **Dynamic Fusion Formula Parameters for Repeated Components (Section 2.3A)**
   - Roller and leg counts are **not hardcoded in Python loops**; they are registered as Fusion formula parameters:
     - `RollerCount = floor((ConvLength - 2 * RollerMargin) / RollerSpacing) + 1`
     - `LegCount = floor((ConvLength - LegSide) / LegSpacing) + 1`
   - When any parameter is changed directly in Fusion's *Modify -> Change Parameters* table or through the API, Fusion's internal constraint solver automatically recalculates component counts and locations!

<<<<<<< HEAD
## Running in Fusion
1. Open Fusion and run `fusion_conveyor_generator.py`.
2. Enter `L,W,H,D,P,S,G,side_guards` in the prompt.
3. Re-run with changed values to regenerate the model and update repeated components.
4. Inspect the `GG_ConveyorModule` attributes for the deterministic configuration signature and JSON BOM.
=======
3. **Parametric Rectangular Patterns (`RectangularPatternFeature`)**
   - Single master roller and master leg station patterned along the conveyor axis.
   - Pattern instance quantities and spacings are directly wired to the formula parameters (`RollerCount`, `RollerSpacing`, `LegCount`, `LegSpacing`).
>>>>>>> origin/main

4. **Zero Duplicate Geometry & In-Place Reconfiguration**
   - Parameter updates do not delete or recreate parts; geometry updates in-place via `design.computeAll()`, preserving timeline integrity and performance.
   - Side guards are built once and toggled parametrically via feature suppression (`feature.isSuppressed = not side_guards`).

5. **Physical CAD B-Rep Bounding Box Verification (Section 2.4)**
   - Automated inspection reads the physical 3D bounding box (`comp.boundingBox.maxPoint - comp.boundingBox.minPoint`) and verifies that real CAD extents ($L, W, H$) match input specifications within 5mm tolerance.

6. **Automated Deliverables & Export Pipeline (Section 2.6)**
   - Exports high-precision **STEP 3D CAD files** (`.step`) for each configuration **only when validation passes** (failed CAD is never shipped).
   - Generates formatted **CSV Bills of Materials (BOM)** (`{name}_BOM.csv`) with quantities read back from the Fusion model (`RollerCount`/`LegCount`), so BOM can never drift from CAD, plus a **Mass (kg)** column — measured from `physicalProperties` in-Fusion, analytic solid-steel estimate offline.
   - Pre-export **hygiene gate** removes empty sketches (logged) before validation/export.
   - Generates a verification report (`validation_report.txt`, overwritten per batch run).

7. **Dual-Mode Fusion User Interface (Section 2.3)**
   - **Mode [1] — Automated 3-Configuration Demonstration Pipeline:**
     Automatically cycles through three substantially different valid configurations (`C1_compact_no_guards`, `C2_medium_with_guards`, `C3_long_with_guards`), validates CAD bounding boxes, exports STEP models (on PASS), and generates CSV BOMs. On Fusion 2026 builds a Configurations-table sync note is recorded; sequential exports remain authoritative on all versions.
   - **Mode [2] — Interactive Custom Parameter Entry:**
     Allows real-time input of custom parameters with automatic boundary validation and instant CAD model reconfiguration.

8. **Offline Testability & CI/CD Support**
   - Pure-Python mathematical models and rule verifications run completely outside of Fusion 360, enabling automated unit testing without CAD dependencies.

---

## 📐 Specification Input Ranges

| Parameter | Symbol | Allowed Range | Default / Demo Example |
| :--- | :---: | :---: | :---: |
| **Conveyor Length** | `L` | 800 – 2000 mm | 1400 mm |
| **Conveyor Width** | `W` | 300 – 600 mm | 450 mm |
| **Frame Height** | `H` | 500 – 900 mm | 750 mm |
| **Roller Diameter** | `D` | 40 – 80 mm | 60 mm |
| **Roller Spacing (c-to-c)** | `P` | 80 – 150 mm | 110 mm |
| **Support-Leg Spacing** | `S` | 500 – 1000 mm | 700 mm |
| **Side-Guard Height** | `G` | 0 – 150 mm | 100 mm |
| **Side Guards** | — | Yes / No | Yes |

---

## 📂 Project Structure

```
├── fusion_conveyor_generator.py   # Primary Fusion API script & core engine
├── conveyor_addin/
│   ├── conveyor_addin.manifest    # Add-in manifest (Fusion Add-Ins folder)
│   └── conveyor_addin.py          # Persistent dialog: typed inputs, live preview,
│                                  # Export button + log, model reuse (same engine)
├── tests/
│   └── test_conveyor_generator.py # Unit suite: derivation, BOM, CSV, floor-pitch sync (offline)
│   └── test_fusion_api_mock.py    # Mocked Fusion-API integration: params, tree, validation, STEP
│   └── test_conveyor_addin.py     # Add-in dialog helpers (offline)
├── Docs/
│   ├── Hackathon_Problem_Statement.pdf
│   ├── FUSION_API_REFERENCE.md    # Shared Fusion API reference + code map
│   └── FUSION_SCRIPT_WORKFLOW.md (+.pdf)  # Workflow explainer
└── README.md                      # Engineering documentation
```

---

## 🛠️ Local Dev Setup (no stubs)

- Python **3.14** venv pinned to match Fusion 2026's embedded runtime:
  ```bash
  "C:\Users\Rishi Misra\AppData\Local\Programs\Python\Python314\python.exe" -m venv .venv
  .\.venv\Scripts\python.exe -m unittest discover -s tests -v
  ```
- VSCode uses Pylance with `diagnosticMode: openFilesOnly`, `FusionMCPSample/**` excluded. No `adsk` stubs are vendored (they only exist inside Fusion); `adsk.*` intelligence intentionally comes from Fusion's **Scripts and Add-Ins → Edit** bridge, not local LSP. Pure-Python (derive/verify/BOM/tests) has full LSP support.

## 📏 Engineering Assumptions (Definition of Done)

- Rail section `20×40 mm`, roller clearance `10 mm`, leg post `40×40 mm`, guard plate `5 mm` — exposed as User Parameters for reviewer edits.
- `RollerMargin = RollerDia/2 + 10 mm`; counts use fixed-pitch floor math (Spacing pattern type, never Extent rescaling).
- `LegCount = floor((ConvLength - LegSide)/LegSpacing)+1` keeps posts inside the envelope; the Brief's simplified `floor(L/S)+1` would overhang the last post by up to 40 mm (e.g. C3). Python, Fusion formula, validator and BOM share one implementation (`leg_count_for`).
- Minimum 2 rollers / 2 leg stations whenever the usable span is positive (stability).
- `GuardHeight` floors at 1 mm for CAD only (zero-length extrude would fail); visibility is via `isSuppressed`, independent of height — `side_guards=False + G>0` is legal.
- Mass estimates assume solid structural steel (7850 kg/m³); rollers modelled solid (hollow-tube savings are a documented overestimate); in-Fusion runs prefer measured `physicalProperties` mass.
- Build collapses to one timeline undo group; reconfigs edit params in place with a single `computeAll()`; patterns use Identical compute for disjoint bodies.

## 📖 Docs

- `Docs/FUSION_SCRIPT_WORKFLOW.md` (+ `.pdf`) — fundamental explainer: how the Python script talks to Fusion, stage by stage.
- `Docs/FUSION_API_REFERENCE.md` — authoritative API detail (§§1–14), GitHub reuse catalog (§15), integration log (§16).

## 📚 Reusable GitHub Patterns Applied

Patterns studied from [`AutodeskFusion360`](https://github.com/AutodeskFusion360) (34 repos) and applied as idioms (nothing vendored): `SpurGear` parametric skeleton + `isComputeDeferred` discipline, `ParameterIO_Python` CSV↔params retry ordering, `SketchRepair`/`SketchChecker_Python` pre-extrude gates, `BulkExportSketchesAsDXF` stay-open export dialog/log discipline, `Fusion360DevTools` cProfile workflow, `FusionMCPSample` thread-safe `execute_api_script` + screenshot verification loop.

---

## 🚀 How to Run

### In Autodesk Fusion 360 (Script)

1. Open Autodesk Fusion.
2. Navigate to **Utilities** → **Scripts and Add-Ins** (or press `Shift + S`).
3. Click the **+** (Add) button under *My Scripts* and select `fusion_conveyor_generator.py`.
4. Click **Run**.
5. Select:
   - **`1`** for the **Automated 3-Configuration Demo Pipeline** (exports all deliverables to `~/ConveyorGenerator_Output/`).
   - **`2`** for **Interactive Custom Configuration** (enter custom comma-separated values).

### In Autodesk Fusion 360 (Add-in, persistent dialog)

1. Copy the `conveyor_addin/` folder **and** `fusion_conveyor_generator.py` so both live side by side, then place the folder in the Add-Ins directory (`%APPDATA%\Autodesk\Autodesk Fusion 360\API\AddIns\` on Windows).
2. Under **Scripts and Add-Ins → Add-Ins**, run `conveyor_addin` (enable *Run on Startup* to keep it).
3. Use the toolbar command: typed mm inputs with a **live preview** (counts + est. mass), **Export STEP + BOM Now** without closing, and Apply & Close to reconfigure in place (existing model reused, never rebuilt).

### Batch outputs (per run, `~/ConveyorGenerator_Output/`)

`{C1,C2,C3}[_Custom]*.step` (on PASS) · `{…}_BOM.csv` (model counts + mass) · `validation_report.txt` · `snapshots.csv` + `comparer.html` (viewport PNGs when run inside Fusion) · per-config browser labels with best-effort guard-face etch.

### Standalone Unit Tests (Outside Fusion)
```bash
.\.venv\Scripts\python.exe -m unittest tests.test_conveyor_generator tests.test_fusion_api_mock -v
```
All 17 tests validate mathematical derivations, floor-pitch CAD↔BOM sync, guard independence, range bounds, deterministic signatures, BOM generation (including model-read BOM), CSV exports, mocked param/tree/validation/STEP integration.
