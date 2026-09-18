# Standards, Quality Control & Safety Benchmarks

> **Engineering Philosophy:** Modern industrial automation does not succeed by isolated cleverness; it succeeds through **strict standardisation, unyielding quality control, and uncompromising safety benchmarks**. In daily life—from the timely delivery of life-saving medical supplies to the seamless flow of consumer goods—unseen conveyor networks quietly transport millions of packages 24/7. A single non-standard bolt, an unverified CAD geometry drift of 5 mm, or a high-speed parcel pinch point can cause catastrophic line halts, component failure, or severe human injury. This repository is built ground-up to embed these principles directly into automated parametric CAD generation.

---

## 🏛️ The Three Pillars in Engineering and Daily Life

### 1. The Critical Role of Standardisation
Standardisation is the cornerstone of interchangeable manufacturing, modular scalability, and global supply chains.

* **Impact on Daily Life:**
  - **Interchangeability & Uptime:** When a distribution center conveyor fails at 2 AM, standardized components (DIN bearings, standard aluminum extrusion slots, CEMA roller diameters) mean replacement parts are sourced off-the-shelf within hours rather than requiring bespoke machine-shop fabrication.
  - **Interoperability across Vendors:** Packages travel across straight sections, 90° curves, merges, and sorters built by different OEMs. Standardized widths and roller pitch rules ensure that cartons never tumble or snag at transfer points.
* **Standards Implemented in this Project:**
  - **CEMA 400-Series & DIN 15201 / ISO 5048:** Roller diameter ranges ($D \in [40, 80]$ mm) and center-to-center pitch rules ($P \in [80, 150]$ mm) guaranteeing the *3-roller support rule* ($P \le L_{\text{box}}/3$) for continuous material handling.
  - **DIN 625-1 (Deep Groove Ball Bearings):** Roller assemblies standardize on 6002-2RZ sealed ball bearings ($15\text{ mm ID}, 32\text{ mm OD}, 9\text{ mm width}$) with M8/M12 fasteners.
  - **EN 12020-2 / DIN 17615 (Aluminum Structural Profiles):** 40×40 mm and 40×80 mm T-slot framing profiles ensuring worldwide accessory mounting (sensors, brackets, stops).
  - **OPC-UA (IEC 62541):** Digital twin integration with standard information modeling, exposing machine nodes (`ConveyorSpeed`, `RollerCount`, `MotorDriveStatus`, `PhotoelectricBlocked`) for Industry 4.0 automation.
  - **Standardized Docking Ports:** Rigorous kinematic port frames ($[x, y, z, \theta_z]$) ensuring straight and curve modules dock with zero manual shimming.

### 2. The Uncompromising Mandate for Quality Control
Quality control guarantees that design intent is preserved from digital synthesis through to CNC fabrication, assembly, and commissioning.

* **Impact on Daily Life:**
  - **Preventing Production Line Stoppages:** Undetected geometric interference in CAD leads to physical collisions on the factory floor, costing thousands of dollars per minute in downtime.
  - **BOM Honesty & Cost Integrity:** In commercial contracts, a discrepancy between the CAD drawing and the Bill of Materials leads to stock shortages or massive inventory waste.
* **Quality Control Gating Implemented in this Project:**
  - **Automated Physical B-Rep Metrology:** The pipeline queries the physical CAD bounding box (`comp.boundingBox`) in 3D space after generation, verifying length, width, and height against input requirements within an aggressive **$\pm 5.0\text{ mm}$ tolerance gate**.
  - **Pre-Export Hygiene Gate:** Empty sketches, unconsumed profile planes, or orphan features cause geometry recalculation failures and bloat STEP file sizes. The automated hygiene cleaner purges unconsumed sketches before export.
  - **Model-Driven BOM Extraction:** Quantities and physical masses are extracted directly from active Fusion 360 User Parameters (`design.userParameters.itemByName('RollerCount').value`) and B-Rep solid properties—guaranteeing that the exported CSV BOM can never drift from the synthesized 3D CAD model.
  - **Defect Gating (`Export Gated on PASS`):** STEP models and release packages are strictly blocked from export if any verification check fails.

### 3. Safety Benchmarks as Moral and Functional Imperatives
Safety standards protect human life, prevent worker injury, and ensure mechanical reliability under continuous operational stress.

* **Impact on Daily Life:**
  - **Operator Protection:** Factory personnel interact with conveyors daily. Unguarded roller nips, protruding bolt heads, or tipping packages pose severe crush, entanglement, and impact hazards.
  - **Package Integrity & Jam Prevention:** In parcel sorting hubs processing 40,000 items/hour, package skew on curves causes chain-reaction pileups, crushed packages, and fire hazards.
* **Safety Benchmarks Implemented in this Project:**
  - **ISO 13857 & EN 619 (Machinery Guarding & Ergonomic Reach):** Side guards ($G \in [0, 150]\text{ mm}$) shield moving roller pinch points from operator reach and prevent cartons from tipping off the line into walkways. Guard height is evaluated independently of suppression state.
  - **Kinematic Taper Safety ($\le 5.0^\circ$ Inter-Roller Cap per Damon & Interroll):** On curves, cylindrical rollers induce differential slip that skews parcels into side rails. Conical rollers enforce kinematic speed-matching ($v = \omega \cdot r$ where $d_{\text{outer}} = d_{\text{inner}} \cdot R_o/R_i$). Adjacent roller angle is strictly capped at $\le 5^\circ$ to prevent pinch gaps and package snagging.
  - **Docking Pitch Continuity Gate:** Multi-module docking validation enforces that inter-module joint pitch satisfies $P_{\text{joint}} \le \max(P_1, P_2) + 10\text{ mm}$, eliminating parcel drop or impact shock across module boundaries.
  - **Sensor & E-Stop Infrastructure (IF-040 & IF-051):** Automated generation of mounting provisions for retroreflective photoelectric sensors and emergency stop circuits.

---

## 1. Local copies (`Docs/standards/` — committed, everyone reads these)

| File | Source / status | Applies to |
|---|---|---|
| `interroll-rollers-technical-basics-EN.pdf` (1.1 MB) | Interroll, free official PDF, full text held | 3-roller rule, tapered-roller curve design (Ri 770–850 series), shaft M8×15 ⌀12/14, 6002-2RZ bearings, shaft tilt 1.8°, jam calc `Ra/ELmin`, RollerDrive curves |
| `damon-curve-conveying.html` | Damon Group, free tech page, full text held | ≤5° inter-roller angle, taper velocity matching, roller-length-from-goods calc |
| `inbelts-curved-roller-conveyor-design.html` | Inbelts, free design guide, full text held | Curve angles 30/45/90/180, Ri/Ro practice, tapered-roller duty table, guard use |

## 2. Local reference models (`Docs/reference models/` — measured, not normative)

`Conveyor Assembly.stp` (+`Roller.stp`, `4080 aluminum profile.stp`,
`Anti-slip foot cup.stp`, photos): Poly-V conveyor teardown behind
`INTEGRATION.md` §1 — extrusion construction, hole rows, motor tension plate,
sensor/pallet-stop accessories. Dimensions taken from these files are
**measured values**, flagged as such wherever used.

## 3. External normative standards (pointer + application; full texts mostly paid)

| ID | Title relevance | How we apply it |
|---|---|---|
| CEMA Unit Handling Conveyors (CEMA 400-series / *Belt Book* ch. on rollers) | US industry practice for unit-handling conveyors | Sizing conservatism, guarding expectations; full text paywalled — apply via Interroll/Damon excerpts above until purchased |
| ISO 606 / ANSI B29.1 | Roller-chain dimensions (if chain-drive curve option is built) | Sprocket/pitch selection for IF-030 chain variant; verify before modelling teeth |
| ISO 4017 / 4762, ISO 4032 | Hex/socket-head bolts + nuts (docking, plates, motor mount) | IF-060 bolt grid fasteners; hole clearances per ISO 273 |
| EN 12020-2 | Tolerances for aluminum extruded profiles | 4080/4040 interface fits (slot/pin); confirm against profile vendor sheet |
| IEC 60072 / NEMA MG-1 | Motor frame dimensions | IF-031 mount hole pattern once a frame (e.g. 63/71) is selected |
| ISO 12100 / EN 619 / ISO 13857 (continuous handling safety) | Machinery guarding + conveyor safety distances | Guard heights (G), nip-point covers, estop/sensor placement with IF-051 |
| IEC 62541 (OPC-UA) | Open Platform Communications Unified Architecture | Industry 4.0 standard nodeset schema for digital twin speed, telemetry, and diagnostics |

## 4. Maintenance rule

New bought-out part or interface ⇒ add its standard here **before** modelling.
Prefer free authoritative excerpts (vendors, universities) as local copies;
paywalled texts get pointer + excerpt-based working rule + owner + date to
revisit. Reviewers check `STANDARDS.md` coverage the same way CI checks code.
