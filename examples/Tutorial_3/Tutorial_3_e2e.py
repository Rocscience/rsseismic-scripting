"""
Tutorial 3 — NSHMP → motions → seven GQ/H projects → batch compute → plots.

Standalone: ``rsseismic`` + NumPy + Matplotlib only. Run from this folder (``examples/Tutorial_3/``).

Workflow: Steps 0–12 (see section headers in this file).

  cd examples\\Tutorial_3

  python Tutorial_3_e2e.py ^
    --username YOUR_GMDB_USER ^
    --password YOUR_GMDB_PASS
"""

from __future__ import annotations

import argparse
import csv
import math
import os
import re
import sqlite3
import sys
from dataclasses import dataclass, field

import matplotlib
import matplotlib.pyplot as plt
import numpy as np

try:
    from rsseismic import (
        AmplitudeScalingParams,
        DatabaseSearchFilters,
        DoubleRange,
        GroundMotionDatabase,
        NshmpAnnualFrequencyOfExceedance,
        NshmpHazardModel,
        NshmpTargetSpectraModel,
        RecordSelectionParams,
        RSSeismicApplication,
        TargetSpectra,
        UnitSystem,
        UserDefinedTargetSpectraModel,
        logger,
    )
    from rsseismic._client import DEFAULT_SCRIPTING_PORT
    from rsseismic.exceptions import ScriptingError
except ImportError as ex:
    missing = getattr(ex, "name", str(ex))
    print(
        "This script needs a current RSSeismicScripting install.\n\n"
        f"Import failed: {missing}\n\n"
        "From the repo root:\n"
        "  python -m pip install --force-reinstall .\n",
        file=sys.stderr,
    )
    raise SystemExit(1) from ex

# =============================================================================
# STEP 1 — Configuration (paths, NSHMP site, batch settings)
# =============================================================================

_TUTORIAL_ROOT = os.path.dirname(os.path.abspath(__file__))
_EXAMPLES_DIR = os.path.dirname(_TUTORIAL_ROOT)

SCRIPTING_PORT = int(os.environ.get("RSSEISMIC_SCRIPTING_PORT", DEFAULT_SCRIPTING_PORT))
PROFILE_NAME = "Profile 1"
CSV_DIR = os.path.join(_TUTORIAL_ROOT, "Inputs")
NUM_PROFILE_CASES = 7
OUTPUT_PROJECT_DIR = os.path.join(_TUTORIAL_ROOT, "projects")
OUTPUT_PLOT_DIR = os.path.join(_TUTORIAL_ROOT, "plots")
MOTION_DIR = os.path.join(_TUTORIAL_ROOT, "Motions")
TARGET_SPECTRUM_FILE = os.path.normpath(
    os.path.join(_EXAMPLES_DIR, "..", "tests", "resources", "target_spectrum_example.txt")
)
PROJECT_CASES = [
    (f"case_{i:02d}", os.path.join(CSV_DIR, f"profile_{i:02d}.csv"),
     os.path.join(OUTPUT_PROJECT_DIR, f"gqh_case_{i:02d}.rsseismicfile"))
    for i in range(1, NUM_PROFILE_CASES + 1)
]
NSHMP_LATITUDE, NSHMP_LONGITUDE = 37.7749, -122.4194
NSHMP_HAZARD_MODEL = NshmpHazardModel.CONTERMINOUS_US_2018
NSHMP_VS30 = 760
NSHMP_AFE = NshmpAnnualFrequencyOfExceedance.AFE_2475
NSHMP_TRUNCATE = NSHMP_MAXDIR = None
PARALLEL_DEGREE = 2
MAX_CONCURRENT_ANALYSES = None
COMPUTE_TIMEOUT = 7200
CONTINUE_ON_ERROR = True

def step(number: int | str, title: str) -> None:
    print(f"Step {number} — {title}")


def default_target_spectrum_file(examples_dir: str) -> str:
    return os.path.normpath(
        os.path.join(examples_dir, "..", "tests", "resources", "target_spectrum_example.txt")
    )


# Motion matching, NSHMP parsing, db3 post-processing (defaults shared by tutorials)

DATABASE = GroundMotionDatabase.GMDB
TARGET_SOURCE = "nshmp"

_NSHMP_HAZARD_MODEL_CHOICES = {model.name: model for model in NshmpHazardModel}
_NSHMP_AFE_CHOICES = {afe.name: afe for afe in NshmpAnnualFrequencyOfExceedance}

MAGNITUDE_MIN = 6.0
MAGNITUDE_MAX = 8.0
RRUP_KM_MAX = 50.0
NUM_GROUND_MOTIONS = 11
SCALING_DAMPING = 0.05
SCALING_TOLERANCE_PERCENT = 10.0
AMPLITUDE_T1_S = 0.01
AMPLITUDE_T2_S = 10.0
PREVIEW_SEARCH_MAX_RESULTS = 10

MATCH_PLOT_FILENAME = "match_to_target_spectra.png"

DB3_FILENAME = "deepsoilout.db3"
MOTION_FOLDER_PREFIX = "Motion_"
RS_LAYER_INDEX = 1

_MATCH_INDIVIDUAL = dict(color="silver", linewidth=0.8, alpha=0.45)
_MATCH_TARGET = dict(color="crimson", linewidth=2.0, label="Target spectrum")
_MATCH_ENSEMBLE = dict(color="black", linewidth=1.8, label=r"$\mu_{\ln}$ of geometric-mean Sa")

_MOTION_UI_CONFLICT_HINT = """
Motion library update failed (ObservableCollection / CollectionChanged).

Try:
  1. ``--launch-rsseismic`` and run before opening the Motion tab.
  2. Close Motion Manager / Motion tab, then re-run from Step 6.
  3. ``--motions-only`` to validate NSHMP + save without building projects.
"""

DATABASE_CHOICES = {
    "GMDB": GroundMotionDatabase.GMDB,
    "ESM": GroundMotionDatabase.ESM,
}


def database_from_cli_choice(label: str) -> GroundMotionDatabase:
    return DATABASE_CHOICES[label.strip().upper()]


def _database_label(database: GroundMotionDatabase) -> str:
    return "ESM" if database == GroundMotionDatabase.ESM else database.name


def _is_motion_ui_collection_conflict(error: BaseException) -> bool:
    text = str(error)
    return "ObservableCollection" in text or "CollectionChanged" in text


# =============================================================================
# STEP 2 — Connect to RSSeismic
# =============================================================================


def connect_app(port: int) -> RSSeismicApplication:
    """Open the scripting client and verify the server responds (Step 2)."""
    app = RSSeismicApplication(port=port)
    app.ping()
    return app


# =============================================================================
# STEPS 3–7 — Motions (NSHMP + automatic selection)
# =============================================================================


def _motion_directory_registered(directories: list[str], output_directory: str) -> bool:
    target = os.path.normcase(os.path.abspath(output_directory))
    return any(os.path.normcase(os.path.abspath(path)) == target for path in directories)


def prepare_motion_output_directory(app: RSSeismicApplication, output_directory: str) -> str:
    output_directory = os.path.normpath(os.path.abspath(output_directory))
    os.makedirs(output_directory, exist_ok=True)

    model = app.newProject()
    try:
        directories = model.Motions.listMotionDirectories()
        if _motion_directory_registered(directories, output_directory):
            print(f"  Motion folder already registered:\n    {output_directory}")
            return output_directory

        print(f"  Registering motion folder:\n    {output_directory}")
        updated = model.Motions.addMotionDirectory(output_directory)
        if not _motion_directory_registered(updated, output_directory):
            raise RuntimeError(
                f"Could not register motion directory: {output_directory}\n"
                "Add it manually under RSSeismic Preferences → Motions."
            )
    finally:
        model.close(saveProject=False)

    return output_directory


def _build_search_filters(
    magnitude_min: float,
    magnitude_max: float,
    rrup_km_max: float,
) -> DatabaseSearchFilters:
    return DatabaseSearchFilters(
        magnitude=DoubleRange(min=magnitude_min, max=magnitude_max),
        rrupKm=DoubleRange(max=rrup_km_max),
    )


@dataclass(frozen=True)
class NshmpSiteParameters:
    latitude: float
    longitude: float
    hazard_model: NshmpHazardModel | None = None
    vs30: int | None = None
    annual_frequency_of_exceedance: NshmpAnnualFrequencyOfExceedance | None = None
    truncate: bool | None = None
    maxdir: bool | None = None


def _parse_nshmp_hazard_model(name: str) -> NshmpHazardModel | None:
    key = name.strip().upper()
    if not key or key == "DEFAULT":
        return None
    try:
        return _NSHMP_HAZARD_MODEL_CHOICES[key]
    except KeyError as ex:
        options = ", ".join(sorted(_NSHMP_HAZARD_MODEL_CHOICES))
        raise ValueError(f"Unknown NSHMP hazard model '{name}'. Choose: {options}") from ex


def _parse_nshmp_afe(name: str) -> NshmpAnnualFrequencyOfExceedance | None:
    key = name.strip().upper()
    if not key or key == "DEFAULT":
        return None
    try:
        return _NSHMP_AFE_CHOICES[key]
    except KeyError as ex:
        options = ", ".join(sorted(_NSHMP_AFE_CHOICES))
        raise ValueError(f"Unknown NSHMP AFE '{name}'. Choose: {options}") from ex


def _build_nshmp_target_spectra_model(params: NshmpSiteParameters) -> NshmpTargetSpectraModel:
    return NshmpTargetSpectraModel(
        latitude=params.latitude,
        longitude=params.longitude,
        hazardModel=params.hazard_model,
        vs30=params.vs30,
        annualFrequencyOfExceedance=params.annual_frequency_of_exceedance,
        truncate=params.truncate,
        maxdir=params.maxdir,
    )


def _describe_nshmp_parameters(params: NshmpSiteParameters) -> str:
    def _label(value, default_text: str) -> str:
        return default_text if value is None else str(value)

    return (
        f"lat={params.latitude}, lon={params.longitude}, "
        f"model={_label(params.hazard_model, 'server default')}, "
        f"Vs30={_label(params.vs30, 'server default')}, "
        f"AFE={_label(params.annual_frequency_of_exceedance, 'server default')}, "
        f"truncate={_label(params.truncate, 'server default')}, "
        f"maxdir={_label(params.maxdir, 'server default')}"
    )


def resolve_target_spectra(
    library,
    target_source: str,
    target_file: str,
    *,
    nshmp: NshmpSiteParameters,
) -> TargetSpectra:
    source = target_source.strip().lower()
    if source == "file":
        path = os.path.normpath(target_file)
        if not os.path.isfile(path):
            raise FileNotFoundError(f"Target spectrum file not found: {path}")
        print(f"  Loading user-defined target from:\n    {path}")
        return library.getTargetSpectra(UserDefinedTargetSpectraModel(filePath=path))

    if source == "nshmp":
        print("  Querying NSHMP Dynamic Hazard Curves...")
        print(f"  {_describe_nshmp_parameters(nshmp)}")
        return library.getTargetSpectra(_build_nshmp_target_spectra_model(nshmp))

    raise ValueError(f"Unknown target source '{target_source}'. Use 'file' or 'nshmp'.")


def run_motion_selection_steps(
    app: RSSeismicApplication,
    *,
    motion_dir: str,
    database: GroundMotionDatabase,
    username: str,
    password: str,
    target_source: str,
    target_file: str,
    nshmp: NshmpSiteParameters,
    preview_max_results: int | None,
    overwrite: bool,
    plot_dir: str | None,
) -> TargetSpectra | None:
    if database == GroundMotionDatabase.CESMD:
        raise ValueError("Automatic selection supports GMDB and ESM only.")
    if not password.strip():
        raise ValueError("Database password is required.")

    filters = _build_search_filters(MAGNITUDE_MIN, MAGNITUDE_MAX, RRUP_KM_MAX)
    selection = RecordSelectionParams(
        nGm=NUM_GROUND_MOTIONS,
        damping=SCALING_DAMPING,
        tolPercent=SCALING_TOLERANCE_PERCENT,
        isScaled=True,
    )
    amplitude = AmplitudeScalingParams(t1=AMPLITUDE_T1_S, t2=AMPLITUDE_T2_S)
    library = app.MotionLibrary

    step(3, "Prepare motion output folder")
    motion_dir = prepare_motion_output_directory(app, motion_dir)

    db_label = _database_label(database)
    step(4, f"Database: {db_label}")
    library.authenticateDatabase(database=database, username=username, password=password)

    print("  Preview database search")
    preview = library.searchDatabaseRecords(
        database=database,
        filters=filters,
        maxResults=preview_max_results,
    )
    print(f"  Records returned: {len(preview)}")
    for record in preview[:5]:
        print(
            f"    {record.id}  M={record.magnitude}  Rrup={record.rrupKm:.1f} km  "
            f"sta={record.station}"
        )
    if len(preview) > 5:
        print(f"    ... and {len(preview) - 5} more")

    step(
        5,
        "Target spectra (NSHMP Dynamic Hazard Curves)"
        if target_source.strip().lower() == "nshmp"
        else "Target spectra",
    )
    target = resolve_target_spectra(
        library, target_source, target_file, nshmp=nshmp,
    )
    if not target.points:
        raise RuntimeError("Target spectra returned no period–Sa points.")
    print(f"  {len(target.points)} period–Sa point(s).")

    step(6, "Automatic record selection and save")
    print(
        "  Avoid opening the Motion tab before this step completes "
        "(or use --launch-rsseismic)."
    )
    try:
        result = library.matchToTargetSpectraAutomatic(
            database=database,
            filters=filters,
            targetSpectra=target,
            outputDirectory=motion_dir,
            selection=selection,
            amplitude=amplitude,
            overwrite=overwrite,
        )
    except ScriptingError as ex:
        if _is_motion_ui_collection_conflict(ex):
            print(_MOTION_UI_CONFLICT_HINT, file=sys.stderr)
        raise

    print(f"  Saved {len(result.savedMotionNames)} motion component(s) under:\n    {motion_dir}")
    for name in result.savedMotionNames[:8]:
        print(f"    {name}")
    if len(result.savedMotionNames) > 8:
        print(f"    ... and {len(result.savedMotionNames) - 8} more")

    if plot_dir is not None and result.savedMotionNames:
        step(7, "Plot target vs scaled geometric-mean spectra")
        period_arrays, sa_arrays = collect_geometric_mean_spectra(
            library, motion_dir, list(result.savedMotionNames),
        )
        if period_arrays:
            plot_path = os.path.join(os.path.abspath(plot_dir), MATCH_PLOT_FILENAME)
            plot_match_to_target_spectra(target, period_arrays, sa_arrays, plot_path)
            print(f"  Saved: {plot_path}")
        else:
            logger.warning("  No pair spectra available for match plot.")

    return target


_SCALE_FACTOR_SUFFIX = re.compile(r"_SF=[0-9.+\-eE]+$")


def _strip_scale_factor_suffix(motion_name: str) -> str:
    return _SCALE_FACTOR_SUFFIX.sub("", motion_name)


def _shared_prefix_from_motion_name(motion_name: str) -> str | None:
    stem = _strip_scale_factor_suffix(motion_name)
    split_at = stem.rfind("_")
    if split_at <= 0:
        return None
    return stem[:split_at]


def _group_saved_motion_pairs(saved_motion_names: list[str]) -> list[tuple[str, str]]:
    buckets: dict[str, list[str]] = {}
    for motion_name in saved_motion_names:
        prefix = _shared_prefix_from_motion_name(motion_name)
        if prefix is None:
            continue
        buckets.setdefault(prefix, []).append(motion_name)

    pairs: list[tuple[str, str]] = []
    for prefix, names in buckets.items():
        unique_names = sorted(set(names))
        if len(unique_names) == 2:
            pairs.append((unique_names[0], unique_names[1]))
    return pairs


def _pick_sa_column(spectral_df) -> str:
    for column in ("FrequencyDomain", "GeometricMeanSa", "Duhamel", "Newmark"):
        if column in spectral_df.columns:
            return column
    candidates = [col for col in spectral_df.columns if col != "Period"]
    if not candidates:
        raise ValueError(f"No spectral acceleration column in {list(spectral_df.columns)}")
    return candidates[0]


def _geometric_mean_spectrum_from_motion_names(
    library,
    h1_name: str,
    h2_name: str,
) -> tuple[np.ndarray, np.ndarray]:
    _, spec_h1 = library.getMotion(h1_name).getSpectralData()
    _, spec_h2 = library.getMotion(h2_name).getSpectralData()
    sa_column = _pick_sa_column(spec_h1)

    period_h1 = spec_h1["Period"].values.astype(float)
    sa_h1 = spec_h1[sa_column].values.astype(float)
    period_h2 = spec_h2["Period"].values.astype(float)
    sa_h2 = spec_h2[sa_column].values.astype(float)

    mask_h1 = np.isfinite(period_h1) & np.isfinite(sa_h1) & (period_h1 > 0) & (sa_h1 > 0)
    mask_h2 = np.isfinite(period_h2) & np.isfinite(sa_h2) & (period_h2 > 0) & (sa_h2 > 0)
    period_h1, sa_h1 = period_h1[mask_h1], sa_h1[mask_h1]
    period_h2, sa_h2 = period_h2[mask_h2], sa_h2[mask_h2]

    order_h2 = np.argsort(period_h2)
    period_h2, sa_h2 = period_h2[order_h2], sa_h2[order_h2]
    sa_h2_on_h1 = np.interp(period_h1, period_h2, sa_h2, left=np.nan, right=np.nan)
    valid = np.isfinite(sa_h2_on_h1)
    period = period_h1[valid]
    geo_sa = np.sqrt(sa_h1[valid] * sa_h2_on_h1[valid])
    return period, geo_sa


def collect_geometric_mean_spectra(
    library,
    output_directory: str,
    saved_motion_names: list[str],
) -> tuple[list[np.ndarray], list[np.ndarray]]:
    periods_list: list[np.ndarray] = []
    sa_list: list[np.ndarray] = []

    pairs = _group_saved_motion_pairs(saved_motion_names)
    if not pairs:
        discovered = library.discoverMotionPairsInFolder(output_directory)
        pairs = [(pair.motionH1Name, pair.motionH2Name) for pair in discovered.allPairs]

    for h1_name, h2_name in pairs:
        try:
            period, geo_sa = _geometric_mean_spectrum_from_motion_names(
                library, h1_name, h2_name,
            )
        except Exception as ex:
            logger.warning("  Skipping pair for plot: %s", ex)
            continue
        if period.size:
            periods_list.append(period)
            sa_list.append(geo_sa)

    return periods_list, sa_list


def _log_mean_spectrum(
    period_arrays: list[np.ndarray],
    sa_arrays: list[np.ndarray],
    common_periods: np.ndarray,
) -> np.ndarray:
    cx = np.log(common_periods)
    matrix = np.full((len(common_periods), len(period_arrays)), np.nan)
    for j, (periods, sa_values) in enumerate(zip(period_arrays, sa_arrays)):
        order = np.argsort(periods)
        xp = np.log(np.clip(periods[order], 1e-300, None))
        matrix[:, j] = np.interp(cx, xp, sa_values[order], left=np.nan, right=np.nan)

    with np.errstate(divide="ignore", invalid="ignore"):
        ln_mean = np.nanmean(np.log(matrix), axis=1)
    return np.exp(ln_mean)


def plot_match_to_target_spectra(
    target: TargetSpectra,
    period_arrays: list[np.ndarray],
    sa_arrays: list[np.ndarray],
    plot_path: str,
) -> None:
    target_periods = np.array([point.period for point in target.points], dtype=float)
    target_sa = np.array([point.sa for point in target.points], dtype=float)
    target_mask = (
        np.isfinite(target_periods)
        & np.isfinite(target_sa)
        & (target_periods > 0)
        & (target_sa > 0)
    )
    target_periods = target_periods[target_mask]
    target_sa = target_sa[target_mask]

    period_grid = np.sort(
        np.unique(np.concatenate([target_periods, period_arrays[0][period_arrays[0] > 0]]))
    )
    ensemble_sa = _log_mean_spectrum(period_arrays, sa_arrays, period_grid)

    fig, ax = plt.subplots(figsize=(6, 4.5))
    for periods, sa_values in zip(period_arrays, sa_arrays):
        ax.semilogx(periods, sa_values, **_MATCH_INDIVIDUAL)
    ax.semilogx(period_grid, ensemble_sa, **_MATCH_ENSEMBLE)
    ax.semilogx(target_periods, target_sa, **_MATCH_TARGET)
    ax.set_xscale("log")
    ax.set_yscale("linear")
    ax.set_xlabel("Period (s)")
    ax.set_ylabel("Spectral acceleration (g)")
    ax.legend(frameon=False)
    ax.grid(True, which="both", alpha=0.3)
    fig.tight_layout()

    os.makedirs(os.path.dirname(plot_path) or ".", exist_ok=True)
    fig.savefig(plot_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


# =============================================================================
# STEP 8 — Resolve motion names for project build
# =============================================================================


def _motion_file_in_directory(file_path: str, motion_dir: str) -> bool:
    file_abs = os.path.normcase(os.path.abspath(file_path))
    dir_abs = os.path.normcase(os.path.abspath(motion_dir))
    return file_abs == dir_abs or file_abs.startswith(dir_abs + os.sep)


def resolve_motion_names(model, motion_dir: str) -> list[str]:
    motion_dir = os.path.normpath(motion_dir)
    model.Motions.addMotionDirectory(motion_dir)
    model.Motions.refreshMotionsList()

    all_motions = model.Motions.listMotions()
    target_names = [
        motion.name for motion in all_motions
        if _motion_file_in_directory(motion.filePath, motion_dir)
    ]
    if not target_names:
        raise RuntimeError(
            f"No motions found under {motion_dir}. "
            "Run without --skip-motions first, or check the folder."
        )
    model.Motions.setMotionSelection(target_names, selectOnlyListed=True)
    return target_names


# =============================================================================
# STEPS 11–12 — Read db3 from disk and aggregate plots
# =============================================================================


def compute_results_root(project_path: str) -> str:
    project_path = os.path.normpath(project_path)
    project_dir = os.path.dirname(project_path)
    stem = os.path.splitext(os.path.basename(project_path))[0]
    return os.path.join(project_dir, stem)


def iter_deepsoilout_db3(results_root: str):
    if not os.path.isdir(results_root):
        return

    for profile_folder in sorted(os.listdir(results_root)):
        profile_dir = os.path.join(results_root, profile_folder)
        if not os.path.isdir(profile_dir):
            continue
        for motion_folder in sorted(os.listdir(profile_dir)):
            if not motion_folder.startswith(MOTION_FOLDER_PREFIX):
                continue
            db3_path = os.path.join(profile_dir, motion_folder, DB3_FILENAME)
            if os.path.isfile(db3_path):
                motion_label = motion_folder[len(MOTION_FOLDER_PREFIX):]
                yield profile_folder, motion_label, db3_path


def read_standard_db3(db3_path: str, rs_layer_index: int = RS_LAYER_INDEX) -> tuple[
    np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray,
]:
    rs_column = f"LAYER{rs_layer_index}_RS"
    with sqlite3.connect(db3_path) as conn:
        rs_rows = conn.execute(
            f"SELECT PERIOD, {rs_column} FROM RESPONSE_SPECTRA"
        ).fetchall()
        profile_rows = conn.execute(
            "SELECT DEPTH_LAYER_MID, MAX_STRAIN, PGA_TOTAL FROM PROFILES"
        ).fetchall()

    periods = np.array([row[0] for row in rs_rows], dtype=float)
    rs_values = np.array([row[1] for row in rs_rows], dtype=float)
    depths = np.array([row[0] for row in profile_rows], dtype=float)
    strains = np.array([row[1] for row in profile_rows], dtype=float)
    pga_values = np.array([row[2] for row in profile_rows], dtype=float)
    return periods, rs_values, depths, strains, pga_values


@dataclass
class AggregatedSamples:
    rs_periods: list[np.ndarray] = field(default_factory=list)
    rs_values: list[np.ndarray] = field(default_factory=list)
    strain_depths: list[np.ndarray] = field(default_factory=list)
    strain_values: list[np.ndarray] = field(default_factory=list)
    pga_depths: list[np.ndarray] = field(default_factory=list)
    pga_values: list[np.ndarray] = field(default_factory=list)
    rs_units: dict[str, str] = field(default_factory=dict)
    depth_units: dict[str, str] = field(default_factory=dict)
    pga_units: dict[str, str] = field(default_factory=dict)


def collect_results_from_disk(project_paths: list[str]) -> AggregatedSamples:
    samples = AggregatedSamples()
    samples.rs_units = {"period": "s", "rs": "g"}
    samples.depth_units = {"depth": "m"}
    samples.pga_units = {"pga": "g"}

    for project_path in project_paths:
        results_root = compute_results_root(project_path)
        for _profile_folder, _motion_label, db3_path in iter_deepsoilout_db3(results_root):
            periods, rs_values, depths, strains, pga_values = read_standard_db3(db3_path)
            samples.rs_periods.append(periods)
            samples.rs_values.append(rs_values)
            samples.strain_depths.append(depths)
            samples.strain_values.append(strains)
            samples.pga_depths.append(depths)
            samples.pga_values.append(pga_values)

    return samples


matplotlib.rcParams.update({
    "font.family": "Times New Roman",
    "font.size": 12,
    "axes.labelsize": 12,
    "legend.fontsize": 12,
    "xtick.labelsize": 12,
    "ytick.labelsize": 12,
})
_ANALYSIS_INDIVIDUAL = dict(color="silver", linewidth=0.7, alpha=0.65, marker="o", markersize=3)
_ANALYSIS_MEAN = dict(color="black", linewidth=1.5, marker="o", markersize=4)
_ANALYSIS_BOUND = dict(color="black", linewidth=1.0, linestyle="--", marker="o", markersize=3)


def strain_to_percent(strain: np.ndarray) -> np.ndarray:
    return strain.astype(float) * 100.0


def log_mean_std(
    x_arrays: list[np.ndarray],
    y_arrays: list[np.ndarray],
    common_x: np.ndarray,
    *,
    log_x: bool = False,
    log_y: bool = True,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    n_pts = len(common_x)
    n_samp = len(x_arrays)
    matrix = np.full((n_pts, n_samp), np.nan)

    cx = np.log(common_x) if log_x else common_x
    for j, (x, y) in enumerate(zip(x_arrays, y_arrays)):
        order = np.argsort(x)
        xs, ys = x[order], y[order]
        xj = np.log(np.clip(xs, 1e-300, None)) if log_x else xs
        matrix[:, j] = np.interp(cx, xj, ys)

    valid = np.isfinite(matrix) & (matrix > 0)
    if log_y:
        with np.errstate(divide="ignore", invalid="ignore"):
            ln_mat = np.where(valid, np.log(matrix), np.nan)
            mu = np.nanmean(ln_mat, axis=1)
            sigma = np.nanstd(ln_mat, axis=1, ddof=1)
        return np.exp(mu), np.exp(mu + sigma), np.exp(mu - sigma)

    mu = np.nanmean(matrix, axis=1)
    sigma = np.nanstd(matrix, axis=1, ddof=1)
    return mu, mu + sigma, mu - sigma


def aggregate_by_layer_index(
    depth_arrays: list[np.ndarray],
    value_arrays: list[np.ndarray],
    *,
    log_y: bool = True,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    max_layers = max(len(d) for d in depth_arrays)
    mean_depths: list[float] = []
    val_means: list[float] = []
    val_uppers: list[float] = []
    val_lowers: list[float] = []

    for layer_idx in range(max_layers):
        depths: list[float] = []
        values: list[float] = []
        for depth_arr, value_arr in zip(depth_arrays, value_arrays):
            if layer_idx < len(depth_arr):
                depths.append(float(depth_arr[layer_idx]))
                values.append(float(value_arr[layer_idx]))
        if not values:
            continue

        values_arr = np.array(values, dtype=float)
        if log_y:
            positive = values_arr[values_arr > 0]
            if positive.size == 0:
                continue
            ln_vals = np.log(positive)
            mu = float(np.mean(ln_vals))
            sigma = float(np.std(ln_vals, ddof=1)) if positive.size > 1 else 0.0
            val_means.append(math.exp(mu))
            val_uppers.append(math.exp(mu + sigma))
            val_lowers.append(math.exp(mu - sigma))
        else:
            mu = float(np.mean(values_arr))
            sigma = float(np.std(values_arr, ddof=1)) if values_arr.size > 1 else 0.0
            val_means.append(mu)
            val_uppers.append(mu + sigma)
            val_lowers.append(mu - sigma)
        mean_depths.append(float(np.mean(depths)))

    return (
        np.array(mean_depths),
        np.array(val_means),
        np.array(val_uppers),
        np.array(val_lowers),
    )


def _sorted_layer_profile(values: np.ndarray, depths: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    order = np.argsort(depths)
    return values[order], depths[order]


def plot_aggregated(samples: AggregatedSamples, output_dir: str) -> None:
    if not samples.rs_periods:
        raise RuntimeError(
            "No deepsoilout.db3 samples found. Run batch compute first or check project paths."
        )

    n = len(samples.rs_periods)
    step(12, f"Plot aggregates ({n} project × motion sample(s))")

    period_unit = samples.rs_units.get("period", "s")
    rs_unit = samples.rs_units.get("rs", "g")
    depth_unit = samples.depth_units.get("depth", "m")
    pga_unit = samples.pga_units.get("pga", "g")

    period_grid = np.sort(samples.rs_periods[0][samples.rs_periods[0] > 0])
    rs_mean, rs_upper, rs_lower = log_mean_std(
        samples.rs_periods, samples.rs_values, period_grid, log_x=True, log_y=True,
    )

    fig1, ax1 = plt.subplots(figsize=(5, 4.5))
    for xp, yp in zip(samples.rs_periods, samples.rs_values):
        ax1.semilogx(xp, yp, **_ANALYSIS_INDIVIDUAL)
    ax1.semilogx(period_grid, rs_mean, label=r"$\mu_{\ln}$", **_ANALYSIS_MEAN)
    ax1.semilogx(period_grid, rs_upper, label=r"$\mu_{\ln} \pm \sigma_{\ln}$", **_ANALYSIS_BOUND)
    ax1.semilogx(period_grid, rs_lower, **_ANALYSIS_BOUND)
    ax1.set_xscale("log")
    ax1.set_yscale("linear")
    ax1.set_xlabel(f"Period ({period_unit})")
    ax1.set_ylabel(f"Spectral Acceleration ({rs_unit})")
    ax1.legend(frameon=False)
    ax1.grid(True, which="both", alpha=0.3)
    fig1.tight_layout()

    strain_pct_samples = [strain_to_percent(v) for v in samples.strain_values]
    s_depths, s_mean, s_upper, s_lower = aggregate_by_layer_index(
        samples.strain_depths, strain_pct_samples, log_y=True,
    )

    fig2, ax2 = plt.subplots(figsize=(4, 5.5))
    for strain_pct, depths in zip(strain_pct_samples, samples.strain_depths):
        xs, ys = _sorted_layer_profile(strain_pct, depths)
        ax2.plot(xs, ys, **_ANALYSIS_INDIVIDUAL)
    ax2.plot(s_mean, s_depths, label=r"$\mu_{\ln}$", **_ANALYSIS_MEAN)
    ax2.plot(s_upper, s_depths, label=r"$\mu_{\ln} \pm \sigma_{\ln}$", **_ANALYSIS_BOUND)
    ax2.plot(s_lower, s_depths, **_ANALYSIS_BOUND)
    ax2.set_xlabel("Max Shear Strain (%)")
    ax2.set_ylabel(f"Depth ({depth_unit})")
    ax2.invert_yaxis()
    ax2.legend(frameon=False)
    ax2.grid(True, which="major", alpha=0.3)
    fig2.tight_layout()

    p_depths, p_mean, p_upper, p_lower = aggregate_by_layer_index(
        samples.pga_depths, samples.pga_values, log_y=True,
    )

    fig3, ax3 = plt.subplots(figsize=(4, 5.5))
    for pga, depths in zip(samples.pga_values, samples.pga_depths):
        xs, ys = _sorted_layer_profile(pga, depths)
        ax3.plot(xs, ys, **_ANALYSIS_INDIVIDUAL)
    ax3.plot(p_mean, p_depths, label=r"$\mu_{\ln}$", **_ANALYSIS_MEAN)
    ax3.plot(p_upper, p_depths, label=r"$\mu_{\ln} \pm \sigma_{\ln}$", **_ANALYSIS_BOUND)
    ax3.plot(p_lower, p_depths, **_ANALYSIS_BOUND)
    ax3.set_xlabel(f"PGA ({pga_unit})")
    ax3.set_ylabel(f"Depth ({depth_unit})")
    ax3.invert_yaxis()
    ax3.legend(frameon=False)
    ax3.grid(True, which="major", alpha=0.3)
    fig3.tight_layout()

    os.makedirs(output_dir, exist_ok=True)
    for fig, name in [
        (fig1, "response_spectra.png"),
        (fig2, "max_strain_profile.png"),
        (fig3, "pga_profile.png"),
    ]:
        path = os.path.join(output_dir, name)
        fig.savefig(path, dpi=150, bbox_inches="tight")
        print(f"  Saved: {path}")
        plt.close(fig)

# STEP 9 — Build seven projects from profile CSV
# =============================================================================


@dataclass
class ProfileLayerRow:
    thickness_m: float
    unit_weight: float
    vs_m_s: float
    shear_strength_kPa: float
    soil_type: str
    curve_model: str
    reduction_factor_formulation: str
    ref_params: dict[str, str] = field(default_factory=dict)


def _cell(row: dict[str, str], key: str) -> str:
    return row.get(key, "").strip()


def _require_float(row: dict[str, str], key: str) -> float:
    return float(_cell(row, key))


def parse_key_value_params(text: str) -> dict[str, str]:
    if not text.strip():
        return {}
    params: dict[str, str] = {}
    for part in text.split(";"):
        part = part.strip()
        if not part:
            continue
        key, _, value = part.partition("=")
        key, value = key.strip(), value.strip()
        if key and value:
            params[key] = value
    return params


def apply_scalar_params(accessor, params: dict[str, str]) -> None:
    for key, value in params.items():
        accessor.setDoubleProperty(key, float(value))


def load_profile_rows(csv_path: str) -> list[ProfileLayerRow]:
    csv_path = os.path.normpath(csv_path)
    with open(csv_path, newline="", encoding="utf-8-sig") as handle:
        data_lines = [
            line for line in handle
            if line.strip() and not line.lstrip().startswith("#")
        ]
        reader = csv.DictReader(data_lines)
        rows: list[ProfileLayerRow] = []
        for raw in reader:
            if not any(_cell(raw, key) for key in raw):
                continue
            rows.append(ProfileLayerRow(
                thickness_m=_require_float(raw, "thickness_m"),
                unit_weight=_require_float(raw, "unit_weight"),
                vs_m_s=_require_float(raw, "vs_m_s"),
                shear_strength_kPa=_require_float(raw, "shear_strength_kPa"),
                soil_type=_cell(raw, "soil_type"),
                curve_model=_cell(raw, "curve_model"),
                reduction_factor_formulation=_cell(raw, "reduction_factor_formulation"),
                ref_params=parse_key_value_params(_cell(raw, "ref_params")),
            ))
    return rows


def mrdf_fitting_procedure(formulation: str) -> str | None:
    if formulation == "None":
        return None
    if formulation == "MRDF_Darendeli":
        return "MRDF_Derendeli"
    return "MRDF_UIUC"


def configure_project_settings(model) -> None:
    model.ProjectSettings.changeUnitSystem(UnitSystem.Metric)
    model.ProjectSettings.Data.setBoolValue("automaticProfileGeneration", False)
    model.ProjectSettings.Data.setEnumValue("analysisMode", "Nonlinear")
    model.ProjectSettings.Data.setEnumValue("defaultSoilModel", "GQ_H")
    model.ProjectSettings.Data.setEnumValue("hystereticFormulation", "NonMasing")


def build_profile_from_csv(model, csv_path: str, profile_name: str = PROFILE_NAME) -> None:
    rows = load_profile_rows(csv_path)
    model.Profiles.setActiveProfile(profile_name)

    existing = model.Profiles.listActiveSoilLayers()
    need = len(rows) - len(existing)
    if need > 0:
        model.SoilLayers.appendLayers(need)

    for summary, spec in zip(model.Profiles.listActiveSoilLayers(), rows):
        layer = model.Profiles.getSoilLayer(summary.layerID)
        layer.setSoilModel("GQ_H")
        layer.setThickness(spec.thickness_m)
        layer.setUnitWeight(spec.unit_weight)
        layer.Data.setDoubleProperty("ShearWaveVelocity", spec.vs_m_s)
        layer.Data.setDoubleProperty("ShearStrength", spec.shear_strength_kPa)

        ref = layer.ReferenceCurve
        ref.setSoilType(spec.soil_type)
        ref.setCurveModel(spec.curve_model)
        apply_scalar_params(ref.Data, spec.ref_params)
        ref.generateReferenceCurve()

        fit_proc = mrdf_fitting_procedure(spec.reduction_factor_formulation)
        if fit_proc is not None:
            layer.Curve.runCurveFit(fit_proc)


def build_all_projects(
    app: RSSeismicApplication,
    motion_names: list[str],
    motion_dir: str,
) -> list[str]:
    os.makedirs(OUTPUT_PROJECT_DIR, exist_ok=True)
    project_paths: list[str] = []

    for case_id, csv_path, project_path in PROJECT_CASES:
        if not os.path.isfile(csv_path):
            raise FileNotFoundError(f"Missing profile CSV for {case_id}: {csv_path}")

        print(f"  Building {case_id} → {os.path.basename(project_path)}")
        model = app.newProject()
        configure_project_settings(model)
        build_profile_from_csv(model, csv_path)
        resolve_motion_names(model, motion_dir)
        model.Motions.setMotionSelection(motion_names, selectOnlyListed=True)
        model.saveAs(project_path)
        model.close(saveProject=False)
        project_paths.append(os.path.normpath(project_path))

    return project_paths


def default_project_paths() -> list[str]:
    return [os.path.normpath(project_path) for _, _, project_path in PROJECT_CASES]


# =============================================================================
# STEP 10 — Batch compute
# =============================================================================


def run_batch_compute(
    app: RSSeismicApplication,
    project_paths: list[str],
    motion_names: list[str],
) -> None:
    batch_result = app.runBatchCompute(
        project_paths,
        motion_names=motion_names,
        parallel_degree=PARALLEL_DEGREE,
        max_concurrent_analyses=MAX_CONCURRENT_ANALYSES,
        timeout=COMPUTE_TIMEOUT,
        close_save_project=False,
        continue_on_error=CONTINUE_ON_ERROR,
    )

    ok = sum(1 for job in batch_result.results if job.success and not job.partial_success)
    partial = sum(1 for job in batch_result.results if job.success and job.partial_success)
    failed = sum(1 for job in batch_result.results if not job.success)
    print()
    print("=" * 70)
    print(f"  Batch complete — {len(batch_result.results)} project(s)")
    print(f"  Full success : {ok}   Partial : {partial}   Failed : {failed}")
    print("=" * 70)
    for job in batch_result.results:
        name = os.path.basename(job.file_path)
        status = "OK" if job.success and not job.partial_success else (
            "PARTIAL" if job.success else "FAILED"
        )
        print(f"  [{status:7s}]  {name}")
        if job.error_message:
            print(f"             {job.error_message}")
    print()

def parse_args() -> argparse.Namespace:
    """Define command-line flags for partial runs and NSHMP/motion options."""
    parser = argparse.ArgumentParser(
        description="Tutorial 3: NSHMP target spectra to motions to batch GQ/H analysis.",
    )
    parser.add_argument("--port", "-p", type=int, default=SCRIPTING_PORT)
    parser.add_argument("--username", help="GMDB/ESM username (required unless --results-only).")
    parser.add_argument("--password", help="GMDB/ESM password.")
    parser.add_argument(
        "--database",
        "-d",
        default=_database_label(DATABASE),
        choices=sorted(DATABASE_CHOICES.keys()),
    )
    parser.add_argument("--target-source", choices=("file", "nshmp"), default=TARGET_SOURCE)
    parser.add_argument("--target-file", default=TARGET_SPECTRUM_FILE)
    parser.add_argument("--latitude", type=float, default=NSHMP_LATITUDE)
    parser.add_argument("--longitude", type=float, default=NSHMP_LONGITUDE)
    parser.add_argument(
        "--nshmp-model",
        default=NSHMP_HAZARD_MODEL.name if NSHMP_HAZARD_MODEL is not None else "DEFAULT",
    )
    parser.add_argument("--nshmp-vs30", type=int, default=NSHMP_VS30 if NSHMP_VS30 is not None else 0)
    parser.add_argument(
        "--nshmp-afe",
        default=NSHMP_AFE.name if NSHMP_AFE is not None else "DEFAULT",
    )
    parser.add_argument("--nshmp-truncate", action="store_true")
    parser.add_argument("--nshmp-maxdir", action="store_true")
    parser.add_argument("--preview-max-results", type=int, default=PREVIEW_SEARCH_MAX_RESULTS)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--motion-dir", default=MOTION_DIR)
    parser.add_argument("--plot-dir", default=OUTPUT_PLOT_DIR)
    parser.add_argument("--no-match-plot", action="store_true")
    parser.add_argument("--launch-rsseismic", action="store_true")
    parser.add_argument("--rsseismic-exe", default="")
    parser.add_argument("--skip-motions", action="store_true", help="Skip Steps 3–7.")
    parser.add_argument("--motions-only", action="store_true", help="Run Steps 3–7 only.")
    parser.add_argument("--results-only", action="store_true", help="Steps 11–12 only.")
    parser.add_argument("--skip-compute", action="store_true", help="Build projects; skip Step 10.")
    return parser.parse_args()


def nshmp_params_from_args(args: argparse.Namespace) -> NshmpSiteParameters:
    """Map CLI NSHMP flags to ``NshmpSiteParameters`` for Step 5."""
    return NshmpSiteParameters(
        latitude=args.latitude,
        longitude=args.longitude,
        hazard_model=_parse_nshmp_hazard_model(args.nshmp_model),
        vs30=args.nshmp_vs30 if args.nshmp_vs30 > 0 else None,
        annual_frequency_of_exceedance=_parse_nshmp_afe(args.nshmp_afe),
        truncate=True if args.nshmp_truncate else NSHMP_TRUNCATE,
        maxdir=True if args.nshmp_maxdir else NSHMP_MAXDIR,
    )


def main() -> int:
    """Run Tutorial 3 end-to-end (or a subset via CLI flags)."""
    args = parse_args()

    if args.results_only:
        try:
            step(11, "Read deepsoilout.db3 from disk")
            samples = collect_results_from_disk(default_project_paths())
            plot_aggregated(samples, OUTPUT_PLOT_DIR)
        except Exception as ex:
            print(f"Results post-processing failed: {ex}", file=sys.stderr)
            return 1
        print("\nTutorial 3 post-processing finished.")
        return 0

    if not args.username or not args.password:
        print("--username and --password are required (unless --results-only).", file=sys.stderr)
        return 1

    preview_cap: int | None = args.preview_max_results
    if preview_cap is not None and preview_cap <= 0:
        preview_cap = None

    nshmp_params = nshmp_params_from_args(args)
    motion_dir = os.path.normpath(os.path.abspath(args.motion_dir))
    plot_dir = None if args.no_match_plot else args.plot_dir
    database = database_from_cli_choice(args.database)

    try:
        if args.launch_rsseismic:
            print("Launching RSSeismic...")
            launch_kwargs: dict = {"port": args.port}
            if args.rsseismic_exe.strip():
                launch_kwargs["overridePathToExecutable"] = args.rsseismic_exe.strip()
            RSSeismicApplication.startApplication(**launch_kwargs)

        step(2, "Connect to RSSeismic scripting server")
        app = connect_app(args.port)

        if not args.skip_motions:
            run_motion_selection_steps(
                app,
                motion_dir=motion_dir,
                database=database,
                username=args.username,
                password=args.password,
                target_source=args.target_source,
                target_file=args.target_file,
                nshmp=nshmp_params,
                preview_max_results=preview_cap,
                overwrite=args.overwrite,
                plot_dir=plot_dir,
            )
        else:
            print("Steps 3–7 — Skipped (--skip-motions)")

        if args.motions_only:
            app.close()
            print("\nTutorial 3 motions-only run finished.")
            return 0

        step(8, "Resolve motion names")
        probe = app.newProject()
        motion_names = resolve_motion_names(probe, motion_dir)
        probe.close(saveProject=False)
        print(f"  Selected {len(motion_names)} motion(s) from tutorial folder.")

        step(9, "Build seven projects from CSV")
        project_paths = build_all_projects(app, motion_names, motion_dir)

        if args.skip_compute:
            app.close()
            print("\nTutorial 3 finished (projects built; compute skipped).")
            return 0

        step(10, "Batch compute")
        run_batch_compute(app, project_paths, motion_names)
        app.close()

        step(11, "Read deepsoilout.db3 from disk")
        samples = collect_results_from_disk(project_paths)
        plot_aggregated(samples, OUTPUT_PLOT_DIR)

    except Exception as ex:
        print(f"Tutorial 3 failed: {ex}", file=sys.stderr)
        if _is_motion_ui_collection_conflict(ex):
            print(_MOTION_UI_CONFLICT_HINT, file=sys.stderr)
        return 1

    print("\nTutorial 3 end-to-end run finished.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
