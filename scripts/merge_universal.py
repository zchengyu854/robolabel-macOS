#!/usr/bin/env python3
"""把 arm64 与 x86_64 两个 .app 合并为 universal2（fat binary）。

用法: merge_universal.py <arm64.app> <x86_64.app> <out.app>

原则: 以 arm64 版为基底复制；对每个 Mach-O 文件，若已是 fat（universal2）
则保留，否则用 lipo 合并两架构版本；最后从内到外 ad-hoc 签名。
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


def run(cmd: list[str], text: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=text)


def is_macho(path: Path) -> bool:
    return "Mach-O" in run(["file", "-b", str(path)]).stdout


def archs(path: Path) -> list[str]:
    out = run(["lipo", "-info", str(path)]).stdout
    if "Non-fat file" in out:
        return [out.split("architecture:")[1].strip().split()[0]]
    if "fat file" in out:
        return out.split("are:")[1].split()
    return []


def merge_file(arm: Path, x86: Path, out: Path, rel: Path) -> None:
    a, x, o = arm / rel, x86 / rel, out / rel
    if not a.exists() or a.is_symlink() or not a.is_file():
        return
    if not is_macho(a):
        return  # 非二进制直接保留
    if len(archs(a)) > 1:
        return  # 已是 universal2，保留
    if not x.exists():
        print(f"!! 缺少 x86 对应文件: {rel}")
        return
    result = run(["lipo", "-create", str(a), str(x), "-output", str(o)])
    if result.returncode != 0:
        print(f"lipo 失败: {rel}\n{result.stderr}")
        sys.exit(1)
    print(f"merge {rel}")


def sign_all(app: Path) -> None:
    """从内到外 ad-hoc 签名: 先签 Contents 下所有 Mach-O，再签整个 bundle。"""
    for root, _dirs, files in os_walk(app / "Contents"):
        for name in files:
            p = Path(root) / name
            if not p.is_symlink() and is_macho(p):
                run(["codesign", "-f", "-s", "-", str(p)])
    result = run(["codesign", "-f", "-s", "-", str(app)])
    print("codesign bundle:", result.returncode, result.stderr.strip()[:200])


def os_walk(base: Path):
    import os

    for root, dirs, files in os.walk(base):
        yield Path(root), dirs, files


def main() -> None:
    arm, x86, out = (Path(p) for p in sys.argv[1:4])
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(arm, out, symlinks=True)

    for root, _dirs, files in os_walk(out):
        for name in files:
            merge_file(arm, x86, out, (Path(root) / name).relative_to(out))

    sign_all(out)
    print("完成:", out)


if __name__ == "__main__":
    main()
