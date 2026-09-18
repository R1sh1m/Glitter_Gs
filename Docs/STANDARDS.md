# Standards Index — What Governs This Project and Where It Lives

> Everything the team must obey or consult, with its local copy or exact
> external pointer. **Status honesty rule:** entries say whether we hold the
> full text, a free excerpt, or only a pointer — never imply full coverage we
> don't have. Code/BOM review must cite an entry here for every bought-out
> part and every interface in `INTEGRATION.md`.

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
| ISO 4017 / 4762, ISO 4032 | Hex/socket-head bolts + nuts (docking, plates, motor mount) | IF-060 bolt grid fasteners;hole clearances per ISO 273 |
| EN 12020-2 | Tolerances for aluminum extruded profiles | 4080/4040 interface fits (slot/pin); confirm against profile vendor sheet |
| IEC 60072 / NEMA MG-1 | Motor frame dimensions | IF-031 mount hole pattern once a frame (e.g. 63/71) is selected |
| ISO 12100 / EN 619 (continuous handling safety) | Machinery guarding + conveyor safety distances | Guard heights (G), nip-point covers, estop/sensor placement with IF-051 |

## 4. Maintenance rule

New bought-out part or interface ⇒ add its standard here **before** modelling.
Prefer free authoritative excerpts (vendors, universities) as local copies;
paywalled texts get pointer + excerpt-based working rule + owner + date to
revisit. Reviewers check `STANDARDS.md` coverage the same way CI checks code.
