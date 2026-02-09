# Agent Monitor Server Makefile

VERSION ?= 1.0.0
BUILD_TIME := $(shell date -u '+%Y-%m-%d %H:%M:%S UTC')

.PHONY: install run dev test build-docker clean version set-version

# Install dependencies
install:
	pip install -r requirements.txt

# Run production server
run:
	uvicorn app.main:app --host 0.0.0.0 --port 8080

# Run development server with reload
dev:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8080

# Run tests
test:
	pytest tests/ -v

# Build Docker image
build-docker:
	docker build -t agent-monitor-server:$(VERSION) .
	@echo "Built Docker image agent-monitor-server:$(VERSION)"

# Clean cache files
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	rm -f *.db

# Show version
version:
	@echo "Version: $(VERSION)"
	@python -c "from app import __version__; print(f'Package Version: {__version__}')"

# Set version in package
set-version:
	@sed -i 's/__version__ = ".*"/__version__ = "$(VERSION)"/' app/__init__.py
	@sed -i "s/__build_time__ = \".*\"/__build_time__ = \"$(BUILD_TIME)\"/" app/__init__.py
	@echo "Set version to $(VERSION) (built: $(BUILD_TIME))"
