"""
Smoke test: reset generated profiles, set numProfiles, then generate profiles.

Uses the rsseismic package (see example_auto_profile_workflow.py). Requires RSSeismic
running with scripting enabled and a project configured for automatic profile generation.

  python deepsoil_auto_profile_smoke_test.py --port 60058 "E:\\path\\to\\project.rsseismicfile"
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow importing sibling example script when run from examples/ without install path hacks.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from example_auto_profile_workflow import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
