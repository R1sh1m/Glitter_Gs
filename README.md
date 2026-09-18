# Glitter_Gs

Fusion API implementation for a **parametric adjustable roller conveyor configuration generator**.

## Implemented Scope
- User-driven configuration input through Fusion UI:
  - `length_mm` (L): 800–2000
  - `width_mm` (W): 300–600
  - `height_mm` (H): 500–900
  - `roller_diameter_mm` (D): 40–80
  - `roller_spacing_mm` (P): 80–150
  - `support_spacing_mm` (S): 500–1000
  - `side_guard_height_mm` (G): 0–150
  - `side_guards`: Yes/No
- Automated generation of:
  - frame
  - rollers
  - support legs
  - optional side guards
- Repeated component logic:
  - roller count/positions computed from selected length, diameter, and max spacing
  - support-leg pair count/positions computed from selected length and max spacing
- Deterministic output:
  - identical inputs produce identical derived layout/signature
- Idempotent regeneration:
  - stale generated components with `GG_` prefix are removed before rebuild
- Automatic verification:
  - overall dimensions and feature consistency
  - roller/support spacing constraints and computed positions
- BOM/component summary generated for each configuration.
- Fusion parameter persistence:
  - active dimensions are written to named `GG_` user parameters
  - the generated module stores its configuration signature and BOM as Fusion attributes
- Regeneration safety:
  - support-leg pair centres stay inside the selected conveyor length
  - rollers are centred across the conveyor width

## Files
- `/home/runner/work/Glitter_Gs/Glitter_Gs/fusion_conveyor_generator.py`
  - input validation and conflict rejection
  - conveyor parameter derivation
  - verification checks
  - deterministic configuration signature
  - BOM builder
  - Fusion geometry generation
  - three demonstration configurations
- `/home/runner/work/Glitter_Gs/Glitter_Gs/tests/test_conveyor_generator.py`
  - valid configuration checks
  - invalid/conflicting input rejection
  - repeated-component parameter dependence
  - deterministic signature checks
  - three-configuration generation verification
  - BOM checks

## Three Demonstration Configurations
- `C1_compact_no_guards`
- `C2_medium_with_guards`
- `C3_long_with_guards`

All three are valid and substantially different in dimensions/features.

## Running in Fusion
1. Open Fusion and run `fusion_conveyor_generator.py`.
2. Enter `L,W,H,D,P,S,G,side_guards` in the prompt.
3. Re-run with changed values to regenerate the model and update repeated components.
4. Inspect the `GG_ConveyorModule` attributes for the deterministic configuration signature and JSON BOM.

## Local Verification (outside Fusion)
```bash
cd /home/runner/work/Glitter_Gs/Glitter_Gs
python -m unittest discover -s tests -v
```

## Technical Notes / Assumptions
- Roller center positions include edge offsets of `D/2` from both ends.
- Support-leg pairs span from `x=0` to `x=L`.
- Computed spacing is always less than or equal to selected maximum spacing.
- When `side_guards=False`, `side_guard_height_mm` must be `0`.
