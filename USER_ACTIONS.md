# User actions for real ToF-ERD validation

The synthetic workflow now exercises theory calculation and automatic banana
selection without measured data.  The following inputs are still required to
turn the result into a calibrated KIST workflow.

## Highest priority

1. Provide one previously analysed measurement containing the raw ToF-Energy
   events and its accepted Potku selection file.  Three to five measurements
   from different samples would support the first machine-learning split.
   Keep each raw event file paired with the exact `.selections` file and
   measurement name used during analysis so training rows cannot be mismatched.
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
   demonstration uses isotope-specific labels.  The new Accept dialog requires
   the element/isotope to be confirmed and shows a final warning before saving.
9. If possible, include one difficult spectrum with overlapping bananas or an
   expected element that is absent.  These cases are now explicit synthetic
   tests and need a real-data comparison before threshold calibration.
10. When the review workflow is tested, keep a small record of automatic
    candidates that were accepted unchanged, edited, or rejected.  For an edit,
    retain both the original proposal and the final accepted polygon. Existing
    `.selections` files contain positive examples, but these review decisions
    are needed to teach the correction model what a poor proposal looks like.
    The current baseline model contains synthetic decisions only and must not
    be enabled as a real-data calibration until these records are available.

No real measurement is currently present in this working copy.  Until these
items arrive, confidence values measure performance on synthetic data and must
not be interpreted as calibrated probabilities for real spectra.
