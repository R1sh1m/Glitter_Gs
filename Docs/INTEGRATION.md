# Integration Handbook — From Floating Solids to Working Conveyor

> Non-code companion to `ENGINEERING.md` (sizing) and `STANDARDS.md`
> (sources). Part numbers like `IF-010` are **interface requirements**: code,
> CAD review and BOM sign-off all trace to them. Evidence:
> `reference models/` (teardown §1), `standards/` (§2 sources).

## 1. Reference teardown (`reference models/` — Poly-V belt conveyor)

Measured 2026-09-18 from `Conveyor Assembly.stp` (3.9 MB), `Roller.stp`,
`4080 aluminum profile.stp`, `Anti-slip foot cup.stp`, `Conveyor_1/2.jpg`:

- **Frame = 4080 + 4040 T-slot aluminum extrusion**, not plate: legs, cross
  members, motor plate all hang off slots via connection boards/plates and
  `Support foot connection plate`s. Legs end in `Anti-slip foot cup`s
  (M-thread stem + pad) — adjustable height + floor levelling.
- **Side plates carry HOLE ROWS** (visible in both photos): one hole per
  roller seat at pitch P, plus guard-mount holes. Rollers are located by
  holes, never by eye.
- **Rollers are a sub-assembly**: tube + stepped shafts + `Positioning rod`
  features + **multi-wedge (Poly-V) grooves** (`Active multi-wedge pulley`
  on the drive side). Belt line runs under the bed to the motor.
- **Drive = under-slung motor on `Motor Tension Push Plate`** (slotted holes
  for belt tensioning) + mount bracket, mid-span under the frame.
- **Accessories are first-class**: `Front Sensor Bracket` + photoelectric
  sensor (`D-M9N`), `Pallet Stop` on `MGPM20-40` guided cylinder +
  `Thrust cylinder base plate`, `Plastic baffle`, end `Connection Board`s
  joining frame segments.
- **Lesson:** every catalogue conveyor is frame + located holes + roller
  assembly + drive + feet + accessories. Our generator's straight/curve
  solids are only the first of these layers (§2 gaps).

## 2. Gap analysis (our CAD today — see curve end photo)

| # | Gap vs reference | Interface requirement |
|---|---|---|
| 1 | Rollers float; rails have no seats | **IF-010** rail hole row: one shaft bore per roller station at pitch P (curve: at angular pitch), bore = shaft ⌀ + clearance, anti-rotation flat/hex where the shaft standard needs it |
| 2 | Rollers are solid tubes, no shafts/bearings | **IF-020** roller assembly: tube + ⌀12/14 shaft, female thread **M8×15** both ends (Interroll series), precision bearing **6002-2RZ** (15×32×9) or stainless variant; stepped journals per `Roller.stp` |
| 3 | No drive of any kind | **IF-030** drive-ready roller: Poly-V multi-wedge grooves (or sprocket option for chain curves); **IF-031** motor bay: under-slung mount plate with tension slots + pulley data (centre distance, ratio, belt length in BOM notes) |
| 4 | Legs are solid blocks, no feet/adjustment | **IF-040** support = 40-series extrusion post + connection plate + anti-slip foot cup (match `reference models/`); anchor-hole option in foot plate |
| 5 | No sensing/stopping | **IF-051** sensor bracket interface (slotted M12/M18 photoeye mount, one per module end); **IF-052** stop-cylinder bolt pattern (MGPM20 footprint) on side plate |
| 6 | Modules can't dock (LEGO goal) | **IF-060** docking: end `Connection Board` with 40 mm-grid bolt pattern + 2 locating pins; inlet/outlet ports defined by generator (`VISION_PRODUCTION_LINES.md`) |

## 3. Implementation order (each step independently shippable/testable)

1. **P1 — IF-010 hole rows** (straight rails, then arc rails): hole features
   in the same sketch/pattern as rollers so seats can never drift from
   roller positions; validator counts holes == rollers.
   **DONE curve 2026-09-18:** 18 bores/rail (bore dia 16 for dia-14 shaft),
   both arc rails, scoped cuts, guards untouched, STEP re-exported
   (`Curve90_Ri800_holes.step`). End stations stay open (rail-to-rail ends
   leave no material for a full bore) — validator honesty band N-2..N.
   Straight side: positions math + builder + tests in place, live sign-off
   pending first straight live build.
2. **P2 — IF-020 roller assembly**: shaft + bearing-seat recesses; BOM gains
   shaft/bearing rows; mass model switches tube to hollow.
3. **P3 — IF-030/031 drive option**: grooved master roller variant + motor
   plate with slots; BOM notes carry pulley/belt data.
4. **P4 — IF-040 extrusion supports + IF-051/052 accessories**: replace solid
   legs; bracket/cylinder patterns as suppressed-by-default features.
5. **P5 — IF-060 docking**: connection boards + pin holes; layout manager
   mates them (see `VISION_PRODUCTION_LINES.md`).

Rule: no new solid without its holes, no new pattern without its validator
count, no new bought-out part without a BOM row and a standard in
`STANDARDS.md`.

## 4. Live-execution lessons (Fusion API, paid for in full)

- **Sketch-on-face needs an area gate:** the host face loop appears as a
  sketch profile; cutting with it deletes the whole body (twice observed).
  Filter profiles to bore area (`keeps_hole_profile`, 0.5–2x band).
- **Holes follow station angle x band centre**, never raw tube-end rims
  (shafts extend past tube ends into rails by design).
- **Scope cuts** with `participantBodies=[rail]` (python list) or stacked
  bodies all get pierced.
- **Check the timeline for Move features first:** stray manual moves shift
  absolute coordinates between sessions (radii/positions then mislead);
  restore authored state by deleting them, and verify with rim/band radii.
- **One structural delete per run**, exact names only — blind index deletes
  hit the wrong features, and combined delete transactions hang the solver.
- **Prints vanish on failure:** split probe/build/verify into small runs so
  every success leaves a readable trail.
- **Deploy-copy rule:** `conveyor_addin/fusion_conveyor_generator.py` is a
  byte-copy of the root engine (self-contained install); refresh it after
  every root edit or tests import stale code.
