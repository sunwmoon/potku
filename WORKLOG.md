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
