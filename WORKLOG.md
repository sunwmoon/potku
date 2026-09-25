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
- Standard HTTPS `git push` could not read GitHub credentials in the execution
  shell. The tested files were instead published through the connected GitHub
  API as a non-force, fast-forward commit on the same feature branch.
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

## 2026-09-24 20:01 KST - Detector timing-foil integration

Implemented:

- Read the ordered timing-foil indexes, carbon layer thicknesses, and
  densities from the active Potku `Detector` rather than requiring duplicate
  runtime inputs.
- Built one cached carbon-stopping interpolator per timing foil and recoil
  isotope. The first timing foil now supplies the pre-flight loss, while later
  timing foils are applied sequentially to the post-flight detector energy.
- Added an enabled-by-default `Apply carbon timing-foil energy loss` option to
  the theory dialog. Turning it off preserves the exact ideal calculation.
- Connected detector foil loss to runtime theory calculation. Unsupported
  foil layouts, unavailable isotopes, JIBAL errors, and nonphysical stopping
  results fall back independently to the ideal locus for each element.
- Added `Foil`, `Ideal`, and `Mixed` states to the histogram theory toggle.
  Fallback reasons are available in its tooltip while element labels remain
  unchanged.
- Kept all loci and status fields transient; no prediction is added to or
  saved through `Measurement.selector`.

Verification:

- `python -m unittest tests.unit.test_tofe_theory`
  `tests.unit.test_tofe_overlay tests.unit.test_tofe_stopping`:
  **32 tests passed**.
- Tests cover detector foil extraction, ordered multi-foil energy loss,
  foil-aware measurement calculation, per-element ideal fallback, and the
  user-controlled ideal-only mode.
- `python -m compileall -q` for all changed Python files: **passed**.
- `git diff --check`: **passed**.

Failure / limitation:

- The first new fixture used Potku's default timing indexes `(1, 2)` without
  creating the preceding non-timing foil, so its initial test run failed with
  an out-of-range index. The fixture was corrected to preserve actual detector
  indexing; the production bounds check was retained and all tests pass.
- This integration corrects carbon timing foils only. A downstream SiN energy
  detector window and target energy loss are not yet modeled, so `Foil` means
  carbon timing-foil corrected rather than a complete transport simulation.
- PyQt5 and an initialized JIBAL executable/data installation remain absent in
  this environment. GUI rendering and numerical comparison against real JIBAL
  stopping values therefore remain pending; runtime failure is covered by the
  tested ideal fallback.

Next:

1. Add a lightweight overlay report/export containing predicted channel
   endpoints, correction mode, and fallback reason so the result can be
   checked against a real histogram without inspecting tooltips.
2. Initialize JIBAL in a Potku development environment and compare cached
   interpolation against direct carbon stopping over representative H, D, C,
   O, and Si recoil-energy ranges.
3. Add target/dead-layer transport interfaces before using theory distance as
   an automatic banana-candidate confidence feature.

## 2026-09-24 21:06 KST - Theory overlay report and TSV export

Implemented:

- Added a Qt-independent report builder for every displayed theoretical locus.
  Each row contains the low-energy and surface ToF/Energy channel endpoints,
  maximum recoil energy, detector-resolution FWHM values, correction mode,
  and any per-element ideal-fallback reason.
- Added deterministic TSV serialization with safe quoting for multiline or
  tab-containing fallback messages and blank fields for unavailable detector
  resolutions.
- Added a `Report…` histogram-toolbar action that is enabled only while
  transient theory loci exist. The dialog supports inspection, clipboard
  copy, and an explicit user-selected TSV export path.
- Kept the report completely separate from `Measurement.selector`; opening,
  copying, or exporting a report never creates or accepts a selection.
- Added validation for empty, non-1D, mismatched, and non-finite channel data
  so a malformed prediction cannot silently produce a misleading report.

Verification:

- `python -m unittest tests.unit.test_tofe_theory`
  `tests.unit.test_tofe_overlay tests.unit.test_tofe_stopping`
  `tests.unit.test_tofe_report`: **36 tests passed**.
- `python -m compileall -q` for all theory, overlay, stopping, report, dialog,
  histogram, and report-test files: **passed**.
- `git diff --check`: **passed**.

Failure / limitation:

- No unit test failed in the completed work unit.
- Standard HTTPS `git push` could not read credentials in the execution shell.
  The exact tested Git tree was published as a non-force fast-forward through
  the connected GitHub API, and the local branch was synchronized to it.
- PyQt5 remains unavailable in this execution environment, so the new report
  dialog compiles but could not be opened interactively. Report generation,
  endpoint validation, fallback preservation, and TSV quoting are covered by
  Qt-independent tests.
- The exported surface Energy channel includes the implemented carbon
  timing-foil correction when available, but still excludes target loss and
  the energy-detector entrance dead layer. The report labels the calculation
  mode and fallback, but it is not yet a complete transport calculation.

Next:

1. Open the report against a concrete measurement with PyQt5/JIBAL available
   and compare its channel endpoints with the visible histogram.
2. Add target/dead-layer transport inputs or explicitly report them as omitted
   before treating distance from the theory locus as a confidence feature.
3. Start the Qt-independent banana-candidate stage: detect histogram ridges
   near each theory band and return non-persistent polygon/confidence proposals
   for later Accept/Edit/Reject integration.

## 2026-09-24 22:03 KST - Theory-guided banana candidate core

Implemented:

- Added a Qt-independent candidate detector that accepts a 2D ToF-E histogram
  in `(energy bin, ToF bin)` order plus one or more theoretical channel loci.
- Sampled each theory locus and searched along its local normal direction in
  detector-resolution units. Motion along the banana tangent is penalized so
  adjacent theory samples do not collapse onto the same high-count bin, while
  a measured banana shifted normal to the theory curve can still be found.
- Added local background and Poisson-like peak thresholding. Flat histograms
  now return no proposal rather than producing a polygon from noise alone.
- Added `BananaCandidate`, containing an editable closed polygon, detected
  ridge, confidence, coverage, contrast, and theory-adherence diagnostics.
  Confidence combines signal coverage, local contrast, and normalized distance
  from the physics prediction.
- Added bin-width fallback search scales for old detector settings that do not
  provide ToF or Energy resolution.
- Kept the detector completely separate from `Measurement.selector`; it only
  returns NumPy data and cannot create or save a Potku selection.

Verification:

- `python -m unittest tests.unit.test_tofe_candidate`
  `tests.unit.test_tofe_theory tests.unit.test_tofe_overlay`
  `tests.unit.test_tofe_stopping tests.unit.test_tofe_report`:
  **41 tests passed**.
- Synthetic tests cover an aligned banana, a measured banana shifted from the
  theory locus, lower confidence for that shift, a flat-background rejection,
  missing-resolution fallback, closed polygons, and invalid histogram shapes.
- `python -m compileall -q modules/tofe_candidate.py`
  `tests/unit/test_tofe_candidate.py`: **passed**.
- `git diff --check`: **passed**.

Failure / limitation:

- The first synthetic test run returned no candidates because searching the
  full two-dimensional window let neighboring theory samples choose duplicate
  ridge maxima, producing a degenerate polygon. The search was changed to use
  local tangent/normal coordinates with a tangent-distance penalty; all tests
  then passed.
- Confidence is currently a transparent heuristic, not a calibrated
  probability. Its thresholds need tuning against real Potku spectra with
  manually accepted and rejected selections.
- Only deterministic synthetic histograms were available. Overlapping
  bananas, detector artifacts, sparse tails, and strongly varying background
  have not yet been validated.
- This work produces proposal data only. It deliberately does not draw a
  proposal or expose Accept/Edit/Reject controls yet, so there is still no path
  by which an automatic result can be saved.

Next:

1. Draw candidate polygons/ridges as transient histogram artists with label
   and confidence, without adding them to `Measurement.selector`.
2. Add proposal state and `Accept`, `Edit`, and `Reject` controls; only an
   explicit Accept action may convert a proposal into a Potku selection.
3. Build real histogram arrays from the widget's raw measurement data and
   compression settings, then tune detection thresholds against representative
   separated, overlapping, weak, and background-dominated bananas.

## 2026-09-24 23:19 KST - Transient candidate overlay

Implemented:

- Added a Qt-independent Matplotlib renderer for `BananaCandidate` objects.
  It draws the proposed polygon fill, dotted boundary, detected ridge, element
  label, confidence percentage, and an explicit `proposed` status.
- Used a fixed amber proposal color and separate line styles so an automatic
  suggestion is visually distinct from accepted Potku selections and from the
  theoretical center-line overlay.
- Added normal and transposed-axis rendering for both polygon and ridge
  coordinates. The confidence annotation follows the correct ridge endpoint
  after the axes are swapped.
- Added a disabled-by-default `Candidates` histogram-toolbar toggle plus
  `set_candidate_proposals()` and `clear_candidate_proposals()` APIs. These
  methods retain candidate data only in the histogram widget and never call
  `Measurement.selector`.
- Automatically clear stale candidate proposals whenever the theory loci are
  recalculated, replaced, or removed.
- Added validation for malformed/non-finite proposal coordinates and
  confidence values outside `[0, 1]` before rendering.

Verification:

- `python -m unittest tests.unit.test_tofe_overlay`
  `tests.unit.test_tofe_candidate tests.unit.test_tofe_theory`
  `tests.unit.test_tofe_stopping tests.unit.test_tofe_report`:
  **46 tests passed**.
- Tests cover candidate styling, confidence label, polygon/ridge coordinates,
  axis transposition, empty overlays, and invalid coordinates/confidence.
- `python -m compileall -q modules/tofe_overlay.py`
  `tests/unit/test_tofe_overlay.py`
  `widgets/matplotlib/measurement/tofe_histogram.py`: **passed**.
- `git diff --check`: **passed**.

Failure / limitation:

- No test failed in this completed work unit.
- PyQt5 is still unavailable in the execution environment. The Matplotlib
  artists were verified with the non-interactive Agg backend and the widget
  source compiles, but the new toolbar toggle could not be clicked in a live
  Potku window.
- Candidate generation is not yet invoked from the histogram widget; this
  change provides the safe transient display boundary and lifecycle only.
- The displayed polygons are not yet interactively editable and there are no
  Accept/Edit/Reject controls. Consequently, proposals still cannot enter the
  selector or be persisted.

Next:

1. Build a `(counts, ToF edges, Energy edges)` histogram bridge from the raw
   measurement data and the active compression settings, then invoke the
   candidate detector from an explicit user action.
2. Add per-proposal selection state and `Accept`, `Edit`, and `Reject`
   controls. Only `Accept` may create a Potku selection; Reject must only clear
   transient data.
3. Add draggable proposal vertices for Edit while keeping changes outside
   `Measurement.selector` until the user confirms acceptance.

## 2026-09-25 00:02 KST - Raw measurement histogram bridge

Implemented:

- Added `build_candidate_histogram()` to convert raw Potku event channels into
  an explicit canonical grid: Energy bins are rows and ToF bins are columns.
- Applied the same integer span/compression bin-count rule used by the existing
  histogram widget, including one-bin handling for constant axes and a maximum
  bin-count cap.
- Added finite-value, equal-length, non-empty, positive-compression, and
  maximum-bin-count validation before allocating the histogram.
- Added an explicit `Suggest` toolbar action. It is enabled only after theory
  loci exist and runs candidate detection only when the user clicks it.
- Mapped active compression settings back to canonical ToF/Energy axes when
  the displayed histogram is transposed, then passed the generated counts and
  edges into the existing theory-guided detector.
- Connected successful results to the transient candidate overlay and included
  the proposal count in its toggle. A no-candidate result clears old proposals
  and reports that no selection was created or saved.
- Kept the complete suggestion path outside `Measurement.selector`; this work
  adds no automatic selection-creation or persistence call.

Verification:

- `python -m unittest tests.unit.test_tofe_candidate`
  `tests.unit.test_tofe_overlay tests.unit.test_tofe_theory`
  `tests.unit.test_tofe_stopping tests.unit.test_tofe_report`:
  **50 tests passed**.
- Added tests for histogram orientation, compression-derived dimensions,
  maximum-bin capping, constant axes, invalid raw events, and a deterministic
  end-to-end path from noisy raw events to a high-confidence banana proposal.
- `python -m compileall -q modules/tofe_candidate.py`
  `tests/unit/test_tofe_candidate.py`
  `widgets/matplotlib/measurement/tofe_histogram.py`: **passed**.
- `git diff --check`: **passed**.

Failure / limitation:

- An auxiliary parity script that imported Potku's broader
  `modules.math_functions` could not run because `shapely` is not installed in
  this environment. The visible bin-count rule was reproduced in the focused,
  dependency-free helper and is covered by unit tests.
- PyQt5 is also unavailable, so the `Suggest` button and informational dialog
  compile but could not be exercised in a live Potku window.
- Default confidence/search parameters remain uncalibrated on real ToF-ERD
  measurements. The end-to-end verification uses deterministic synthetic
  banana events plus uniform background.
- Proposals remain transient and non-editable. There is still no Accept path,
  so automatic output cannot become or save a selection.

Next:

1. Add a Qt-independent proposal-state controller supporting pending,
   rejected, editing, and accepted transitions while retaining polygon edits
   outside `Measurement.selector`.
2. Expose per-proposal `Accept`, `Edit`, and `Reject` GUI controls. Reject must
   remove only the transient proposal; Edit must not autosave.
3. Implement the explicit Accept adapter against Potku's `Selection` API with
   element confirmation and tests proving no selector mutation occurs before
   that action.
## 2026-09-25 00:40 KST - Synthetic KIST geometry and auto-selection demo

Implemented:

- Added a parameterized synthetic ToF-ERD geometry preset for a 1.9 MV tandem
  with a 35Cl5+ beam. The nominal output energy is calculated as 11.4 MeV from
  `(q + 1) * terminal voltage`; injection energy remains a separate parameter.
- Defined recoil/detector angle as 30 degrees, incidence and exit angles as 75
  degrees from the surface normal, and flight length as a configurable 0.5 m.
  The preset checks that the coplanar geometry closes at 30 degrees.
- Added ideal channel-space loci for 1H, 12C, 16O, and 28Si, together with
  configurable ToF/Energy calibration and detector FWHM.
- Added deterministic synthetic event generation with detector broadening,
  element-specific calibration/stopping offsets, and uniform background noise.
- Added a runnable example that bins the raw events, detects each ridge, draws
  automatic closed polygons, and exports PNG, NPZ, and TSV evidence.
- Added `USER_ACTIONS.md` listing the real measurement, calibration, geometry,
  and selection inputs required from the user.

Verification:

- `python -m unittest tests.unit.test_tofe_synthetic`
  `tests.unit.test_tofe_candidate tests.unit.test_tofe_theory`
  `tests.unit.test_tofe_stopping tests.unit.test_tofe_report`
  `tests.unit.test_tofe_overlay`: **55 tests passed**.
- The standalone demo generated **25,000 events** and detected **4/4** recoil
  candidates: 1H confidence 0.802, 12C 0.749, 16O 0.692, and 28Si 0.686.
- `python -m compileall` for the new module, example, and test plus
  `git diff --check`: **passed**.

Limitation:

- No real KIST ToF-ERD event or accepted selection file is present. The current
  thresholds and confidence scores are validated only on synthetic data.
- Incidence and exit angles are recorded and checked but are not yet applied
  to sample stopping. The present ideal locus spans an energy fraction; a
  target-layer stopping model will use these path angles in a later unit.

Next:

1. Add acceptance metrics against synthetic truth labels and failure cases
   with overlapping or missing bananas.
2. Add Accept/Edit/Reject state and a controlled adapter into Potku selections.
3. Replace the synthetic calibration with one real KIST measurement, then
   quantify theory offset and polygon overlap before ML training.

## 2026-09-25 01:05 KST - Safe candidate review state

Implemented:

- Added a Qt-independent `CandidateReviewSession` for explicit `pending`,
  `editing`, `rejected`, and `accepted` proposal states.
- Assigned stable candidate IDs, including duplicate isotope labels, while
  keeping input proposal arrays copied and read-only inside the review state.
- Added begin, replace, finish, and cancel edit transitions. Polygon updates
  require a finite, closed shape with at least three distinct vertices.
- Added reject handling that only changes transient review state.
- Added an explicit acceptance callback boundary. No transition except
  `accept()` receives or invokes a selector conversion callback.
- Made acceptance transactional at the state level: if the future Potku
  selection adapter raises an exception, the candidate remains pending.

Verification:

- `python -m unittest tests.unit.test_tofe_candidate_review`
  `tests.unit.test_tofe_candidate tests.unit.test_tofe_overlay`
  `tests.unit.test_tofe_synthetic tests.unit.test_tofe_theory`
  `tests.unit.test_tofe_stopping tests.unit.test_tofe_report`:
  **63 tests passed**.
- The deterministic synthetic demo regenerated **25,000 events** and detected
  **4/4** candidates. Confidence remained 0.802 for 1H, 0.749 for 12C, 0.692
  for 16O, and 0.686 for 28Si.
- `python -m compileall -q` for the review module and test: **passed**.
- `git diff --check`: **passed**.

Failure / limitation:

- No test failed in the completed work unit.
- PyQt5 remains unavailable, so review buttons and interactive vertex dragging
  were not added or exercised in a live Potku window.
- The acceptance callback is a safety boundary only. The concrete adapter that
  converts an approved polygon and confirmed element into Potku's `Selection`
  is intentionally deferred until its GUI confirmation flow can be tested.
- Real KIST events and accepted selections remain unavailable. Confidence
  values are still synthetic heuristic scores rather than calibrated
  probabilities.

Next:

1. Connect the review session to a proposal list with per-candidate
   `Accept`, `Edit`, and `Reject` controls.
2. Add the explicit Potku `Selection` adapter behind `Accept`, with isotope
   confirmation and tests proving no selector or selection file mutation
   before that action.
3. Add synthetic truth-overlap metrics and overlapping or missing banana
   cases before tuning confidence thresholds.

## 2026-09-25 04:20 KST - Transactional Potku selection adapter

Implemented:

- Added an explicit adapter that converts one approved banana polygon into a
  closed ERD `Selection` with the user-confirmed element and isotope.
- Kept proposal coordinates canonical as `(ToF, Energy)` and swapped them only
  when Potku currently displays transposed axes. Selection-file output therefore
  remains compatible with Potku's existing transpose handling.
- Rounded candidate vertices to integer channels, removed consecutive duplicate
  vertices, and rejected polygons that collapse below three distinct points.
- Connected the adapter to the existing `CandidateReviewSession.accept()`
  callback boundary in tests. Edit and Reject never receive the adapter and do
  not mutate the selector or create a selection file.
- Added transactional rollback around Potku's `update_selections()` call. A
  failed update removes the new in-memory selection, restores the prior
  `.selections` bytes, removes a partial first file, and leaves the review item
  pending for correction or retry.
- Updated `USER_ACTIONS.md` to request confirmation of isotope-specific versus
  natural-element defaults before the GUI Accept dialog is finalized.

Verification:

- `python -m unittest tests.unit.test_tofe_selection_adapter`
  `tests.unit.test_tofe_candidate_review tests.unit.test_tofe_candidate`
  `tests.unit.test_tofe_overlay tests.unit.test_tofe_synthetic`
  `tests.unit.test_tofe_theory tests.unit.test_tofe_stopping`
  `tests.unit.test_tofe_report`: **71 tests passed**.
- Tests prove that Edit and Reject perform **0** selector updates, Accept
  performs exactly **1**, transposed coordinates are mapped correctly, and a
  simulated failed save restores both memory and the original file.
- The deterministic synthetic demo regenerated **25,000 events** and again
  detected **4/4** candidates with unchanged confidence values: 1H 0.802,
  12C 0.749, 16O 0.692, and 28Si 0.686.
- `python -m compileall -q` for the adapter and tests: **passed**.
- `git diff --check`: **passed**.

Failure / limitation:

- No automated test failed in the completed work unit.
- PyQt5 remains unavailable, so the adapter uses an injectable factory in
  tests and the concrete Potku `Selection` could not be instantiated here.
- The GUI still has no review list or `Accept`, `Edit`, and `Reject` controls.
  The new adapter is therefore implemented and verified but not yet reachable
  from the live histogram window.
- Real KIST events and selections are still absent, so confidence and polygon
  accuracy remain synthetic-only.

Next:

1. Add a review dialog that lists proposals with confidence and exposes
   `Accept`, `Edit`, and `Reject` actions.
2. Require element/isotope confirmation in that dialog and call the new
   adapter only after the final Accept confirmation.
3. Add synthetic truth-overlap metrics plus overlapping and missing-banana
   cases before moving to ML feature extraction.

## 2026-09-25 07:10 KST - Candidate review dialog and GUI connection

Implemented:

- Added a Qt-independent review controller that exposes candidate label,
  confidence, ridge coverage, status, and editable polygon coordinates.
- Added a `Review…` action to the ToF-E histogram. It is enabled only while
  transient candidate proposals exist and opens a table for reviewing each
  candidate.
- Added polygon editing as explicit ToF/Energy coordinate rows. Applying or
  cancelling an edit changes only the transient candidate state; Reject also
  removes only the proposal overlay.
- Added explicit element/isotope confirmation and a final warning that Accept
  will update the Potku selection file. Only that confirmed action calls the
  transactional selection adapter.
- Removed accepted and rejected proposals from the transient overlay after the
  dialog closes, while leaving pending proposals available for later review.
- Updated `USER_ACTIONS.md` to reflect that isotope confirmation and the final
  save warning are now implemented.

Verification:

- `python -m unittest tests.unit.test_tofe_review_controller`
  `tests.unit.test_tofe_selection_adapter tests.unit.test_tofe_candidate_review`
  `tests.unit.test_tofe_candidate tests.unit.test_tofe_overlay`
  `tests.unit.test_tofe_synthetic tests.unit.test_tofe_theory`
  `tests.unit.test_tofe_stopping tests.unit.test_tofe_report`:
  **77 tests passed**.
- Controller tests prove Edit and Reject perform **0** selector updates and
  create no file, while a confirmed Accept performs exactly **1** update.
- `python -m compileall -q` for the controller, dialog, histogram integration,
  and tests: **passed**.
- `git diff --check`: **passed**.
- The deterministic synthetic demo regenerated **25,000 events** and detected
  **4/4** candidates: 1H confidence 0.802, 12C 0.749, 16O 0.692, and 28Si
  0.686. The spectrum PNG, raw-event NPZ, and polygon TSV were refreshed.

Failure / limitation:

- No automated test failed in the completed implementation.
- PyQt5 is not installed in this execution environment, so the new dialog and
  toolbar action compile but could not be exercised interactively or captured
  from a live Potku window.
- Polygon editing currently uses numeric ToF/Energy rows rather than draggable
  handles on the histogram. This preserves the approval boundary but is less
  convenient than direct visual editing.
- Real KIST events and accepted selections remain absent. Confidence values
  and the review workflow are therefore verified on synthetic data only.

Next:

1. Add synthetic truth-overlap metrics and overlapping or missing-banana
   scenarios to quantify polygon precision and recall before ML extraction.
2. Add non-persistent drag handles for proposal vertices, then send the edited
   polygon back through the same review controller.
3. Exercise the dialog with PyQt5, JIBAL, and one real measurement once those
   dependencies and data are available.

## 2026-09-25 10:08 KST - Synthetic truth-event selection metrics

Implemented:

- Added Qt-independent evaluation of automatic polygons against per-event
  synthetic truth labels. Each element now reports selected/true event counts,
  true positives, false positives, false negatives, precision, recall, F1, and
  event IoU.
- Added micro-averaged summary metrics and explicit rows for expected elements
  with no candidate. Missing bananas therefore remain visible with
  `detected=False` and zero recall instead of disappearing from the report.
- Added a dependency-free, vectorized point-in-polygon implementation with
  finite, closed, and non-degenerate polygon validation.
- Extended the synthetic demo TSV and plot labels with event-level overlap
  metrics. The raw events and automatic polygons are otherwise unchanged.
- Added an overlapping-banana scenario using two labels at the same physical
  locus. Both ridges are detected, but cross-label contamination reduces
  precision to about 0.50 and event IoU below 0.47.
- Added an absent-element scenario. A 16O locus searched against a synthetic
  spectrum containing only 12C produces no 16O candidate and is reported as
  not detected.
- Updated `USER_ACTIONS.md` to request a real difficult spectrum containing
  overlapping bananas or an expected element that is absent, if available.

Verification:

- `python -m unittest tests.unit.test_tofe_candidate_metrics`
  `tests.unit.test_tofe_review_controller tests.unit.test_tofe_selection_adapter`
  `tests.unit.test_tofe_candidate_review tests.unit.test_tofe_candidate`
  `tests.unit.test_tofe_overlay tests.unit.test_tofe_synthetic`
  `tests.unit.test_tofe_theory tests.unit.test_tofe_stopping`
  `tests.unit.test_tofe_report`: **86 tests passed**.
- Default 25,000-event demo: **4/4 candidates**, micro precision **0.992**,
  recall **0.839**, F1 **0.909**, and event IoU **0.834**.
- Per-element event IoU: 1H **0.880**, 12C **0.849**, 16O **0.817**, and
  28Si **0.789**.
- Fully overlapping 12C labels: precision **0.496 / 0.504**, recall
  **0.845 / 0.860**, and event IoU **0.455 / 0.466**.
- `python -m compileall -q` for the metric module, demo, and tests:
  **passed**.
- `git diff --check`: **passed**.

Failure / limitation:

- No automated test failed in the completed implementation.
- Event IoU measures labeled event membership, not geometric polygon-area IoU.
  Its value depends on the synthetic event distribution and background density,
  which is appropriate for this generator but is not a calibrated real-data
  accuracy probability.
- Identical overlapping loci expose contamination but cannot by themselves
  decide how shared events should be assigned. The later ML stage needs shape,
  physics-offset, and neighbouring-candidate features for that decision.
- Real KIST events, accepted selections, PyQt5, and JIBAL remain unavailable in
  this environment. Existing Potku operation and the approval-only selection
  save boundary are unchanged.

Next:

1. Convert accepted Potku selections plus their enclosed measurement events
   into ML-ready rows with physics-offset and polygon-shape features.
2. Add candidate-to-candidate overlap and nearest-neighbour features so the ML
   correction model can identify ambiguous shared ridges.
3. Add non-persistent drag handles for proposal vertices and validate the GUI
   with PyQt5 and one real measurement when available.

## 2026-09-25 13:10 KST - Accepted selections to ML feature rows

Implemented:

- Added a Qt- and scikit-learn-independent adapter for completed Potku ERD
  selections. It filters incomplete and RBS selections, restores canonical
  `(ToF, Energy)` coordinates for transposed displays, closes polygons, and
  preserves element/isotope labels.
- Added one deterministic 25-field ML row per accepted polygon. The schema
  contains measurement identity and target, enclosed-event count/fraction and
  moments, polygon area/perimeter/compactness/extents/centroid, detector-FWHM
  normalized offsets from the matching theory locus, and event-based overlap
  with neighbouring selections.
- Added strict validation for finite events, valid isotope labels, nonzero
  polygon area, unique theory labels, and binary acceptance targets. Empty
  polygons produce finite zero-valued event statistics rather than NaN.
- Added stable TSV export and extended the synthetic demonstration to write
  `ml_training_rows.tsv`. The extraction layer only reads event and selection
  objects; it does not create, edit, or save any Potku selection.
- Updated `USER_ACTIONS.md` to require each raw event file to remain paired
  with the exact accepted `.selections` file and measurement identity.

Verification:

- `python -m unittest tests.unit.test_tofe_training_data`
  `tests.unit.test_tofe_candidate_metrics tests.unit.test_tofe_review_controller`
  `tests.unit.test_tofe_selection_adapter tests.unit.test_tofe_candidate_review`
  `tests.unit.test_tofe_candidate tests.unit.test_tofe_overlay`
  `tests.unit.test_tofe_synthetic tests.unit.test_tofe_theory`
  `tests.unit.test_tofe_stopping tests.unit.test_tofe_report`:
  **95 tests passed**.
- `python -m compileall -q` for the new feature module, synthetic demo, and
  tests: **passed**.
- `git diff --check`: **passed**.
- Default 25,000-event demo: **4/4 candidates**, micro precision **0.992**,
  recall **0.839**, F1 **0.909**, and event IoU **0.834**.
- The four accepted synthetic polygons produced **4 rows x 25 fields**. Their
  enclosed-event counts were 4,445 (1H), 4,311 (12C), 4,142 (16O), and 4,016
  (28Si); every row matched a theory locus and all values were finite.

Failure / limitation:

- The first synthetic conversion test used only 1,200 signal events per locus;
  three candidates fell below the established ridge thresholds. The test was
  corrected to use the documented 25,000-event preset and then all 95 tests
  passed. No production threshold was weakened.
- Existing accepted selections provide positive examples only. A correction
  model also needs proposed polygons that users rejected or edited, recorded
  without saving them as accepted Potku selections.
- Theory offsets use the present ideal/foil-corrected locus and detector FWHM;
  they are not calibrated real-data residuals until KIST events and settings
  are supplied.
- Real KIST events, accepted selections, PyQt5, and JIBAL remain unavailable.
  Existing Potku behavior and the explicit approval-only save boundary are
  unchanged.

Next:

1. Represent proposed, edited, accepted, and rejected candidate decisions as
   labeled training examples without writing rejected polygons to Potku files.
2. Train and serialize a small optional baseline correction model using the 25
   physical/shape fields, with deterministic fallback to heuristic confidence
   when no compatible model exists.
3. Add grouped measurement-level train/validation splitting and verify it on
   synthetic overlap, missing-element, and shifted-locus scenarios.
