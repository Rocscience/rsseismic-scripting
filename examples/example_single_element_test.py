"""
Single Element Test workflow using the installed rsseismic package.

Requires a running RSSeismic scripting server and a project that can use
Single Element Test (Nonlinear analysis + Lumped Mass solver). Mean-profile
layers are not supported.

Strain values are in percent (%), matching the Single Element Test dialog.

  python examples/example_single_element_test.py "E:\\path\\to\\project.rsseismicfile"
  python examples/example_single_element_test.py --port 60058 --layer-id <GUID> project.rsseismicfile
"""

from __future__ import annotations

import argparse
import os
import sys

from rsseismic import RSSeismicApplication, StrainPathSegment
from rsseismic._client import DEFAULT_SCRIPTING_PORT
from rsseismic.enums import AnalysisMode, SolverType


def _ensure_element_test_settings(model) -> None:
    """Ensure Nonlinear analysis and Lumped Mass solver for Single Element Test."""
    settings = model.ProjectSettings
    analysis_mode = settings.getAnalysisMethod()
    solver_type = settings.getSolverType()

    if analysis_mode != AnalysisMode.Nonlinear:
        print(f"Setting analysis mode: {analysis_mode.value} -> Nonlinear")
        settings.setAnalysisMethod(AnalysisMode.Nonlinear)
    else:
        print(f"Analysis mode: {analysis_mode.value}")

    if solver_type != SolverType.LumpedMassModel:
        print(f"Setting solver type: {solver_type.value} -> LumpedMassModel")
        settings.setSolverType(SolverType.LumpedMassModel)
    else:
        print(f"Solver type: {solver_type.value}")


def _resolve_layer(model, layer_id: str | None, profile_name: str):
    if layer_id:
        return model.Profiles.getSoilLayer(layer_id)

    layers = (
        model.Profiles.listSoilLayers(profile_name)
        if profile_name
        else model.Profiles.listActiveSoilLayers()
    )
    if not layers:
        raise RuntimeError("Project has no soil layers to test.")
    return model.Profiles.getSoilLayer(layers[0].layerID)


def run_single_element_test_workflow(
    project_path: str,
    port: int = DEFAULT_SCRIPTING_PORT,
    layer_id: str | None = None,
    profile_name: str = "",
) -> None:
    """
    Open a project, create a Single Element Test working copy, run, and verify
    the live profile layer is unchanged.

    Project settings may be adjusted in memory (Nonlinear + Lumped Mass) for the
    session. The project file is closed without saving.
    """
    project_path = os.path.abspath(project_path.strip())
    if not os.path.isfile(project_path):
        raise FileNotFoundError(f"Project file not found: {project_path}")

    app = RSSeismicApplication(port=port)
    model = None

    try:
        app.ping()
        model = app.openFile(project_path)

        active = model.Profiles.getActiveProfile()
        print(f"Opened project. Active profile: {active.profileName}")

        _ensure_element_test_settings(model)

        layer = _resolve_layer(model, layer_id, profile_name)
        live_thickness = layer.getThickness()
        live_ref_strain = layer.getRefStrain()
        live_unit_weight = layer.getUnitWeight()
        print(
            f"Source layer: {layer.layerId} "
            f"(thickness={live_thickness}, refStrain={live_ref_strain}, "
            f"unitWeight={live_unit_weight})"
        )

        strain_path = [
            StrainPathSegment(startingStrain=0.0, endingStrain=0.1, increments=20),
            (0.1, 0.0, 20),
        ]

        with layer.createElementTestLayer(profileName=profile_name) as test:
            print(f"Created element test layer: {test.elementTestLayerId}")
            if test.profileName:
                print(f"  profile: {test.profileName}")

            # Configure the working copy only — not the live profile layer.
            original_test_ref_strain = test.getRefStrain()
            tuned_ref_strain = original_test_ref_strain * 1.1 if original_test_ref_strain else 0.05
            test.setRefStrain(tuned_ref_strain)
            print(
                f"Working-copy ref strain: {original_test_ref_strain} -> {test.getRefStrain()}"
            )

            dataframe = test.runSingleElementTest(strainPath=strain_path)
            print(
                f"First run: {len(dataframe)} row(s), columns={list(dataframe.columns)}"
            )
            units = dataframe.attrs.get("column_units")
            if units:
                print(f"Column units: {units}")
            print(dataframe.head().to_string(index=False))

            # Re-run on the same working copy to show the session is reusable.
            dataframe_again = test.runSingleElementTest(
                strainPath=[(0.0, 0.05, 10), (0.05, 0.0, 10)],
                enableDissipation=False,
            )
            print(f"Second run: {len(dataframe_again)} row(s)")

            if dataframe.empty or dataframe_again.empty:
                raise RuntimeError("Single Element Test returned an empty DataFrame.")

        # Live profile layer must be unchanged by configure/run/close.
        if layer.getThickness() != live_thickness:
            raise RuntimeError("Live layer thickness changed after element test.")
        if layer.getRefStrain() != live_ref_strain:
            raise RuntimeError("Live layer reference strain changed after element test.")
        if layer.getUnitWeight() != live_unit_weight:
            raise RuntimeError("Live layer unit weight changed after element test.")

        print("Live profile layer unchanged. Single Element Test workflow succeeded.")
    finally:
        if model is not None:
            model.close(saveProject=False)
        app.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Open a project, run Single Element Test on a soil-layer working copy, "
            "and verify the live layer is not modified."
        )
    )
    parser.add_argument(
        "project",
        help="Absolute path to a .rsseismicfile",
    )
    parser.add_argument(
        "--port",
        "-p",
        type=int,
        default=int(os.environ.get("RSSEISMIC_SCRIPTING_PORT", DEFAULT_SCRIPTING_PORT)),
        help=f"gRPC port (default: {DEFAULT_SCRIPTING_PORT}, or RSSEISMIC_SCRIPTING_PORT env)",
    )
    parser.add_argument(
        "--layer-id",
        default="",
        metavar="GUID",
        help="Soil layer GUID to test. Default: first layer on the active (or --profile) profile.",
    )
    parser.add_argument(
        "--profile",
        default="",
        metavar="NAME",
        help="Profile name that owns the layer. Leave empty to use the active profile.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        run_single_element_test_workflow(
            args.project,
            port=args.port,
            layer_id=args.layer_id or None,
            profile_name=args.profile,
        )
    except Exception as ex:
        print(f"Single Element Test workflow failed: {ex}", file=sys.stderr)
        return 1

    print("Workflow finished.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
