RSSeismic Scripting Reference Manual
========================================================

**Version: 3.0.1**

Prerequisites
--------------------
Before you begin, ensure you have the RSSeismic program installed. You must have at minimum Version 3.0 in order to use this feature.


Python Environment
--------------------
There are two methods to run a script, which differ in the Python environment used:

1. Running on RocScript Editor
	* Comes pre-installed with RSSeismic and includes the **RSSeismic Python API library**
	* For all-level users
2. Running on your own Python environment
	* Requires downloading the **RSSeismic Python API library**
	* For advanced users

Install RSSeismic Python API Library
-----------------------------------
pip installation

.. code-block::

   pip install RSSeismicScripting

If you are not using the latest release of RSSeismic, you need to specify a library version that matches your RSSeismic version. For example:

.. code-block::

   pip install "RSSeismicScripting==3.0.0"

Table of Contents
-------------------------
.. toctree::
   :titlesonly:
   :maxdepth: 2
   :caption: Contents:

   generatedAPIDocFiles/rsseismic
   examples
