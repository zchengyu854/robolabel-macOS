#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Windows构建脚本（Python版本）：打包robolabel为Windows可执行程序
产物：dist/robolabel/robolabel.exe（onedir模式，双击即用）
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path


def main():
    print("=" * 60)
    print("Building robolabel for Windows")
    print("=" * 60)

    # 检查Python版本
    if sys.version_info < (3, 9):
        print("Error: Python 3.9+ required")
        return 1

    # 检查PyInstaller
    try:
        import PyInstaller
        print(f"Using PyInstaller {PyInstaller.__version__}")
    except ImportError:
        print("Error: PyInstaller not installed. Run: pip install pyinstaller")
        return 1

    root = Path(__file__).parent.parent
    os.chdir(root)

    # 清理旧构建产物
    print("\nCleaning old build artifacts...")
    for path in ["build", "dist/robolabel"]:
        p = Path(path)
        if p.exists():
            shutil.rmtree(p)
            print(f"  Removed: {path}")

    # 执行打包
    print("\nRunning PyInstaller...")
    spec_file = root / "robolabel-win.spec"
    cmd = [
        sys.executable,
        "-m", "PyInstaller",
        str(spec_file),
        "--clean",
        "--noconfirm",
    ]

    result = subprocess.run(cmd)
    if result.returncode != 0:
        print("\nBuild failed!")
        return 1

    print("\n" + "=" * 60)
    print("Build completed successfully!")
    print("=" * 60)
    print(f"Product: dist/robolabel/robolabel.exe")
    print(f"Size: ~{sum(f.stat().st_size for f in Path('dist/robolabel').rglob('*') if f.is_file()) // 1024 // 1024}MB")
    print("\nTo test: cd dist\\robolabel && robolabel.exe")
    return 0


if __name__ == "__main__":
    sys.exit(main())
