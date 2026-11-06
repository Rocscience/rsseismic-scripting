"""
Tri-directional FEM workflow: motion triplets, optional tri layer properties, compute, results.

Requires a project with:
  - solverType = FiniteElementMethod
  - inputMotionConfiguration = TriDirectional
  - Motion files named so H1, H2, and V share a common prefix (triplet id)

Example (Verification 3 FEM project):

  python examples/example_tri_directional_fem_workflow.py "E:\\path\\to\\Verification 3.rsseismicfile"
  python examples/example_tri_directional_fem_workflow.py --triplet Event --no-compute project.rsseismicfile
  python examples/example_tri_directional_fem_workflow.py --port 60058 project.rsseismicfile

Set RSSEISMIC_COMPUTE_TIMEOUT_SECONDS for long FEM runs (default 3600 s when computing).
"""

from __future__ import annotations

import argparse
import os
import sys

from rsseismic import RSSeismicApplication, logger
from rsseismic._client import DEFAULT_SCRIPTING_PORT
from rsseismic.types import MotionTripletInfo

FEM_SOLVER = "FiniteElementMethod"
TRI_DIRECTIONAL = "TriDirectional"


def _assert_tri_directional_fem(model) -> None:
    settings = model.ProjectSettings.Data
    solver_type = settings.getEnumValue("solverType", str)
    if solver_type != FEM_SOLVER:
        raise RuntimeError(
            f"Expected solverType {FEM_SOLVER!r}, got {solver_type!r}. "
            "Open a finite-element project."
        )
    configuration = settings.getEnumValue("inputMotionConfiguration", str)
    if configuration != TRI_DIRECTIONAL:
        raise RuntimeError(
            f"Expected inputMotionConfiguration {TRI_DIRECTIONAL!r}, got {configuration!r}. "
            "Use listMotionTriplets / setMotionTripletSelection only on tri-directional projects."
        )


def _log_tri_fem_layer_properties(model, profile_name: str) -> None:
    """Demonstrate reading tri-directional FEM layer fields exposed on soil/bedrock layers."""
    summaries = model.Profiles.listActiveSoilLayers()
    if summaries:
        layer = model.Profiles.getSoilLayer(summaries[0].layerID)
        vp = layer.getPWaveVelocity()
        dmin_vol = layer.getDminVolumetric()
        logger.info(
            "Top soil layer %s: PWaveVelocity=%.4g, DminVolumetric=%.4g",
            summaries[0].name,
            vp,
            dmin_vol,
        )

    bedrock = model.Profiles.getBedrockLayerProxy(profile_name)
    logger.info("Bedrock PWaveVelocity=%.4g", bedrock.getPWaveVelocity())


def _select_motion_triplet(model, requested_triplet_ids: list[str]) -> MotionTripletInfo:
    model.Motions.refreshMotionsList()
    triplets = model.Motions.listMotionTriplets()
    if not triplets:
        raise RuntimeError(
            "No motion triplets found. Add H1, H2, and V files with a shared name prefix "
            "and ensure motion directories are configured in RSSeismic Preferences."
        )

    if requested_triplet_ids:
        by_id = {triplet.tripletId: triplet for triplet in triplets}
        missing = [triplet_id for triplet_id in requested_triplet_ids if triplet_id not in by_id]
        if missing:
            available = ", ".join(sorted(by_id))
            raise RuntimeError(f"Unknown triplet id(s) {missing}. Available: {available}")
        target_id = requested_triplet_ids[0]
    else:
        selected = [triplet for triplet in triplets if triplet.isSelected]
        target_id = selected[0].tripletId if selected else triplets[0].tripletId

    model.Motions.setMotionTripletSelection([target_id], selectOnlyListed=True)
    updated = model.Motions.listMotionTriplets()
    triplet = next(item for item in updated if item.tripletId == target_id)
    logger.info(
        "Selected triplet %r (H1=%s, H2=%s, V=%s)",
        triplet.tripletId,
        triplet.motionH1Name,
        triplet.motionH2Name,
        triplet.motionVName,
    )
    return triplet


def run_tri_directional_fem_workflow(
    project_path: str,
    port: int = DEFAULT_SCRIPTING_PORT,
    triplet_ids: list[str] | None = None,
    run_compute: bool = True,
    log_layer_properties: bool = True,
) -> list[str]:
    """
    Open a tri-directional FEM project, select a motion triplet, save, optionally compute.

    Returns result database paths when compute runs successfully, otherwise an empty list.
    """
    project_path = os.path.abspath(project_path.strip())
    if not os.path.isfile(project_path):
        raise FileNotFoundError(f"Project file not found: {project_path}")

    compute_timeout = float(os.environ.get("RSSEISMIC_COMPUTE_TIMEOUT_SECONDS", "3600"))

    app = RSSeismicApplication(port=port)
    model = None
    result_paths: list[str] = []

    try:
        app.ping()
        model = app.openFile(project_path)

        _assert_tri_directional_fem(model)
        profile_name = model.Profiles.getActiveProfile().profileName
        if not profile_name:
            raise RuntimeError("Active profile has no name.")

        if log_layer_properties:
            _log_tri_fem_layer_properties(model, profile_name)

        _select_motion_triplet(model, triplet_ids or [])
        model.save()

        if not run_compute:
            return result_paths

        result = model.runCompute(timeout=compute_timeout)
        if not result.success:
            raise RuntimeError(result.errorMessage or "RunCompute failed.")
        if result.partialSuccess:
            raise RuntimeError(f"RunCompute partial success:\n{result.errorMessage}")

        entries = model.Results.listResultDatabases(profile_name, onlyExisting=True)
        if not entries:
            raise RuntimeError("Compute finished but no result databases were listed.")

        for listed in entries:
            entry = model.Results.getResultDatabasePath(profile_name, listed.motionName)
            path = entry.resultDatabasePath
            if path and entry.resultDatabaseExists:
                result_paths.append(path)
                logger.info(
                    "Result DB for motion %r (%s): %s",
                    listed.motionName,
                    listed.motionType,
                    path,
                )

        if not result_paths:
            raise RuntimeError("Result entries were listed but no existing database paths were found.")

        return result_paths
    finally:
        if model is not None:
            model.close(saveProject=False)
        app.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Tri-directional FEM: triplets → save → compute → result databases."
    )
    parser.add_argument(
        "project",
        help="Path to a .rsseismicfile (tri-directional FEM input motion)",
    )
    parser.add_argument(
        "--port",
        "-p",
        type=int,
        default=int(os.environ.get("RSSEISMIC_SCRIPTING_PORT", DEFAULT_SCRIPTING_PORT)),
        help=f"gRPC port (default: {DEFAULT_SCRIPTING_PORT}, or RSSEISMIC_SCRIPTING_PORT env)",
    )
    parser.add_argument(
        "--triplet",
        "-t",
        action="append",
        default=[],
        metavar="ID",
        help="Triplet id (shared motion prefix). Default: keep one already selected, else first triplet.",
    )
    parser.add_argument(
        "--no-compute",
        action="store_true",
        help="Skip RunCompute (open, triplet selection, save, close only)",
    )
    parser.add_argument(
        "--no-layer-log",
        action="store_true",
        help="Skip logging tri FEM soil/bedrock PWaveVelocity and DminVolumetric on the top layer",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        paths = run_tri_directional_fem_workflow(
            args.project,
            port=args.port,
            triplet_ids=args.triplet,
            run_compute=not args.no_compute,
            log_layer_properties=not args.no_layer_log,
        )
    except Exception as ex:
        print(f"Workflow failed: {ex}", file=sys.stderr)
        return 1

    if paths:
        print("Compute finished. Result databases:")
        for path in paths:
            print(f"  {path}")
    else:
        print("Workflow finished (compute skipped).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
