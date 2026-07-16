# -*- mode: python ; coding: utf-8 -*-

import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules


ROOT = Path(SPEC).resolve().parents[2]
VERSION = "3.5.2"
DISTRIBUTION = os.getenv("AEMAX_DISTRIBUTION", "direct")
ICON = ROOT / "packaging" / "macos" / "AudioEnhancerMAX.icns"

hiddenimports = []
for package in ("uvicorn", "backports", "app"):
    hiddenimports.extend(collect_submodules(package))

a = Analysis(
    [str(ROOT / "desktop" / "launcher.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        (str(ROOT / "frontend"), "frontend"),
        (str(ROOT / "presets"), "presets"),
    ],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "pytest"],
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="AudioEnhancerMAX",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    argv_emulation=False,
    target_arch="arm64",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="AudioEnhancerMAX",
)

app = BUNDLE(
    coll,
    name="AudioEnhancerMAX.app",
    icon=str(ICON),
    bundle_identifier="com.fabriziodegni.audioenhancermax",
    version=VERSION,
    info_plist={
        "CFBundleDisplayName": "AudioEnhancerMAX",
        "CFBundleName": "AudioEnhancerMAX",
        "CFBundleShortVersionString": VERSION,
        "CFBundleVersion": VERSION,
        "LSApplicationCategoryType": "public.app-category.music",
        "LSMinimumSystemVersion": "13.0",
        "NSHighResolutionCapable": True,
        "NSLocalNetworkUsageDescription": "AudioEnhancerMAX uses the local network only when connecting to trusted edge workers selected by the user.",
        "AEMAXDistribution": DISTRIBUTION,
    },
)
