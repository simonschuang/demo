#!/bin/bash
# Build Agent Release Packages
# This script builds agent binaries for multiple platforms and creates release ZIP files

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLIENT_DIR="${SCRIPT_DIR}/../client"
OUTPUT_DIR="${SCRIPT_DIR}/releases"
SCRIPTS_DIR="${SCRIPT_DIR}/releases/scripts"

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

# Platforms to build
PLATFORMS=(
    "linux/amd64"
    "linux/arm64"
    "darwin/amd64"
    "darwin/arm64"
    "windows/amd64"
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
    OS=$(echo "$PLATFORM" | cut -d'/' -f1)
    ARCH=$(echo "$PLATFORM" | cut -d'/' -f2)
    
    print_msg "Building for ${OS}/${ARCH}..."
    
    # Set output filename
    if [ "$OS" = "windows" ]; then
        BINARY_NAME="agent.exe"
    else
        BINARY_NAME="agent"
    fi
    
    # Create temp directory for this build
    TEMP_DIR=$(mktemp -d)
    PACKAGE_NAME="install-${OS}-${ARCH}-${VERSION}"
    PACKAGE_DIR="${TEMP_DIR}/${PACKAGE_NAME}"
    mkdir -p "${PACKAGE_DIR}"
    
    # Build binary
    GOOS=$OS GOARCH=$ARCH go build -ldflags="-s -w -X main.Version=${VERSION}" \
        -o "${PACKAGE_DIR}/${BINARY_NAME}" ./cmd/agent/
    
    # Copy scripts
    cp "${SCRIPTS_DIR}/install.sh" "${PACKAGE_DIR}/"
    cp "${SCRIPTS_DIR}/run.sh" "${PACKAGE_DIR}/"
    cp "${SCRIPTS_DIR}/svc.sh" "${PACKAGE_DIR}/"
    cp "${SCRIPTS_DIR}/config.yaml" "${PACKAGE_DIR}/"
    
    # For Windows, create .bat versions
    if [ "$OS" = "windows" ]; then
        cat > "${PACKAGE_DIR}/run.bat" << 'EOF'
@echo off
echo Starting Agent Monitor Agent...
agent.exe -config config.yaml
pause
EOF
    fi
    
    # Create ZIP file
    ZIP_NAME="${PACKAGE_NAME}.zip"
    cd "${TEMP_DIR}"
    zip -r "${VERSION_DIR}/${ZIP_NAME}" "${PACKAGE_NAME}"
    cd "$CLIENT_DIR"
    
    # Cleanup temp directory
    rm -rf "${TEMP_DIR}"
    
    print_msg "Created: ${ZIP_NAME}"
done

# Create checksums
print_msg "Creating checksums..."
cd "${VERSION_DIR}"
sha256sum *.zip > checksums.txt

# Create latest symlink
cd "${OUTPUT_DIR}"
rm -f latest
ln -s "${VERSION}" latest

print_msg ""
print_msg "Build complete!"
print_msg "Release files are in: ${VERSION_DIR}"
print_msg ""
ls -la "${VERSION_DIR}"
