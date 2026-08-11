from __future__ import annotations

import sys
from pathlib import Path


def resource_path(relative: str) -> Path:
    """打包后从应用包内读只读资源；源码运行从项目根读。"""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base / relative
