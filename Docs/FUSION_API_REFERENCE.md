# Fusion API Reference — Parametric Roller Conveyor Generator

> **Purpose:** single shared reference for humans + coding agents. Imported from the
> official [Autodesk Fusion API (APS) overview](https://aps.autodesk.com/developer/overview/autodesk-fusion-api)
> and the Fusion API Reference Manual / User's Manual (`help.autodesk.com`), then
> mapped to this repo's Technical Brief (§3–§5) and `fusion_conveyor_generator.py`.
> **Ground-truth rule:** when AI-generated code disagrees with the Reference Manual,
> the Reference Manual wins.

## 0. APS overview (imported 2026-09-18)

- Autodesk Fusion = cloud-based CAD/CAE/CAM in one platform.
- Fusion API = write **scripts, add-ins, applications** to automate tasks, add features,
  integrate with external systems.
- Start at the APS page → **"View API documentation"** → Reference Manual + User's Manual.
  Same docs are reachable in-product via **Help → Learning and Documentation**.
- Code samples: Autodesk's official sample scripts/add-ins repos + community repos.
- Help channels (in order): API docs → [Fusion API forum](https://forums.autodesk.com/t5/fusion-360-api-and-scripts/bd-p/22)
  → ADN blog → ADN membership → APS support contact.
- Competition constraint (Brief §1): Fusion API must be **central**. External libs are
  supporting-only (math/iteration/debugging). Final modeling stays in Fusion.

## 1. Scripts vs add-ins — what this repo uses

| | Script (what we ship) | Add-in (stretch goal §9.2) |
|---|---|---|
| Entry | `def run(context): ...` + `def stop(context): ...` | `commandCreated` / `CommandInputs` dialog class |
| UI | `ui.inputBox` / `ui.messageBox` (simple, blocking) | Real typed dialog with sliders/checkboxes, live regenerate |
| Lifetime | Runs once, returns | Persists, reacts to events |
| File | Single `fusion_conveyor_generator.py` | Manifest + command module |

Current `run(context)`: mode `1` = batch 3 configs, else custom `L,W,H,D,P,S,G,side_guards`
via CSV prompt. A judge-typed live dialog (stretch) requires converting to an add-in —
do not attempt inside the script's `inputBox` flow.

## 2. Object-model path (memorize this chain)

```python
app = adsk.core.Application.get()
ui = app.userInterface
design = adsk.fusion.Design.cast(app.activeProduct)  # None if no design open -> bail with messageBox
root = design.rootComponent
comp_occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
comp = comp_occ.component  # build everything here, not in root
```

Collections used: `design.userParameters`, `comp.sketches`, `comp.constructionPlanes`,
`comp.features.extrudeFeatures`, `comp.features.rectangularPatternFeatures`,
`design.exportManager`.

## 3. UserParameters — the parametric backbone (Brief §3.4)

Authoritative names — do not rename without updating every reference:

| Param | Kind | Expression / value |
|---|---|---|
| `ConvLength`, `ConvWidth`, `FrameHeight`, `RollerDia`, `RollerSpacing`, `LegSpacing` | base (mm) | numeric, e.g. `"1400 mm"` |
| `GuardHeight` | base (mm) | `max(G, 1.0)` mm — never 0, else zero-length extrude fails; visibility via suppression, not height |
| `RailW`, `RailH`, `LegSide`, `RollerClearance`, `GuardThick` | constants | engineering choices, still params (reviewers check the dialog) |
| `RollerMargin` | derived | `RollerDia / 2 + 10 mm` (end offset to first/last roller centre) |
| `RollerCount` | **formula** | `floor((ConvLength - 2 * RollerMargin) / RollerSpacing) + 1` |
| `LegCount` | **formula** | Brief: `floor(ConvLength / LegSpacing) + 1` (code currently `floor((ConvLength - LegSide)/LegSpacing)+1` — open divergence, see §9) |

API pattern (two-step — `add()` alone won't reliably accept cross-param formulas):

```python
up = design.userParameters
def find_or_add(name, expr, unit, comment=""):
    existing = up.itemByName(name)
    if existing:
        return existing
    return up.add(name, adsk.core.ValueInput.createByString(expr), unit, comment)

find_or_add("RollerCount", "floor((ConvLength - 2 * RollerMargin) / RollerSpacing) + 1", "", "roller instances")
up.itemByName("ConvLength").expression = "1400 mm"  # reconfig = edit expression, never rebuild features
```

Notes:

- `units=""` (empty string) for unitless counts. `"mm"` for lengths.
- `UserParameters.add` does **not** accept boolean `ValueInput` — guard on/off must be
  `feature.isSuppressed`, never a bool param.
- Updating a config = set base expressions + `design.computeAll()` (see §8). Never
  delete/recreate the feature tree per config — that risks §2.3A duplicate-geometry fails.

## 4. ValueInput — `createByString` vs `createByReal`

- `ValueInput.createByString("RollerCount")` / `("GuardHeight")` / `("100 mm")` →
  parsed as expression with units/equations. **Use for every parametric qty, spacing,
  extrude distance, plane offset.**
- `ValueInput.createByReal(5)` → literal in **database units** (cm for length). Bakes a
  dead number — defeats parametrics. Only for genuinely fixed computed values.
- Rule of thumb: if a reviewer editing a User Parameter in the UI should move geometry,
  that geometry's input must have arrived via `createByString`.

## 5. Units — the 10× bug source (Brief §3.3)

- Fusion DB units for Design: **length = cm**, angle = rad. Always, regardless of
  document display units.
- `Point3D.create(x, y, z)` / `Vector3D` take **cm**. Our inputs are mm → **divide by 10**.
- `ValueInput.createByString("15 mm")` handles conversion for you — no /10 there.
- `component.boundingBox` returns cm → **multiply by 10** before comparing to mm inputs.
- `SketchCurve.length` and friends also return cm.

## 6. Sketches — raw points are NOT parametric

```python
sk = sketches.add(plane)
rect = sk.sketchCurves.sketchLines.addTwoPointRectangle(
    adsk.core.Point3D.create(0, 0, 0),
    adsk.core.Point3D.create(140, 2, 0))  # cm placeholders; real size comes from dimensions below
dim = sk.sketchDimensions.addDistanceDimension(p1, p2, orient, textPoint)
dim.parameter.expression = "ConvLength"  # THIS line is what makes it parametric
```

- Circle dia: `addDiameterDimension(circle, textPoint)` → `.parameter.expression = "RollerDia"`.
- Keep the `SketchLine`/`SketchPoint` objects you created; do not rely on
  `rect.item(0)` / `profiles.item(0)` ordering — not guaranteed stable.
- Initial rectangle size only needs to be sane; dimensions drive truth. Still pass
  cm values (`mm/10`), never raw mm.

## 7. Construction planes & axes

```python
inp = planes.createInput()
inp.setByOffset(comp.xYConstructionPlane, adsk.core.ValueInput.createByString("FrameHeight - RailH"))
rail_plane = planes.add(inp)
```

- Rails: offset XY by `FrameHeight - RailH`. Guards: offset XY by `FrameHeight`.
- Roller sketch plane: offset XZ by `RailW + RollerClearance`.
- Pattern direction: `comp.xConstructionAxis` (length = X per Brief §3.3).

## 8. Extrudes — retired API warning

> Repo currently calls `extrudes.createInput(...).setDistanceExtent(...)`.
> `setDistanceExtent` / `setAllExtent` are **RETIRED**. Migrate to:

```python
extrudes = comp.features.extrudeFeatures
inp = extrudes.createInput(profiles, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
extent = adsk.fusion.DistanceExtentDefinition.create(
    adsk.core.ValueInput.createByString("RailH"))
inp.setOneSideExtent(extent, adsk.fusion.ExtentDirections.PositiveExtentDirection)
feat = extrudes.add(inp)
```

or for trivial cases `extrudes.addSimple(profile, distanceValueInput, operation)`.
Extrude distances in this model: `RailH`, `ConvWidth - 2*(RailW + RollerClearance)`,
`FrameHeight - RailH`, `GuardHeight`.

## 9. RectangularPattern — counts come from Fusion, not Python

```python
qty = adsk.core.ValueInput.createByString("RollerCount")      # formula param, not a literal
sp  = adsk.core.ValueInput.createByString("RollerSpacing")    # pitch, centre-to-centre
entities = adsk.core.ObjectCollection.create(); entities.add(masterBody)
inp = patterns.createInput(entities, comp.xConstructionAxis, qty, sp,
    adsk.fusion.PatternDistanceType.SpacingPatternDistanceType)  # Spacing, NOT Extent
pattern = patterns.add(inp)
```

- `SpacingPatternDistanceType` = pitch (matches spec "centre-to-centre"). `Extent` type
  would silently rescale spacing when count changes — wrong.
- Same wiring for legs with `LegCount` / `LegSpacing`.
- Guards are ×2 fixed plates, not patterns — toggle via suppression:

```python
ext_guards.isSuppressed = not params.side_guards
```

## 10. Recompute + validate in code (Brief §5.1, never eyeball)

```python
design.computeAll()  # after every param edit, before reading bbox/values
bbox = comp.boundingBox
L = (bbox.maxPoint.x - bbox.minPoint.x) * 10.0  # cm -> mm
```

Per config assert + log pass/fail:

1. bbox L/W/H within ~5 mm of requested `L` / `W` / `H(+G if guards on)`.
2. `RollerCount` / `LegCount` `.value` read back from Fusion == independent Python
   recomputation via `floor` formulas (don't trust your own formula string).
3. Guard `isSuppressed == (not side_guards)` — test `False + G=150` proves independence.
4. (Stretch) `InterferenceInput` clash check rollers↔rails.

BOM quantities must be **read from the model** (`RollerCount` value / pattern count),
not recomputed in a way that can drift. Current `build_bom` recomputes — known gap.

## 11. Export, BOM mass, drawings (Brief §2.6/§10, stretch §9)

```python
os.makedirs(output_dir, exist_ok=True)
opts = design.exportManager.createSTEPExportOptions(path_step, comp)
design.exportManager.execute(opts)
```

- One STEP + one BOM CSV per config; STEP must open cleanly (Definition of Done).
- Mass estimate (stretch): `body.physicalProperties.mass` (kg, DB units) × qty → BOM column.
- 2D drawing (stretch): Drawing API from model — only if core validation is green first.

## 12. Troubleshooting cheat-sheet

| Symptom | First check |
|---|---|
| Geometry 10× off | `Point3D` mm passed as cm; bbox compared without ×10 |
| UI param edit does nothing | Extrude/pattern used `createByReal` or sketch lacks dimension expression |
| Spacing shrinks as count grows | Pattern uses Extent type instead of Spacing |
| Zero/extrude fail at `G=0` | `GuardHeight` floor at 1 mm + suppression (don't extrude 0) |
| Stale validation numbers | Missing `design.computeAll()` before reads |
| Duplicates after re-run | Feature tree rebuilt per config; fix = edit params in place, clean `ParametricConveyor*` occurrences once at build |
| `adsk` import errors in editor | Expected outside Fusion — `try/except ImportError` + LSP `reportMissingImports=false` (local config, gitignored) |
| `setDistanceExtent` exception | Retired API — migrate to `setOneSideExtent` + `DistanceExtentDefinition` |

## 13. Repo code-map (where brief requirements live)

- Ranges + `validate_inputs` → `fusion_conveyor_generator.py` §1 (`RANGES`, `ConveyorInput`).
  Known divergence: rejects `side_guards=False + G>0`, but Brief §7 edge case requires
  allowing it (suppression independent of height) — fix pending.
- Pure-Python derive/verify/signature/BOM (offline-testable) → §2
  (`derive_configuration`, `verify_configuration`, `deterministic_signature`, `build_bom`).
  Known divergence: `_compute_repeated_positions` uses `ceil`-redistribution while Fusion
  formulas + `validate_cad_model` use `floor`-pitch — counts can disagree; unify on brief formulas.
- Param create/update → §3 (`create_user_parameters`, `update_model_parameters`).
- One-time parametric tree (rails → master roller + pattern → master legs + pattern →
  guards) → §4 (`build_parametric_conveyor_model`). Reconfig never rebuilds.
- CAD validation (bbox×10, formula recompute) + STEP/BOM/report → §5
  (`validate_cad_model`, `export_bom_csv`, `export_step_file`, `run_batch_demonstration`).
- UI entry `run(context)` → §6 (mode 1 batch / mode 2 CSV `L,W,H,D,P,S,G,Yes/No`).
- Tests → `tests/test_conveyor_generator.py`. Baseline 2026-09-18: 8/8 pass
  (`unittest discover -s tests`). Demo keys are `C1/C2/C3`-style
  (`C2_medium_with_guards`, etc.) and aligned between code and tests.
- `README.md` was refreshed in the working tree (config names, run flow) — keep it
  in sync if `demo_configurations()` keys change again.

## 14. Definition of Done reminder (Brief §10)

Param edit regenerates with zero manual steps · validation logged, not eyeballed ·
no orphans after 3+ reconfigs · BOM matches model · STEP opens · assumptions written down
(rail section, roller clearance, min-leg-count rule, guard floor/suppression).
