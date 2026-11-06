"""
Import RSLog boreholes into a new RSSeismic project (JSON file or account).

Requires a running RSSeismic scripting server. Creates a blank project, lists
projects/boreholes from the chosen source, imports selected holes as profiles,
then saves a ``.rsseismicfile`` you can open in RSSeismic to inspect.

File source (no login; uses the Imperial fixture under tests/resources by default):

  python examples/example_rslog_import.py --source file
  python examples/example_rslog_import.py --source file --json "D:\\path\\export.json" --output "D:\\out\\rslog.rsseismicfile"

Account source (authenticate once, then list/import):

  python examples/example_rslog_import.py --source account --company rocscience --username USER --password PASS
"""

from __future__ import annotations

import argparse
import os
import sys

from rsseismic import (
    MultiProfilePolicy,
    ProfileMergeMode,
    RSLogBoreholeImportSpec,
    RSLogBoreholeInfo,
    RSLogGroundwaterSelection,
    RSLogProjectInfo,
    RSSeismicApplication,
    UnitMismatchPolicy,
)
from rsseismic._client import DEFAULT_SCRIPTING_PORT

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_DEFAULT_JSON = os.path.join(
    _REPO_ROOT,
    "tests",
    "resources",
    "RSLog Example Project #1 (Imperial).json",
)
_DEFAULT_OUTPUT = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "output",
    "rslog_import_example.rsseismicfile",
)


def _has_valid_water_table(borehole: RSLogBoreholeInfo) -> bool:
    depth = borehole.defaultDrillingGroundwaterDepth
    if depth is not None and depth >= 0:
        return True
    return any(p.groundwaterMeasurementCount > 0 for p in borehole.piezometers)


def _water_table_label(borehole: RSLogBoreholeInfo) -> str:
    depth = borehole.defaultDrillingGroundwaterDepth
    if depth is not None and depth >= 0:
        return f"drilling GW depth={depth}"
    piezometers = [p for p in borehole.piezometers if p.groundwaterMeasurementCount > 0]
    if piezometers:
        counts = ", ".join(
            f"{p.number or p.id}:{p.groundwaterMeasurementCount}" for p in piezometers
        )
        return f"piezometer measurements ({counts})"
    return "no water table"


def _find_project_with_water_table_boreholes(
    app: RSSeismicApplication,
    projects: list[RSLogProjectInfo],
    list_kwargs: dict,
    max_boreholes: int,
) -> tuple[RSLogProjectInfo, list[RSLogBoreholeInfo]]:
    best_project: RSLogProjectInfo | None = None
    best_boreholes: list[RSLogBoreholeInfo] = []

    for project in projects:
        if project.totalTestHoles <= 0:
            continue
        boreholes = app.RSLog.listBoreholes(project.id, **list_kwargs)
        with_water = [b for b in boreholes if _has_valid_water_table(b)]
        if len(with_water) >= max_boreholes:
            return project, with_water[:max_boreholes]
        if len(with_water) > len(best_boreholes):
            best_project = project
            best_boreholes = with_water

    if best_project is None or not best_boreholes:
        raise RuntimeError(
            "No RSLog borehole with a valid water table was found "
            "(drilling groundwater depth or piezometer measurements)."
        )
    return best_project, best_boreholes


def run_rslog_import_example(
    source: str,
    output_path: str,
    port: int = DEFAULT_SCRIPTING_PORT,
    json_file: str = "",
    company: str = "",
    username: str = "",
    password: str = "",
    server: str = "",
    max_boreholes: int = 2,
) -> None:
    if max_boreholes < 1:
        raise ValueError("--max-boreholes must be at least 1")

    source_key = source.strip().lower()
    if source_key not in ("file", "account"):
        raise ValueError("--source must be 'file' or 'account'")

    output_path = os.path.abspath(output_path)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    json_file_path: str | None = None
    if source_key == "file":
        json_file_path = os.path.abspath(json_file or _DEFAULT_JSON)
        if not os.path.isfile(json_file_path):
            raise ValueError(f"JSON fixture not found: {json_file_path}")
    else:
        if not company.strip() or not username.strip() or not password.strip():
            raise ValueError(
                "--company, --username, and --password are required for --source account"
            )

    app = RSSeismicApplication(port=port)
    model = None
    try:
        app.ping()

        if source_key == "account":
            print(f"Authenticating with RSLog ({company.strip()} / {username.strip()})...")
            auth = app.RSLog.authenticate(
                company.strip(),
                username.strip(),
                password.strip(),
                server=server.strip(),
            )
            if auth.twoFactorRequired:
                raise RuntimeError(
                    "Two-factor authentication is required for this account. "
                    "Complete 2FA in the RSSeismic UI, or use an account without 2FA."
                )

        print("Creating blank project...")
        model = app.newProject()

        list_kwargs: dict = {}
        if json_file_path is not None:
            list_kwargs["jsonFilePath"] = json_file_path

        print("Listing RSLog projects...")
        projects = app.RSLog.listProjects(**list_kwargs)
        if not projects:
            raise RuntimeError("No RSLog projects returned from the selected source.")

        print("Selecting boreholes with a valid water table...")
        project, selected = _find_project_with_water_table_boreholes(
            app,
            projects,
            list_kwargs,
            max_boreholes,
        )
        if len(selected) < max_boreholes:
            print(
                f"Only {len(selected)} borehole(s) with a water table were found "
                f"(requested {max_boreholes})."
            )

        print(
            f"Using project: {project.name!r} "
            f"(id={project.id}, isMetric={project.isMetric}, "
            f"totalTestHoles={project.totalTestHoles})"
        )
        for borehole in selected:
            print(
                f"  {borehole.name!r}  id={borehole.id}  "
                f"layers={borehole.stratigraphyLayerCount}  samples={borehole.sampleCount}  "
                f"{_water_table_label(borehole)}"
            )

        print(f"Importing {len(selected)} borehole(s) with default water table...")
        result = app.RSLog.importBoreholes(
            model,
            project.id,
            [
                RSLogBoreholeImportSpec(
                    boreholeId=b.id,
                    groundwater=RSLogGroundwaterSelection(useDefault=True),
                )
                for b in selected
            ],
            jsonFilePath=json_file_path,
            unitMismatchPolicy=UnitMismatchPolicy.KEEP_PROJECT,
            multiProfilePolicy=MultiProfilePolicy.ENABLE_IF_NEEDED,
            profileMergeMode=ProfileMergeMode.REPLACE_ALL,
        )

        if result.failedBoreholeIds:
            print(f"Failed borehole ids: {result.failedBoreholeIds}")
        if result.warnings:
            for warning in result.warnings:
                print(f"Warning: {warning}")

        print(f"Imported profiles: {result.importedProfileNames}")
        for profile in model.Profiles.listProfiles():
            print(
                f"  profile {profile.name!r}  layers={profile.layerCount}  "
                f"thickness={profile.totalThickness}  active={profile.isActive}"
            )

        print(f"Saving project to {output_path}...")
        model.saveAs(output_path)
        print("Open that file in RSSeismic to inspect the imported profiles.")
    finally:
        if model is not None:
            try:
                model.close(saveProject=False)
            except Exception:
                pass
        app.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import RSLog boreholes (file or account) and save a project for inspection.",
    )
    parser.add_argument(
        "--source",
        choices=("file", "account"),
        default="file",
        help="Import source: local JSON export or authenticated RSLog account (default: file).",
    )
    parser.add_argument(
        "--json",
        default="",
        help=f"Path to RSLog JSON export (file source). Default: {_DEFAULT_JSON}",
    )
    parser.add_argument(
        "--company",
        default="",
        help="RSLog company (account source).",
    )
    parser.add_argument(
        "--username",
        "-u",
        default="",
        help="RSLog username (account source).",
    )
    parser.add_argument(
        "--password",
        "-w",
        default="",
        help="RSLog password (account source).",
    )
    parser.add_argument(
        "--server",
        default="",
        help="Optional RSLog server override (account source; empty = default).",
    )
    parser.add_argument(
        "--max-boreholes",
        type=int,
        default=2,
        help="Maximum boreholes to import (default: 2).",
    )
    parser.add_argument(
        "--output",
        "-o",
        default=_DEFAULT_OUTPUT,
        help=f"Output .rsseismicfile path (default: {_DEFAULT_OUTPUT})",
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
        run_rslog_import_example(
            source=args.source,
            output_path=args.output,
            port=args.port,
            json_file=args.json,
            company=args.company,
            username=args.username,
            password=args.password,
            server=args.server,
            max_boreholes=args.max_boreholes,
        )
    except Exception as ex:
        print(f"Example failed: {ex}", file=sys.stderr)
        return 1
    print("\nRSLog import example finished.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
