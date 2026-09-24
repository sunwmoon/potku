# Potku AI development worklog

## 2026-09-24 - Initial theory core

- Cloned `JYU-IBA/potku` at commit `25e8efb`.
- Created branch `feature/potku-ai-theory`.
- Added a Qt-independent ideal ERD kinematics module.
- Added linear channel calibration and unit tests.
- Kept target and foil stopping explicitly outside the first ideal model.

Next:

1. Read beam, detector angle, flight length, and ToF calibration from Potku
   `Measurement`, `Run`, and `Detector` objects.
2. Add an energy-channel calibration without breaking old detector files.
3. Draw toggleable theoretical loci in the ToF-E histogram.
4. Add carbon timing-foil stopping through the existing JIBAL-backed helpers.

## 2026-09-24 14:05 KST - Measurement settings adapter

Implemented:

- Added `ChannelLocus`, a plot-ready result containing element/isotope label,
  ToF channels, energy channels, and the surface recoil energy.
- Added `calculate_loci_for_measurement()` to read the beam ion and energy,
  detector angle, timing-foil flight length, and ToF calibration directly
  from Potku's existing `Measurement`, `Run`, and `Detector` interfaces.
- Kept energy-channel calibration explicit because Potku does not currently
  persist it in `Detector`; no existing detector or measurement file format
  was changed.
- Added finite/positive-value validation and confirmed the function never
  creates or saves a selection.

Verification:

- `python -m unittest tests.unit.test_tofe_theory`: **7 tests passed**.
- `python -m compileall -q modules/tofe_theory.py tests/unit/test_tofe_theory.py`:
  **passed**.
- `git diff --check`: **passed**.

Failure / limitation:

- An initial test using concrete Potku `Element`/`Detector` instances could
  not be collected because this checkout does not contain the JIBAL submodule
  data file `external/share/jibal/masses.dat`. The adapter is tested against
  minimal objects implementing the same public methods and attributes. A
  concrete-object integration test remains pending until external components
  are initialized and built.
- The locus is still ideal kinematics only; target and foil stopping are not
  included yet.

Next:

1. Add a non-persistent theory-overlay controller to the ToF-E histogram and
   draw these labeled channel loci without modifying saved selections.
2. Define how energy-channel slope/offset are obtained from current datasets
   before adding them to the persistent detector schema.
3. Initialize/build JIBAL external components and add a concrete Potku object
   integration test.

## 2026-09-24 15:07 KST - Non-persistent histogram overlay

Implemented:

- Added `draw_theory_loci()`, a Qt-independent Matplotlib helper that draws
  dashed channel loci and direct isotope/element labels.
- Added a `Theory` toggle to the ToF-E histogram toolbar. The button remains
  disabled until calculated loci are supplied with `set_theory_loci()`.
- Added normal and transposed-axis rendering. The surface-recoil endpoint and
  its element label remain aligned after the histogram axes are swapped.
- Kept overlay data in the histogram widget, outside
  `Measurement.selector`; theoretical lines are never converted to or saved
  as accepted selections.
- Added `clear_theory_loci()` so a future settings dialog can remove stale
  predictions when measurement parameters change.

Verification:

- `python -m unittest tests.unit.test_tofe_theory tests.unit.test_tofe_overlay`:
  **10 tests passed**.
- `python -m compileall -q modules/tofe_theory.py modules/tofe_overlay.py`
  `widgets/matplotlib/measurement/tofe_histogram.py`
  `tests/unit/test_tofe_theory.py tests/unit/test_tofe_overlay.py`: **passed**.
- `git diff --check`: **passed**.

Failure / limitation:

- No test failed in this work unit.
- Direct command-line `git push` was unavailable because this execution
  environment has no interactive HTTPS credentials. The same tested tree was
  successfully committed to `sunwmoon/potku` through the connected GitHub API
  and the `feature/potku-ai-theory` branch was advanced without force.
- The overlay accepts already-calculated channel loci but is not yet populated
  automatically at widget startup. Potku still lacks a persisted
  energy-channel calibration, so silently assuming a slope/offset would put
  physically calculated loci at misleading positions.
- A full Qt widget integration test and screenshot remain pending while the
  JIBAL external data needed to construct concrete Potku objects is absent.

Next:

1. Add a runtime theory settings dialog for recoil elements and explicit
   energy-channel slope/offset, then calculate and inject loci on user request.
2. Invalidate/recalculate displayed loci when beam, detector, or calibration
   settings change.
3. Initialize/build JIBAL external components and add a concrete measurement
   integration test plus a histogram screenshot using example data.

## 2026-09-24 16:10 KST - Runtime theory configuration

Implemented:

- Added a `Theory…` toolbar action that opens runtime settings for recoil
  isotopes/elements, energy-channel slope/offset, and the displayed minimum
  energy fraction.
- Connected accepted settings to the current measurement's beam, detector,
  flight-length, and ToF calibration values, then enabled and displayed the
  calculated labeled loci immediately.
- Added Qt-independent parsing and validation for element notation and energy
  calibration. Empty/invalid/duplicate element lists and zero/non-finite
  slopes are rejected before replacing the existing overlay.
- Kept predictions in the histogram's transient overlay state. The settings
  dialog explicitly states that no selection is created or saved.

Verification:

- `python -m unittest tests.unit.test_tofe_theory tests.unit.test_tofe_overlay`:
  **14 tests passed**.
- `python -m compileall -q` for the changed calculator, dialog, histogram, and
  test files: **passed**.
- `git diff --check`: **passed**.

Failure / limitation:

- The attempted offscreen dialog smoke test could not start because PyQt5 is
  not installed in this execution environment (`ModuleNotFoundError`). The
  dialog file compiles, but interactive rendering still needs verification in
  a Potku development environment with GUI dependencies installed.
- The JIBAL submodules remain uninitialized, so a concrete `Element` and
  `Measurement` integration test and a real histogram screenshot are still
  blocked. Calculation and settings flow are covered with interface-compatible
  test doubles.
- The energy calibration is intentionally runtime-only; it is not silently
  persisted into existing detector files or reused for another measurement.

Next:

1. Initialize/build JIBAL and run the new dialog against a concrete Potku
   measurement, then capture a histogram screenshot with labeled loci.
2. Preserve the last runtime theory settings per open histogram and invalidate
   or recalculate loci when measurement settings change.
3. Add detector-resolution bands around the center loci before using the
   theory distance as an automatic banana-candidate confidence feature.

## 2026-09-24 17:06 KST - Detector-resolution bands

Implemented:

- Read Potku's existing detector time resolution (`timeres`, ps FWHM) and
  energy resolution (`energyres`, keV FWHM) while calculating each channel
  locus, and converted both values through the active ToF and runtime energy
  calibrations.
- Extended `ChannelLocus` with optional channel-space FWHM values without
  changing detector files or requiring them from older callers.
- Added a translucent two-dimensional resolution ribbon around each dashed
  center locus. The ribbon is normal to the curve in resolution-normalized
  coordinates, so both time and energy resolution contribute.
- Preserved the ribbon geometry when the histogram axes are transposed.
- Kept the center line and band as non-persistent Matplotlib artists; neither
  is added to `Measurement.selector` or saved as a selection.

Verification:

- `python -m unittest tests.unit.test_tofe_theory tests.unit.test_tofe_overlay`:
  **17 tests passed**.
- `python -m compileall -q` for the changed calculation, overlay, histogram,
  and test files: **passed**.
- `git diff --check`: **passed**.

Failure / limitation:

- The first transpose-band assertion failed because it compared polygon
  traversal direction, even though the normal and transposed polygons had the
  same vertices. The test now compares direction-independent vertex sets and
  passes.
- The band currently represents detector FWHM only. It does not yet include
  target/foil energy-loss straggling, angular spread, or depth-dependent
  broadening, and must not yet be interpreted as an automatic-selection
  confidence interval.
- PyQt5 and initialized JIBAL data are still unavailable in this environment,
  so interactive rendering with a concrete Potku measurement remains pending.

Next:

1. Initialize/build JIBAL and verify the predicted lines and resolution bands
   against a concrete measurement and histogram screenshot.
2. Add timing-foil energy loss to separate the ToF-flight energy from the
   energy-detector value before treating the theoretical distance as a
   candidate confidence feature.
3. Preserve/invalidate runtime theory settings when measurement or detector
   parameters change.

## 2026-09-24 18:04 KST - Foil-aware locus energy model

Implemented:

- Added a foil-aware locus calculation that keeps three physically distinct
  energy arrays: recoil energy before detector foils, flight energy between
  the timing foils, and energy reaching the active energy detector.
- Made the first timing-foil and downstream losses injectable, vectorized
  callbacks. This gives the next JIBAL integration a narrow interface and
  avoids embedding subprocess or detector-file logic in the kinematics.
- Calculated ToF from the post-first-foil flight energy while retaining the
  post-downstream-material energy for the histogram Energy coordinate.
- Added validation for negative, non-finite, wrong-shaped, and energy-
  exhausting loss results. The existing ideal calculation remains the exact
  zero-loss fallback, so Potku operation is unchanged when no stopping model
  is available.

Verification:

- `python -m unittest tests.unit.test_tofe_theory tests.unit.test_tofe_overlay`:
  **20 tests passed**.
- `python -m compileall -q modules/tofe_theory.py`
  `tests/unit/test_tofe_theory.py`: **passed**.
- `git diff --check`: **passed**.

Failure / limitation:

- No test failed in the completed work unit.
- This commit deliberately does not enable foil stopping in the GUI yet. The
  current `general_functions.carbon_stopping()` launches `jibaltool` once per
  energy and prints subprocess output, so calling it directly for all 300
  locus points would freeze the UI and produce excessive output.
- Target stopping, straggling, angular spread, and non-carbon downstream
  layers are still outside the model. Theory overlays therefore continue to
  use the ideal zero-loss fallback until a tested stopping adapter is supplied.

Next:

1. Add a batched/cached JIBAL carbon-stopping adapter that samples a small
   energy grid, interpolates the losses, and reports tool failures without
   changing the existing overlay.
2. Read the first timing foil and downstream detector layers from `Detector`,
   then pass their stopping models into the foil-aware calculation.
3. Add a GUI option showing whether the displayed locus is `Ideal` or
   `Foil-corrected`, with ideal fallback when JIBAL is unavailable.

## 2026-09-24 19:05 KST - Cached JIBAL stopping adapter

Implemented:

- Added `CarbonStoppingInterpolator`, a vectorized MeV-in/MeV-out callback
  over Potku's scalar JIBAL carbon-stopping helper. It evaluates a configurable
  geometric grid (24 points by default) rather than launching one process for
  every point in a 300-point locus.
- Cached both individual backend samples and the current interpolation grid.
  Repeated redraws and requests inside the cached energy range therefore make
  no additional `jibaltool` calls.
- Added validation for invalid incident energies, backend errors, non-finite
  or negative losses, and losses that exhaust the particle energy. Errors are
  reported as `StoppingCalculationError` with the failing energy included.
- Extended the legacy `carbon_stopping()` helper with backward-compatible
  `verbose` and `strict` options. The adapter suppresses process output and
  treats a non-zero exit or missing `delta E` result as a failure, while old
  callers retain their previous defaults.
- Kept the adapter outside the GUI and did not connect it to the displayed
  locus yet. Consequently, unavailable JIBAL data cannot replace or remove
  the current ideal, non-persistent overlay.

Verification:

- `python -m unittest tests.unit.test_tofe_theory`
  `tests.unit.test_tofe_overlay tests.unit.test_tofe_stopping`:
  **26 tests passed**.
- Tests cover interpolation, cache reuse, scalar and multidimensional input,
  quiet/strict JIBAL invocation, backend failure context, and rejection of
  invalid or energy-exhausting losses.
- `python -m compileall -q` for the changed modules and tests: **passed**.
- `git diff --check`: **passed**.

Failure / limitation:

- The broader `test_general_functions.py` could not be imported because
  `external/share/jibal/masses.dat` is absent. Initializing the JIBAL submodule
  was attempted, but its GitHub clone produced no progress in this restricted
  environment and was interrupted after about 90 seconds.
- The interpolation error has not yet been quantified against real JIBAL
  output. The 24-point default is an implementation starting point, not a
  validated physics-accuracy setting.
- The adapter is not yet constructed from `Detector.foils`; the GUI continues
  to calculate the same ideal overlay as before this change.

Next:

1. Extract the first timing-foil carbon layer and downstream carbon layers
   from `Detector`, construct one cached adapter per recoil isotope, and pass
   them to `calculate_foil_aware_locus()`.
2. Preserve the current ideal locus when the foil definition is unsupported
   or JIBAL fails, and expose an `Ideal` / `Foil-corrected` calculation status
   to the histogram without creating a selection.
3. In an environment with built JIBAL, compare 24-point interpolation with a
   dense direct calculation and set an accuracy-based sampling tolerance.
