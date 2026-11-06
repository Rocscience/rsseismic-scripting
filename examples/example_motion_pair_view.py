"""
Inspect one H1/H2 motion pair (Motion Pair View) and write scaled copies to disk.

Requires a running RSSeismic scripting server. No project file is needed.
``pairId`` is the shared name prefix of the horizontal components in Motion Manager
folders (for example ``Event`` for ``Event_EW.txt`` + ``Event_NS.txt``).

  python examples/example_motion_pair_view.py --pair Event
  python examples/example_motion_pair_view.py --port 60058 --pair Event --output-dir "D:\\out"

Scaling writes two .txt files. It does not add them to the motion library.
"""

from __future__ import annotations

import argparse
import os
import sys

from rsseismic import (
    EAS_BANDWIDTH_PEER_2018,
    GeometricMeanSpectralType,
    RSSeismicApplication,
)
from rsseismic._client import DEFAULT_SCRIPTING_PORT


def _print_properties(title: str, properties) -> None:
    print(title)
    print(f"  Time step          {properties.timeStep} {properties.timeStepUnit}")
    print(f"  Nyquist frequency  {properties.nyquistFrequency} {properties.frequencyUnit}")
    print(f"  PGA                {properties.pga} {properties.accelerationUnit}")
    print(f"  PGV                {properties.pgv} {properties.velocityUnit}")
    print(f"  PGD                {properties.pgd} {properties.displacementUnit}")
    print(f"  Number of points   {properties.numPoints}")


def run_motion_pair_view_example(
    pair_id: str,
    port: int = DEFAULT_SCRIPTING_PORT,
    output_dir: str = "",
) -> None:
    if not pair_id.strip():
        raise ValueError("A pair id is required (shared H1/H2 name prefix).")

    app = RSSeismicApplication(port=port)
    try:
        app.ping()
        pair = app.MotionLibrary.getMotionPair(pair_id.strip())

        props = pair.getProperties()
        print(f"Using pair: {props.pairId} ({props.motionH1Name}, {props.motionH2Name})")
        _print_properties("H1 properties", props.h1)
        _print_properties("H2 properties", props.h2)

        geo = pair.getGeometricMeanSpectrum(GeometricMeanSpectralType.FREQUENCY_DOMAIN)
        print("Geometric-mean columns:", list(geo.columns))
        print(geo.head())

        eas = pair.getEffectiveAmplitudeSpectrum()
        print(f"EAS columns (bandwidth default {EAS_BANDWIDTH_PEER_2018}):", list(eas.columns))
        print(eas.head())

        if not output_dir:
            output_dir = os.path.join(os.getcwd(), "scaled_motion_pairs_example")
        output_dir = os.path.abspath(output_dir)
        os.makedirs(output_dir, exist_ok=True)

        h1_path = os.path.join(output_dir, f"{props.motionH1Name}_to_0p30g.txt")
        h2_path = os.path.join(output_dir, f"{props.motionH2Name}_to_0p30g.txt")
        scaled = pair.scaleToG(0.30, h1_path, h2_path, overwrite=True)
        print(f"\nSaved H1: {scaled.h1FilePath} (factor {scaled.h1AppliedScaleFactor})")
        print(f"Saved H2: {scaled.h2FilePath} (factor {scaled.h2AppliedScaleFactor})")

        if not os.path.isfile(scaled.h1FilePath) or not os.path.isfile(scaled.h2FilePath):
            raise RuntimeError("Expected scaled motion pair files were not written.")

        print("\nOriginal library motions are unchanged.")
        print("Scaled files are on disk only; they are not in the motion library.")
    finally:
        app.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Print Motion Pair View properties and spectra, then save scaled copies."
    )
    parser.add_argument(
        "--pair",
        "-p",
        required=True,
        help="Pair id (shared H1/H2 file-name prefix) from Motion Manager folders.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_SCRIPTING_PORT,
        help=f"Scripting server port (default {DEFAULT_SCRIPTING_PORT}).",
    )
    parser.add_argument(
        "--output-dir",
        default="",
        help="Directory for scaled H1/H2 files (default: ./scaled_motion_pairs_example).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        run_motion_pair_view_example(args.pair, port=args.port, output_dir=args.output_dir)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
