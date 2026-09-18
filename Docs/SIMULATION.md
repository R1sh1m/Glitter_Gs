# Simulation Handbook — What the API Can and Cannot Do

> Verdict (verified 2026-09-18 against the installed Fusion 360 Python
> bindings): **zero** occurrences of `Simulation` in `adsk/fusion.py` — no
> Study, load, constraint, or results API exists. The Simulation workspace
> (Static Stress, Modal, Shape Optimization, …) is **manual-only**. Anything
> claiming API-driven Nastran solves on this build is wrong; re-verify after
> every Fusion update by re-running the grep in §4.

## 1. Greedy optimization loop (what we run instead — and it is real)

The API *does* expose everything an analytic optimizer needs: UserParameters
(read/write), `computeAll()`, `physicalProperties` (mass/volume), bounding
boxes, STEP export. So the closed loop is:

1. **Propose** (offline, tested): beam/shaft/bearing models iterate D/S/W —
   roller mid-span deflection `δ ∝ F·L³/(E·I)`, shaft shear, bearing L10
   life, leg Euler buckling — minimizing mass subject to caps.
2. **Apply**: write winners back via `createByString` expressions (one
   `computeAll()`), exactly like `calculate_load_advisory` feeds the dialog.
3. **Audit**: bbox + mass + count readback; STEP gated on PASS.
4. This fixes and improves things greedily every run **without** the
   Simulation workspace. Owners: `fusion_curve_module.calculate_load_advisory`
   (heuristics today) → analytic models next (tracked below).

## 2. Manual study recipes (run by hand, prescribed here)

| Question | Study | Setup (units mm/kg) |
|---|---|---|
| Leg posts buckling/yield under full load | Static Stress | Fix: foot-plate bottoms (6). Load: total payload + frame mass / 6 downward on rail tops at leg stations. Material: structural steel. Pass: FoS ≥ 3, report max von Mises + displacement |
| Roller tube mid-span sag | Static Stress | Fix: shaft ends (bearing seats). Load: payload/3 uniform on tube OD. Pass: sag ≤ 0.5 mm, FoS ≥ 2 |
| Frame resonance vs motor rpm | Modal Frequencies | Fix: feet. Compare 1st mode vs motor excitation (50/60 Hz + harmonics) |
| Bracket lightening (later) | Shape Optimization | Preserve: bore + mount faces; reduce mass 20% |

Record study name, date, inputs, screenshots and verdict in this file's log
(§5); feed numbers back into the advisory caps.

## 3. Analytical models to implement (greedy core roadmap)

- `roller_deflection_mm(F, L, D, wall)` — hollow-taper approx as equivalent
  cylinder at mean diameter; cap 0.5 mm → drives D/wall.
- `shaft_shear_ok(F, dia)` + `bearing_l10_hours(F, rpm)` (6002 dynamic
  rating C=5.85 kN catalogue) → drives shaft dia + bearing choice.
- `leg_buckling_ok(F, H, section)` Euler with end-fixity 2 → drives S/post.
- Objective: total steel mass (already estimated per part).

## 4. Re-verification command (run after each Fusion update)

```powershell
python -c "import re; t=open(r'C:\Users\Rishi Misra\AppData\Roaming\Autodesk\Autodesk Fusion 360\API\Python\defs\adsk\fusion.py',encoding='utf-8').read(); print('Simulation hits:', len(re.findall('Simulation', t)))"
```

## 5. Study log

| Date | Study | Target | Result | Follow-up |
|---|---|---|---|---|
| — | — | — | — | (none yet — first manual run pending) |
