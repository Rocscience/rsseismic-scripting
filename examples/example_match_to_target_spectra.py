"""
Match ground motions to a target spectrum (Motion Manager wizard scripting).

Mirrors Preferences → Motions → "Match ground motions to target spectra".

Two modes (same as the wizard):

  Manual
    1. Discover H1/H2 pairs in a folder
    2. Select which pairs to use
    3. Load or build target spectra
    4. Amplitude-scale selected pairs into a Motion Manager folder

  Automatic  (GMDB or ESM only — not CESMD)
    1. Authenticate to the database
    2. Provide search filters + optional selection knobs
    3. Load or build target spectra
    4. Record selection + scaling into a Motion Manager folder

``outputDirectory`` must already be listed in RSSeismic Preferences → Motions.

Examples:

  # Manual — user-defined spectrum file + all pairs in a folder
  python examples/example_match_to_target_spectra.py manual ^
    --output-dir "D:\\Motions\\Library" ^
    --pairs-folder "D:\\RawPairs" ^
    --target-file "D:\\spectra\\design_sa.txt"

  # Manual — only specific pair ids
  python examples/example_match_to_target_spectra.py manual ^
    --output-dir "D:\\Motions\\Library" ^
    --pairs-folder "D:\\RawPairs" ^
    --target-file "D:\\spectra\\design_sa.txt" ^
    --pair-ids EventA EventB

  # Automatic — GMDB selection against a spectrum file
  python examples/example_match_to_target_spectra.py automatic ^
    --output-dir "D:\\Motions\\Library" ^
    --target-file "D:\\spectra\\design_sa.txt" ^
    --database GMDB --username USER --password PASS ^
    --magnitude-min 6 --magnitude-max 8 --n-gm 11
"""

from __future__ import annotations

import argparse
import os
import sys

from rsseismic import (
    AmplitudeScalingParams,
    DatabaseSearchFilters,
    DoubleRange,
    GroundMotionDatabase,
    RecordSelectionParams,
    RSSeismicApplication,
    UserDefinedTargetSpectraModel,
)
from rsseismic._client import DEFAULT_SCRIPTING_PORT

_DATABASE_CHOICES = {
    "GMDB": GroundMotionDatabase.GMDB,
    "ESM": GroundMotionDatabase.ESM,
}


def _parse_database(name: str) -> GroundMotionDatabase:
    key = name.strip().upper()
    if key not in _DATABASE_CHOICES:
        raise ValueError(f"Unknown database '{name}'. Use GMDB or ESM (Automatic does not support CESMD).")
    return _DATABASE_CHOICES[key]


def _print_match_result(label: str, result) -> None:
    print(f"\n{label}")
    print(f"  Saved motions ({len(result.savedMotionNames)}):")
    for name in result.savedMotionNames:
        print(f"    {name}")
    if result.failedPairIds:
        print(f"  Failed pair ids: {result.failedPairIds}")
    if result.scaleFactors:
        print("  Scale factors:")
        for item in result.scaleFactors:
            print(f"    {item.pairId}: {item.scaleFactor:.4f}")


def run_manual(
    output_dir: str,
    pairs_folder: str,
    target_file: str,
    port: int,
    pair_ids: list[str] | None,
    overwrite: bool,
    t1: float,
    t2: float,
) -> None:
    output_dir = os.path.abspath(output_dir)
    pairs_folder = os.path.abspath(pairs_folder)
    target_file = os.path.abspath(target_file)

    if not os.path.isdir(output_dir):
        raise ValueError(f"output-dir is not a folder: {output_dir}")
    if not os.path.isdir(pairs_folder):
        raise ValueError(f"pairs-folder is not a folder: {pairs_folder}")
    if not os.path.isfile(target_file):
        raise ValueError(f"target-file not found: {target_file}")

    app = RSSeismicApplication(port=port)
    try:
        app.ping()
        library = app.MotionLibrary

        # Step 1 — discover pairs (same idea as the wizard Manual pick list)
        print(f"1) Discovering motion pairs under {pairs_folder}...")
        discovered = library.discoverMotionPairsInFolder(pairs_folder)
        print(f"   Found {len(discovered.allPairs)} pair(s).")
        for pair in discovered.allPairs:
            print(f"     {pair.pairId}: {pair.motionH1Name} / {pair.motionH2Name}")
        if not discovered.allPairs:
            print("   Nothing to scale.")
            return

        # Step 2 — select pairs (selection starts empty)
        if pair_ids:
            print(f"2) Selecting pair id(s): {', '.join(pair_ids)}")
            discovered.select(pair_ids)
        else:
            print("2) Selecting all discovered pairs...")
            discovered.selectAll()
        print(f"   Selected {len(discovered.selectedPairs)} pair(s).")

        # Step 3 — target spectra (user-defined file; REXEL/NSHMP also work via getTargetSpectra)
        print(f"3) Loading target spectra from {target_file}...")
        target = library.getTargetSpectra(UserDefinedTargetSpectraModel(filePath=target_file))
        print(f"   {len(target.points)} period–Sa point(s).")

        # Step 4 — amplitude match into a preference folder
        print(f"4) Matching selected pairs into {output_dir}...")
        result = library.matchToTargetSpectraManual(
            targetSpectra=target,
            pairs=discovered.selectedPairs,
            outputDirectory=output_dir,
            amplitude=AmplitudeScalingParams(t1=t1, t2=t2),
            overwrite=overwrite,
        )
        _print_match_result("Manual match result", result)
    finally:
        app.close()


def run_automatic(
    output_dir: str,
    target_file: str,
    database: GroundMotionDatabase,
    username: str,
    password: str,
    port: int,
    overwrite: bool,
    magnitude_min: float,
    magnitude_max: float,
    n_gm: int,
    t1: float,
    t2: float,
) -> None:
    output_dir = os.path.abspath(output_dir)
    target_file = os.path.abspath(target_file)

    if not os.path.isdir(output_dir):
        raise ValueError(f"output-dir is not a folder: {output_dir}")
    if not os.path.isfile(target_file):
        raise ValueError(f"target-file not found: {target_file}")
    if not password.strip():
        raise ValueError("--password is required for GMDB and ESM.")

    db_label = "ESM" if database == GroundMotionDatabase.ESM else database.name
    app = RSSeismicApplication(port=port)
    try:
        app.ping()
        library = app.MotionLibrary

        # Step 1 — authenticate (required before Automatic / search / import)
        print(f"1) Authenticating with {db_label}...")
        library.authenticateDatabase(
            database=database,
            username=username,
            password=password,
        )

        # Step 2 — target spectra
        print(f"2) Loading target spectra from {target_file}...")
        target = library.getTargetSpectra(UserDefinedTargetSpectraModel(filePath=target_file))
        print(f"   {len(target.points)} period–Sa point(s).")

        # Step 3 — filters + selection knobs (wizard Automatic panel)
        filters = DatabaseSearchFilters(
            magnitude=DoubleRange(min=magnitude_min, max=magnitude_max),
        )
        selection = RecordSelectionParams(nGm=n_gm)
        print(
            f"3) Running Automatic selection on {db_label} "
            f"(magnitude {magnitude_min}–{magnitude_max}, nGm={n_gm})..."
        )

        # Step 4 — select + scale into preference folder
        result = library.matchToTargetSpectraAutomatic(
            database=database,
            filters=filters,
            targetSpectra=target,
            outputDirectory=output_dir,
            selection=selection,
            amplitude=AmplitudeScalingParams(t1=t1, t2=t2),
            overwrite=overwrite,
        )
        _print_match_result("Automatic match result", result)
    finally:
        app.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Match ground motions to target spectra (Manual or Automatic).",
    )
    parser.add_argument(
        "mode",
        choices=("manual", "automatic"),
        help="Wizard path: manual (folder pairs) or automatic (GMDB/ESM selection).",
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        required=True,
        help="Motion Manager preference folder (Preferences → Motions).",
    )
    parser.add_argument(
        "--target-file",
        "-t",
        required=True,
        help="User-defined target spectrum text file (period and Sa columns).",
    )
    parser.add_argument(
        "--pairs-folder",
        help="Folder of H1/H2 motion files (Manual mode; scanned with subfolders).",
    )
    parser.add_argument(
        "--pair-ids",
        nargs="+",
        default=[],
        help="Optional Manual pair ids to select (default: select all discovered pairs).",
    )
    parser.add_argument(
        "--database",
        "-d",
        default="GMDB",
        choices=sorted(_DATABASE_CHOICES.keys()),
        help="Automatic mode database (GMDB or ESM; default: GMDB).",
    )
    parser.add_argument(
        "--username",
        "-u",
        default="",
        help="Database username (Automatic mode).",
    )
    parser.add_argument(
        "--password",
        "-w",
        default="",
        help="Database password (Automatic mode).",
    )
    parser.add_argument(
        "--magnitude-min",
        type=float,
        default=6.0,
        help="Automatic search: minimum magnitude (default: 6.0).",
    )
    parser.add_argument(
        "--magnitude-max",
        type=float,
        default=8.0,
        help="Automatic search: maximum magnitude (default: 8.0).",
    )
    parser.add_argument(
        "--n-gm",
        type=int,
        default=11,
        help="Automatic: number of ground motions to select (default: 11).",
    )
    parser.add_argument(
        "--t1",
        type=float,
        default=0.01,
        help="Amplitude scaling period window start, seconds (default: 0.01).",
    )
    parser.add_argument(
        "--t2",
        type=float,
        default=10.0,
        help="Amplitude scaling period window end, seconds (default: 10).",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing library motions with the same name.",
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
        if args.mode == "manual":
            if not args.pairs_folder:
                raise ValueError("Manual mode requires --pairs-folder.")
            run_manual(
                output_dir=args.output_dir,
                pairs_folder=args.pairs_folder,
                target_file=args.target_file,
                port=args.port,
                pair_ids=args.pair_ids or None,
                overwrite=args.overwrite,
                t1=args.t1,
                t2=args.t2,
            )
        else:
            if not args.username.strip():
                raise ValueError("Automatic mode requires --username.")
            run_automatic(
                output_dir=args.output_dir,
                target_file=args.target_file,
                database=_parse_database(args.database),
                username=args.username,
                password=args.password,
                port=args.port,
                overwrite=args.overwrite,
                magnitude_min=args.magnitude_min,
                magnitude_max=args.magnitude_max,
                n_gm=args.n_gm,
                t1=args.t1,
                t2=args.t2,
            )
    except Exception as ex:
        print(f"Example failed: {ex}", file=sys.stderr)
        return 1
    print("\nMatch to target spectra example finished.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
