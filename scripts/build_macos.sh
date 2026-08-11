#!/usr/bin/env bash
# 构建 macOS .app 包并做 ad-hoc 签名。产物: dist/robolabel.app
set -euo pipefail
cd "$(dirname "$0")/.."

PYTHON=".venv/bin/python"
if [ ! -x "$PYTHON" ]; then
  echo "未找到 .venv，请先: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt" >&2
  exit 1
fi

# 默认缓存目录 ~/Library/Application Support 常被 macOS 权限拦截，改到 ~/.cache
export PYINSTALLER_CONFIG_DIR="${PYINSTALLER_CONFIG_DIR:-$HOME/.cache/pyinstaller}"

"$PYTHON" -c 'import PyInstaller, sys; sys.exit(0 if int(PyInstaller.__version__.split(".")[0]) >= 6 else 1)' \
  || { echo "需要 PyInstaller >= 6 (当前: $("$PYTHON" -c 'import PyInstaller; print(PyInstaller.__version__)'))" >&2; exit 1; }

"$PYTHON" -m PyInstaller robolabel.spec --clean --noconfirm

# PyInstaller 构建 BUNDLE 时已自动完成 ad-hoc 签名（见构建日志 "Signing the BUNDLE..."）。
# 不要再 codesign --deep 重签：会破坏 bootloader 与嵌套框架的签名一致性导致启动失败。
codesign --verify --deep --strict --verbose=2 "dist/robolabel.app"

# 清理 COLLECT 中间目录（内容已并入 .app）
rm -rf "dist/robolabel"

echo "完成: dist/robolabel.app"
