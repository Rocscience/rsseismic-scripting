rsseismic.enums package
=======================

Typed enum values for RSSeismic scripting properties and project settings.
Import from the public package namespace::

   from rsseismic.enums import SoilModel, AnalysisMode, InputMotionConfiguration

Each enum is a ``str`` subclass: members compare equal to their gRPC wire strings, and
``EnumClass("WireValue")`` resolves the typed member. Reserved name ``None`` is exposed as
``None_`` on enums such as ``CurveModel`` and ``PWPModel``.

.. automodule:: rsseismic.enums._generated
   :members:
   :undoc-members:
   :show-inheritance:

Curve fitting (``SoilLayerCurve.runCurveFit``):

.. automodule:: rsseismic.enums.fitting_procedure
   :members:
   :undoc-members:
   :show-inheritance:

