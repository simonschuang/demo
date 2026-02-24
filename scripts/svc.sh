#!/bin/bash
# Agent Service Management Script
# Install, uninstall, and manage the agent as a systemd service

set -e

# Configuration
SERVICE_NAME="agent"
INSTALL_DIR="/opt/agent"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_msg() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
check_root() {
    if [ "$EUID" -ne 0 ]; then
        print_error "This command requires root privileges"
        print_error "Please run: sudo $0 $1"
        exit 1
    fi
}

# Install service
install_service() {
    check_root "install"
    
    print_msg "Installing Agent service..."
    
    # Check if config is properly configured
    if grep -q 'client_id: ""' "${SCRIPT_DIR}/config.yaml" 2>/dev/null || \
       grep -q "client_id: \"YOUR_CLIENT_ID\"" "${SCRIPT_DIR}/config.yaml" 2>/dev/null; then
        print_error "Config file is not configured"
        print_error "Please run: ./install.sh --token <your_token> first"
        exit 1
    fi
    
    # Create directories
    print_msg "Creating directories..."
    mkdir -p "${INSTALL_DIR}/bin"
    mkdir -p "${INSTALL_DIR}/config"
    mkdir -p "${INSTALL_DIR}/logs"
    mkdir -p "${INSTALL_DIR}/scripts"
    
    # Copy files
    print_msg "Copying files..."
    cp "${SCRIPT_DIR}/agent" "${INSTALL_DIR}/bin/agent"
    cp "${SCRIPT_DIR}/config.yaml" "${INSTALL_DIR}/config/config.yaml"
    cp "${SCRIPT_DIR}/run.sh" "${INSTALL_DIR}/scripts/run.sh"
    cp "${SCRIPT_DIR}/svc.sh" "${INSTALL_DIR}/scripts/svc.sh"
    
    # Set permissions
    chmod +x "${INSTALL_DIR}/bin/agent"
    chmod +x "${INSTALL_DIR}/scripts/run.sh"
    chmod +x "${INSTALL_DIR}/scripts/svc.sh"
    chmod 600 "${INSTALL_DIR}/config/config.yaml"
    
    # Create systemd service file
    print_msg "Creating systemd service..."
    cat > "/etc/systemd/system/${SERVICE_NAME}.service" << EOF
[Unit]
Description=Agent Monitor Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=${INSTALL_DIR}
ExecStart=${INSTALL_DIR}/bin/agent -config ${INSTALL_DIR}/config/config.yaml
Restart=always
RestartSec=5
StandardOutput=append:${INSTALL_DIR}/logs/agent.log
StandardError=append:${INSTALL_DIR}/logs/agent.log

[Install]
WantedBy=multi-user.target
EOF
    
    # Reload systemd
    systemctl daemon-reload
    
    # Enable service
    systemctl enable "${SERVICE_NAME}"
    
    print_msg "Service installed successfully!"
    print_msg ""
    print_msg "Commands:"
    print_msg "  Start:   sudo systemctl start ${SERVICE_NAME}"
    print_msg "  Stop:    sudo systemctl stop ${SERVICE_NAME}"
    print_msg "  Status:  sudo systemctl status ${SERVICE_NAME}"
    print_msg "  Logs:    sudo journalctl -u ${SERVICE_NAME} -f"
    print_msg ""
    print_msg "Or use this script:"
    print_msg "  sudo ./svc.sh start"
    print_msg "  sudo ./svc.sh stop"
    print_msg "  sudo ./svc.sh status"
    print_msg "  sudo ./svc.sh logs"
}

# Uninstall service
uninstall_service() {
    check_root "uninstall"
    
    print_msg "Uninstalling Agent service..."
    
    # Stop service if running
    if systemctl is-active --quiet "${SERVICE_NAME}" 2>/dev/null; then
        print_msg "Stopping service..."
        systemctl stop "${SERVICE_NAME}"
    fi
    
    # Disable service
    if systemctl is-enabled --quiet "${SERVICE_NAME}" 2>/dev/null; then
        print_msg "Disabling service..."
        systemctl disable "${SERVICE_NAME}"
    fi
    
    # Remove service file
    if [ -f "/etc/systemd/system/${SERVICE_NAME}.service" ]; then
        print_msg "Removing service file..."
        rm -f "/etc/systemd/system/${SERVICE_NAME}.service"
        systemctl daemon-reload
    fi
    
    # Remove installation directory
    if [ -d "$INSTALL_DIR" ]; then
        print_msg "Removing installation directory..."
        rm -rf "$INSTALL_DIR"
    fi
    
    print_msg "Service uninstalled successfully!"
}

# Start service
start_service() {
    check_root "start"
    
    if ! systemctl is-enabled --quiet "${SERVICE_NAME}" 2>/dev/null; then
        print_error "Service is not installed"
        print_error "Please run: sudo ./svc.sh install"
        exit 1
    fi
    
    print_msg "Starting ${SERVICE_NAME} service..."
    systemctl start "${SERVICE_NAME}"
    print_msg "Service started"
}

# Stop service
stop_service() {
    check_root "stop"
    
    print_msg "Stopping ${SERVICE_NAME} service..."
    systemctl stop "${SERVICE_NAME}"
    print_msg "Service stopped"
}

# Restart service
restart_service() {
    check_root "restart"
    
    print_msg "Restarting ${SERVICE_NAME} service..."
    systemctl restart "${SERVICE_NAME}"
    print_msg "Service restarted"
}

# Show status
show_status() {
    systemctl status "${SERVICE_NAME}" --no-pager || true
}

# Show logs
show_logs() {
    if [ -f "${INSTALL_DIR}/logs/agent.log" ]; then
        tail -f "${INSTALL_DIR}/logs/agent.log"
    else
        journalctl -u "${SERVICE_NAME}" -f
    fi
}

# Show usage
usage() {
    echo "Usage: $0 <command>"
    echo ""
    echo "Commands:"
    echo "  install    Install agent as systemd service"
    echo "  uninstall  Uninstall agent service and remove files"
    echo "  start      Start the agent service"
    echo "  stop       Stop the agent service"
    echo "  restart    Restart the agent service"
    echo "  status     Show service status"
    echo "  logs       Show and follow service logs"
    echo ""
    echo "Examples:"
    echo "  sudo $0 install"
    echo "  sudo $0 start"
    echo "  $0 status"
    exit 1
}

# Main
case "${1:-}" in
    install)
        install_service
        ;;
    uninstall)
        uninstall_service
        ;;
    start)
        start_service
        ;;
    stop)
        stop_service
        ;;
    restart)
        restart_service
        ;;
    status)
        show_status
        ;;
    logs)
        show_logs
        ;;
    *)
        usage
        ;;
esac
