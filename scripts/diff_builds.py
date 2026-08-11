#!/usr/bin/env python3
"""对比 arm64 / x86_64 两个 onedir 构建（Contents/Frameworks 下），
找出可能导致 Intel 崩溃的差异：
  1) x86_64 独有文件（合并时会被漏掉）
  2) 两边同名但架构不一致的 Mach-O
用法: diff_builds.py <arm64-dir> <x86-dir>
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def rel_files(root: Path) -> set[Path]:
    out = set()
    for path in root.rglob("*"):
        if path.is_file() and not path.is_symlink():
            out.add(path.relative_to(root))
    return out


def archs(path: Path) -> str:
    out = subprocess.run(["lipo", "-info", str(path)], capture_output=True, text=True).stdout
    if "Non-fat file" in out:
        return "single:" + out.split("architecture:")[1].strip().split()[0]
    if "fat file" in out:
        return "fat:" + " ".join(out.split("are:")[1].split())
    return "not-macho"


def main() -> None:
    arm, x86 = Path(sys.argv[1]), Path(sys.argv[2])
    arm_files, x86_files = rel_files(arm), rel_files(x86)

    only_x86 = sorted(x86_files - arm_files)
    only_arm = sorted(arm_files - x86_files)
    print(f"== x86_64 独有文件（{len(only_x86)} 个，合并后会缺失）==")
    for f in only_x86[:30]:
        print("  X86-ONLY:", f)
    print(f"== arm64 独有文件（{len(only_arm)} 个）==")
    for f in only_arm[:20]:
        print("  ARM-ONLY:", f)

    print("== 同名文件架构差异 ==")
    for f in sorted(arm_files & x86_files):
        a, x = archs(arm / f), archs(x86 / f)
        if a != x:
            print(f"  DIFF {f}\n    arm64: {a}\n    x86:   {x}")


if __name__ == "__main__":
    main()
