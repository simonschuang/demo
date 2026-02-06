# Agent Client

Golang Agent Client for Agent Monitor Platform.

## Requirements

- Go 1.21+

## Build

```bash
# Build for current platform
go build -o agent ./cmd/agent

# Cross-compile for different platforms
GOOS=linux GOARCH=amd64 go build -o agent-linux-amd64 ./cmd/agent
GOOS=darwin GOARCH=arm64 go build -o agent-darwin-arm64 ./cmd/agent
GOOS=windows GOARCH=amd64 go build -o agent-windows-amd64.exe ./cmd/agent
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
- Graceful shutdown on SIGINT/SIGTERM
