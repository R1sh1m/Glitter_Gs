# Glitter_Gs — Parametric Adjustable Roller Conveyor Generator
### Autodesk Fusion × Standards: Industry Hackathon (Problem Statement A)

A production-grade Autodesk Fusion API solution that generates and parametrically controls an **Adjustable Roller Conveyor Module** satisfying all requirements from Problem Statement A (sections 2.1 – 2.6).

---

## 📋 Implemented Scope
- **User-driven configuration input** through Fusion UI / Add-In dialog:
  - `length_mm` (L): 800–2000 mm
  - `width_mm` (W): 300–600 mm
  - `height_mm` (H): 500–900 mm
  - `roller_diameter_mm` (D): 40–80 mm
  - `roller_spacing_mm` (P): 80–150 mm
  - `support_spacing_mm` (S): 500–1000 mm
  - `side_guard_height_mm` (G): 0–150 mm
  - `side_guards`: Yes/No
- **Automated generation** of frame side rails, rollers, support legs, and optional side guards.
- **Repeated component logic** with dynamic Fusion formula parameters.
- **Deterministic output & idempotent in-place regeneration**.
- **Automated physical CAD B-Rep verification** (bounding box within 5mm tolerance).
- **Automated deliverables & export pipeline**: STEP 3D CAD files + CSV Bills of Materials (BOM) with measured physical masses.
- **Interactive Add-In & Batch Demonstration Pipeline**.

## 🌟 Key Innovations & Salient Architectural Features

1. **Genuine Native Parametric CAD Modeling (Section 2.4)**
   - Unlike static B-rep solid generators, the CAD model is **fully driven by native Autodesk Fusion User Parameters** (`ConvLength`, `ConvWidth`, `FrameHeight`, `RollerDia`, `RollerSpacing`, `LegSpacing`, `GuardHeight`).
   - Every sketch line and extrusion dimension is parametrically tied via `.parameter.expression`.

2. **Dynamic Fusion Formula Parameters for Repeated Components (Section 2.3A)**
   - Roller and leg counts are **not hardcoded in Python loops**; they are registered as Fusion formula parameters:
     - `RollerCount = floor((ConvLength - 2 * RollerMargin) / RollerSpacing) + 1`
     - `LegCount = floor((ConvLength - LegSide) / LegSpacing) + 1`
   - When any parameter is changed directly in Fusion's *Modify -> Change Parameters* table or through the API, Fusion's internal constraint solver automatically recalculates component counts and locations!

3. **Parametric Rectangular Patterns (`RectangularPatternFeature`)**
   - Single master roller and master leg station patterned along the conveyor axis.
   - Pattern instance quantities and spacings are directly wired to the formula parameters (`RollerCount`, `RollerSpacing`, `LegCount`, `LegSpacing`).

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
├── fusion_conveyor_generator.py   # Primary Fusion API script & core engine (straight, spec-only)
├── fusion_curve_module.py         # Curved module (peer): tapered revolve + circular pattern,
│                                  # C_* params, load advisory, layout-manager ports
├── conveyor_addin/
│   ├── conveyor_addin.manifest    # Add-in manifest (Fusion Add-Ins folder)
│   └── conveyor_addin.py          # Persistent dialog: typed inputs, live preview,
│                                  # Export button + log, model reuse (same engine)
├── tests/
│   └── test_conveyor_generator.py # Unit suite: derivation, BOM, CSV, floor-pitch sync (offline)
│   └── test_curve_module.py       # Curve math, taper kinematics, advisory, formula idioms (offline)
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

> Non-code engineering lives in `Docs/` — this section is an index, not the
> source. Source of truth: `Docs/ENGINEERING.md` (sizing, taper theory,
> advisory rules), `Docs/INTEGRATION.md` (holes, shafts, drives, docking
> IF-gates), `Docs/STANDARDS.md` (normative index), `Docs/VISION_PRODUCTION_LINES.md`
> (interlockable-system roadmap). Key facts: `RollerMargin = D/2+10`,
> fixed-pitch floor counts, inside-envelope legs, suppression-based guards,
> rail `20×40` / clearance `10` / post `40×40` / guard `5`, solid-steel mass
> assumption — all detailed and sourced in `Docs/ENGINEERING.md`.

## 🌀 Curved Module (Full Tapered, Modules-First)

- **Kinematics:** `d_outer = d_inner · Ro/Ri` (surface-speed match); frustum verified live (`Cone` face, analytic volume 1277.6 vs measured 1277.2 cm³).
- **Counts:** outer-arc floor pitch + 5° angular cap → canonical `N = max(floor, ceil(Θ/5)+1)`; demo 90°/Ri800/W450/P110 → **19 rollers @ 5.0°**, 3 leg stations.
- **Fusion idioms (live-proven):** trapezoid sketch → `revolveFeatures` 360° → `circularPatternFeatures` about curve-center axis; arc rails/guards as annular-sector sketches → one-sided extrudes; legs radial-patterned; guards via `isSuppressed`. Angles unit-strip with `/ 1 rad`; `pi` and `max()` are **not** available — canonical max lives in Python, Fusion carries both operands (`C_RollerCount`/`C_RollerCountMin`, read back live).
- **Inputs:** spec-only core untouched; `calculate_load_advisory(box_mass, box_len, box_wid)` suggests P/D/S/W (P≤L/3, W=box+100) clamped to spec ranges.
- **Deliverables:** `~/ConveyorGenerator_Output/Curve90_Ri800.step` + `Curve90_Ri800_BOM.csv` (7/7 live checks PASS, STEP gated on PASS).

## 📖 Docs (all non-code knowledge lives here — start here, not in code comments)

- `Docs/ENGINEERING.md` — sizing math, taper theory, advisory rules, assumptions ledger.
- `Docs/INTEGRATION.md` — reference-model teardown, floating-roller gaps, IF-010…IF-060 interface gates.
- `Docs/STANDARDS.md` — index of `Docs/standards/` downloads + normative pointers (CEMA/ISO/IEC).
- `Docs/VISION_PRODUCTION_LINES.md` — interlockable Lego-style roadmap to production lines.
- `Docs/reference models/` — measured Poly-V conveyor STEP + photos (teardown evidence).
- `Docs/standards/` — Interroll/Damon/Inbelts sources (committed, offline-readable).
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

1. Copy the `conveyor_addin/` folder **and** `fusion_conveyor_generator.py` so both live side by side, then place the folder in the Add-Ins directory (`%APPDATA%\Autodesk\Autodesk Fusion 360\API\AddIns\` on Windows). After any root-engine edit, refresh `conveyor_addin/fusion_conveyor_generator.py` as a byte-copy (tests import the copy).
2. Under **Scripts and Add-Ins → Add-Ins**, run `conveyor_addin` (enable *Run on Startup* to keep it).
3. Use the toolbar command: typed mm inputs with a **live preview** (counts + est. mass), **Export STEP + BOM Now** without closing, and Apply & Close to reconfigure in place (existing model reused, never rebuilt).

### Batch outputs (per run, `~/ConveyorGenerator_Output/`)

`{C1,C2,C3}[_Custom]*.step` (on PASS) · `{…}_BOM.csv` (model counts + mass) · `validation_report.txt` · `snapshots.csv` + `comparer.html` (viewport PNGs when run inside Fusion) · per-config browser labels with best-effort guard-face etch.

### Standalone Unit Tests (Outside Fusion)
```bash
.\.venv\Scripts\python.exe -m unittest tests.test_conveyor_generator tests.test_fusion_api_mock -v
```
All 37 tests validate mathematical derivations, floor-pitch CAD↔BOM sync, guard independence, range bounds, deterministic signatures, BOM generation (including model-read BOM), CSV exports, mocked param/tree/validation/STEP integration, and curve taper/advisory/formula idioms.
