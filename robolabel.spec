# -*- mode: python ; coding: utf-8 -*-

import os
from pathlib import Path

ROOT = Path.cwd()

# universal2 双架构构建时通过环境变量指定目标架构（arm64 / x86_64）
TARGET_ARCH = os.environ.get("ROBOLABEL_TARGET_ARCH")

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
    exclude_binaries=True,
    name="robolabel",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=True,
    target_arch=TARGET_ARCH,
    codesign_identity=None,
    entitlements_file=None,
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
app = BUNDLE(
    coll,
    name="robolabel.app",
    icon=str(ROOT / "assets" / "app.icns"),
    bundle_identifier="com.robolabel.app",
    info_plist={
        "CFBundleName": "robolabel",
        "CFBundleDisplayName": "RoboLabel",
        "CFBundleShortVersionString": "1.0.0",
        "CFBundleVersion": "1.0.0",
        "NSHighResolutionCapable": True,
        "LSMinimumSystemVersion": "12.0",
        "NSHumanReadableCopyright": "robolabel contributors",
    },
    version=None,
)
