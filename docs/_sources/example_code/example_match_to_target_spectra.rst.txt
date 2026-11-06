Match ground motions to target spectra
======================================

Script the Motion Manager wizard **Match ground motions to target spectra**.
Scaled motions are written into a folder listed under RSSeismic
**Preferences → Motions** (same rules as convert / database import).

The example supports both wizard paths:

**Manual**

1. Discover H1/H2 pairs under a folder (and subfolders).
2. Select pairs (``selectAll`` or specific pair ids).
3. Load target spectra (here: a user-defined period–Sa text file via
   ``getTargetSpectra(UserDefinedTargetSpectraModel(...))``; REXEL and NSHMP
   models work the same way).
4. Call ``matchToTargetSpectraManual`` with amplitude scaling parameters.

**Automatic** (GMDB or ESM only; CESMD is not supported)

1. ``authenticateDatabase`` for the session.
2. Load target spectra.
3. Call ``matchToTargetSpectraAutomatic`` with search filters and optional
   ``RecordSelectionParams`` (wizard knobs: ``nGm``, damping, tolerance,
   ``isScaled``, ``maxCandidates``, ``defaultSigmaLn``). Period window and
   scale-factor bounds come from ``AmplitudeScalingParams``.

.. note::
   Pair discovery returns an empty selection. Always ``select`` / ``selectAll``
   before Manual match. For Automatic, authenticate first (same as search/import).

.. literalinclude:: ../../examples/example_match_to_target_spectra.py
   :language: python
   :linenos:
