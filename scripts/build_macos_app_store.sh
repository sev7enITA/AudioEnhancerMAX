#!/bin/zsh
set -euo pipefail

ROOT="${0:A:h:h}"
VERSION="${AEMAX_MARKETING_VERSION:-3.8.3}"
BUILD_NUMBER="${AEMAX_BUILD_NUMBER:-3.8.4}"
BUILD_DIR="${ROOT}/build/macos-app-store"
DIST_DIR="${ROOT}/dist/macos-app-store"
ICON_SOURCE="${ROOT}/packaging/macos/AudioEnhancerMAX.svg"
ICONSET="${BUILD_DIR}/AudioEnhancerMAX.iconset"
ICON="${ROOT}/packaging/macos/AudioEnhancerMAX.icns"
PYTHON="${AEMAX_PYTHON:-${ROOT}/venv/bin/python}"
PYTHON_FRAMEWORK="${AEMAX_PYTHON_FRAMEWORK:-}"
APP_IDENTITY="${AEMAX_APP_IDENTITY:-3rd Party Mac Developer Application: Fabrizio Degni (BR9VY292BU)}"
INSTALLER_IDENTITY="${AEMAX_INSTALLER_IDENTITY:-3rd Party Mac Developer Installer: Fabrizio Degni (BR9VY292BU)}"
APP_ENTITLEMENTS="${ROOT}/packaging/macos/app-store-entitlements.plist"
CHILD_ENTITLEMENTS="${ROOT}/packaging/macos/app-store-child-entitlements.plist"
PRIVACY_MANIFEST="${ROOT}/packaging/macos/PrivacyInfo.xcprivacy"
THIRD_PARTY_NOTICES="${ROOT}/packaging/macos/THIRD_PARTY_NOTICES.md"
DEFAULT_PROVISIONING_PROFILE="${HOME}/Documents/AudioEnhancerMAX_Mac_App_Store_37.provisionprofile"
PROVISIONING_PROFILE="${AEMAX_PROVISIONING_PROFILE:-${DEFAULT_PROVISIONING_PROFILE}}"
MODEL_CACHE_ROOT="${XDG_CACHE_HOME:-${HOME}/.cache}/huggingface/hub/models--Systran--faster-whisper-medium/snapshots"
WHISPER_MODEL_DIR="${AEMAX_WHISPER_MODEL_DIR:-}"
LICENSE_DIR="${BUILD_DIR}/licenses"
PKG_PATH="${DIST_DIR}/AudioEnhancerMAX-v${VERSION}-build-${BUILD_NUMBER}-MacAppStore.pkg"
REUSABLE_APP="${BUILD_DIR}/dist/AudioEnhancerMAX.app"
SIGNING_ROOT="$(mktemp -d /tmp/audioenhancermax-mas-sign.XXXXXX)"
SIGNED_APP="${SIGNING_ROOT}/AudioEnhancerMAX.app"
PKG_TEMP="${SIGNING_ROOT}/AudioEnhancerMAX-v${VERSION}-build-${BUILD_NUMBER}-MacAppStore.pkg"
SKIP_BUILD="${AEMAX_SKIP_BUILD:-0}"
SKIP_NESTED_SIGN="${AEMAX_SKIP_NESTED_SIGN:-0}"

# A relocatable Python.org framework needs these paths exported after zsh
# starts; macOS strips DYLD_* variables while launching protected shells.
if [[ -n "${PYTHON_FRAMEWORK}" ]]; then
    [[ -d "${PYTHON_FRAMEWORK}/Versions/3.11" ]] || {
        print -u2 "Python framework not found: ${PYTHON_FRAMEWORK}"
        exit 1
    }
    export DYLD_FRAMEWORK_PATH="${PYTHON_FRAMEWORK:h}"
    export DYLD_LIBRARY_PATH="${PYTHON_FRAMEWORK}/Versions/3.11/lib"
fi

trap 'rm -rf "${SIGNING_ROOT}"' EXIT

function require_identity() {
    local identity="$1"
    if ! security find-identity -v | grep -Fq "\"${identity}\""; then
        print -u2 "Signing identity not available with its private key: ${identity}"
        exit 1
    fi
}

function validate_profile() {
    local profile="$1"
    local decoded
    decoded="$(mktemp /tmp/audioenhancermax-profile.XXXXXX.plist)"
    security cms -D -i "${profile}" > "${decoded}"

    if ! plutil -extract Platform xml1 -o - "${decoded}" | grep -q '<string>OSX</string>'; then
        rm -f "${decoded}"
        print -u2 "The provisioning profile is not a macOS profile: ${profile}"
        exit 1
    fi

    local application_identifier
    application_identifier="$(/usr/libexec/PlistBuddy -c 'Print :Entitlements:com.apple.application-identifier' "${decoded}" 2>/dev/null || /usr/libexec/PlistBuddy -c 'Print :Entitlements:application-identifier' "${decoded}")"
    rm -f "${decoded}"

    if [[ "${application_identifier}" != "BR9VY292BU.com.fabriziodegni.audioenhancermax" ]]; then
        print -u2 "Provisioning profile App ID mismatch: ${application_identifier}"
        exit 1
    fi
}

function sign_nested_code() {
    local app_path="$1"
    local main_executable="${app_path}/Contents/MacOS/AudioEnhancerMAX"
    local item description

    while IFS= read -r -d '' item; do
        [[ "${item}" == "${main_executable}" ]] && continue
        description="$(file -b "${item}")"
        [[ "${description}" == *"Mach-O"* ]] || continue

        if [[ "${description}" == *"executable"* ]]; then
            codesign --force --sign "${APP_IDENTITY}" --timestamp --entitlements "${CHILD_ENTITLEMENTS}" "${item}"
        else
            codesign --force --sign "${APP_IDENTITY}" --timestamp "${item}"
        fi
    done < <(find "${app_path}/Contents" -type f -print0)

    while IFS= read -r framework; do
        codesign --force --sign "${APP_IDENTITY}" --timestamp "${framework}"
    done < <(find "${app_path}/Contents" -type d -name '*.framework' | awk '{ print length, $0 }' | sort -rn | cut -d' ' -f2-)
}

if [[ "$(uname -m)" != "arm64" ]]; then
    print -u2 "This App Store release target is Apple Silicon (arm64)."
    exit 1
fi

if [[ ! -x "${PYTHON}" ]]; then
    print -u2 "Python environment not found: ${PYTHON}"
    exit 1
fi

if [[ -z "${WHISPER_MODEL_DIR}" ]]; then
    WHISPER_MODEL_DIR="$(find "${MODEL_CACHE_ROOT}" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | head -n 1)"
fi
if [[ ! -d "${WHISPER_MODEL_DIR}" ]]; then
    print -u2 "Faster-Whisper Medium model snapshot not found. Set AEMAX_WHISPER_MODEL_DIR."
    exit 1
fi
for model_file in config.json model.bin tokenizer.json vocabulary.txt; do
    [[ -f "${WHISPER_MODEL_DIR}/${model_file}" ]] || {
        print -u2 "Incomplete Faster-Whisper model: missing ${model_file}"
        exit 1
    }
done

require_identity "${APP_IDENTITY}"
require_identity "${INSTALLER_IDENTITY}"
plutil -lint "${APP_ENTITLEMENTS}" "${CHILD_ENTITLEMENTS}" >/dev/null
plutil -lint "${PRIVACY_MANIFEST}" >/dev/null

[[ -f "${PROVISIONING_PROFILE}" ]] || {
    print -u2 "Mac App Store provisioning profile not found: ${PROVISIONING_PROFILE}"
    print -u2 "Set AEMAX_PROVISIONING_PROFILE to the AudioEnhancerMAX distribution profile."
    exit 1
}
validate_profile "${PROVISIONING_PROFILE}"

if [[ "${SKIP_BUILD}" == "1" ]]; then
    [[ -d "${REUSABLE_APP}" ]] || { print -u2 "Existing app bundle not found: ${REUSABLE_APP}"; exit 1; }
    print "Reusing existing app bundle: ${REUSABLE_APP}"
    ditto --norsrc --noextattr --noqtn --noacl "${REUSABLE_APP}" "${SIGNED_APP}"
else
    "${PYTHON}" -m pip install --upgrade \
        -r "${ROOT}/packaging/macos/requirements-runtime-app-store.txt" \
        -r "${ROOT}/packaging/macos/requirements-build.txt" \
        -c "${ROOT}/packaging/macos/requirements-app-store-lock.txt"

    "${PYTHON}" - <<'PY'
import importlib.util
import sysconfig

target = str(sysconfig.get_config_var("MACOSX_DEPLOYMENT_TARGET") or "0")
if int(target.split(".")[0]) > 13:
    raise SystemExit(f"Python deployment target {target} exceeds supported macOS 13")
for forbidden in ("librosa", "numba", "llvmlite", "TTS"):
    if importlib.util.find_spec(forbidden) is not None:
        raise SystemExit(f"Forbidden JIT/runtime dependency present: {forbidden}")
PY
    "${PYTHON}" -m pip check

    # Keep previously signed PKGs available as an audit trail while rebuilding
    # the disposable staging tree for the new build number.
    rm -rf "${BUILD_DIR}"
    mkdir -p "${BUILD_DIR}" "${DIST_DIR}" "${ICONSET}" "${LICENSE_DIR}"

    PYAV_LICENSE="$("${PYTHON}" - <<'PY'
from importlib.metadata import distribution
dist = distribution("av")
for item in dist.files or ():
    if str(item).endswith(("dist-info/licenses/LICENSE.txt", "dist-info/LICENSE.txt")):
        print(dist.locate_file(item))
        break
PY
)"
    FASTER_WHISPER_LICENSE="$("${PYTHON}" - <<'PY'
from importlib.metadata import distribution
dist = distribution("faster-whisper")
for item in dist.files or ():
    if str(item).endswith("dist-info/LICENSE"):
        print(dist.locate_file(item))
        break
PY
)"
    LGPL_LICENSE="$(find -L "$(brew --prefix ffmpeg 2>/dev/null)" -maxdepth 2 -name COPYING.LGPLv3 -type f 2>/dev/null | head -n 1)"
    [[ -f "${PYAV_LICENSE}" ]] || { print -u2 "PyAV license file not found"; exit 1; }
    [[ -f "${FASTER_WHISPER_LICENSE}" ]] || { print -u2 "Faster-Whisper license file not found"; exit 1; }
    [[ -f "${LGPL_LICENSE}" ]] || { print -u2 "LGPLv3 license text not found"; exit 1; }
    cp "${PYAV_LICENSE}" "${LICENSE_DIR}/PyAV-LICENSE.txt"
    cp "${FASTER_WHISPER_LICENSE}" "${LICENSE_DIR}/Faster-Whisper-LICENSE.txt"
    cp "${FASTER_WHISPER_LICENSE}" "${LICENSE_DIR}/Whisper-Medium-LICENSE.txt"
    cp "${LGPL_LICENSE}" "${LICENSE_DIR}/COPYING.LGPLv3"

    qlmanage -t -s 1024 -o "${BUILD_DIR}" "${ICON_SOURCE}" >/dev/null 2>&1
    MASTER_ICON="${BUILD_DIR}/AudioEnhancerMAX.svg.png"

    for size in 16 32 128 256 512; do
        sips -z "${size}" "${size}" "${MASTER_ICON}" --out "${ICONSET}/icon_${size}x${size}.png" >/dev/null
        double=$((size * 2))
        sips -z "${double}" "${double}" "${MASTER_ICON}" --out "${ICONSET}/icon_${size}x${size}@2x.png" >/dev/null
    done
    iconutil -c icns "${ICONSET}" -o "${ICON}"

    AEMAX_DISTRIBUTION=app-store \
    AEMAX_MARKETING_VERSION="${VERSION}" \
    AEMAX_BUILD_NUMBER="${BUILD_NUMBER}" \
    AEMAX_WHISPER_MODEL_DIR="${WHISPER_MODEL_DIR}" \
    AEMAX_LICENSE_DIR="${LICENSE_DIR}" \
    "${PYTHON}" -m PyInstaller \
        --noconfirm \
        --clean \
        --workpath "${BUILD_DIR}/pyinstaller" \
        --distpath "${BUILD_DIR}/dist" \
        "${ROOT}/packaging/macos/AudioEnhancerMAX.spec"

    UNSIGNED_APP="${BUILD_DIR}/dist/AudioEnhancerMAX.app"
    ditto --norsrc --noextattr --noqtn --noacl "${UNSIGNED_APP}" "${SIGNED_APP}"

fi

# A reused PyInstaller bundle may come from an earlier internal build. Stamp
# the requested version before signing so App Store Connect receives a unique
# CFBundleVersion, and embed the distribution profile in both build paths.
/usr/libexec/PlistBuddy -c "Set :CFBundleShortVersionString ${VERSION}" "${SIGNED_APP}/Contents/Info.plist"
/usr/libexec/PlistBuddy -c "Set :CFBundleVersion ${BUILD_NUMBER}" "${SIGNED_APP}/Contents/Info.plist"
cp "${PROVISIONING_PROFILE}" "${SIGNED_APP}/Contents/embedded.provisionprofile"

cp "${PRIVACY_MANIFEST}" "${SIGNED_APP}/Contents/Resources/PrivacyInfo.xcprivacy"

# PyInstaller mirrors top-level data files into Contents/Frameworks with a
# symlink back to Contents/Resources. App Store Connect requires every
# PrivacyInfo.xcprivacy it encounters to be a regular file, so retain only the
# canonical Resources copy and reject any unexpected directory at this path.
FRAMEWORK_PRIVACY_MANIFEST="${SIGNED_APP}/Contents/Frameworks/PrivacyInfo.xcprivacy"
if [[ -L "${FRAMEWORK_PRIVACY_MANIFEST}" || -f "${FRAMEWORK_PRIVACY_MANIFEST}" ]]; then
    rm -f "${FRAMEWORK_PRIVACY_MANIFEST}"
elif [[ -e "${FRAMEWORK_PRIVACY_MANIFEST}" ]]; then
    print -u2 "Invalid privacy manifest path is not a removable file or symlink: ${FRAMEWORK_PRIVACY_MANIFEST}"
    exit 1
fi
[[ -f "${SIGNED_APP}/Contents/Resources/PrivacyInfo.xcprivacy" ]]
[[ ! -e "${FRAMEWORK_PRIVACY_MANIFEST}" && ! -L "${FRAMEWORK_PRIVACY_MANIFEST}" ]]

if [[ "${SKIP_NESTED_SIGN}" == "1" ]]; then
    print "Reusing existing nested code signatures"
else
    sign_nested_code "${SIGNED_APP}"
fi
xattr -cr "${SIGNED_APP}"
codesign --force --sign "${APP_IDENTITY}" --timestamp --entitlements "${APP_ENTITLEMENTS}" "${SIGNED_APP}"
codesign --verify --deep --strict --verbose=2 "${SIGNED_APP}"

SIGNED_ENTITLEMENTS="${SIGNING_ROOT}/signed-main-entitlements.plist"
codesign -d --entitlements :- "${SIGNED_APP}" > "${SIGNED_ENTITLEMENTS}" 2>/dev/null
[[ "$(/usr/libexec/PlistBuddy -c 'Print :com.apple.application-identifier' "${SIGNED_ENTITLEMENTS}")" == "BR9VY292BU.com.fabriziodegni.audioenhancermax" ]] || {
    print -u2 "Signed app is missing the required Mac App Store application identifier"
    exit 1
}
[[ "$(/usr/libexec/PlistBuddy -c 'Print :com.apple.developer.team-identifier' "${SIGNED_ENTITLEMENTS}")" == "BR9VY292BU" ]] || {
    print -u2 "Signed app is missing the required Apple developer team identifier"
    exit 1
}

[[ "$(/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "${SIGNED_APP}/Contents/Info.plist")" == "${VERSION}" ]]
[[ "$(/usr/libexec/PlistBuddy -c 'Print :CFBundleVersion' "${SIGNED_APP}/Contents/Info.plist")" == "${BUILD_NUMBER}" ]]
[[ -f "${SIGNED_APP}/Contents/Frameworks/models/faster-whisper-medium/model.bin" ]] || {
    print -u2 "Signed app is missing the bundled transcription model"
    exit 1
}
VAD_ASSET_DIR="${SIGNED_APP}/Contents/Frameworks/faster_whisper/assets"
if [[ ! -f "${VAD_ASSET_DIR}/silero_vad_v6.onnx" ]] && \
   [[ ! -f "${VAD_ASSET_DIR}/silero_encoder_v5.onnx" || ! -f "${VAD_ASSET_DIR}/silero_decoder_v5.onnx" ]]; then
    print -u2 "Signed app is missing the bundled Whisper VAD assets"
    exit 1
fi
rm -f "${PKG_PATH}" "${PKG_TEMP}"
productbuild \
    --component "${SIGNED_APP}" /Applications \
    --sign "${INSTALLER_IDENTITY}" \
    --timestamp \
    "${PKG_TEMP}"

cp "${PKG_TEMP}" "${PKG_PATH}"
pkgutil --check-signature "${PKG_PATH}"
(cd "${DIST_DIR}" && shasum -a 256 "${PKG_PATH:t}" > "${PKG_PATH:t}.sha256")

print "Built ${PKG_PATH}"
print "Version: ${VERSION} (${BUILD_NUMBER})"
print "Application identity: ${APP_IDENTITY}"
print "Installer identity: ${INSTALLER_IDENTITY}"
print "Provisioning profile: ${PROVISIONING_PROFILE}"
