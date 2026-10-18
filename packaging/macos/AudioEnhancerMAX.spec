# -*- mode: python ; coding: utf-8 -*-

import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules


ROOT = Path(SPEC).resolve().parents[2]
VERSION = os.getenv("AEMAX_MARKETING_VERSION", "3.8.3")
BUILD_NUMBER = os.getenv("AEMAX_BUILD_NUMBER", "3.8.4")
DISTRIBUTION = os.getenv("AEMAX_DISTRIBUTION", "direct")
ICON = ROOT / "packaging" / "macos" / "AudioEnhancerMAX.icns"
WHISPER_MODEL_DIR = Path(os.getenv("AEMAX_WHISPER_MODEL_DIR", ""))
LICENSE_DIR = Path(os.getenv("AEMAX_LICENSE_DIR", ""))

datas = [
    (str(ROOT / "frontend"), "frontend"),
    (str(ROOT / "presets"), "presets"),
    (str(ROOT / "packaging" / "macos" / "PrivacyInfo.xcprivacy"), "."),
    (str(ROOT / "packaging" / "macos" / "THIRD_PARTY_NOTICES.md"), "."),
]
datas.extend(collect_data_files("faster_whisper", includes=["assets/*.onnx"]))

if DISTRIBUTION == "app-store":
    required_model_files = {"config.json", "model.bin", "tokenizer.json", "vocabulary.txt"}
    if not WHISPER_MODEL_DIR.is_dir():
        raise SystemExit(f"Bundled Whisper model directory not found: {WHISPER_MODEL_DIR}")
    missing_model_files = sorted(name for name in required_model_files if not (WHISPER_MODEL_DIR / name).is_file())
    if missing_model_files:
        raise SystemExit("Incomplete bundled Whisper model: " + ", ".join(missing_model_files))
    datas.append((str(WHISPER_MODEL_DIR), "models/faster-whisper-medium"))

    required_licenses = {
        "PyAV-LICENSE.txt",
        "COPYING.LGPLv3",
        "Faster-Whisper-LICENSE.txt",
        "Whisper-Medium-LICENSE.txt",
    }
    if not LICENSE_DIR.is_dir():
        raise SystemExit(f"License staging directory not found: {LICENSE_DIR}")
    missing_licenses = sorted(name for name in required_licenses if not (LICENSE_DIR / name).is_file())
    if missing_licenses:
        raise SystemExit("Incomplete license staging directory: " + ", ".join(missing_licenses))
    datas.append((str(LICENSE_DIR), "licenses"))

hiddenimports = []
for package in ("uvicorn", "backports", "app", "desktop"):
    hiddenimports.extend(collect_submodules(package))
hiddenimports.extend(["AppKit", "Cocoa", "Foundation", "WebKit", "objc"])

excluded_packages = ["tkinter", "pytest", "librosa", "numba", "llvmlite", "TTS"]
if DISTRIBUTION == "app-store":
    excluded_packages.extend([
        "audiosr", "demucs", "df", "kokoro", "pyannote", "torch", "torchaudio"
    ])

a = Analysis(
    [str(ROOT / "desktop" / "launcher.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excluded_packages,
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
        "CFBundleVersion": BUILD_NUMBER,
        "LSApplicationCategoryType": "public.app-category.music",
        "LSMinimumSystemVersion": "13.0",
        "NSHighResolutionCapable": True,
        "NSLocalNetworkUsageDescription": "AudioEnhancerMAX uses the local network only when connecting to trusted edge workers selected by the user.",
        "NSHumanReadableCopyright": "Copyright (c) 2026 Fabrizio Degni",
        "ITSAppUsesNonExemptEncryption": False,
        "LSMultipleInstancesProhibited": True,
        "NSQuitAlwaysKeepsWindows": False,
        "AEMAXDistribution": DISTRIBUTION,
    },
)
