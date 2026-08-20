#!/bin/zsh
set -euo pipefail

ROOT="${0:A:h:h}"
VERSION="3.7.0"
BUILD_NUMBER="${AEMAX_BUILD_NUMBER:-3.7.2}"
BUILD_DIR="${ROOT}/build/macos"
DIST_DIR="${ROOT}/dist/macos"
ICON_SOURCE="${ROOT}/packaging/macos/AudioEnhancerMAX.svg"
ICONSET="${BUILD_DIR}/AudioEnhancerMAX.iconset"
ICON="${ROOT}/packaging/macos/AudioEnhancerMAX.icns"
PYTHON="${AEMAX_PYTHON:-${ROOT}/venv/bin/python}"
DISTRIBUTION="${AEMAX_DISTRIBUTION:-direct}"
APP_IDENTITY="${AEMAX_APP_IDENTITY:-Developer ID Application: Fabrizio Degni (BR9VY292BU)}"
SKIP_BUILD="${AEMAX_SKIP_BUILD:-0}"
NOTARY_PROFILE="${AEMAX_NOTARY_PROFILE:-}"

if [[ "${DISTRIBUTION}" != "direct" ]]; then
    print -u2 "This script builds the direct-download DMG only. The App Store package requires its dedicated signed workflow."
    exit 1
fi

if [[ "$(uname -m)" != "arm64" ]]; then
    print -u2 "This release target is Apple Silicon (arm64)."
    exit 1
fi

if [[ ! -x "${PYTHON}" ]]; then
    print -u2 "Python environment not found: ${PYTHON}"
    exit 1
fi

if ! security find-identity -v -p codesigning | grep -Fq "\"${APP_IDENTITY}\""; then
    print -u2 "Developer ID signing identity not available with its private key: ${APP_IDENTITY}"
    exit 1
fi

function sign_nested_code() {
    local app_path="$1"
    local main_executable="${app_path}/Contents/MacOS/AudioEnhancerMAX"
    local item description framework

    while IFS= read -r -d '' item; do
        [[ "${item}" == "${main_executable}" ]] && continue
        description="$(file -b "${item}")"
        [[ "${description}" == *"Mach-O"* ]] || continue
        codesign --force --sign "${APP_IDENTITY}" --timestamp --options runtime "${item}"
    done < <(find "${app_path}/Contents" -type f -print0)

    while IFS= read -r framework; do
        codesign --force --sign "${APP_IDENTITY}" --timestamp --options runtime "${framework}"
    done < <(find "${app_path}/Contents" -type d -name '*.framework' | awk '{ print length, $0 }' | sort -rn | cut -d' ' -f2-)
}

APP_PATH="${DIST_DIR}/AudioEnhancerMAX.app"

if [[ "${SKIP_BUILD}" == "1" ]]; then
    [[ -d "${APP_PATH}" ]] || { print -u2 "Existing app bundle not found: ${APP_PATH}"; exit 1; }
    print "Reusing existing app bundle: ${APP_PATH}"
else
    "${PYTHON}" -m pip install -r "${ROOT}/packaging/macos/requirements-build.txt"

    rm -rf "${BUILD_DIR}" "${DIST_DIR}" "${ICONSET}"
    mkdir -p "${BUILD_DIR}" "${DIST_DIR}" "${ICONSET}"

    qlmanage -t -s 1024 -o "${BUILD_DIR}" "${ICON_SOURCE}" >/dev/null 2>&1
    MASTER_ICON="${BUILD_DIR}/AudioEnhancerMAX.svg.png"

    for size in 16 32 128 256 512; do
        sips -z "${size}" "${size}" "${MASTER_ICON}" --out "${ICONSET}/icon_${size}x${size}.png" >/dev/null
        double=$((size * 2))
        sips -z "${double}" "${double}" "${MASTER_ICON}" --out "${ICONSET}/icon_${size}x${size}@2x.png" >/dev/null
    done
    iconutil -c icns "${ICONSET}" -o "${ICON}"

    AEMAX_DISTRIBUTION="${DISTRIBUTION}" \
    AEMAX_MARKETING_VERSION="${VERSION}" \
    AEMAX_BUILD_NUMBER="${BUILD_NUMBER}" \
    "${PYTHON}" -m PyInstaller \
        --noconfirm \
        --clean \
        --workpath "${BUILD_DIR}/pyinstaller" \
        --distpath "${DIST_DIR}" \
        "${ROOT}/packaging/macos/AudioEnhancerMAX.spec"
fi

SIGNING_ROOT="$(mktemp -d /tmp/audioenhancermax-sign.XXXXXX)"
trap 'rm -rf "${SIGNING_ROOT}"' EXIT
SIGNED_APP="${SIGNING_ROOT}/AudioEnhancerMAX.app"
DMG_ROOT="${SIGNING_ROOT}/dmg"
DMG_TEMP="${SIGNING_ROOT}/AudioEnhancerMAX-v${VERSION}-macOS-arm64.dmg"
DMG_PATH="${DIST_DIR}/AudioEnhancerMAX-v${VERSION}-macOS-arm64.dmg"

ditto --norsrc --noqtn "${APP_PATH}" "${SIGNED_APP}"
xattr -cr "${SIGNED_APP}"
sign_nested_code "${SIGNED_APP}"
codesign --force --sign "${APP_IDENTITY}" --timestamp --options runtime "${SIGNED_APP}"
codesign --verify --deep --strict --verbose=2 "${SIGNED_APP}"

rm -rf "${DMG_ROOT}" "${DMG_PATH}" "${DMG_PATH}.sha256"
mkdir -p "${DMG_ROOT}"
ditto --norsrc --noqtn "${SIGNED_APP}" "${DMG_ROOT}/AudioEnhancerMAX.app"
ln -s /Applications "${DMG_ROOT}/Applications"
hdiutil create \
    -volname "AudioEnhancerMAX ${VERSION}" \
    -srcfolder "${DMG_ROOT}" \
    -ov \
    -format UDZO \
    "${DMG_TEMP}"

cp "${DMG_TEMP}" "${DMG_PATH}"
codesign --force --sign "${APP_IDENTITY}" --timestamp "${DMG_PATH}"
codesign --verify --verbose=2 "${DMG_PATH}"

if [[ -n "${NOTARY_PROFILE}" ]]; then
    xcrun notarytool submit "${DMG_PATH}" \
        --keychain-profile "${NOTARY_PROFILE}" \
        --wait
    xcrun stapler staple "${DMG_PATH}"
    xcrun stapler validate "${DMG_PATH}"
    spctl -a -vvv -t open --context context:primary-signature "${DMG_PATH}"
else
    print "Notarization skipped. Set AEMAX_NOTARY_PROFILE to a notarytool Keychain profile for public distribution."
fi

(
    cd "${DIST_DIR}"
    shasum -a 256 "${DMG_PATH:t}" > "${DMG_PATH:t}.sha256"
)
print "Built intermediate ${APP_PATH}"
print "Built ${DMG_PATH}"
print "Version: ${VERSION} (${BUILD_NUMBER})"
print "Application identity: ${APP_IDENTITY}"
print "Distribution channel: ${DISTRIBUTION}"
