"""
Workflow
--------
  Step 0  Import libraries
  Step 1  Configuration (5 CSV → project paths, motion folder, batch settings)
  Step 2  Connect to RSSeismic
  Step 3  Resolve motion names (all motions under MOTION_DIR)
  Step 4  Build 5 project files from CSV (single Profile 1, MRDF fit, save)
  Step 5  Batch compute all projects with the same motion selection
  Step 6  Read deepsoilout.db3 from disk (no scripting API — RSSeismic can be closed)
  Step 7  Aggregate and write PNG plots

Steps 1–5 require the RSSeismic scripting server. Steps 6–7 are pure Python and can
even be run later on another machine that only has the project/result folders.

CSV columns: thickness_m, unit_weight, vs_m_s, shear_strength_kPa, soil_type,
curve_model, reduction_factor_formulation, ref_params (optional)
Sample CSVs : profile_01.csv … profile_05.csv in Inputs/ (see Step 1)

Run from the repo root:

    python examples/Tutorial_2/Scripting-Tutorial_2.py
"""

# =============================================================================
# STEP 0 — Import libraries
# =============================================================================
from __future__ import annotations
import csv
import math
import os
import sqlite3
from dataclasses import dataclass, field

import matplotlib
import matplotlib.pyplot as plt
import numpy as np

from rsseismic import RSSeismicApplication, UnitSystem

# =============================================================================
# STEP 1 — Configuration
# =============================================================================

_TUTORIAL_ROOT = os.path.dirname(os.path.abspath(__file__))
SCRIPTING_PORT = 60058
PROFILE_NAME = "Profile 1"

CSV_DIR = os.path.join(_TUTORIAL_ROOT, "Inputs")
OUTPUT_PROJECT_DIR = os.path.join(_TUTORIAL_ROOT, "projects")
OUTPUT_PLOT_DIR = os.path.join(_TUTORIAL_ROOT, "plots")

PROJECT_CASES: list[tuple[str, str, str]] = [
    (
        f"case_{index:02d}",
        os.path.join(CSV_DIR, f"profile_{index:02d}.csv"),
        os.path.join(OUTPUT_PROJECT_DIR, f"gqh_case_{index:02d}.rsseismicfile"),
    )
    for index in range(1, 6)
]

MOTION_DIR = r"C:\Program Files\Rocscience\RSSeismic\Resources\InputMotions"
MOTION_NAMES: list[str] = []

PARALLEL_DEGREE = 2
MAX_CONCURRENT_ANALYSES: int | None = None
COMPUTE_TIMEOUT: float | None = 7200
CONTINUE_ON_ERROR = True


# =============================================================================
# STEP 2 — Connect to RSSeismic
# =============================================================================

def connect_app() -> RSSeismicApplication:
    app = RSSeismicApplication(port=SCRIPTING_PORT)
    app.ping()
    return app


# =============================================================================
# STEP 3 — Resolve motion names
# =============================================================================

def _motion_file_in_directory(file_path: str, motion_dir: str) -> bool:
    file_abs = os.path.normcase(os.path.abspath(file_path))
    dir_abs = os.path.normcase(os.path.abspath(motion_dir))
    return file_abs == dir_abs or file_abs.startswith(dir_abs + os.sep)


def resolve_motion_names(model) -> list[str]:
    motion_dir = os.path.normpath(MOTION_DIR)
    model.Motions.addMotionDirectory(motion_dir)
    model.Motions.refreshMotionsList()

    all_motions = model.Motions.listMotions()
    if MOTION_NAMES:
        model.Motions.setMotionSelection(MOTION_NAMES, selectOnlyListed=True)
        return list(MOTION_NAMES)

    target_names = [
        motion.name for motion in all_motions
        if _motion_file_in_directory(motion.filePath, motion_dir)
    ]
    model.Motions.setMotionSelection(target_names, selectOnlyListed=True)
    return target_names


# =============================================================================
# STEP 4 — Build project files from CSV
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


def build_all_projects(app: RSSeismicApplication, motion_names: list[str]) -> list[str]:
    os.makedirs(OUTPUT_PROJECT_DIR, exist_ok=True)
    project_paths: list[str] = []

    for _, csv_path, project_path in PROJECT_CASES:
        model = app.newProject()
        configure_project_settings(model)
        build_profile_from_csv(model, csv_path)
        resolve_motion_names(model)
        model.Motions.setMotionSelection(motion_names, selectOnlyListed=True)
        model.saveAs(project_path)
        model.close(saveProject=False)
        project_paths.append(os.path.normpath(project_path))

    return project_paths


# =============================================================================
# STEP 5 — Batch compute
# =============================================================================

def run_batch_compute(app: RSSeismicApplication, project_paths: list[str], motion_names: list[str]):
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

    return batch_result


# =============================================================================
# STEP 6 — Read results from disk
# =============================================================================

DB3_FILENAME = "deepsoilout.db3"
MOTION_FOLDER_PREFIX = "Motion_"
RS_LAYER_INDEX = 1


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

    allowed_motions: set[str] | None = None
    if MOTION_NAMES:
        allowed_motions = set(MOTION_NAMES)

    for project_path in project_paths:
        results_root = compute_results_root(project_path)
        for profile_folder, motion_label, db3_path in iter_deepsoilout_db3(results_root):
            if allowed_motions and motion_label not in allowed_motions:
                continue

            periods, rs_values, depths, strains, pga_values = read_standard_db3(db3_path)
            samples.rs_periods.append(periods)
            samples.rs_values.append(rs_values)
            samples.strain_depths.append(depths)
            samples.strain_values.append(strains)
            samples.pga_depths.append(depths)
            samples.pga_values.append(pga_values)

    return samples


# =============================================================================
# STEP 7 — Aggregate and plot
# =============================================================================

matplotlib.rcParams.update({
    "font.family": "Times New Roman",
    "font.size": 12,
    "axes.labelsize": 12,
    "legend.fontsize": 12,
    "xtick.labelsize": 12,
    "ytick.labelsize": 12,
})
_INDIVIDUAL = dict(color="silver", linewidth=0.7, alpha=0.65, marker="o", markersize=3)
_MEAN = dict(color="black", linewidth=1.5, marker="o", markersize=4)
_BOUND = dict(color="black", linewidth=1.0, linestyle="--", marker="o", markersize=3)


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
    n = len(samples.rs_periods)
    print(f"Total samples (project × motion pairs): {n}")

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
        ax1.semilogx(xp, yp, **_INDIVIDUAL)
    ax1.semilogx(period_grid, rs_mean, label=r"$\mu_{\ln}$", **_MEAN)
    ax1.semilogx(period_grid, rs_upper, label=r"$\mu_{\ln} \pm \sigma_{\ln}$", **_BOUND)
    ax1.semilogx(period_grid, rs_lower, **_BOUND)
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
        ax2.plot(xs, ys, **_INDIVIDUAL)
    ax2.plot(s_mean, s_depths, label=r"$\mu_{\ln}$", **_MEAN)
    ax2.plot(s_upper, s_depths, label=r"$\mu_{\ln} \pm \sigma_{\ln}$", **_BOUND)
    ax2.plot(s_lower, s_depths, **_BOUND)
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
        ax3.plot(xs, ys, **_INDIVIDUAL)
    ax3.plot(p_mean, p_depths, label=r"$\mu_{\ln}$", **_MEAN)
    ax3.plot(p_upper, p_depths, label=r"$\mu_{\ln} \pm \sigma_{\ln}$", **_BOUND)
    ax3.plot(p_lower, p_depths, **_BOUND)
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
        print(f"Saved: {path}")
        plt.close(fig)


# =============================================================================
# Main — run Steps 2–7
# =============================================================================

def main() -> None:
    app = connect_app()

    # Step 3 — Resolve motion names once
    probe = app.newProject()
    motion_names = resolve_motion_names(probe)
    probe.close(saveProject=False)

    # Step 4 — Build and save all projects
    project_paths = build_all_projects(app, motion_names)

    # Step 5 — Batch compute
    run_batch_compute(app, project_paths, motion_names)
    app.close()

    # Step 6 — Read results from disk
    samples = collect_results_from_disk(project_paths)

    # Step 7 — Aggregate and plot
    plot_aggregated(samples, OUTPUT_PLOT_DIR)


if __name__ == "__main__":
    main()
