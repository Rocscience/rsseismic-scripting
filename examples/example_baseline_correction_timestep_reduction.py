"""
Apply baseline correction and timestep reduction to one Motion Manager library motion.

Requires a running RSSeismic scripting server. No project file is needed.
Motion names are the .txt file names (without extension) in the Motion Manager
folders from RSSeismic Preferences.

  python examples/example_baseline_correction_timestep_reduction.py --motion ChiChi
  python examples/example_baseline_correction_timestep_reduction.py --port 60058 --motion ChiChi --output-dir "D:\\out"
"""

from __future__ import annotations

import argparse
import os
import sys

from rsseismic import RSSeismicApplication
from rsseismic._client import DEFAULT_SCRIPTING_PORT


def _print_properties(title: str, properties) -> None:
    print(title)
    print(f"  Time step          {properties.timeStep} {properties.timeStepUnit}")
    print(f"  Nyquist frequency  {properties.nyquistFrequency} {properties.frequencyUnit}")
    print(f"  Number of points   {properties.numPoints}")
    print(f"  PGA                {properties.pga} {properties.accelerationUnit}")


def run_correction_example(
    motion_name: str,
    port: int = DEFAULT_SCRIPTING_PORT,
    output_dir: str = "",
) -> None:
    if not motion_name.strip():
        raise ValueError("A motion name is required (file name without .txt).")

    app = RSSeismicApplication(port=port)
    try:
        app.ping()
        motion = app.MotionLibrary.getMotion(motion_name.strip())
        original = motion.getProperties()
        print(f"Using motion: {motion.name}")
        _print_properties("Original properties", original)

        if not output_dir:
            output_dir = os.path.join(os.getcwd(), "corrected_motions_example")
        output_dir = os.path.abspath(output_dir)
        os.makedirs(output_dir, exist_ok=True)

        corrected_path = os.path.join(output_dir, f"{motion.name}_baseline.txt")
        reduced_path = os.path.join(output_dir, f"{motion.name}_dt2.txt")

        correction = motion.baselineCorrection(corrected_path, overwrite=True)
        print(f"\nSaved baseline-corrected file: {correction.filePath}")
        print(f"Offset: {correction.offsetSeconds} s ({correction.offsetPoints} data points)")
        _print_properties("Properties after baseline correction", correction.properties)

        reduction = motion.timestepReduction(2, reduced_path, overwrite=True)
        print(f"\nSaved timestep-reduced file: {reduction.filePath}")
        print(f"Reduction factor: {reduction.reductionFactor}")
        _print_properties("Properties after timestep reduction", reduction.properties)

        after = motion.getProperties()
        if after.timeStep != original.timeStep or after.numPoints != original.numPoints:
            raise RuntimeError(
                "Correction should write a new file only; the original library motion changed unexpectedly."
            )

        if not os.path.isfile(correction.filePath) or not os.path.isfile(reduction.filePath):
            raise RuntimeError("Expected corrected motion files were not written.")

        print("\nOriginal library motion is unchanged.")
        print("Corrected files are on disk only; they are not in the motion library.")
    finally:
        app.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Apply baseline correction and timestep reduction to one library motion."
    )
    parser.add_argument(
        "--motion",
        "-m",
        required=True,
        help="Motion name (file name without .txt) from Motion Manager folders.",
    )
    parser.add_argument(
        "--port",
        "-p",
        type=int,
        default=int(os.environ.get("RSSEISMIC_SCRIPTING_PORT", DEFAULT_SCRIPTING_PORT)),
        help=f"gRPC port (default: {DEFAULT_SCRIPTING_PORT}, or RSSEISMIC_SCRIPTING_PORT)",
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        default="",
        help="Folder for output files. Default: ./corrected_motions_example",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        run_correction_example(args.motion, port=args.port, output_dir=args.output_dir)
    except Exception as ex:
        print(f"Example failed: {ex}", file=sys.stderr)
        return 1
    print("Baseline correction / timestep reduction example finished.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
