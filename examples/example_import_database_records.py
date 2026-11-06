"""
Search GMDB / CESMD / ESM and import selected records into the Motion Manager library.

Requires a running RSSeismic scripting server. No project file is needed.
``outputDirectory`` must be one of the Motion Manager preference folders
(RSSeismic Preferences → Motions).

Authenticate once per database for the scripting session, then search/import
without credentials on those calls.

  python examples/example_import_database_records.py --output-dir "D:\\Motions" --database GMDB --username USER --password PASS
  python examples/example_import_database_records.py --output-dir "D:\\Motions" --database CESMD --username email@example.com --max-results 20 --max-records 3
  python examples/example_import_database_records.py --output-dir "D:\\Motions" --database ESM --username email@example.com --password PASS --network-code IV --overwrite
"""

from __future__ import annotations

import argparse
import os
import sys

from rsseismic import (
    DatabaseSearchFilters,
    DoubleRange,
    GroundMotionDatabase,
    ProcessingType,
    RSSeismicApplication,
)
from rsseismic._client import DEFAULT_SCRIPTING_PORT

_DATABASE_CHOICES = {
    "GMDB": GroundMotionDatabase.GMDB,
    "CESMD": GroundMotionDatabase.CESMD,
    "ESM": GroundMotionDatabase.ESM,
}


def _parse_database(name: str) -> GroundMotionDatabase:
    key = name.strip().upper()
    if key not in _DATABASE_CHOICES:
        raise ValueError(f"Unknown database '{name}'. Use GMDB, CESMD, or ESM.")
    return _DATABASE_CHOICES[key]


def run_import_example(
    output_dir: str,
    database: GroundMotionDatabase,
    username: str,
    password: str,
    port: int = DEFAULT_SCRIPTING_PORT,
    max_results: int | None = None,
    max_records: int = 5,
    overwrite: bool = False,
    magnitude_min: float = 6.0,
    magnitude_max: float = 8.0,
    network_code: str = "",
) -> None:
    output_dir = os.path.abspath(output_dir)
    if not os.path.isdir(output_dir):
        raise ValueError(f"output-dir is not a folder: {output_dir}")
    if max_records < 1:
        raise ValueError("--max-records must be at least 1")
    if max_results is not None and max_results < 1:
        raise ValueError("--max-results must be at least 1 when set")
    if database != GroundMotionDatabase.CESMD and not password.strip():
        raise ValueError("--password is required for GMDB and ESM (optional for CESMD).")

    db_label = "ESM" if database == GroundMotionDatabase.ESM else database.name
    app = RSSeismicApplication(port=port)
    try:
        app.ping()
        library = app.MotionLibrary

        print(f"Authenticating with {db_label}...")
        library.authenticateDatabase(
            database=database,
            username=username,
            password=password,
        )

        filters = DatabaseSearchFilters(
            magnitude=DoubleRange(min=magnitude_min, max=magnitude_max),
            networkCode=network_code.strip(),
            # GMDB-only enum example (ignored on CESMD/ESM):
            processingType=(
                ProcessingType.MANUAL if database == GroundMotionDatabase.GMDB else None
            ),
        )
        print(
            f"Searching {db_label} (magnitude {magnitude_min}–{magnitude_max}"
            + (f", network={network_code}" if network_code.strip() else "")
            + ")..."
        )
        records = library.searchDatabaseRecords(
            database=database,
            filters=filters,
            maxResults=max_results,
        )
        print(f"Found {len(records)} record(s).")
        if not records:
            return

        selected = records[:max_records]
        for record in selected:
            print(
                f"  {record.id}  {record.eventName}  station={record.station}  "
                f"M={record.magnitude}  PGA_H1={record.maxAccelH1G} g"
            )

        print(f"\nImporting {len(selected)} record(s) into {output_dir}...")
        result = library.importDatabaseRecords(
            database=database,
            outputDirectory=output_dir,
            records=selected,
            overwrite=overwrite,
        )
        print(f"Imported: {result.importedMotionNames}")
        if result.failedRecordIds:
            print(f"Failed:   {result.failedRecordIds}")
    finally:
        app.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Search GMDB/CESMD/ESM and import records into Motion Manager."
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        required=True,
        help="Motion Manager preference folder.",
    )
    parser.add_argument(
        "--database",
        "-d",
        default="GMDB",
        choices=sorted(_DATABASE_CHOICES.keys()),
        help="External database (default: GMDB).",
    )
    parser.add_argument(
        "--username",
        "-u",
        required=True,
        help="Database username (email for CESMD/ESM).",
    )
    parser.add_argument(
        "--password",
        "-w",
        default="",
        help="Database password (required for GMDB/ESM; optional for CESMD).",
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=None,
        help="Optional server-side cap on search hits (omit = no truncate).",
    )
    parser.add_argument(
        "--max-records",
        type=int,
        default=5,
        help="Maximum number of returned hits to import (default: 5).",
    )
    parser.add_argument(
        "--magnitude-min",
        type=float,
        default=6.0,
        help="Minimum magnitude filter (default: 6.0).",
    )
    parser.add_argument(
        "--magnitude-max",
        type=float,
        default=8.0,
        help="Maximum magnitude filter (default: 8.0).",
    )
    parser.add_argument(
        "--network-code",
        default="",
        help='Optional network code filter (CESMD/ESM multi: "CI,NP").',
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
        run_import_example(
            output_dir=args.output_dir,
            database=_parse_database(args.database),
            username=args.username,
            password=args.password,
            port=args.port,
            max_results=args.max_results,
            max_records=args.max_records,
            overwrite=args.overwrite,
            magnitude_min=args.magnitude_min,
            magnitude_max=args.magnitude_max,
            network_code=args.network_code,
        )
    except Exception as ex:
        print(f"Example failed: {ex}", file=sys.stderr)
        return 1
    print("\nImport database records example finished.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
