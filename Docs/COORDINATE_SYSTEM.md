# Coordinate System Specification — Conveyor Engineering Automation Platform

> **Normative.** This document is the single source of truth for all frames,
> port definitions, unit boundaries, and transform conventions.
> Code (`conveyor_addin/core/`, `docking/`, `modules/`, `fusion/`) implements
> these rules and never redefines them. If a docstring disagrees with this
> file, fix the code.
>
> Related: `Docs/ENGINEERING.md` (sizing/taper), `Docs/ASSEMBLY.md` (Part-doc
> rule), `Docs/VISION_PRODUCTION_LINES.md` (IF-060 Lego docking).

---

## §1 World frame

1. Right-handed Cartesian frame. `+Z` is up (anti-gravity).
2. All Python engineering math uses **millimetres** for length and **degrees**
   for angles unless a symbol is explicitly suffixed (`_cm`, `_rad`).
3. Fusion 360 database units are **centimetres** (length) and **radians**
   (angle). Conversion happens ONLY at the Fusion boundary via
   `conveyor_addin/core/units.py`. Raw `/ 10.0` / `* 10.0` outside that
   module is forbidden (CI-gated).
4. Flow is unbounded: a layout may extend along any horizontal heading.
   There is no global "conveyor axis".

## §2 Module local frame

1. Every module owns a local right-handed frame `M = (O_m, X_m, Y_m, Z_m)`:
   - `O_m` — inlet **bottom-center at floor level**, i.e. `(0, 0, 0)` local.
   - `X_m` — nominal flow direction (unit).
   - `Y_m` — left lateral when facing flow (`Y = Z × X`), unit.
   - `Z_m` — up, nominally `(0, 0, 1)`.
2. The **carry plane** (roller tangent plane) is `z = H` where `H` is the
   frame height in mm (`500–900` straight spec).
3. Rationale: legs, bounding boxes, and `validate_cad_model()` are already
   floor-based; ports are carry-plane offsets of this frame. One origin,
   two elevations — never two origins.
4. Module placement in a layout is a rigid transform `T = (R, t)` mapping
   `M`-local mm coordinates to world mm coordinates: `p_world = R·p + t`.

## §3 Port frame (universal, all module types)

1. Every module exposes exactly `inlet_port` and `outlet_port`
   (`ConveyorPort`, see `docking/port.py`).
2. Port frame `P = (O_p, x, y, z)`:
   - `O_p` — centre of the carry plane at the module end (mm, module-local).
   - `x` — **direction**: unit flow vector at that port.
   - `z` — **up**: unit vector, nominally `(0, 0, 1)`.
   - `y` — **lateral_axis**: `y = z × x`, unit, right-handed.
     The legacy dict key `"normal"` is retained ONLY in
     `ConveyorPort.from_legacy_dict()` and maps to `lateral_axis`.
     New code uses `lateral_axis`; do not use the word "normal" for ports
     (it collides with CAD face-normal terminology).
3. Ports carry engineering payload: `width_mm`, `height_mm` (carry height
   `H`, not overall height), `roller_pitch_mm` (see §5), `conveyor_type`,
   `connection_rules` (see `docking/connection_rules.py`).

## §4 Per-type port definitions (module-local mm)

All vectors are unit length. `W` = width, `H` = carry height, `L` = length.

### §4.1 Straight (length `L`)

- inlet: `O=(0, W/2, H)`, `x=(1,0,0)`, `y=(0,1,0)`, `z=(0,0,1)`.
- outlet: `O=(L, W/2, H)`, `x=(1,0,0)`, `y=(0,1,0)`, `z=(0,0,1)`.

### §4.2 Curved (inner radius `Ri`, angle `Θ`, centre radius `Rc=Ri+W/2`)

Curve local frame places the arc centre at `(0, 0)` in plan, arc swept
from angle `0` to `Θ` about `+Z`:

- inlet: `O=(Rc, 0, H)`, `x=(0,1,0)`, `y=(-1,0,0)`, `z=(0,0,1)`.
- outlet: `O=(Rc·cosΘ, Rc·sinΘ, H)`,
  `x=(-sinΘ, cosΘ, 0)`, `y=(-cosΘ, -sinΘ, 0)`, `z=(0,0,1)`.

Note the inlet flow `+Y` vs straight `+X`: a collinear straight→curve
dock requires a −90° yaw. This is by construction (arc tangent), not an
error — the 6-DOF solver derives it from the port bases.

### §4.3 Incline (length `L`, rise `ΔH`)

- inlet: `O=(0, W/2, H_in)`, `x=(cosα, 0, sinα)`, `z≈(0,0,1)` orthogonalized
  by the solver (`z` is re-orthogonalized via Gram-Schmidt, so pass true up
  and let `frames.orthonormal_basis` fix it), `y=(0,1,0)`-equivalent.
- outlet: `O=(L·cosα, W/2, H_in+ΔH)`, same `x`. `α=asin(ΔH/L)`.
- This is the case the legacy yaw-only solver could never handle
  (it projected directions into the XY plane).

### §4.4 Merge / Transfer / Custom

- Merge: one outlet (as §4.1 outlet), two inlets (main + branch at
  documented branch angle); branch port carries
  `connection_rules={"branch": True}`.
- Transfer: short flat module, ports as §4.1 with `L ≤ 800`.
- Custom: ports caller-defined but MUST satisfy §3 right-handedness;
  `validate_port()` rejects non-orthonormal triads.

## §5 Pitch convention (normative, resolves legacy ambiguity)

1. Straight `P` = linear roller centre-to-centre along `X` (80–150mm).
2. Curve `P_outer` = outer-arc c-to-c at radius `Ro=Ri+W`.
3. Joint-gap validation uses **centerline-equivalent pitch**:
   `P_eq = P_outer · Rc / Ro` for curves, `P_eq = P` otherwise.
   Joint limit: `gap ≤ max(P_eq_parent, P_eq_child) + PITCH_JOINT_SLACK`
   (`PITCH_JOINT_SLACK = 10mm`, see `core/invariants.py`).
4. `roller_pitch_mm` stored on the port is always the RAW native pitch
   (`P` or `P_outer`); conversion to `P_eq` happens inside validators,
   never at port construction.

## §6 Transform convention (normative)

1. `p_world = R·p_local + t`, `R` orthonormal 3×3, `det(R)=+1`, lengths mm.
2. Docking solution: given parent outlet `A` and child inlet `B` (both in
   their own module-local frames already placed in world — parent at its
   world `T_A`, child at identity), solve `R, t` with
   `B_A = basis(A)`, `B_B = basis(B)`, `R = B_A·B_Bᵀ`,
   `t = O_A − R·O_B`.
3. Verification (all required): `R·x_B ≈ x_A`, `R·z_B ≈ z_A` (angle tol),
   `R·O_B + t == O_A`, `RᵀR = I`, `det = +1`.
4. Chaining: world transform of module `k` in a line
   `T_k = S_k · … · S_1` where `S_i` is the i-th docking solution
   (4×4 homogeneous composition).
5. Fusion boundary: `Matrix3D.setWithArray` receives row-major
   `[R00,R01,R02,tx_cm, R10,…,tz_cm, 0,0,0,1]` with `t_cm = t_mm / 10`.
   Packing lives in exactly one function (`frames.to_fusion_cells()` when
   `adsk` is present; pure-Python cell builder otherwise for tests).

## §7 Tolerances (values live in `core/invariants.py`; this doc states intent)

| Check | Tolerance | Failure meaning |
|---|---|---|
| Carry height `|ΔH|` | ≤ 1.0mm | needs riser/shim; error message MUST state `Required correction: ±Nmm riser module` |
| Width `|ΔW|` | ≤ 1.0mm | mechanical mismatch, reject |
| Direction angle | ≤ 0.5° | reject (opposite-direction ≈180° is its own error) |
| Up-vector angle | ≤ 0.5° | reject (twisted install) |
| Joint pitch gap | ≤ max(P_eq)+10mm | warn-or-reject per `connection_rules` severity |
| Collision | AABB gap ≥ 0 | reject on overlap |

## §8 Worked reference values (regression anchors)

- `Straight L1400 W450 H750` outlet: `(1400, 225, 750)`, `x=(1,0,0)`.
- `Curve Ri800 Θ90 W450 H750`: `Rc=1025`; inlet `(1025, 0, 750)` `x=(0,1,0)`;
  outlet `(1025·cos90, 1025·sin90, 750) ≈ (0, 1025, 750)`,
  `x=(-1, 0, 0)` (tolerance 1e-9 on the ~6.3e-14 floating residue).
- Straight→Straight (L1400+L1000): `R=I`, `t=(1400,0,0)`.
- Straight→Curve90: `R=[[0,1,0],[-1,0,0],[0,0,1]]` (−90° yaw),
  child inlet lands on parent outlet exactly.
