# User actions for real ToF-ERD validation

The synthetic workflow now exercises theory calculation and automatic banana
selection without measured data.  The following inputs are still required to
turn the result into a calibrated KIST workflow.

## Highest priority

1. Provide one previously analysed measurement containing the raw ToF-Energy
   events and its accepted Potku selection file.  Three to five measurements
   from different samples would support the first machine-learning split.
2. Export or confirm the measurement settings used for that run: beam isotope,
   terminal voltage or beam energy, charge state, recoil angle, timing-foil
   positions, foil material and thickness, detector time resolution, detector
   energy resolution, ToF slope/offset, and energy slope/offset.
3. Confirm the angle convention.  The current preset treats the 75 degree
   incidence and exit angles as angles from the sample surface normal.  In a
   coplanar reflection geometry this gives a 30 degree recoil angle.

## Useful follow-up

4. Confirm whether the typical 1.9 MV setting means terminal voltage or the
   analysed beam energy.  The current tandem preset assumes 1.9 MV terminal
   voltage and calculates 35Cl5+ as 11.4 MeV before adding injection energy.
5. Confirm the actual timing flight length.  The synthetic preset currently
   uses 0.5 m.
6. Identify which recoil elements should appear by default.  The synthetic
   demonstration currently uses 1H, 12C, 16O, and 28Si.
7. Supply a blank/background measurement if available.  It will help calibrate
   the candidate confidence and minimum-event thresholds.
8. Confirm whether accepted automatic selections should default to a specific
   isotope (for example, 16O) or to the natural element (O).  The synthetic
   demonstration uses isotope-specific labels, and the planned Accept dialog
   will require the element/isotope to be confirmed before saving.

No real measurement is currently present in this working copy.  Until these
items arrive, confidence values measure performance on synthetic data and must
not be interpreted as calibrated probabilities for real spectra.
