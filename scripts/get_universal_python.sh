#!/usr/bin/env bash
# 下载并解包 python.org universal2 Python（无需 sudo），供双架构构建使用。
# 产物: ${PYORG_DEST:-/tmp/pyorg}/fwroot/Python.framework（含 arm64 + x86_64）
set -euo pipefail

VERSION="${PYORG_VERSION:-3.12.10}"
MIRROR="${PYORG_MIRROR:-https://mirrors.huaweicloud.com/python}"
DEST="${PYORG_DEST:-/tmp/pyorg}"

pkg="$DEST/python-$VERSION-macos11.pkg"
if [ ! -f "$pkg" ]; then
  mkdir -p "$DEST"
  echo "下载 python.org $VERSION (universal2)..."
  curl -sSL -o "$pkg" --max-time 600 "$MIRROR/$VERSION/python-$VERSION-macos11.pkg"
fi
rm -rf "$DEST/expanded" "$DEST/fwroot"
pkgutil --expand-full "$pkg" "$DEST/expanded"
mkdir -p "$DEST/fwroot"
ln -sfn "$DEST/expanded/Python_Framework.pkg/Payload" "$DEST/fwroot/Python.framework"
echo "universal2 Python 就绪: $DEST/fwroot/Python.framework"
