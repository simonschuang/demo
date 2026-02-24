#!/bin/bash
# Agent Run Script - Foreground Execution
# Run the agent in foreground mode with console output

set -e

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_BIN="${SCRIPT_DIR}/agent"
CONFIG_FILE="${SCRIPT_DIR}/config.yaml"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_msg() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if agent binary exists
if [ ! -f "$AGENT_BIN" ]; then
    print_error "Agent binary not found: $AGENT_BIN"
    exit 1
fi

# Check if config exists
if [ ! -f "$CONFIG_FILE" ]; then
    print_error "Config file not found: $CONFIG_FILE"
    print_error "Please run install.sh first"
    exit 1
fi

# Check if config is properly configured
if grep -q 'client_id: ""' "$CONFIG_FILE" || grep -q "client_id: \"YOUR_CLIENT_ID\"" "$CONFIG_FILE"; then
    print_error "Config file is not configured"
    print_error "Please run: ./install.sh --token <your_token>"
    exit 1
fi

# Make agent executable
chmod +x "$AGENT_BIN"

print_msg "Starting Agent Monitor Agent..."
print_msg "Config: $CONFIG_FILE"
print_msg "Press Ctrl+C to stop"
print_msg ""

# Run agent
exec "$AGENT_BIN" -config "$CONFIG_FILE"
