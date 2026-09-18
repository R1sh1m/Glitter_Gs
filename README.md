# Glitter_Gs

Fusion API implementation for a **parametric multi-type gear pair generator**.

## Implemented Scope
- Gear types: **external spur** and **external helical**
- Inputs:
  - `gear_type`: spur/helical
  - `mn` (normal module): 1.5–3 mm
  - `z1`: 18–40
  - `z2`: 30–80
  - `pressure_angle_deg`: fixed at 20°
  - `face_width`: 6–15 mm
  - `helix_angle_deg`: 0–30° (must be 0 for spur)
- Automatic verification:
  - tooth-count bounds
  - ratio `i = z2/z1`
  - pitch diameters
  - center distance
  - pressure/helix consistency
- Idempotent regeneration:
  - stale generated components/joints with `GG_` prefix are removed before rebuild.

## Gear Equations / Convention
This project uses a **normal-module convention** for both spur and helical gears.

- Transverse module: `mt = mn / cos(beta)`
- Pitch diameters: `d1 = mt * z1`, `d2 = mt * z2`
- Transmission ratio: `i = z2 / z1`
- Center distance: `a = (d1 + d2)/2`

For spur gears, `beta = 0`, so `mt = mn` and the pitch diameter reduces to `d = m*z`.

## Files
- `/home/runner/work/Glitter_Gs/Glitter_Gs/fusion_gear_generator.py`
  - input validation
  - gear mathematics
  - automatic verification
  - Fusion geometry generation (spur + helical)
  - assembly positioning and motion-link attempt
- `/home/runner/work/Glitter_Gs/Glitter_Gs/tests/test_gear_math.py`
  - focused checks for:
    - configuration A (spur 2:1)
    - configuration B (helical 3:1)
    - additional unseen parameter set

## Required Example Configurations
- **A – Spur pair**: `m=2`, `z1=20`, `z2=40`, `PA=20°`, `b=10`
  - ratio 2:1, `d1=40 mm`, `d2=80 mm`, `a=60 mm`
- **B – Helical pair**: `m=2`, `z1=20`, `z2=60`, `PA=20°`, `b=12`, `beta=20°`
  - ratio 3:1 with dimensions from the normal-module convention above

## Running in Fusion
1. Open Fusion and run `/home/runner/work/Glitter_Gs/Glitter_Gs/fusion_gear_generator.py`.
2. In `run(context)`, choose either demo configuration or replace with your own `GearInput`.
3. Re-run with new parameters to regenerate without stale duplicate generated items.

## Local Verification (outside Fusion)
```bash
cd /home/runner/work/Glitter_Gs/Glitter_Gs
python -m unittest -v
```
