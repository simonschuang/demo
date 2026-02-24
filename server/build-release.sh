#!/bin/bash
# Build Agent Release Packages
# This script builds agent binaries for multiple platforms and creates release packages.
# Linux and macOS are packaged as .tar.gz; Windows is packaged as .zip.

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLIENT_DIR="${SCRIPT_DIR}/../client"
OUTPUT_DIR="${SCRIPT_DIR}/releases"
SCRIPTS_DIR="${SCRIPT_DIR}/../scripts"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_msg() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Get version from argument or default
VERSION="${1:-v0.1.0}"

# Platforms to build: GOOS/GOARCH/PackageOS/PackageArch
# PackageOS and PackageArch are the user-facing names used in filenames.
PLATFORMS=(
    "linux/amd64/linux/x64"
    "linux/arm64/linux/arm64"
    "darwin/amd64/macos/x64"
    "darwin/arm64/macos/arm64"
    "windows/amd64/windows/x64"
)

print_msg "Building Agent Release ${VERSION}"
print_msg "==============================="

# Create output directory
VERSION_DIR="${OUTPUT_DIR}/${VERSION}"
mkdir -p "${VERSION_DIR}"

# Check if client directory exists
if [ ! -d "$CLIENT_DIR" ]; then
    print_error "Client directory not found: $CLIENT_DIR"
    exit 1
fi

# Check if scripts exist
if [ ! -f "${SCRIPTS_DIR}/install.sh" ]; then
    print_error "Scripts not found in: $SCRIPTS_DIR"
    exit 1
fi

cd "$CLIENT_DIR"

# Build for each platform
for PLATFORM in "${PLATFORMS[@]}"; do
    GOOS=$(echo "$PLATFORM" | cut -d'/' -f1)
    GOARCH=$(echo "$PLATFORM" | cut -d'/' -f2)
    PKG_OS=$(echo "$PLATFORM" | cut -d'/' -f3)
    PKG_ARCH=$(echo "$PLATFORM" | cut -d'/' -f4)

    print_msg "Building for ${GOOS}/${GOARCH} (${PKG_OS}/${PKG_ARCH})..."

    # Set output binary filename
    if [ "$GOOS" = "windows" ]; then
        BINARY_NAME="agent.exe"
    else
        BINARY_NAME="agent"
    fi

    # Create temp directory for this build
    TEMP_DIR=$(mktemp -d)
    PACKAGE_NAME="mon-agent-${PKG_OS}-${PKG_ARCH}-${VERSION}"
    PACKAGE_DIR="${TEMP_DIR}/${PACKAGE_NAME}"
    mkdir -p "${PACKAGE_DIR}"

    # Build binary
    GOOS=$GOOS GOARCH=$GOARCH go build -ldflags="-s -w -X main.Version=${VERSION}" \
        -o "${PACKAGE_DIR}/${BINARY_NAME}" ./cmd/agent/

    # Copy scripts
    cp "${SCRIPTS_DIR}/install.sh" "${PACKAGE_DIR}/"
    cp "${SCRIPTS_DIR}/run.sh" "${PACKAGE_DIR}/"
    cp "${SCRIPTS_DIR}/svc.sh" "${PACKAGE_DIR}/"
    cp "${SCRIPTS_DIR}/config.yaml" "${PACKAGE_DIR}/"

    # For Windows: create .bat helper and package as .zip
    # For Linux/macOS: package as .tar.gz
    if [ "$GOOS" = "windows" ]; then
        cat > "${PACKAGE_DIR}/run.bat" << 'EOF'
@echo off
echo Starting Agent Monitor Agent...
agent.exe -config config.yaml
pause
EOF
        ARCHIVE_NAME="${PACKAGE_NAME}.zip"
        cd "${TEMP_DIR}"
        zip -r "${VERSION_DIR}/${ARCHIVE_NAME}" "${PACKAGE_NAME}"
        cd "$CLIENT_DIR"
    else
        ARCHIVE_NAME="${PACKAGE_NAME}.tar.gz"
        cd "${TEMP_DIR}"
        tar czf "${VERSION_DIR}/${ARCHIVE_NAME}" "${PACKAGE_NAME}"
        cd "$CLIENT_DIR"
    fi

    # Cleanup temp directory
    rm -rf "${TEMP_DIR}"

    print_msg "Created: ${ARCHIVE_NAME}"
done

# Create checksums (cover both .tar.gz and .zip)
print_msg "Creating checksums..."
cd "${VERSION_DIR}"
find . -maxdepth 1 \( -name "mon-agent-*.tar.gz" -o -name "mon-agent-*.zip" \) | sort | xargs sha256sum > checksums.txt

# Create latest symlink
cd "${OUTPUT_DIR}"
rm -f latest
ln -s "${VERSION}" latest

print_msg ""
print_msg "Build complete!"
print_msg "Release files are in: ${VERSION_DIR}"
print_msg ""
ls -la "${VERSION_DIR}"
