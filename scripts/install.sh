#!/bin/bash
# Agent Install Script
# This script registers the agent with the server and configures config.yaml

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${SCRIPT_DIR}/config.yaml"

# Default values
SERVER_URL="${SERVER_URL:-}"
INSTALL_TOKEN=""
HOSTNAME=$(hostname)

# Print colored message
print_msg() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Show usage
usage() {
    echo "Usage: $0 --token <install_token> [--server <server_url>] [--hostname <hostname>]"
    echo ""
    echo "Options:"
    echo "  --token     Install token from Web UI (required)"
    echo "  --server    Server URL (e.g., mon.myelintek.com)"
    echo "  --hostname  Hostname for this client (default: system hostname)"
    echo "  --help      Show this help message"
    echo ""
    echo "Example:"
    echo "  $0 --token eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
    exit 1
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --token)
            INSTALL_TOKEN="$2"
            shift 2
            ;;
        --server)
            SERVER_URL="$2"
            shift 2
            ;;
        --hostname)
            HOSTNAME="$2"
            shift 2
            ;;
        --help)
            usage
            ;;
        *)
            print_error "Unknown option: $1"
            usage
            ;;
    esac
done

# Validate required arguments
if [ -z "$INSTALL_TOKEN" ]; then
    print_error "Install token is required"
    usage
fi

# Read server URL from config if not provided
if [ -z "$SERVER_URL" ]; then
    if [ -f "$CONFIG_FILE" ]; then
        SERVER_URL=$(grep "^server_url:" "$CONFIG_FILE" | sed 's/server_url: *"\{0,1\}\([^"]*\)"\{0,1\}/\1/' | tr -d ' ')
    fi
fi

if [ -z "$SERVER_URL" ]; then
    print_error "Server URL is required. Provide via --server or set in config.yaml"
    exit 1
fi

print_msg "Agent Install Script"
print_msg "===================="
print_msg "Server URL: $SERVER_URL"
print_msg "Hostname: $HOSTNAME"
print_msg ""

# Determine protocol (https if server looks like a domain)
if [[ "$SERVER_URL" == *"."* ]] && [[ "$SERVER_URL" != *":"* ]]; then
    API_URL="https://${SERVER_URL}/api/v1/download/register"
    WS_SCHEME="wss"
else
    API_URL="http://${SERVER_URL}/api/v1/download/register"
    WS_SCHEME="ws"
fi

print_msg "Registering client with server..."

# Register client with server
RESPONSE=$(curl -s -X POST "${API_URL}?token=${INSTALL_TOKEN}&hostname=${HOSTNAME}" \
    -H "Content-Type: application/json" \
    2>&1) || {
    print_error "Failed to connect to server"
    print_error "Response: $RESPONSE"
    exit 1
}

# Check for error in response
if echo "$RESPONSE" | grep -q '"detail"'; then
    ERROR_MSG=$(echo "$RESPONSE" | grep -o '"detail":"[^"]*"' | sed 's/"detail":"\([^"]*\)"/\1/')
    print_error "Registration failed: $ERROR_MSG"
    exit 1
fi

# Parse response
CLIENT_ID=$(echo "$RESPONSE" | grep -o '"client_id":"[^"]*"' | sed 's/"client_id":"\([^"]*\)"/\1/')
CLIENT_TOKEN=$(echo "$RESPONSE" | grep -o '"client_token":"[^"]*"' | sed 's/"client_token":"\([^"]*\)"/\1/')

if [ -z "$CLIENT_ID" ] || [ -z "$CLIENT_TOKEN" ]; then
    print_error "Failed to parse server response"
    print_error "Response: $RESPONSE"
    exit 1
fi

print_msg "Registration successful!"
print_msg "Client ID: $CLIENT_ID"

# Update config.yaml
print_msg "Updating config.yaml..."

if [ -f "$CONFIG_FILE" ]; then
    # Update existing config
    sed -i "s|^server_url:.*|server_url: \"${SERVER_URL}\"|" "$CONFIG_FILE"
    sed -i "s|^client_id:.*|client_id: \"${CLIENT_ID}\"|" "$CONFIG_FILE"
    sed -i "s|^client_token:.*|client_token: \"${CLIENT_TOKEN}\"|" "$CONFIG_FILE"
    sed -i "s|^ws_scheme:.*|ws_scheme: \"${WS_SCHEME}\"|" "$CONFIG_FILE"
else
    print_error "config.yaml not found in ${SCRIPT_DIR}"
    exit 1
fi

print_msg "Configuration updated successfully!"
print_msg ""
print_msg "Next steps:"
print_msg "  1. Run agent in foreground: ./run.sh"
print_msg "  2. Or install as service:   sudo ./svc.sh install && sudo ./svc.sh start"
print_msg ""
print_msg "Installation complete!"
