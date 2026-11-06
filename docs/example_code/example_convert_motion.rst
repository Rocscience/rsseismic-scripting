Convert and delete library motions
==================================

Convert a text or PEER AT2 file into the Motion Manager library, or delete motions by name. Convert adds the motion to the library (unlike scale/baseline/timestep, which write external files only).

``outputDirectory`` must be a folder listed in RSSeismic Preferences → Motions.

.. literalinclude:: ../../examples/example_convert_motion.py
   :language: python
   :linenos:
