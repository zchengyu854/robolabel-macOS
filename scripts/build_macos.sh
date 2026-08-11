#!/usr/bin/env bash
# 构建 universal2（arm64 + Intel）macOS .app。产物: dist/robolabel.app
#
# 依赖 python.org 的 universal2 Python（因 numpy/opencv 等无 universal2 wheel，
# 需分别在 arm64 / x86_64 两个解释器下构建后 lipo 合并）。
# 设置 PYORG_FWROOT 指向 universal2 Python.framework 的父目录（含 Python.framework 软链），
# 默认尝试 /tmp/pyorg/fwroot（scripts/get_universal_python.sh 解包所得）。
set -euo pipefail
cd "$(dirname "$0")/.."

FWROOT="${PYORG_FWROOT:-/tmp/pyorg/fwroot}"
PYLIB="$(cd "$FWROOT/Python.framework" 2>/dev/null && pwd)/Versions/3.12/lib"
PYEXE="$FWROOT/Python.framework/Versions/3.12/bin/python3.12"
[ -x "$PYEXE" ] || { echo "缺少 universal2 Python (PYORG_FWROOT=$FWROOT)。请先运行 scripts/get_universal_python.sh" >&2; exit 1; }

export DYLD_FRAMEWORK_PATH="$FWROOT"
export DYLD_LIBRARY_PATH="$PYLIB"
export PYINSTALLER_CONFIG_DIR="${PYINSTALLER_CONFIG_DIR:-$HOME/.cache/pyinstaller}"

# 1. 准备双架构 venv（缺依赖时自动安装）
for mode in arm64 x86_64; do
  venv="build-venv-$mode"
  if [ ! -x "$venv/bin/python" ]; then
    if [ "$mode" = arm64 ]; then
      "$PYEXE" -m venv "$venv"
      "$venv/bin/pip" install -i https://mirrors.aliyun.com/pypi/simple/ -r requirements.txt
    else
      arch -x86_64 env DYLD_FRAMEWORK_PATH="$FWROOT" DYLD_LIBRARY_PATH="$PYLIB" "$PYEXE" -m venv "$venv"
      # 依赖版本与 arm64 venv 对齐
      build-venv-arm64/bin/pip freeze | grep -viE '^(pip|setuptools|wheel)=' > /tmp/deps.txt
      arch -x86_64 env DYLD_FRAMEWORK_PATH="$FWROOT" DYLD_LIBRARY_PATH="$PYLIB" \
        "$venv/bin/pip" install -i https://mirrors.aliyun.com/pypi/simple/ -r /tmp/deps.txt
    fi
  fi
done

# 2. 双架构 onedir 构建（不直接出 .app，合并后再组）
# PyInstaller 隔离子进程需继承 DYLD_FRAMEWORK_PATH（解包 python 场景）
build-venv-arm64/bin/python scripts/patch_pyinstaller_dyld.py build-venv-arm64
build-venv-arm64/bin/python scripts/patch_pyinstaller_dyld.py build-venv-x86

rm -rf dist-arm64 dist-x86 build-arm64 build-x86
ROBOLABEL_TARGET_ARCH=arm64 build-venv-arm64/bin/python -m PyInstaller robolabel.spec \
  --distpath dist-arm64 --workpath build-arm64 --noconfirm
arch -x86_64 env DYLD_FRAMEWORK_PATH="$FWROOT" DYLD_LIBRARY_PATH="$PYLIB" \
  ROBOLABEL_TARGET_ARCH=x86_64 build-venv-x86/bin/python -m PyInstaller robolabel.spec \
  --distpath dist-x86 --workpath build-x86 --noconfirm

# 3. lipo 合并为 universal2 .app
build-venv-arm64/bin/python scripts/merge_universal.py \
  dist-arm64/robolabel.app dist-x86/robolabel.app dist/robolabel.app

# 4. 验证
lipo -info dist/robolabel.app/Contents/MacOS/robolabel
codesign --verify --deep --strict --verbose=2 dist/robolabel.app

# 清理中间产物
rm -rf dist-arm64 dist-x86 build-arm64 build-x86 dist/robolabel

echo "完成: dist/robolabel.app (universal2: Apple Silicon + Intel)"
