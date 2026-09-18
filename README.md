# Glitter_Gs — Parametric Adjustable Roller Conveyor Generator
### Autodesk Fusion × Standards: Industry Hackathon (Problem Statement A)

A production-grade Autodesk Fusion API solution that generates and parametrically controls an **Adjustable Roller Conveyor Module** satisfying all requirements from Problem Statement A (sections 2.1 – 2.6).

---

## 🌟 Key Innovations & Salient Architectural Features

1. **Genuine Native Parametric CAD Modeling (Section 2.4)**
   - Unlike static B-rep solid generators, the CAD model is **fully driven by native Autodesk Fusion User Parameters** (`ConvLength`, `ConvWidth`, `FrameHeight`, `RollerDia`, `RollerSpacing`, `LegSpacing`, `GuardHeight`).
   - Every sketch line and extrusion dimension is parametrically tied via `.parameter.expression`.

2. **Dynamic Fusion Formula Parameters for Repeated Components (Section 2.3A)**
   - Roller and leg counts are **not hardcoded in Python loops**; they are registered as Fusion formula parameters:
     - `RollerCount = floor((ConvLength - 2 * RollerMargin) / RollerSpacing) + 1`
     - `LegCount = floor((ConvLength - LegSide) / LegSpacing) + 1`
   - When any parameter is changed directly in Fusion's *Modify -> Change Parameters* table or through the API, Fusion's internal constraint solver automatically recalculates component counts and locations!

3. **Parametric Rectangular Patterns (`RectangularPatternFeature`)**
   - Single master roller and master leg station patterned along the conveyor axis.
   - Pattern instance quantities and spacings are directly wired to the formula parameters (`RollerCount`, `RollerSpacing`, `LegCount`, `LegSpacing`).

4. **Zero Duplicate Geometry & In-Place Reconfiguration**
   - Parameter updates do not delete or recreate parts; geometry updates in-place via `design.computeAll()`, preserving timeline integrity and performance.
   - Side guards are built once and toggled parametrically via feature suppression (`feature.isSuppressed = not side_guards`).

5. **Physical CAD B-Rep Bounding Box Verification (Section 2.4)**
   - Automated inspection reads the physical 3D bounding box (`comp.boundingBox.maxPoint - comp.boundingBox.minPoint`) and verifies that real CAD extents ($L, W, H$) match input specifications within 5mm tolerance.

6. **Automated Deliverables & Export Pipeline (Section 2.6)**
   - Exports high-precision **STEP 3D CAD files** (`.step`) for each configuration.
   - Generates formatted **CSV Bills of Materials (BOM)** (`{name}_BOM.csv`) with part names, quantities, and structural dimensions.
   - Generates a timestamped verification report (`validation_report.txt`).

7. **Dual-Mode Fusion User Interface (Section 2.3)**
   - **Mode [1] — Automated 3-Configuration Demonstration Pipeline:**
     Automatically cycles through three substantially different valid configurations (`ConfigA_Compact`, `ConfigB_Standard`, `ConfigC_LongHeavy`), validates CAD bounding boxes, exports STEP models, and generates CSV BOMs.
   - **Mode [2] — Interactive Custom Parameter Entry:**
     Allows real-time input of custom parameters with automatic boundary validation and instant CAD model reconfiguration.

8. **Offline Testability & CI/CD Support**
   - Pure-Python mathematical models and rule verifications run completely outside of Fusion 360, enabling automated unit testing without CAD dependencies.

---

## 📐 Specification Input Ranges

| Parameter | Symbol | Allowed Range | Default / Demo Example |
| :--- | :---: | :---: | :---: |
| **Conveyor Length** | `L` | 800 – 2000 mm | 1400 mm |
| **Conveyor Width** | `W` | 300 – 600 mm | 450 mm |
| **Frame Height** | `H` | 500 – 900 mm | 750 mm |
| **Roller Diameter** | `D` | 40 – 80 mm | 60 mm |
| **Roller Spacing (c-to-c)** | `P` | 80 – 150 mm | 110 mm |
| **Support-Leg Spacing** | `S` | 500 – 1000 mm | 700 mm |
| **Side-Guard Height** | `G` | 0 – 150 mm | 100 mm |
| **Side Guards** | — | Yes / No | Yes |

---

## 📂 Project Structure

```
├── fusion_conveyor_generator.py   # Primary Fusion API script & core engine
├── tests/
│   └── test_conveyor_generator.py # Comprehensive unit test suite
├── Docs/
│   └── Hackathon_Problem_Statement.pdf
└── README.md                      # Engineering documentation
```

---

## 🚀 How to Run

### In Autodesk Fusion 360
1. Open Autodesk Fusion.
2. Navigate to **Utilities** → **Scripts and Add-Ins** (or press `Shift + S`).
3. Click the **+** (Add) button under *My Scripts* and select `fusion_conveyor_generator.py`.
4. Click **Run**.
5. Select:
   - **`1`** for the **Automated 3-Configuration Demo Pipeline** (exports all deliverables to `~/ConveyorGenerator_Output/`).
   - **`2`** for **Interactive Custom Configuration** (enter custom comma-separated values).

### Standalone Unit Tests (Outside Fusion)
```bash
python -m unittest discover -s tests -v
```
All tests validate mathematical derivations, range bounds, deterministic signatures, BOM generation, and CSV exports.
