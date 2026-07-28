"""
Single-profile RSSeismic scripting workflow using the installed rsseismic package.

  python examples/example_single_profile_workflow.py "E:\\path\\to\\project.rsseismicfile"
  python examples/example_single_profile_workflow.py --port 60058 --motion EQ1 project.rsseismicfile
  python examples/example_single_profile_workflow.py --no-compute project.rsseismicfile
"""

from __future__ import annotations

import argparse
import os
import sys

from rsseismic import RSSeismicApplication, logger
from rsseismic._client import DEFAULT_SCRIPTING_PORT


def _select_motion_names(model, requested_names: list[str]) -> list[str]:
    model.Motions.refreshMotionsList()
    motions = model.Motions.listMotions()
    if not motions:
        raise RuntimeError(
            "No motions available. Configure motion directories in RSSeismic Preferences "
            "or ensure the project has motions."
        )

    if requested_names:
        return requested_names

    selected = [motion.name for motion in motions if motion.isSelected]
    if selected:
        return selected

    return [motions[0].name]


def run_single_profile_workflow(
    project_path: str,
    port: int = DEFAULT_SCRIPTING_PORT,
    motion_names: list[str] | None = None,
    run_compute: bool = True,
) -> str | None:
    """
    Open a project, configure motion selection, save, optionally compute, return db3 path.

    Returns resultDatabasePath when compute runs successfully, otherwise None.
    """
    project_path = os.path.abspath(project_path.strip())
    if not os.path.isfile(project_path):
        raise FileNotFoundError(f"Project file not found: {project_path}")

    app = RSSeismicApplication(port=port)
    model = None
    db3_path: str | None = None

    try:
        app.ping()
        model = app.openFile(project_path)

        profile_name = model.Profiles.getActiveProfile().profileName
        names_to_select = _select_motion_names(model, motion_names or [])
        model.Motions.setMotionSelection(names_to_select, selectOnlyListed=True)
        model.save()

        if not run_compute:
            return None

        result = model.runCompute()
        if not result.success:
            raise RuntimeError(result.errorMessage or "RunCompute failed.")
        if result.partialSuccess:
            logger.warning("Some profile/motion pairs failed:\n%s", result.errorMessage)

        motion_name = names_to_select[0]
        entry = model.Results.getResultDatabasePath(profile_name, motion_name)
        db3_path = entry.resultDatabasePath
        deconv = model.Profiles.getBedrockLayerProxy(profile_name).Data.getBoolValue("Deconvolution")
        if not db3_path and not deconv:
            raise RuntimeError("Compute succeeded but resultDatabasePath is empty.")
        return db3_path
    finally:
        if model is not None:
            model.close(saveProject=False)
        app.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a single-profile open → motion → save → compute → db3 workflow."
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
        "--motion",
        "-m",
        action="append",
        default=[],
        metavar="NAME",
        help="Motion name to select for compute (repeatable). Default: already-selected, else first motion.",
    )
    parser.add_argument(
        "--no-compute",
        action="store_true",
        help="Skip RunCompute (open, motion selection, save, close only)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        db3_path = run_single_profile_workflow(
            args.project,
            port=args.port,
            motion_names=args.motion,
            run_compute=not args.no_compute,
        )
    except Exception as ex:
        print(f"Workflow failed: {ex}", file=sys.stderr)
        return 1

    if db3_path:
        print(f"Compute finished. Result database: {db3_path}")
    else:
        print("Workflow finished (compute skipped).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
