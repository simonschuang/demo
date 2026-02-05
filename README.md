# demo

Demo repository for testing and development.

## Documentation

📚 Complete architecture design documentation is available in the [docs](./docs/) directory.

### Quick Links

- **[Documentation Index](./docs/README.md)** - Main documentation portal
- **[Architecture Overview](./docs/architecture/overview.md)** - System architecture overview
- **[Architecture Documentation](./docs/architecture/README.md)** - Complete architecture design documents

### Architecture Documents

The architecture documentation includes:

1. **System Architecture Overview** - Client-Server architecture, core components, connection mechanisms
2. **Server Design** - Python implementation, REST API, WebSocket management
3. **Client Design** - Golang implementation, heartbeat mechanism, inventory collection
4. **WebSocket Protocol** - Communication protocol, message formats, error handling
5. **Installation & Distribution** - install.sh, run.sh, svc.sh script designs
6. **Data Model** - Database schema, Redis structures, indexing strategies
7. **Kubernetes Deployment** - K8s resource configurations, Ingress, TLS settings
8. **Security Design** - Authentication, encryption, audit monitoring

### System Features

- 🐍 **Server**: Python implementation deployed on Kubernetes
- 🐹 **Client**: Golang implementation supporting multiple platforms (Linux/macOS/Windows)
- 🔐 **Security**: HTTPS/WSS encryption, token-based authentication
- 💓 **Heartbeat**: 15s interval, 60s offline timeout
- 📊 **Monitoring**: Collects OS, CPU, Memory, Disk, Network information
- 🚀 **Deployment**: Kubernetes + Ingress + TLS
- 🔄 **High Availability**: Multi-pod deployment, Redis presence management

## Getting Started

For detailed information about the system design and implementation, please refer to the [documentation](./docs/).

---

**Documentation Language**: Traditional Chinese (繁體中文) with English technical terms  
**Last Updated**: 2024-02-05