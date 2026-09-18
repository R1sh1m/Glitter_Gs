# Assembly Handbook — Parts, Components and Multi-Module Lines

> Proven 2026-09-18: `root.occurrences.addNewComponent` fails in our
> documents with *"Part Design documents can only contain one component"*.
> **A Part-design document holds exactly one component — no exceptions, no
> workaround.** Verified in the API bindings: `addExistingComponent` EXISTS
> on Occurrences and is the assembly path.

## 1. Rules

- **One module = one Part-design document.** Curve lives in
  `ghost_testing_1`; the straight module gets its own fresh document
  (create via File > New Design — I cannot create documents from the API).
- **Never mix two modules in one Part doc** (shared root bbox breaks every
  validator; name soup; STEP exports tangle).
- **Assembly = separate Assembly-design document** that references module
  docs via `occurrences.addExistingComponent(sourceComponent, transform)`
  plus Joints API for motion (Joints API confirmed present in bindings).
  I will script the assembly (derive-place-mate-validate) the moment an
  assembly doc is open.

## 2. Assembly build procedure (scripted, on request)

1. Open module docs (curve, straight, …) + one fresh assembly doc.
2. Run assembler: `addExistingComponent` per module with port-mating
   transforms from `layout_ports_straight` / `layout_place_curve_after_straight`
   (joint-pitch continuity enforced, §VISION_PRODUCTION_LINES.md §2).
3. Validate: carry-height coplanarity ±1 mm, joint pitch, BOM roll-up.
4. Export assembly STEP.

## 3. Requested from user

- [ ] Fresh document for the straight C2 live build (name it e.g.
      `straight_C2`), then say go: C2 + holes + shafts in ~5 runs.
- [ ] Assembly document when ready for the first 2-module line.
