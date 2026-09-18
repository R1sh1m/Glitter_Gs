# End-to-End Demo Runbook — Fusion App (no code, just clicks)

> Proves the whole system working inside Fusion: straight + curve modules,
> docking line, deliverables. Assumes the add-in is installed (see §0) and
> designs `ghost_testing_1` (curve) exist. Time: ~15 minutes.

## 0. One-time setup (Windows)

1. Copy the repo `conveyor_addin/` folder (with the engine `.py` files beside
   it) to `%APPDATA%\Autodesk\Autodesk Fusion 360\API\AddIns\`.
2. After every repo update, re-copy the `.py` files (or the UI shows stale
   metadata — the manifest is cached: if version/OS looks old, restart
   Fusion; Utilities → Scripts and Add-Ins → Add-Ins → run `conveyor_addin`,
   enable *Run on Startup*).
3. Keep the MCP add-in running only when an agent session needs it.

## 1. Act 1 — Straight C2 module (ghost_testing_2)

> The straight tree is too solve-heavy for the script bridge — build it
> **in-process** via the add-in (no timeout), then the agent finishes holes
> + shafts over the bridge (light ops).

1. Open `ghost_testing_2` (it holds retired `OLD_*` features from the first
   attempt — leave them; the rebuild takes clean names).
2. Add-ins panel → `Parametric Conveyor Generator` → Straight Section,
   preset `C2: Medium Standard (With Guards)` → Build/Apply.
3. Expect: rails 0–1400, 13 rollers (not 39 — direction-two is pinned),
   2 leg stations, guards; message box shows checks.
4. Ping the agent: it validates (subset bbox), cuts rail seat bores +
   shafts, screenshots, STEP/BOM.

## 2. Act 2 — Curve module (ghost_testing_1)

1. Open `ghost_testing_1`: 90° tapered curve, 19 rollers, shafts, bearings,
   housings, motor bay, feet, sensor bracket, dock boards.
2. Top view: concentric rails, small-ends-in rollers, 18 seat bores/rail.
3. Change Parameters → `C_CurveAngle` 90 → 45: pattern, rails, legs follow.

## 3. Act 3 — Docked line (assembly doc)

1. New Design (assembly), derive/insert both module docs, mate outlet→inlet
   per `Docs/ASSEMBLY.md` (pins locate, bolts clamp, carry heights ±1 mm).
2. Drop test boxes on the line; drag through straight → curve handoff.

## 4. Act 4 — Deliverables close-out

`~/ConveyorGenerator_Output/`: per-module STEP (opens clean), BOM CSVs with
masses, `validation_report.txt`, OPC-UA nodeset JSONs. Suite: 56/56 offline.

## Troubleshooting

- Stale version/OS in add-in panel → re-copy files, restart Fusion.
- `Part Design documents can only contain one component` → expected: one
  module per doc, assemble via derivation (Act 3), never in-doc occurrences.
- Solver weirdness after manual drags → check Timeline for Move features;
  delete them to restore authored positions.
