# Agent Client

Golang Agent Client for Agent Monitor Platform.

## Version

Current version: **v1.0.0**

Check version:
```bash
./agent -version
```

## Requirements

- Go 1.21+

## Build

### Development Build

```bash
# Build for current platform
go build -o agent ./cmd/agent
```

### Production Build (with version info)

```bash
# Using Makefile (recommended)
make build-release VERSION=1.0.0

# Or manually with ldflags
VERSION=1.0.0
BUILD_TIME=$(date -u '+%Y-%m-%d %H:%M:%S UTC')
go build -ldflags "-X 'main.version=v${VERSION}' -X 'main.buildTime=${BUILD_TIME}'" -o agent ./cmd/agent
```

### Cross-compile for Different Platforms

```bash
# Using Makefile
make build-linux VERSION=1.0.0
make build-windows VERSION=1.0.0
make build-all VERSION=1.0.0

# Or manually
GOOS=linux GOARCH=amd64 go build -ldflags "-X 'main.version=v1.0.0'" -o agent-linux-amd64 ./cmd/agent
GOOS=darwin GOARCH=arm64 go build -ldflags "-X 'main.version=v1.0.0'" -o agent-darwin-arm64 ./cmd/agent
GOOS=windows GOARCH=amd64 go build -ldflags "-X 'main.version=v1.0.0'" -o agent-windows-amd64.exe ./cmd/agent
```

## Configuration

Create a `config.yaml` file:

```yaml
server_url: "agent.example.com"
client_id: "your-client-uuid"
client_token: "your-client-token"
ws_scheme: "wss"
ws_path: "/ws"
heartbeat_interval: 15
reconnect_interval: 5
collect_interval: 60
log_level: "info"
```

## Run

```bash
./agent -config ./config.yaml
```

## Features

- WebSocket connection with automatic reconnection
- Heartbeat mechanism (15 second interval)
- System inventory collection:
  - Host information (hostname, OS, platform, architecture)
  - CPU information (count, model)
  - Memory information (total, used, free)
  - Disk information (total, used, free)
  - Network information (IP addresses, MAC addresses)
- BMC (Baseboard Management Controller) support:
  - Collect hardware inventory from BMC via Redfish API or IPMI
  - Supports hybrid mode (local + BMC) or BMC-only mode
- Graceful shutdown on SIGINT/SIGTERM

## BMC Mode

When managing physical servers with BMC (iDRAC, iLO, etc.), you can configure the agent to collect hardware information from the BMC instead of or in addition to the local host.

### Configuration

Add BMC configuration to your `config.yaml`:

```yaml
bmc:
  enabled: true                 # Enable BMC collection
  ip: "192.168.1.100"          # BMC IP address
  username: "admin"            # BMC username
  password: "password"         # BMC password
  protocol: "redfish"          # "redfish" (recommended) or "ipmi"
  port: 443                    # BMC port (443 for Redfish, 623 for IPMI)
  insecure_skip_verify: true   # Skip TLS certificate verification
```

### Collection Modes

1. **Local-only** (default): Collects system information from the host running the agent
2. **Hybrid mode**: When BMC is enabled, collects from both local host and BMC
3. **BMC-only mode**: Use `-bmc-only` flag to collect only from BMC

```bash
# Hybrid mode (local + BMC)
./agent -config ./config.yaml

# BMC-only mode
./agent -config ./config.yaml -bmc-only
```

### BMC Data Collected

When BMC mode is enabled, the following information is collected:

- System: Manufacturer, model, serial number, BIOS version
- Processors: Model, cores, threads, speed
- Memory: Total capacity, module details
- Storage: Drives, capacity, media type
- Network: Port information, MAC/IP addresses
- Power: State, power supply information
- Thermal: Fan status, temperature readings
- Health: Overall system health status
