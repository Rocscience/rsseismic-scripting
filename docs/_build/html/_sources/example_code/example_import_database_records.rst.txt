Import records from GMDB / CESMD / ESM
=====================================

Authenticate once for the scripting session, then search an external ground-motion database and import selected records into the Motion Manager library. ``outputDirectory`` must be a folder listed in RSSeismic Preferences → Motions.

Use ``--database GMDB``, ``CESMD``, or ``ESM``. CESMD uses an email username and does not require a password; GMDB and ESM require both. Pass full ``DatabaseRecordInfo`` objects from search into import (download fields differ by database; search results already include what import needs).

``DatabaseSearchFilters`` exposes the wizard-visible filter union for all three databases (unused fields for a DB are ignored). Option-list values are strings; multi-select networks and similar fields use comma-separated codes (for example ``\"CI,NP\"``). PGA filters are in **g**. Dates are ``yyyy-MM-dd``. GMDB enums are typed as ``ProcessingType``, ``MagnitudeType``, and ``EventType``. Pass ``maxResults`` to ``searchDatabaseRecords`` (or ``--max-results`` in the example) to cap returned hits; ``--max-records`` still controls how many of those hits are imported.

.. note::
   ``GroundMotionDatabase.ESM`` is the public name for the Engineering Strong-Motion database.
   On the wire it maps to the server enum value historically named FDSN.

.. literalinclude:: ../../examples/example_import_database_records.py
   :language: python
   :linenos:
