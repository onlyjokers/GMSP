from __future__ import annotations

import sys
from pathlib import Path


def ensure_src_path() -> Path:
    project_root = Path(__file__).resolve().parents[1]
    src_dir = project_root / "src"
    src_value = str(src_dir)
    if src_value not in sys.path:
        sys.path.insert(0, src_value)
    return project_root

