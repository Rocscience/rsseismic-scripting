"""
Inspect one ground motion (Single Motion View) and write scaled copies to disk.

Requires a running RSSeismic scripting server. No project file is needed.
Motion names are the .txt file names (without extension) in the Motion Manager
folders from RSSeismic Preferences.

  python examples/example_single_motion_view.py --motion ChiChi
  python examples/example_single_motion_view.py --port 60058 --motion ChiChi --output-dir "D:\\out"

Scaling writes a new .txt file. It does not add that file to the motion library.
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
    print(f"  PGA                {properties.pga} {properties.accelerationUnit}")
    print(f"  PGV                {properties.pgv} {properties.velocityUnit}")
    print(f"  PGD                {properties.pgd} {properties.displacementUnit}")
    print(f"  Number of points   {properties.numPoints}")


def run_single_motion_view_example(
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
        if original.numPoints <= 0:
            raise RuntimeError(
                f"Motion '{motion.name}' has no time-history points. "
                "Check that this name exists in the Motion Manager folders."
            )

        time_history = motion.getTimeHistoryData()
        print("Time-history columns:", list(time_history.columns))
        print(time_history.head())

        fourier, spectral_acceleration = motion.getSpectralData()
        print("Fourier columns:", list(fourier.columns))
        print("Spectral acceleration columns:", list(spectral_acceleration.columns))

        if not output_dir:
            output_dir = os.path.join(os.getcwd(), "scaled_motions_example")
        output_dir = os.path.abspath(output_dir)
        os.makedirs(output_dir, exist_ok=True)

        scaled_to_g_path = os.path.join(output_dir, f"{motion.name}_to_0p30g.txt")
        scaled_by_path = os.path.join(output_dir, f"{motion.name}_x1p20.txt")

        to_g = motion.scaleToG(0.30, scaled_to_g_path, overwrite=True)
        print(f"\nSaved scale-to-g file: {to_g.filePath}")
        print(f"Applied scale factor: {to_g.appliedScaleFactor}")
        _print_properties("Properties after scale to 0.30 g", to_g.properties)

        by_factor = motion.scaleBy(1.20, scaled_by_path, overwrite=True)
        print(f"\nSaved scale-by file: {by_factor.filePath}")
        print(f"Applied scale factor: {by_factor.appliedScaleFactor}")
        _print_properties("Properties after scale by 1.20", by_factor.properties)

        after_scale = motion.getProperties()
        if after_scale.pga != original.pga:
            raise RuntimeError(
                "Scaling should write a new file only; the original library "
                "motion PGA changed unexpectedly."
            )

        if not os.path.isfile(to_g.filePath) or not os.path.isfile(by_factor.filePath):
            raise RuntimeError("Expected scaled motion files were not written.")

        print("\nOriginal library motion is unchanged.")
        print("Scaled files are on disk only; they are not in the motion library.")
    finally:
        app.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Print Single Motion View properties and tables, then save scaled copies."
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
        help="Folder for scaled files. Default: ./scaled_motions_example",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        run_single_motion_view_example(args.motion, port=args.port, output_dir=args.output_dir)
    except Exception as ex:
        print(f"Example failed: {ex}", file=sys.stderr)
        return 1
    print("Single Motion View example finished.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
