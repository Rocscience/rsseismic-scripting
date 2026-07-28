"""
Plot computed profile and layer results using pandas DataFrames from model.Results.

Requires RSSeismic with scripting server connected and a .rsseismicfile with motions.
matplotlib is installed with RSSeismicScripting.

  python examples/example_plot_results_v1.py "E:\\path\\to\\project.rsseismicfile"
  python examples/example_plot_results_v1.py --port 60058 --motion ChiChi project.rsseismicfile
  python examples/example_plot_results_v1.py --no-compute project.rsseismicfile
  python examples/example_plot_results_v1.py --output-dir ./plots project.rsseismicfile
"""

from __future__ import annotations

import argparse
import os
import sys

from rsseismic import RSSeismicApplication, logger, ResultSeriesKind
from rsseismic._client import DEFAULT_SCRIPTING_PORT
from rsseismic.exceptions import ScriptingError


def _select_motion_names(model, requested_names: list[str]) -> list[str]:
    model.Motions.refreshMotionsList()
    motions = model.Motions.listMotions()
    if not motions:
        raise RuntimeError(
            "No motions available. Configure motion directories in RSSeismic Preferences "
            "or ensure the project has motions."
        )

    if requested_names:
        return requested_names

    selected = [motion.name for motion in motions if motion.isSelected]
    if selected:
        return selected

    return [motions[0].name]


def _require_matplotlib():
    try:
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise RuntimeError(
            "matplotlib is required for this example. Reinstall RSSeismicScripting "
            "(pip install --force-reinstall RSSeismicScripting) or run: pip install matplotlib"
        ) from exc
    return plt


def _save_or_show(plt, fig, output_dir: str | None, filename: str) -> None:
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, filename)
        fig.savefig(output_path, dpi=150)
        print(f"Saved plot: {output_path}")
    else:
        plt.show()


def plot_results(
    project_path: str,
    port: int = DEFAULT_SCRIPTING_PORT,
    motion_names: list[str] | None = None,
    run_compute: bool = True,
    output_dir: str | None = None,
) -> None:
    project_path = os.path.abspath(project_path.strip())
    if not os.path.isfile(project_path):
        raise FileNotFoundError(f"Project file not found: {project_path}")

    plt = _require_matplotlib()
    app = RSSeismicApplication(port=port)
    model = None

    try:
        app.ping()
        model = app.openFile(project_path)

        profile_name = model.Profiles.getActiveProfile().profileName
        names_to_select = _select_motion_names(model, motion_names or [])
        model.Motions.setMotionSelection(names_to_select, selectOnlyListed=True)
        model.save()

        if run_compute:
            result = model.runCompute()
            if not result.success:
                raise RuntimeError(result.errorMessage or "RunCompute failed.")
            if result.partialSuccess:
                logger.warning("Some profile/motion pairs failed:\n%s", result.errorMessage)

        motion_name = names_to_select[0]
        entry = model.Results.getResultDatabasePath(profile_name, motion_name)
        deconv = model.Profiles.getBedrockLayerProxy(profile_name).Data.getBoolValue("Deconvolution")
        has_db3 = entry.resultDatabaseExists or entry.complementaryResultDatabaseExists

        layers = model.Profiles.listActiveSoilLayers()
        if not layers:
            raise RuntimeError("Active profile has no soil layers.")

        layer_id = layers[0].layerID
        layer_label = layers[0].name or f"layer {layers[0].index1Based}"

        fig, axes = plt.subplots(1, 2, figsize=(10, 5))
        fig.suptitle(f"{profile_name} — {motion_name}")

        if not deconv and has_db3:
            max_strain_df = model.Results.getResultSeriesDataFrame(
                profile_name,
                motion_name,
                ResultSeriesKind.MAX_STRAIN,
            )
            profile_df = model.Results.getProfileResultsDataFrame(profile_name, motion_name)

            axes[0].plot(
                max_strain_df["maxStrain"],
                max_strain_df["depth"],
                marker="o",
                linewidth=1,
            )
            axes[0].set_xlabel("max strain")
            axes[0].set_ylabel("depth")
            axes[0].set_title("Max strain profile")
            axes[0].grid(True, alpha=0.3)
            axes[0].invert_yaxis()

            print(f"Profile rows: {len(profile_df)}")
            print(f"Max-strain series rows: {len(max_strain_df)}")
            print(f"Profile columns: {list(profile_df.columns)}")
        else:
            reason = "deconvolution profile" if deconv else "no db3 result database"
            logger.info("Skipping profile-level results (%s).", reason)
            axes[0].set_title(f"Profile results unavailable ({reason})")
            axes[0].axis("off")

        can_read_layer = (
            entry.deconvolutionBedrockMotionExists
            or any(layer.layerMotionExists for layer in entry.deconvolutionLayerFiles)
            if deconv
            else has_db3
        )
        if can_read_layer:
            try:
                time_history_df = model.Results.getLayerTimeHistoryDataFrame(
                    profile_name,
                    motion_name,
                    layer_id,
                )
            except ScriptingError as ex:
                logger.warning(
                    "Skipping layer time-history plot for %s (%s): %s",
                    layer_label,
                    layer_id,
                    ex,
                )
                axes[1].set_title("Layer time history (unavailable)")
                axes[1].axis("off")
            else:
                axes[1].plot(time_history_df["time"], time_history_df["accel"], linewidth=0.8)
                axes[1].set_xlabel("time")
                axes[1].set_ylabel("acceleration")
                axes[1].set_title(f"Acceleration — {layer_label}")
                axes[1].grid(True, alpha=0.3)
        else:
            logger.info("Skipping layer time history (no layer motion/db3 output).")
            axes[1].set_title("Layer time history (not available)")
            axes[1].axis("off")

        fig.tight_layout()
        _save_or_show(
            plt,
            fig,
            output_dir,
            f"{profile_name}_{motion_name}_results.png".replace(" ", "_"),
        )

        strain_motion_name = None
        for name in names_to_select:
            strain_entry = model.Results.getResultDatabasePath(profile_name, name)
            if strain_entry.strainConvergenceExists:
                strain_motion_name = name
                break

        if strain_motion_name is not None:
            try:
                strain_df = model.Results.getStrainConvergenceDataFrame(
                    profile_name,
                    strain_motion_name,
                )
            except ScriptingError as ex:
                logger.warning(
                    "Strain convergence query failed for motion %r: %s",
                    strain_motion_name,
                    ex,
                )
            else:
                fig2, ax2 = plt.subplots(figsize=(8, 4))
                fig2.suptitle(f"{profile_name} — {strain_motion_name} (strain convergence)")
                layer_columns = [col for col in strain_df.columns if col.startswith("strainLayer")]
                if layer_columns:
                    for column in layer_columns:
                        ax2.plot(strain_df["iteration"], strain_df[column], marker="o", label=column)
                    ax2.legend(loc="best", fontsize=8)
                ax2.set_xlabel("iteration")
                ax2.set_ylabel("strain")
                ax2.grid(True, alpha=0.3)
                fig2.tight_layout()
                _save_or_show(
                    plt,
                    fig2,
                    output_dir,
                    f"{profile_name}_{strain_motion_name}_strain_convergence.png".replace(" ", "_"),
                )
                print(f"Strain convergence rows: {len(strain_df)}")
        else:
            logger.info(
                "Skipping strain convergence (no strain.txt for selected motions on profile %s).",
                profile_name,
            )

        displacement_animation = model.ProjectSettings.Data.getBoolValue("displacementAnimation")
        if displacement_animation and not deconv and entry.resultDatabaseExists:
            try:
                disp_df = model.Results.getRealTimeDisplacementDataFrame(
                    profile_name,
                    motion_name,
                )
            except ScriptingError as ex:
                logger.warning("Real-time displacement query failed: %s", ex)
            else:
                disp_columns = [col for col in disp_df.columns if col.startswith("dispLayer")]
                if disp_columns:
                    fig3, ax3 = plt.subplots(figsize=(8, 4))
                    fig3.suptitle(f"{profile_name} — {motion_name} (real-time displacement)")
                    ax3.plot(disp_df["time"], disp_df[disp_columns[0]], linewidth=0.8)
                    ax3.set_xlabel("time")
                    ax3.set_ylabel(disp_columns[0])
                    ax3.set_title(f"{disp_columns[0]} vs time")
                    ax3.grid(True, alpha=0.3)
                    fig3.tight_layout()
                    _save_or_show(
                        plt,
                        fig3,
                        output_dir,
                        f"{profile_name}_{motion_name}_displacement.png".replace(" ", "_"),
                    )
                    print(f"Real-time displacement rows: {len(disp_df)}")
        else:
            logger.info(
                "Skipping real-time displacement (requires displacementAnimation, standard db3, non-deconv)."
            )
    finally:
        if model is not None:
            model.close(saveProject=False)
        app.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compute (optional) and plot RSSeismic result DataFrames."
    )
    parser.add_argument(
        "project",
        help="Absolute path to a .rsseismicfile",
    )
    parser.add_argument(
        "--port",
        "-p",
        type=int,
        default=int(os.environ.get("RSSEISMIC_SCRIPTING_PORT", DEFAULT_SCRIPTING_PORT)),
        help=f"gRPC port (default: {DEFAULT_SCRIPTING_PORT}, or RSSEISMIC_SCRIPTING_PORT env)",
    )
    parser.add_argument(
        "--motion",
        "-m",
        action="append",
        default=[],
        metavar="NAME",
        help="Motion name to select for compute (repeatable). Default: already-selected, else first motion.",
    )
    parser.add_argument(
        "--no-compute",
        action="store_true",
        help="Skip RunCompute and read existing result databases",
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        default="",
        help="Save PNG to this directory instead of opening an interactive window",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        plot_results(
            args.project,
            port=args.port,
            motion_names=args.motion,
            run_compute=not args.no_compute,
            output_dir=args.output_dir or None,
        )
    except Exception as ex:
        print(f"Plot workflow failed: {ex}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
