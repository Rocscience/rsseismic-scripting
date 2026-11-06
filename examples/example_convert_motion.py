"""
Convert text or PEER AT2 motion files into the Motion Manager library.

Requires a running RSSeismic scripting server. No project file is needed.
``outputDirectory`` must be one of the Motion Manager preference folders
(RSSeismic Preferences → Motions).

Unlike scale/baseline/timestep RPCs, convert adds the motion to the library
(and updates Motion Manager if it is open).

  python examples/example_convert_motion.py --output-dir "D:\\Motions" --text-file "D:\\in\\raw.txt" --name Kobe
  python examples/example_convert_motion.py --output-dir "D:\\Motions" --at2-file "D:\\in\\record.AT2" --name ChiChi
  python examples/example_convert_motion.py --output-dir "D:\\Motions" --delete Kobe OldMotion
"""

from __future__ import annotations

import argparse
import os
import sys

from rsseismic import (
    RSSeismicApplication,
    MotionAccelerationUnit,
    MotionConvertDelimiter,
    MotionConvertLayout,
)
from rsseismic._client import DEFAULT_SCRIPTING_PORT


def _print_convert_result(label: str, result) -> None:
    props = result.properties
    print(f"\n{label}")
    print(f"  Motion name   {result.motionName}")
    print(f"  Output file   {result.filePath}")
    print(f"  Time step     {props.timeStep} {props.timeStepUnit}")
    print(f"  PGA           {props.pga} {props.accelerationUnit}")
    print(f"  Num points    {props.numPoints}")


def run_convert_example(
    output_dir: str,
    port: int = DEFAULT_SCRIPTING_PORT,
    text_file: str = "",
    at2_file: str = "",
    motion_name: str = "",
    time_step: float = 0.02,
    overwrite: bool = False,
    delete_names: list[str] | None = None,
) -> None:
    output_dir = os.path.abspath(output_dir)
    if not os.path.isdir(output_dir):
        raise ValueError(f"output-dir is not a folder: {output_dir}")

    app = RSSeismicApplication(port=port)
    try:
        app.ping()
        library = app.MotionLibrary

        if delete_names:
            deleted = library.deleteMotions(delete_names)
            print(f"Deleted: {deleted.deletedMotionNames}")
            if deleted.failedMotionNames:
                print(f"Failed:  {deleted.failedMotionNames}")

        if text_file:
            if not motion_name.strip():
                raise ValueError("--name is required with --text-file")
            result = library.convertMotionText(
                sourceFilePath=os.path.abspath(text_file),
                motionName=motion_name.strip(),
                outputDirectory=output_dir,
                accelerationUnit=MotionAccelerationUnit.G,
                layout=MotionConvertLayout.ACCELERATION_ONLY,
                delimiter=MotionConvertDelimiter.SPACE,
                timeStep=time_step,
                hasTimeStep=True,
                accelerationColumn=2,
                timeColumn=1,
                firstLine=1,
                lastLine=0,
                overwrite=overwrite,
            )
            _print_convert_result("Text convert result", result)

        if at2_file:
            at2_name = motion_name.strip() or os.path.splitext(os.path.basename(at2_file))[0]
            result = library.convertMotionAT2(
                sourceFilePath=os.path.abspath(at2_file),
                motionName=at2_name,
                outputDirectory=output_dir,
                overwrite=overwrite,
                # accelerationUnit=None → auto-detect from AT2 header
            )
            _print_convert_result("AT2 convert result", result)

        if not delete_names and not text_file and not at2_file:
            raise ValueError("Provide --text-file, --at2-file, and/or --delete")
    finally:
        app.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert or delete Motion Manager library motions."
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        required=True,
        help="Motion Manager preference folder.",
    )
    parser.add_argument("--text-file", help="Plain-text motion file to convert.")
    parser.add_argument("--at2-file", help="PEER AT2 file to convert.")
    parser.add_argument(
        "--name",
        "-n",
        default="",
        help="Output motion name (without .txt). Required for --text-file.",
    )
    parser.add_argument(
        "--time-step",
        type=float,
        default=0.02,
        help="Timestep for acceleration-only text files.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing library motion.",
    )
    parser.add_argument(
        "--delete",
        nargs="+",
        default=[],
        help="Motion names to delete from the library.",
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
        run_convert_example(
            output_dir=args.output_dir,
            port=args.port,
            text_file=args.text_file or "",
            at2_file=args.at2_file or "",
            motion_name=args.name,
            time_step=args.time_step,
            overwrite=args.overwrite,
            delete_names=args.delete or None,
        )
    except Exception as ex:
        print(f"Example failed: {ex}", file=sys.stderr)
        return 1
    print("\nConvert motion example finished.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
