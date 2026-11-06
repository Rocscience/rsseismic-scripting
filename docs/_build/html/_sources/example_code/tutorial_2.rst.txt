Tutorial 2 — batch projects from CSV profiles
=============================================

Build five GQ/H projects from CSV layer definitions, batch-compute them against motions
from the RSSeismic motion folder, then read ``deepsoilout.db3`` files and aggregate
response plots with Matplotlib.

**Requires:** RSSeismic scripting server; NumPy and Matplotlib in your Python environment.

Input CSVs live under ``examples/Tutorial_2/Inputs/`` (one file per case). Column layout:

.. literalinclude:: ../../examples/Tutorial_2/Inputs/profile_01.csv
   :language: text
   :lines: 1-3

Download inputs (place under ``examples/Tutorial_2/Inputs/`` next to the script):

* :download:`profile_01.csv <../../examples/Tutorial_2/Inputs/profile_01.csv>`
* :download:`profile_02.csv <../../examples/Tutorial_2/Inputs/profile_02.csv>`
* :download:`profile_03.csv <../../examples/Tutorial_2/Inputs/profile_03.csv>`
* :download:`profile_04.csv <../../examples/Tutorial_2/Inputs/profile_04.csv>`
* :download:`profile_05.csv <../../examples/Tutorial_2/Inputs/profile_05.csv>`

Run from the repository root:

.. code-block:: text

   python examples/Tutorial_2/Scripting-Tutorial_2.py

.. literalinclude:: ../../examples/Tutorial_2/Scripting-Tutorial_2.py
   :language: python
   :linenos:
