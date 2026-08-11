#!/usr/bin/env python3
"""让 PyInstaller 的隔离子进程继承 DYLD_FRAMEWORK_PATH。

解包的 python.org Python 依赖绝对路径 /Library/Frameworks/...，运行需
DYLD_FRAMEWORK_PATH；而 PyInstaller __wrap_python 只经 `arch -e` 传播
DYLD_LIBRARY_PATH，导致子进程加载解释器失败。本脚本幂等地补齐传播。

用法: patch_pyinstaller_dyld.py <venv-dir>
"""
from __future__ import annotations

import sys
from pathlib import Path

OLD = """        if 'DYLD_LIBRARY_PATH' in os.environ:
            path = os.environ['DYLD_LIBRARY_PATH']
            py_prefix += ['-e', 'DYLD_LIBRARY_PATH=%s' % path]"""
NEW = """        for var in ('DYLD_LIBRARY_PATH', 'DYLD_FRAMEWORK_PATH'):
            if var in os.environ:
                py_prefix += ['-e', '%s=%s' % (var, os.environ[var])]"""


def main() -> None:
    compat = Path(sys.argv[1]) / "lib/python3.12/site-packages/PyInstaller/compat.py"
    src = compat.read_text()
    if OLD not in src:
        print("无需 patch（目标已变化）:", compat)
        return
    compat.write_text(src.replace(OLD, NEW))
    print("patched:", compat)


if __name__ == "__main__":
    main()
