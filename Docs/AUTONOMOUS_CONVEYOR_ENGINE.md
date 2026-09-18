# Dynamic Conveyor Structural & Autonomous Capacity Engine

This document details the **Dynamic Structural Engine**, **Real-Time Automated Capacity & Sizing Calculator**, and **Autonomous On-The-Fly Add-In** for Autodesk Fusion 360.

---

## 1. Executive Summary & Capabilities Added

| Capability | Previous Implementation | New Dynamic & Autonomous Implementation |
| :--- | :--- | :--- |
| **Leg Stations & Bracing** | Static 2-leg or fixed pitch; no cross-struts | **Dynamic variable leg stationing** based on span + **CAD-modeled horizontal & diagonal cross-strut braces** (`build_leg_cross_bracing`) for lateral stiffness and buckling resistance. |
| **Weight Capacity** | Static arbitrary rating without engineering formulas | **Complete mechanical engineering calculations** (`ConveyorCapacity`): roller load rating, single-package 3-roller contact limit, side-rail bending stress & deflection, leg column buckling with effective-length factor adjustments, and rated Safe Working Load (SWL). |
| **Autonomy & On-The-Fly Adaptation** | Manual trial-and-error input editing | **Autonomous Optimizer** (`autonomous_optimize_conveyor`): dynamically tunes roller diameters, roller pitch, leg pitch, and enables cross-bracing on the fly to meet requested target payload capacities with a target safety factor $\ge 2.0$. |
| **Fusion 360 Interactive Add-In** | Static dialog with static descriptions | **Live reactive dialog** (`conveyor_addin.py`): on-the-fly recalculation of rated payload, kg/m, and structural safety factor directly in the command preview, with immediate auto-tuning upon payload input. |
| **Industry 4.0 / Digital Twin** | Fixed metadata | **OPC-UA node companions** with live telemetry nodes for payload capacity, safe working load, and real-time structural safety factor. |

---

## 2. Engineering Formulation: Real-Time Structural & Capacity Calculation

The new engine calculates capacity across all critical mechanical failure modes:

1. **Roller Dynamic Load Capacity**:
   $$\text{Roller Cap} = 30.0 \times \left(\frac{D_{\text{roller}}}{50.0}\right)^{1.4} \times \left(\frac{500.0}{W}\right)^{0.5} \times \text{speed\_factor}$$
2. **Single Package Point Load** (governed by 3-roller minimum continuous support):
   $$\text{Cap}_{\text{package}} = \min(3, N_{\text{rollers}}) \times \text{Roller Cap} \times 0.85$$
3. **Side-Rail Bending Stress & Deflection** (Euler-Bernoulli beam under distributed load across max leg span):
   $$\sigma_b = \frac{M_{\max} \cdot c}{I_{xx}}, \quad \delta_{\max} = \frac{5 w L_{\text{span}}^4}{384 E I_{xx}}$$
   Ensures rail deflection stays within the allowable $\le L/500$ conveyor industry standard.
4. **Leg Column Buckling & Sway Factor** (Euler critical load):
   $$P_{\text{cr}} = \frac{\pi^2 E I}{(K \cdot H)^2}$$
   Cross-bracing reduces the effective length factor $K$ from $1.5$ (unbraced cantilever) to $0.85$ (braced frame), increasing leg load carrying capacity by **over 3.1x**!
5. **Rated Total Safe Working Load (SWL)**:
   The structural minimum of all failure modes divided by the design safety factor ($SF \ge 2.0$).

---

## 3. Autonomous Optimization Engine (`autonomous_optimize_conveyor`)

When a user specifies a target payload capacity (e.g. 500 kg, 1200 kg) or selects a duty class, the autonomous engine auto-tunes the physical parameters:

```python
from fusion_conveyor_generator import ConveyorInput, derive_configuration, autonomous_optimize_conveyor

# Base lightweight conveyor
base = ConveyorInput(length_mm=2500.0, width_mm=600.0, height_mm=800.0, roller_diameter_mm=50.0, roller_pitch_mm=100.0, leg_pitch_mm=1200.0)

# Autonomous upgrade to handle 1000 kg pallet load:
optimized = autonomous_optimize_conveyor(base, target_payload_kg=1000.0)

print("Optimized Roller Dia:", optimized.roller_diameter_mm) # 80.0 mm
print("Optimized Roller Pitch:", optimized.roller_pitch_mm) # 85.0 mm
print("Cross-bracing Enabled:", optimized.cross_bracing)      # True
print("Optimized Leg Pitch:", optimized.leg_pitch_mm)        # Reduced span for rail stiffness
```

---

## 4. Fusion 360 Add-In Real-Time Interface

In the Autodesk Fusion 360 Add-in (`conveyor_addin.py`):

1. **Duty Class Dropdown**:
   - `Light Duty (50 kg)`: 38mm rollers, 100mm pitch, 1000mm leg span.
   - `Medium Duty (150 kg)`: 50mm rollers, 100mm pitch, 800mm leg span.
   - `Heavy Duty (400 kg)`: 60mm rollers, 80mm pitch, 600mm leg span, cross-braces enabled.
   - `Pallet High-Load (1000 kg)`: 80mm rollers, 85mm pitch, 500mm leg span, cross-braces enabled.
2. **Auto-Tune to Target Payload (Autonomy)**:
   - Checkbox enables dynamic real-time resizing. Changing the target load in kilograms instantly adjusts roller diameters, pitches, leg spans, and cross-bracing in the active Fusion 360 session.
3. **Live Command Preview**:
   - Displays real-time calculations:
     ```text
     Rated Capacity: 755.3 kg (539.5 kg/m)
     Safety Factor: 2.00
     Single Pkg Max: 191.2 kg
     Cross-Braced Legs: Enabled (4 pairs)
     ```
4. **Parametric Modeling of Cross-Struts**:
   - Invokes `build_leg_cross_bracing(comp, params, derived)` creating physical extruded tie bars across leg frames for high-load structural realism.

---

## 5. Verification & Test Results

All 7 stages of the CI pipeline pass cleanly:

```bash
>> Stage 1: Python Syntax Compilation (py_compile) -> [PASS] (36/36 files)
>> Stage 2: AST Code Analysis & Structure Check    -> [PASS] (36/36 files)
>> Stage 3: Linting & Code Quality (flake8)        -> [PASS] (Clean, 0 errors)
>> Stage 4: Static Type Checking (pyright)         -> [PASS] (0 errors, 0 warnings)
>> Stage 5: Core Conveyor Generator Unit Tests     -> [PASS] (25 unit tests)
>> Stage 6: Fusion 360 API Integration Tests       -> [PASS] (7 integration tests)
>> Stage 7: Fusion MCP Server Contract Tests       -> [PASS] (5 contract tests)
```

100% deploy-sync is verified between `fusion_conveyor_generator.py` and `conveyor_addin/fusion_conveyor_generator.py`.
