"""
Automatic profile generation workflow using the installed rsseismic package.

  python examples/example_auto_profile_workflow.py "E:\\path\\to\\Test_Auto_Profile.rsseismicfile"
  python examples/example_auto_profile_workflow.py --port 60058 --num-profiles 10 --seed 12345 project.rsseismicfile
"""

from __future__ import annotations

import argparse
import os
import sys

from rsseismic import RSSeismicApplication
from rsseismic._client import DEFAULT_SCRIPTING_PORT
from rsseismic.Model import GenerateProfilesResult, ResetGeneratedProfilesResult


DEFAULT_NUM_PROFILES = 20
DEFAULT_GENERATE_TIMEOUT_SECONDS = 60 * 60


def run_auto_profile_workflow(
    project_path: str,
    port: int = DEFAULT_SCRIPTING_PORT,
    num_profiles: int = DEFAULT_NUM_PROFILES,
    seed: int = 0,
    timeout: float | None = DEFAULT_GENERATE_TIMEOUT_SECONDS,
    save_on_close: bool = False,
) -> tuple[ResetGeneratedProfilesResult, GenerateProfilesResult]:
    """
    Open a project, reset generated profiles, set numProfiles, and generate profiles.

    Returns (resetResult, generateResult). Raises on missing file or RPC/scripting errors.
    """
    project_path = os.path.abspath(project_path.strip())
    if not os.path.isfile(project_path):
        raise FileNotFoundError(f"Project file not found: {project_path}")

    if num_profiles < 1:
        raise ValueError("num_profiles must be at least 1.")

    app = RSSeismicApplication(port=port)
    model = None

    try:
        app.ping()
        model = app.openFile(project_path)

        reset_result = model.resetGeneratedProfiles()
        model.ProfileGenerationSettings.setProfilesToGenerate(num_profiles)
        generate_result = model.generateProfiles(seed=seed, timeout=timeout)

        return reset_result, generate_result
    finally:
        if model is not None:
            model.close(saveProject=save_on_close)
        app.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reset generated profiles, set numProfiles, and run GenerateProfiles.",
    )
    parser.add_argument(
        "project",
        help="Absolute path to a .rsseismicfile configured for automatic profile generation",
    )
    parser.add_argument(
        "--port",
        "-p",
        type=int,
        default=int(os.environ.get("RSSEISMIC_SCRIPTING_PORT", DEFAULT_SCRIPTING_PORT)),
        help=f"gRPC port (default: {DEFAULT_SCRIPTING_PORT}, or RSSEISMIC_SCRIPTING_PORT env)",
    )
    parser.add_argument(
        "--num-profiles",
        "-n",
        type=int,
        default=DEFAULT_NUM_PROFILES,
        help=f"Number of profiles to generate (default: {DEFAULT_NUM_PROFILES})",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=0,
        help="RNG seed for GenerateProfiles (0 = server picks a random seed)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_GENERATE_TIMEOUT_SECONDS,
        help=f"GenerateProfiles timeout in seconds (default: {DEFAULT_GENERATE_TIMEOUT_SECONDS})",
    )
    parser.add_argument(
        "--save-on-close",
        action="store_true",
        help="Save project before Close (default: close without saving)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        reset_result, generate_result = run_auto_profile_workflow(
            args.project,
            port=args.port,
            num_profiles=args.num_profiles,
            seed=args.seed,
            timeout=args.timeout,
            save_on_close=args.save_on_close,
        )
    except Exception as ex:
        print(f"Workflow failed: {ex}", file=sys.stderr)
        return 1

    print(f"ResetGeneratedProfiles OK (hasBeenGenerated={reset_result.hasBeenGenerated})")
    print(
        f"GenerateProfiles OK (profileCount={generate_result.profileCount}, "
        f"hasBeenGenerated={generate_result.hasBeenGenerated})"
    )
    for name in generate_result.profileNames:
        print(f"  - {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
