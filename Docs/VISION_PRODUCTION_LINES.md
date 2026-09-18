# Vision — Interlockable Conveyor Construction Set (Production Lines, Lego-Style)

> Target: **the state of the art for automating roller-conveyor assemblies** —
> a planner picks modules, the generator emits the line, the BOM and the CAD
> agree by construction. This doc is the north star; `INTEGRATION.md` IF-gates
> are the entrance tickets, `ENGINEERING.md` the physics floor.

## 1. What "state of the art" means (acceptance bar)

1. **Hours, not weeks:** straight/curve/merge/stop modules configured from
   one dialog; full line CAD + BOM + validation report in a single run.
2. **Single source of truth:** parameters → CAD → BOM → layout can never
   drift (model-read counts, suppression readback, gated STEP export —
   the pattern this repo already enforces).
3. **Physical interlock:** any two modules dock with standard hardware in
   minutes, aligned first-time (pins locate, bolts clamp — §2).
4. **Reconfigurable:** a line re-sequences (straight↔curve swap, length
   change) by editing parameters/occurrences, never by remodelling.
5. **Automation-ready:** every module exposes drive, sensing and stop
   interfaces so a controls engineer can quote the line from our BOM.

## 2. Module system (taxonomy + interfaces)

**Taxonomy (build in this order):** S-straight · C-curve (done) · E-end/drive
unit (motor bay) · T-transfer/merge · P-pallet-stop/sensor gate · F-feet/
support set. Accessories (sensor brackets, baffles) attach to any module.

**Mechanical interface (all modules):**
- Datum: inlet/outlet ports from the generator (position + direction +
  carry height must match across the joint).
- Docking hardware per IF-060: end connection board, **40 mm-grid bolt
  pattern** (matches 40-series extrusion), **2 locating pins** (one round,
  one slotted for tolerance), shared fastener schedule (STANDARDS.md §3).
- Height/pitch continuity rule: carry surfaces coplanar within ±1 mm,
  roller pitch across a joint ≤ max(P₁, P₂) + 10 mm (no dead zones).

**Electrical/data interface (phase 2):** 24 V accessory bus with one
connector position per module end; module ID = generator signature
(`deterministic_signature` pattern) so the BOM line, CAD occurrence and
controls list share one key.

## 3. Roadmap (each phase demoable, each gate enforced)

- **Phase 0 — now:** parametric straight + tapered curve, validated CAD/BOM
  (done, 37/37 tests, 7/7 live checks).
- **Phase 1 — located parts:** IF-010 holes → IF-020 shafts/bearings →
  IF-040 extrusion supports (conveyor stops floating).
- **Phase 2 — powered + aware:** IF-030/031 drive option, IF-051/052
  sensing/stop; first powered demo (motor → belt → rollers turn).
- **Phase 3 — dockable:** IF-060 connection boards; layout manager mates
  straight→curve→straight with joint-pitch validation; first 3-module line.
- **Phase 4 — productized set:** catalogue of presets (30/45/90 curves,
  standard lengths), one-click line BOM with bought-out rows, assembly
  instructions generated from the model.

Gate rule (no exceptions): a phase ships only with its validator counts,
its STEP/BOM pair, and its standards citations updated.
