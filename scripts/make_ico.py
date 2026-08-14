#!/usr/bin/env python3
"""从 assets/app.icns 提取最大 PNG，用 Pillow 生成多尺寸 Windows 图标 assets/app.ico。

用法: python scripts/make_ico.py [源png]   # 源png缺省时自动从 app.icns 提取
依赖: Pillow（仅构建期需要，不进 requirements.txt）
"""
from __future__ import annotations

import io
import struct
import sys
from pathlib import Path

ASSETS = Path(__file__).resolve().parent.parent / "assets"
ICO_SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def extract_largest_png(icns_path: Path) -> bytes:
    data = icns_path.read_bytes()
    if data[:4] != b"icns":
        raise ValueError(f"not an icns file: {icns_path}")
    offset = 8
    best, best_width = None, 0
    while offset + 8 <= len(data):
        chunk_type = data[offset : offset + 4]
        size = struct.unpack(">I", data[offset + 4 : offset + 8])[0]
        chunk = data[offset + 8 : offset + size]
        if chunk[:4] == b"\x89PNG" and chunk_type in {
            b"ic07", b"ic08", b"ic09", b"ic10", b"ic11", b"ic12", b"ic13", b"ic14",
        }:
            width = struct.unpack(">I", chunk[16:20])[0]
            if width > best_width:
                best, best_width = chunk, width
        offset += size
    if best is None:
        raise ValueError(f"no PNG chunks found in icns: {icns_path}")
    return best


def make_ico(png_bytes: bytes, output: Path) -> None:
    from PIL import Image

    image = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    image.save(output, sizes=ICO_SIZES)
    print(f"生成 {output} ({len(ICO_SIZES)} 个尺寸)")


def main() -> int:
    from PIL import Image  # 提前 import，缺失时给出明确提示

    source = sys.argv[1] if len(sys.argv) > 1 else None
    if source:
        png_bytes = Path(source).read_bytes()
    else:
        png_bytes = extract_largest_png(ASSETS / "app.icns")
    make_ico(png_bytes, ASSETS / "app.ico")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
