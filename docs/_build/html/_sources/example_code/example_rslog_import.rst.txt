Import boreholes from RSLog
===========================

Create a blank project, list RSLog projects and boreholes from a **JSON export**
or an **authenticated RSLog account**, import selected test holes as profiles,
then save a ``.rsseismicfile`` you can open in RSSeismic to inspect the result.

File source uses the Imperial fixture under ``tests/resources/`` by default
(no login). Account source requires ``--company``, ``--username``, and
``--password``. The script prefers boreholes that already have a drilling
groundwater depth (or piezometer measurements) and imports them with the
default water table applied.

.. code-block:: console

   python examples/example_rslog_import.py --source file
   python examples/example_rslog_import.py --source account --company COMPANY --username USER --password PASS

.. literalinclude:: ../../examples/example_rslog_import.py
   :language: python
   :linenos:
