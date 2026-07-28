"""
Raw gRPC smoke test (legacy dev script). Prefer the installed rsseismic package for new scripts.

Run from repo root after: pip install dist\\...whl  OR with stubs on PYTHONPATH.

  python examples/deepsoil_smoke_test.py --port 60058 "E:\\path\\to\\project.rsseismicfile"
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_STUB_DIR = Path(__file__).resolve().parents[1] / "src" / "rsseismic" / "generatedFiles"
sys.path.insert(0, str(_STUB_DIR))

import grpc

import ApplicationService_pb2 as app_pb2
import ApplicationService_pb2_grpc as app_grpc
import ModelService_pb2 as model_pb2
import ModelService_pb2_grpc as model_grpc
import MotionService_pb2 as motion_pb2
import MotionService_pb2_grpc as motion_grpc

HOST = "localhost"
DEFAULT_PORT = int(os.environ.get("RSSEISMIC_SCRIPTING_PORT", "60058"))
COMPUTE_TIMEOUT_SECONDS = 60 * 60


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="RSSeismic gRPC scripting smoke test")
    parser.add_argument(
        "project",
        help="Absolute path to .rsseismicfile (native format)",
    )
    parser.add_argument(
        "--port",
        "-p",
        type=int,
        default=DEFAULT_PORT,
        help=f"gRPC port (default: {DEFAULT_PORT}, or RSSEISMIC_SCRIPTING_PORT env)",
    )
    parser.add_argument(
        "--motion",
        "-m",
        action="append",
        default=[],
        metavar="NAME",
        help="Motion name to select for compute (repeatable). Default: already-selected motions, else first motion.",
    )
    parser.add_argument(
        "--motion-dir",
        action="append",
        default=[],
        metavar="PATH",
        help="Add a motion directory to app preferences before refresh (repeatable)",
    )
    parser.add_argument(
        "--no-compute",
        action="store_true",
        help="Skip RunCompute (Ping / OpenFile / Save / Close only)",
    )
    return parser.parse_args()


def require_success(label: str, response) -> bool:
    if response.success:
        return True
    print(f"  FAILED: {response.errorMessage}")
    return False


def add_motion_directories(motion: motion_grpc.MotionServiceStub, directories: list[str]) -> bool:
    for directory in directories:
        directory = os.path.abspath(directory.strip())
        print(f"AddMotionDirectory: {directory}")
        if not os.path.isdir(directory):
            print(f"  FAILED: directory does not exist: {directory}")
            return False
        resp = motion.AddMotionDirectory(
            motion_pb2.AddMotionDirectoryRequest(motionDirectory=directory)
        )
        if not require_success("AddMotionDirectory", resp):
            return False
        print("  OK")
    return True


def ensure_motion_selection(
    motion: motion_grpc.MotionServiceStub,
    model_id: str,
    requested_names: list[str],
) -> bool:
    print("RefreshMotionsList ...")
    refresh_resp = motion.RefreshMotionsList(
        motion_pb2.RefreshMotionsListRequest(modelID=model_id)
    )
    if not require_success("RefreshMotionsList", refresh_resp):
        return False
    print(f"  loaded {refresh_resp.motionsLoaded} motion(s)")

    print("ListMotions ...")
    list_resp = motion.ListMotions(motion_pb2.ListMotionsRequest(modelID=model_id))
    if not require_success("ListMotions", list_resp):
        return False

    if not list_resp.motions:
        print("  FAILED: no motions available.")
        print("  Add motion folders in RSSeismic Preferences, or pass --motion-dir PATH.")
        return False

    for entry in list_resp.motions:
        selected = "selected" if entry.isSelected else "not selected"
        print(f"  - {entry.name} ({selected})")

    if requested_names:
        names_to_select = requested_names
    else:
        names_to_select = [m.name for m in list_resp.motions if m.isSelected]
        if not names_to_select:
            names_to_select = [list_resp.motions[0].name]

    print(f"SetMotionSelection: {names_to_select}")
    select_resp = motion.SetMotionSelection(
        motion_pb2.SetMotionSelectionRequest(
            modelID=model_id,
            motionNames=names_to_select,
            selectOnlyListed=True,
        )
    )
    if not require_success("SetMotionSelection", select_resp):
        return False
    print("  OK")
    return True


def main() -> int:
    args = parse_args()
    project_path = os.path.abspath(args.project.strip())
    if not os.path.isfile(project_path):
        print(f"File not found: {project_path}")
        return 1

    target = f"{HOST}:{args.port}"
    print(f"Connecting to {target} ...")

    with grpc.insecure_channel(target) as channel:
        app = app_grpc.ApplicationServiceStub(channel)
        model = model_grpc.ModelServiceStub(channel)
        motion = motion_grpc.MotionServiceStub(channel)

        print("Ping ...")
        app.Ping(app_pb2.PingRequest())
        print("  OK")

        print(f"OpenFile: {project_path}")
        open_resp = app.OpenFile(app_pb2.OpenFileRequest(fileName=project_path))
        if not open_resp.success:
            print("  FAILED: OpenFile returned success=false")
            return 1
        model_id = open_resp.modelID
        print(f"  modelID = {model_id}")

        if args.motion_dir and not add_motion_directories(motion, args.motion_dir):
            return 1

        print("Save ...")
        save_resp = model.Save(model_pb2.SaveRequest(modelID=model_id))
        if save_resp.success:
            print("  OK")
        else:
            print(f"  skipped or failed: {save_resp.errorMessage}")

        if not args.no_compute:
            if not ensure_motion_selection(motion, model_id, args.motion):
                return 1

            print(f"RunCompute (timeout {COMPUTE_TIMEOUT_SECONDS}s) ...")
            compute_resp = model.RunCompute(
                model_pb2.RunComputeRequest(modelID=model_id),
                timeout=COMPUTE_TIMEOUT_SECONDS,
            )
            if compute_resp.success:
                print("  OK")
                if compute_resp.partialSuccess:
                    print("  partialSuccess=true: some profile/motion tasks may have failed")
            else:
                print(f"  FAILED: {compute_resp.errorMessage}")
                return 1

        print("Close ...")
        close_resp = model.Close(
            model_pb2.CloseRequest(modelID=model_id, saveProject=False)
        )
        if close_resp.success:
            print("  OK")
        else:
            print(f"  FAILED: {close_resp.errorMessage}")
            return 1

    print("Smoke test finished successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
