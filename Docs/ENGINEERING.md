# Engineering Handbook — Roller Conveyor Sizing & Theory (no code)

> **Rule of this repo:** everything non-programming lives in `Docs/`. Code files
> (`fusion_conveyor_generator.py`, `fusion_curve_module.py`, `conveyor_addin/`)
> implement these rules; they never redefine them. If this doc and a docstring
> disagree, **this doc wins** and the code must be fixed.
> Related: `INTEGRATION.md` (holes, shafts, drives, docking), `STANDARDS.md`
> (source index), `VISION_PRODUCTION_LINES.md` (LEGO roadmap),
> `reference models/` (measured teardown), `standards/` (downloaded sources).

## 1. Straight-module sizing (spec core, Problem Statement A)

| Symbol | Range (mm) | Meaning |
|---|---|---|
| L | 800–2000 | Overall conveyor length |
| W | 300–600 | Overall conveyor width |
| H | 500–900 | Floor to frame top |
| D | 40–80 | Roller outside diameter |
| P | 80–150 | Roller pitch, centre-to-centre |
| S | 500–1000 | Leg-station spacing |
| G | 0–150 | Side-guard height (0 allowed) |

Structural constants (exposed as Fusion User Parameters, reviewer-editable):
rail section `20×40`, roller-to-rail clearance `10`, leg post `40×40`,
guard plate `5`. Steel `7850 kg/m³` for mass estimates. Curve tubes are
modelled **hollow** (3 mm wall, capped ends — live 240.6 vs 1277.2 cm³
solid); straight-module rollers remain solid assumption until their live
build (documented overestimate vs hollow tube).

- **End margin:** `RollerMargin = D/2 + 10`. First/last roller centres sit one
  margin inside each frame end.
- **Roller count:** `N = floor((L − 2·Margin)/P) + 1`, min 2 when span > 0
  (stability). Fixed-pitch `Spacing` pattern — pitch never rescaled.
- **Leg stations:** `M = floor((L − LegSide)/S) + 1`, min 2. Subtracting
  `LegSide` keeps the last 40 mm post inside the envelope (the Brief's
  simplified `floor(L/S)+1` overhangs, e.g. C3 L=2000/S=1000).
- **Guards:** visibility = feature suppression, independent of height.
  `GuardHeight` floors at 1 mm in CAD only (zero-length extrudes fail);
  `side_guards=False + G>0` is legal and tested.
- **Heights:** overall H = frame top; validation uses
  `max(roller_top, guard_top)` so low guards (G < D/2) don't false-fail.

## 2. Load advisory (Tier-2, heuristic — not FEA)

Optional `calculate_load_advisory(box_mass, box_length, box_width)` maps a
payload to *recommended spec values*; it never bypasses spec ranges (outputs
are clamped, warnings explain the clamp):

- **Pitch:** `P ≤ Lbox/3` — at least **3 rollers under the load at all times**
  (Interroll planning rule, see `standards/interroll-*.pdf`). Shorter boxes
  need tighter pitch; below spec minimum ⇒ warn, use min P.
- **Diameter by mass-per-roller (≈mass/3):** ≤60 kg → D50 · ≤120 kg → D60 ·
  above → D80. Shaft/bearing check (IF-standards in `INTEGRATION.md`) governs
  final sign-off.
- **Leg spacing by mass:** ≤60 kg → 1000 · ≤120 kg → 700 · above → 500.
- **Width:** straight `W = box + 50`; **curve `W = box + 100`** (extra sweep
  margin — a curve roller for a given box is always longer than the straight
  equivalent; standardize on the curve length for mixed lines).

## 3. Curve theory (full-tapered only)

Cylindrical rollers on a curve slip/skew (`2πRo > 2πRi`). Tapered rollers fix
it kinematically: **`d_in/Ri = d_out/Ro`** so surface speed tracks angular
velocity across the width. Industry standard cone ≈ **3.6°**, roller axes
aimed at the curve centre, shaft tilted ≈1.8° so the cone top runs level
(Interroll; Damon). Our demo: Ri800/W450/D50 → d_out 78.1, cone ≈3.9°.

- **Arc lengths:** `A(R) = R·Θ(rad)` for inner/centre/outer radii.
- **Roller count (outer-arc floor pitch + angular cap):**
  `usable = Ro·Θ − 2·(D/2+10)`, `N = max(floor(usable/P)+1, ceil(Θ/5°)+1)`,
  min 3. Adjacent-roller angle must stay **≤5°** (Damon/Interroll); when the
  cap binds, pitch redistributes (`usable/(N−1)`, e.g. demo 105.2 mm).
  Demo 90°/Ri800/W450/P110 → **N=19 @ 5.0°**, 3 leg stations.
- **Curve width vs jams (Interroll):** `Ra_min = 50 + √((Ri+W)² + (Lbox/2)²)`,
  `ELmin = Ra_min − Ri`, round up to 50 mm increments; reject/warn when the
  frame is narrower. Long boxes jam in narrow curves even with open sides.
- **End treatment:** curve modules run rollers **rail-to-rail** (flush ends
  for clean handoff); envelope = `Ro + d_out`. (Straight modules inset by
  margin instead — deliberate, documented asymmetry.)
- **Rail seat holes (IF-010):** bore dia 16 for dia-14 shafts, positioned at
  station angle x rail band centre (`Ri+RailW/2`, `Ro-RailW/2`); end stations
  stay open bores. See `INTEGRATION.md` §3.
- **Fusion expression limits (live-proven 2026-09-18):** strip angle units
  with `/ 1 rad`; `pi` and `max()` are unavailable — Python holds the
  canonical `max()`, Fusion carries both operands (`C_RollerCount`,
  `C_RollerCountMin`) for audit readback.

## 4. Status ledger (what is proven vs assumed)

- **Proven live in Fusion:** taper frustum (`Cone` face, analytic vs measured
  volume 1277.6 vs 1277.2 cm³), 19-roller 90° build, 7/7 bbox/count/
  suppression checks, STEP gated on PASS (`tests/` 37/37 offline).
- **Assumed, pending physical sign-off:** solid-roller mass, heuristic
  D/S steps, 120 mm taper-OD shop limit, bearing/shaft ratings — see
  `INTEGRATION.md` IF-gates and `STANDARDS.md` for the sources to close them.
