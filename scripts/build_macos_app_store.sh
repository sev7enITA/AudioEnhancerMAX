#!/bin/zsh
set -euo pipefail

ROOT="${0:A:h:h}"
VERSION="${AEMAX_MARKETING_VERSION:-3.7.0}"
BUILD_NUMBER="${AEMAX_BUILD_NUMBER:-3.7.2}"
BUILD_DIR="${ROOT}/build/macos-app-store"
DIST_DIR="${ROOT}/dist/macos-app-store"
ICON_SOURCE="${ROOT}/packaging/macos/AudioEnhancerMAX.svg"
ICONSET="${BUILD_DIR}/AudioEnhancerMAX.iconset"
ICON="${ROOT}/packaging/macos/AudioEnhancerMAX.icns"
PYTHON="${AEMAX_PYTHON:-${ROOT}/venv/bin/python}"
APP_IDENTITY="${AEMAX_APP_IDENTITY:-3rd Party Mac Developer Application: Fabrizio Degni (BR9VY292BU)}"
INSTALLER_IDENTITY="${AEMAX_INSTALLER_IDENTITY:-3rd Party Mac Developer Installer: Fabrizio Degni (BR9VY292BU)}"
APP_ENTITLEMENTS="${ROOT}/packaging/macos/app-store-entitlements.plist"
CHILD_ENTITLEMENTS="${ROOT}/packaging/macos/app-store-child-entitlements.plist"
PRIVACY_MANIFEST="${ROOT}/packaging/macos/PrivacyInfo.xcprivacy"
THIRD_PARTY_NOTICES="${ROOT}/packaging/macos/THIRD_PARTY_NOTICES.md"
PROVISIONING_PROFILE="${AEMAX_PROVISIONING_PROFILE:-}"
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

if [[ -n "${PROVISIONING_PROFILE}" ]]; then
    [[ -f "${PROVISIONING_PROFILE}" ]] || { print -u2 "Provisioning profile not found: ${PROVISIONING_PROFILE}"; exit 1; }
    validate_profile "${PROVISIONING_PROFILE}"
fi

if [[ "${SKIP_BUILD}" == "1" ]]; then
    [[ -d "${REUSABLE_APP}" ]] || { print -u2 "Existing app bundle not found: ${REUSABLE_APP}"; exit 1; }
    print "Reusing existing app bundle: ${REUSABLE_APP}"
    ditto --norsrc --noextattr --noqtn --noacl "${REUSABLE_APP}" "${SIGNED_APP}"
else
    "${PYTHON}" -m pip install -r "${ROOT}/packaging/macos/requirements-build.txt"

    # Keep previously signed PKGs available as an audit trail while rebuilding
    # the disposable staging tree for the new build number.
    rm -rf "${BUILD_DIR}"
    mkdir -p "${BUILD_DIR}" "${DIST_DIR}" "${ICONSET}" "${LICENSE_DIR}"

    PYAV_LICENSE="$("${PYTHON}" - <<'PY'
from importlib.metadata import distribution
dist = distribution("av")
for item in dist.files or ():
    if str(item).endswith("dist-info/licenses/LICENSE.txt"):
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

    if [[ -n "${PROVISIONING_PROFILE}" ]]; then
        cp "${PROVISIONING_PROFILE}" "${SIGNED_APP}/Contents/embedded.provisionprofile"
    fi
fi

cp "${PRIVACY_MANIFEST}" "${SIGNED_APP}/Contents/Resources/PrivacyInfo.xcprivacy"

if [[ "${SKIP_NESTED_SIGN}" == "1" ]]; then
    print "Reusing existing nested code signatures"
else
    sign_nested_code "${SIGNED_APP}"
fi
xattr -cr "${SIGNED_APP}"
codesign --force --sign "${APP_IDENTITY}" --timestamp --entitlements "${APP_ENTITLEMENTS}" "${SIGNED_APP}"
codesign --verify --deep --strict --verbose=2 "${SIGNED_APP}"

[[ "$(/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "${SIGNED_APP}/Contents/Info.plist")" == "${VERSION}" ]]
[[ "$(/usr/libexec/PlistBuddy -c 'Print :CFBundleVersion' "${SIGNED_APP}/Contents/Info.plist")" == "${BUILD_NUMBER}" ]]
[[ -f "${SIGNED_APP}/Contents/Frameworks/models/faster-whisper-medium/model.bin" ]] || {
    print -u2 "Signed app is missing the bundled transcription model"
    exit 1
}
[[ -f "${SIGNED_APP}/Contents/Frameworks/faster_whisper/assets/silero_vad_v6.onnx" ]] || {
    print -u2 "Signed app is missing the bundled Whisper VAD asset"
    exit 1
}
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
if [[ -n "${PROVISIONING_PROFILE}" ]]; then
    print "Provisioning profile: ${PROVISIONING_PROFILE}"
else
    print "Provisioning profile: not embedded (no restricted entitlements)"
fi
