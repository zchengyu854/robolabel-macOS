# -*- mode: python ; coding: utf-8 -*-
# Windows 打包配置：onedir（产物 dist/robolabel/robolabel.exe，双击即用）。
# 用法: python -m PyInstaller robolabel-win.spec --clean --noconfirm

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
    [],
    exclude_binaries=True,           # onedir：exe 与依赖分目录放置
    name="robolabel",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,                   # windowed：双击不弹控制台
    disable_windowed_traceback=False,
    # argv_emulation 是 macOS 专属，Windows 不需要
    icon=str(ROOT / "assets" / "app.ico"),
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="robolabel",
)
