"""
Estimate kappa for one ground motion from the Motion Manager library.

Requires a running RSSeismic scripting server. No project file is needed.
Motion names are the .txt file names (without extension) in the Motion Manager
folders from RSSeismic Preferences.

  python examples/example_estimate_kappa.py --motion ChiChi
  python examples/example_estimate_kappa.py --port 60058 --motion ChiChi
"""

from __future__ import annotations

import argparse
import os
import sys

from rsseismic import RSSeismicApplication
from rsseismic._client import DEFAULT_SCRIPTING_PORT


def _print_kappa(title: str, info) -> None:
    print(title)
    print(f"  Start frequency  {info.startFrequency} Hz")
    print(f"  End frequency    {info.endFrequency} Hz")
    print(f"  Kappa            {info.kappa}")
    print(f"  Y-intercept      {info.yIntercept}")
    print(f"  Start amplitude  {info.startAmplitude}")
    print(f"  End amplitude    {info.endAmplitude}")


def run_estimate_kappa_example(motion_name: str, port: int = DEFAULT_SCRIPTING_PORT) -> None:
    if not motion_name.strip():
        raise ValueError("A motion name is required (file name without .txt).")

    app = RSSeismicApplication(port=port)
    try:
        app.ping()
        motion = app.MotionLibrary.getMotion(motion_name.strip())
        print(f"Using motion: {motion.name}")

        from_bounds = motion.estimateKappaFromBoundingFrequencies(
            startFrequency=1.0,
            endFrequency=20.0,
        )
        _print_kappa("Bounding frequencies (1–20 Hz)", from_bounds)

        from_constant = motion.estimateKappaFromConstantIntercept(
            kappa=from_bounds.kappa,
            yIntercept=from_bounds.yIntercept,
        )
        _print_kappa("Constant kappa and intercept (freqs default to 0 and 100 Hz)", from_constant)
    finally:
        app.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Estimate kappa for one Motion Manager library motion."
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
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        run_estimate_kappa_example(args.motion, port=args.port)
    except Exception as ex:
        print(f"Example failed: {ex}", file=sys.stderr)
        return 1
    print("Estimate Kappa example finished.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
