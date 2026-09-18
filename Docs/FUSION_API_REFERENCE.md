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
| `LegCount` | **formula** | `floor((ConvLength - LegSide) / LegSpacing) + 1` — intentional refinement of Brief's `floor(ConvLength / LegSpacing) + 1` so the last 40 mm post stays inside the envelope (see `leg_count_for()` docstring; single-sourced 2026-09-18) |

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

## 8. Extrudes — retired API migrated (2026-09-18)

> Repo previously called `extrudes.createInput(...).setDistanceExtent(...)`.
> `setDistanceExtent` / `setAllExtent` are **RETIRED** and now migrated to:

```python
extrudes = comp.features.extrudeFeatures
inp = extrudes.createInput(profiles, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
extent = adsk.fusion.DistanceExtentDefinition.create(
    adsk.core.ValueInput.createByString("RailH"))
inp.setOneSideExtent(extent, adsk.fusion.ExtentDirections.PositiveExtentDirection)
feat = extrudes.add(inp)
```

Central helper `_extrude_profiles_one_side()` wraps this with a legacy
fallback for very old builds. Extrude distances: `RailH`,
`ConvWidth - 2*(RailW + RollerClearance)`, `FrameHeight - RailH`, `GuardHeight`.

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
| `adsk` import errors in editor | Expected outside Fusion — `try/except ImportError` + `reportMissingImports=false` (local config, gitignored). No stubs vendored by policy; `adsk.*` intelligence comes from Fusion's Edit bridge, pure-Python keeps full LSP |
| `setDistanceExtent` exception | Retired API — migrated 2026-09-18 to `setOneSideExtent` + `DistanceExtentDefinition` (`_extrude_profiles_one_side`, legacy fallback retained) |

## 13. Repo code-map (where brief requirements live)

- Ranges + `validate_inputs` → `fusion_conveyor_generator.py` §1 (`RANGES`, `ConveyorInput`).
  Status 2026-09-18: FIXED — `side_guards=False + G>0` is now accepted
  (suppression independent of height, Brief §7 edge case).
- Pure-Python derive/verify/signature/BOM (offline-testable) → §2
  (`derive_configuration`, `verify_configuration`, `deterministic_signature`, `build_bom`).
  Status 2026-09-18: FIXED — floor-pitch unified via `roller_count_for()` /
  `leg_count_for()` / `_compute_floor_positions()`; Python, Fusion formulas,
  validator and BOM share one implementation. `build_bom_from_model()` reads
  counts back from Fusion when available; phantom `frame_cross_members` removed.
- Param create/update → §3 (`create_user_parameters`, `update_model_parameters`).
  Status 2026-09-18: `update_model_parameters` validates before touching live
  params, single `computeAll()`, `is not None` suppression guard.
- One-time parametric tree (rails → master roller + pattern → master legs + pattern →
  guards) → §4 (`build_parametric_conveyor_model`). Reconfig never rebuilds.
  Status 2026-09-18: extrudes migrated, Identical pattern compute, sketch
  handles retained + profile-count asserts, timeline undo grouping, safe
  occurrence cleanup.
- CAD validation (bbox×10, formula recompute) + STEP/BOM/report → §5
  (`validate_cad_model`, `export_bom_csv`, `export_step_file`, `run_batch_demonstration`).
  Status 2026-09-18: validator self-computes, `round()` counts, height uses
  `max(roller-top, guard-top)`, suppression readback, STEP gated on PASS,
  BOM prefers model counts, Configurations-table sync attempted with
  sequential fallback.
- UI entry `run(context)` → §6 (mode 1 batch / mode 2 CSV `L,W,H,D,P,S,G,Yes/No`).
  Status 2026-09-18: Parametric-design gate, timeline-rollback cleanup on
  build failure, custom path gated the same as batch.
- Tests → `tests/test_conveyor_generator.py`. Baseline 2026-09-18: 11/11 pass
  (`unittest discover -s tests`). Demo keys are `C1/C2/C3`-style
  (`C2_medium_with_guards`, etc.) and aligned between code and tests.
- `README.md` was refreshed in the working tree (config names, run flow) — keep it
  in sync if `demo_configurations()` keys change again.

## 14. Definition of Done reminder (Brief §10)

Param edit regenerates with zero manual steps · validation logged, not eyeballed ·
no orphans after 3+ reconfigs · BOM matches model · STEP opens · assumptions written down
(rail section, roller clearance, min-leg-count rule, guard floor/suppression).

## 15. GitHub reuse catalog (`AutodeskFusion360` org, 34 repos)

Policy: **reference-only** — idioms are re-implemented by hand in our script;
no third-party files are vendored (keeps licensing trivial and the single-file
script deployable via Scripts and Add-Ins). Licenses below are per-repo as
published; `FusionAPIReference` (CC BY-NC-SA) is local-lookup only, never bundled.

| Rank | Repo | License | Reuse in this project |
|---|---|---|---|
| 1 | `ExtractBOM` | MIT | `walkThrough` loop shape (`allOccurrences` → dedupe → sum `body.volume`) → mass/volume BOM columns. Volume is cm³ — convert. |
| 2 | `EmptySketchFinder` | MIT | `find_empty_sketches()` predicate → `clean_for_export()` pre-STEP gate; fix its `-1` hack, add `sketchDimensions`/`sketchTexts` guard from `AutoDeleteEmptySketch`. Keep confirm/log, never silent-delete. |
| 3 | `BulkExportSketchesAsDXF` | MIT | Stay-open export dialog (`isOKButtonVisible=False`, Export button, `status_log` + `doEvents()`, `_update_preview` on `inputChanged`) → conveyor Export/Params dialog (Wave B). Its DXF-options API is preview — STEP stays primary. |
| 4 | `AddInSample` | MIT | Script→Add-in conversion skeleton (`run`/`stop`, `handlers=[]` anti-GC, `addButtonDefinition`, `commandCreated→commandInputs→execute`). Modernize `toolbarPanels.item(0)` → `workspaces/itemById`. |
| 5 | `Bolt` | MIT | Best parametric template: `ValueInput` + `executePreview` live update, chamfer/fillet, `threadFeatures` for leveling feet (guard `recommendData` — needs network). |
| 6 | `SpurGear` | MIT-stated | `evaluateExpression(...,cm/deg)` + `addNewComponent(Matrix3D)` + pattern structure. Skip involute math — we need cylinders/boxes. |
| 7 | `ChangeComparer_Python` | sample* | Same-viewpoint C1/C2/C3 snapshots (`restoreCamera` → `saveAsImageFile` → compare page). Verify `InspectPanel` ID on current Fusion. *No LICENSE file — attribute, don't redistribute standalone. |
| 8 | `ParameterIO_Python` | MIT-stated | CSV↔params retry ordering (dependency-safe expression sets) → `variants.csv` driven configs. |
| 9 | `SketchRepair` / `SketchChecker_Python` | MIT | `find_gaps`/`getLoopEndPoints` pre-extrude gates; Fix-All coincident repair. |
| 10 | `DXFBulkImport` | MIT | `close_sketch_gaps` + `profiles.count==0` gate; `entry.py` input-enable/validation discipline. Strip `ezdxf`/`fusionAddInUtils` deps. |
| 11 | `Fusion360DevTools` | MIT | cProfile perf capture + API Object Explorer for live signature discovery. Note Py3.14 `sys.monitoring` slot fix. |
| 12 | `FusionMCPSample` | MIT | Thread-safe `execute_api_script` + `get_screenshot` agent loop. Never call Fusion API from the HTTP thread (marshal via custom event). |
| 13 | `Pipe` / `Bottle` | MIT-stated | Sweep rollers / revolve+shell end-caps; curved-rail stretch only. |
| 14 | `SurfaceText_python` | MIT-stated | Etch config name on frame (`sketchTexts` + 0.5 mm Cut); 2015 code + bundled FontTools — test early. |
| 15 | `ImportSplineCSV` / `DXFSplineToPolyline_Python` | MIT-stated/sample | CSV→params drive; `evaluator.getStrokes(tol)` fidelity note. Guard `SketchControlPointSpline` on version. |
| 16 | `DeleteEmptyComponents` | MIT | Assembly purge pre-export. Destructive — confirm via dialog. |
| — | `Intersections` | MIT-stated | Do NOT use for solid clash (plane/curve math only); occurrence-walk pattern only. Real clash: `analyzeInterference()` / `boundingBox.intersects()`. |
| — | `NativeUI` | MIT | Skip — C++/Windows-only, no benefit for Python. |
| — | `DesignAutomationSamples`, `EntitlementAPI`, `HttpSample` | MIT | Out of scope: APS auth/credits, store licensing, network-in-judging risk. |

"MIT-stated" = README claims MIT but no `LICENSE` file in repo; treat as reusable
sample with attribution, don't relicense.

## 16. Integration log

| Date | Wave | What was integrated (as re-implemented idiom) | Source | Verified by |
|---|---|---|---|---|
| 2026-09-18 | P0/P1 core | `setOneSideExtent` migration, floor-pitch counts, model-read BOM, guard independence, sketch hardening, undo groups, export-on-PASS | §§8–13 above | 17/17 offline tests |
| 2026-09-18 | A | Measured-vs-estimated mass BOM column; `clean_for_export()` hygiene gate (EmptySketchFinder predicate + AutoDeleteEmptySketch guards) | §15 ranks 1–2 | unit + mock tests |
| 2026-09-18 | B | `conveyor_addin/` dialog (typed inputs, live preview, Export button + log, model reuse) on the AddInSample skeleton | §15 ranks 3–4 | 5 offline helper tests; live Fusion run pending |
| 2026-09-18 | C | Same-viewpoint snapshots + `snapshots.csv`/`comparer.html`; per-config browser labels; best-effort guard-face etch | §15 ranks 7, 14 | writer/helper tests; capture+etch need live Fusion |
