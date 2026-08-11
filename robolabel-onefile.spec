# -*- mode: python ; coding: utf-8 -*-
# 回退方案：旧版 onefile 单文件打包（dist/robolabletools）。
# 用法: python -m PyInstaller robolabel-onefile.spec --clean --noconfirm

from pathlib import Path

ROOT = Path.cwd()

config_files = [
    "coordination_modes.yaml",
    "lite_vocabulary.json",
    "phase_actions.json",
    "scene_templates.yaml",
    "skill_object_slots.json",
    "skill_templates.yaml",
]

a = Analysis(
    [str(ROOT / "lite_annotator" / "app.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        (str(ROOT / "config" / name), "config")
        for name in config_files
    ],
    hiddenimports=[
        "common.skill_schema",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "torch",
        "sam2",
        "segment_anything",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="robolabletools",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
