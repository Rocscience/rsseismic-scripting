Python Script Examples
======================

These pages show how example scripts are wired into the reference manual.
They are **scaffold samples** for engineers to replace or expand with production-quality examples later.

To add a new example:

1. Add or update a script under ``examples/``.
2. Add ``docs/example_code/<name>.rst`` with a ``.. literalinclude::`` directive.
3. Register the page in the appropriate toctree below.

Getting started
---------------
.. toctree::
   :maxdepth: 1

   example_code/example_ping
   example_code/example_auto_launch_app

Workflows
---------
.. toctree::
   :maxdepth: 1

   example_code/example_single_profile_workflow
   example_code/example_single_profile_workflow_v1
   example_code/example_auto_profile_workflow
   example_code/example_plot_results_v1
