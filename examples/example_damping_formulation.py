"""
Damping Formulation scripting: read settings, optional recommended frequencies, preview tables.

Requires a running RSSeismic scripting server and a time-domain project file.

  python examples/example_damping_formulation.py path\\to\\project.rsseismicfile
  python examples/example_damping_formulation.py --motion EQ1 --apply-recommended project.rsseismicfile
  python examples/example_damping_formulation.py --no-preview project.rsseismicfile
"""

from __future__ import annotations

import argparse
import os
import sys

from rsseismic import RSSeismicApplication
from rsseismic._client import DEFAULT_SCRIPTING_PORT
from rsseismic.exceptions import ScriptingError
from rsseismic.types import DampingMatrixType, RayleighDampingType


def _select_motion_name(model, requested: str) -> str:
    if requested.strip():
        return requested.strip()
    model.Motions.refreshMotionsList()
    motions = model.Motions.listMotions()
    if not motions:
        raise RuntimeError(
            "No motions in the project. Add motions in RSSeismic or pass --motion."
        )
    selected = [motion.name for motion in motions if motion.isSelected]
    return selected[0] if selected else motions[0].name


def run_damping_formulation_example(
    project_path: str,
    *,
    port: int = DEFAULT_SCRIPTING_PORT,
    motion_name: str = "",
    apply_recommended: bool = False,
    run_preview: bool = True,
) -> None:
    project_path = os.path.abspath(project_path.strip())
    if not os.path.isfile(project_path):
        raise FileNotFoundError(f"Project not found: {project_path}")

    app = RSSeismicApplication(port=port)
    model = None
    try:
        app.ping()
        model = app.openFile(project_path)
        damping = model.DampingFormulation

        settings = damping.getSettings()
        print("Current damping options:")
        print(f"  Matrix type     {settings.dampingMatrixType.name}")
        print(f"  Rayleigh type   {settings.rayleighDampingType.name}")
        print(
            f"  Frequencies Hz  {settings.modeFreq1}, {settings.modeFreq2}, "
            f"{settings.modeFreq3}, {settings.modeFreq4}"
        )

        if apply_recommended:
            if settings.dampingMatrixType is not DampingMatrixType.RAYLEIGH:
                damping.setRayleigh(useFrequencies=True)
            elif settings.rayleighDampingType is not RayleighDampingType.FREQUENCIES:
                damping.setRayleigh(useFrequencies=True)
            settings = damping.applyRecommendedFrequencies()
            print("Applied recommended Rayleigh frequencies:")
            print(f"  f1 = {settings.modeFreq1} Hz, f2 = {settings.modeFreq2} Hz")
            model.save()

        if not run_preview:
            return

        if settings.dampingMatrixType is DampingMatrixType.RAYLEIGH:
            curve = damping.getDampingCurveDataFrame()
            print(f"Damping curve table: {len(curve)} rows, columns {list(curve.columns)}")

        motion = _select_motion_name(model, motion_name)
        print(f"Preview motion: {motion}")

        ftf, sa = damping.getFrequencyDomainSolutionDataFrames(motion)
        print(
            f"Frequency-domain preview: FTF {len(ftf)} rows, "
            f"spectral acceleration {len(sa)} rows"
        )

        time_ftf, time_sa = damping.getTimeDomainSolutionDataFrames(motion)
        print(
            f"Time-domain preview: FTF {len(time_ftf)} rows, "
            f"spectral acceleration {len(time_sa)} rows"
        )
    except ScriptingError as ex:
        raise RuntimeError(str(ex)) from ex
    finally:
        if model is not None:
            model.close(saveProject=False)
        app.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Damping Formulation settings and preview tables for a project."
    )
    parser.add_argument(
        "project",
        help="Path to a .rsseismicfile (time-domain project).",
    )
    parser.add_argument(
        "--motion",
        "-m",
        default="",
        help="Motion name for preview plots (file name without extension).",
    )
    parser.add_argument(
        "--apply-recommended",
        action="store_true",
        help="Apply recommended Rayleigh frequencies from the active profile, then save.",
    )
    parser.add_argument(
        "--no-preview",
        action="store_true",
        help="Only read (and optionally apply recommended) settings; skip preview tables.",
    )
    parser.add_argument(
        "--port",
        "-p",
        type=int,
        default=int(os.environ.get("RSSEISMIC_SCRIPTING_PORT", DEFAULT_SCRIPTING_PORT)),
        help=f"gRPC port (default: {DEFAULT_SCRIPTING_PORT}, or RSSEISMIC_SCRIPTING_PORT)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        run_damping_formulation_example(
            args.project,
            port=args.port,
            motion_name=args.motion,
            apply_recommended=args.apply_recommended,
            run_preview=not args.no_preview,
        )
    except (FileNotFoundError, RuntimeError, ValueError) as ex:
        print(ex, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
