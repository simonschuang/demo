# Agent Client Makefile

VERSION ?= 1.0.0
BUILD_TIME := $(shell date -u '+%Y-%m-%d %H:%M:%S UTC')
LDFLAGS := -X 'main.version=v$(VERSION)' -X 'main.buildTime=$(BUILD_TIME)'

.PHONY: build build-release build-linux build-windows clean

# Development build
build:
	go build -o agent ./cmd/agent

# Release build with version info
build-release:
	go build -ldflags "$(LDFLAGS)" -o agent ./cmd/agent
	@echo "Built agent v$(VERSION)"

# Cross-compile for Linux amd64
build-linux:
	GOOS=linux GOARCH=amd64 go build -ldflags "$(LDFLAGS)" -o agent-linux-amd64 ./cmd/agent
	@echo "Built agent-linux-amd64 v$(VERSION)"

# Cross-compile for Windows amd64
build-windows:
	GOOS=windows GOARCH=amd64 go build -ldflags "$(LDFLAGS)" -o agent-windows-amd64.exe ./cmd/agent
	@echo "Built agent-windows-amd64.exe v$(VERSION)"

# Build all platforms
build-all: build-linux build-windows
	@echo "Built all platforms v$(VERSION)"

# Clean build artifacts
clean:
	rm -f agent agent-linux-amd64 agent-windows-amd64.exe

# Show version
version:
	@echo "Version: $(VERSION)"
	@echo "Build Time: $(BUILD_TIME)"
