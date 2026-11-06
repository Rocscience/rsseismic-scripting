Tutorial 3 — NSHMP, motions, seven profiles, batch compute
==========================================================

Full workflow: GMDB authentication, target spectra (NSHMP or a user-defined file),
automatic motion selection, seven GQ/H projects from CSV inputs, batch compute, and
post-processing plots.

**Requires:** GMDB credentials; RSSeismic scripting; NumPy and Matplotlib.

Download profile CSVs (place under ``examples/Tutorial_3/Inputs/``):

* :download:`profile_01.csv <../../examples/Tutorial_3/Inputs/profile_01.csv>`
* :download:`profile_02.csv <../../examples/Tutorial_3/Inputs/profile_02.csv>`
* :download:`profile_03.csv <../../examples/Tutorial_3/Inputs/profile_03.csv>`
* :download:`profile_04.csv <../../examples/Tutorial_3/Inputs/profile_04.csv>`
* :download:`profile_05.csv <../../examples/Tutorial_3/Inputs/profile_05.csv>`
* :download:`profile_06.csv <../../examples/Tutorial_3/Inputs/profile_06.csv>`
* :download:`profile_07.csv <../../examples/Tutorial_3/Inputs/profile_07.csv>`

Default user-defined target spectrum when using ``--target-source file`` (repo default path
``tests/resources/target_spectrum_example.txt``; copy beside the tutorial or pass ``--target-file``):

* :download:`target_spectrum_example.txt <../../tests/resources/target_spectrum_example.txt>`

Run from the repository root:

.. code-block:: text

   python examples/Tutorial_3/Tutorial_3_e2e.py --username USER --password PASS

.. literalinclude:: ../../examples/Tutorial_3/Tutorial_3_e2e.py
   :language: python
   :linenos:
