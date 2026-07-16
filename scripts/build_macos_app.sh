#!/bin/zsh
set -euo pipefail

ROOT="${0:A:h:h}"
VERSION="3.5.2"
BUILD_DIR="${ROOT}/build/macos"
DIST_DIR="${ROOT}/dist/macos"
ICON_SOURCE="${ROOT}/packaging/macos/AudioEnhancerMAX.svg"
ICONSET="${BUILD_DIR}/AudioEnhancerMAX.iconset"
ICON="${ROOT}/packaging/macos/AudioEnhancerMAX.icns"
PYTHON="${AEMAX_PYTHON:-${ROOT}/venv/bin/python}"
DISTRIBUTION="${AEMAX_DISTRIBUTION:-direct}"

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

"${PYTHON}" -m PyInstaller \
    --noconfirm \
    --clean \
    --workpath "${BUILD_DIR}/pyinstaller" \
    --distpath "${DIST_DIR}" \
    "${ROOT}/packaging/macos/AudioEnhancerMAX.spec"

APP_PATH="${DIST_DIR}/AudioEnhancerMAX.app"
SIGNING_ROOT="$(mktemp -d /tmp/audioenhancermax-sign.XXXXXX)"
trap 'rm -rf "${SIGNING_ROOT}"' EXIT
SIGNED_APP="${SIGNING_ROOT}/AudioEnhancerMAX.app"
DMG_ROOT="${SIGNING_ROOT}/dmg"
DMG_TEMP="${SIGNING_ROOT}/AudioEnhancerMAX-v${VERSION}-macOS-arm64.dmg"
DMG_PATH="${DIST_DIR}/AudioEnhancerMAX-v${VERSION}-macOS-arm64.dmg"

ditto --norsrc --noqtn "${APP_PATH}" "${SIGNED_APP}"
xattr -cr "${SIGNED_APP}"
codesign --force --deep --sign - --timestamp=none "${SIGNED_APP}"
codesign --verify --deep --strict "${SIGNED_APP}"

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

shasum -a 256 "${DMG_PATH}" > "${DMG_PATH}.sha256"
print "Built intermediate ${APP_PATH}"
print "Built ${DMG_PATH}"
print "Distribution channel: ${DISTRIBUTION}"
