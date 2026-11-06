Tri-directional FEM workflow
============================

This example targets **finite-element** projects with **tri-directional** input motion
(``inputMotionConfiguration = TriDirectional``). It shows:

* Verifying solver and input-motion mode on ``ProjectSettings``
* Reading tri FEM layer fields (``PWaveVelocity``, ``DminVolumetric`` on a soil layer; bedrock ``PWaveVelocity``)
* ``Motions.refreshMotionsList``, ``listMotionTriplets``, and ``setMotionTripletSelection``
* ``runCompute`` and listing result database paths via ``Results``

Use a tri-directional FEM project with motion triplets (H1, H2, V files sharing a name prefix).
A local **Verification 3** fixture (see ``tests/resources/README.md``) matches the integration tests.

.. literalinclude:: ../../examples/example_tri_directional_fem_workflow.py
   :language: python
   :linenos:
