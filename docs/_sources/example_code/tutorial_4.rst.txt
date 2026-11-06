Tutorial 4 — NSHMP motions and FEM auto-profile project
=======================================================

Motion selection (GMDB / NSHMP or user-defined spectrum), FEM project setup, optional
automatic profile generation from a template project, compute, and result plots.

**Requires:** GMDB credentials for the motion-selection steps; NumPy and Matplotlib.

Download inputs (place under ``examples/Tutorial_4/Inputs/``):

* :download:`mean_profile_layers.csv <../../examples/Tutorial_4/Inputs/mean_profile_layers.csv>`
* :download:`mean_profile_layers_column_map.csv <../../examples/Tutorial_4/Inputs/mean_profile_layers_column_map.csv>`
* :download:`profile_generation_settings.csv <../../examples/Tutorial_4/Inputs/profile_generation_settings.csv>`

User-defined target spectrum (``--target-source file``; default path ``tests/resources/target_spectrum_example.txt``):

* :download:`target_spectrum_example.txt <../../tests/resources/target_spectrum_example.txt>`

For ``--randomize``, provide an auto-profile template — see
``examples/Tutorial_4/template/README.md`` or ``tests/resources/Test_Auto_Profile.rsseismicfile``.

Run from the repository root:

.. code-block:: text

   python examples/Tutorial_4/Tutorial_4_e2e.py --username USER --password PASS

.. literalinclude:: ../../examples/Tutorial_4/Tutorial_4_e2e.py
   :language: python
   :linenos:
