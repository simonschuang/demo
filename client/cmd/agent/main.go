// Agent Client - Main Entry Point
package main

import (
	"flag"
	"fmt"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/demo/agent-client/internal/config"
	"github.com/demo/agent-client/internal/heartbeat"
	"github.com/demo/agent-client/internal/inventory"
	"github.com/demo/agent-client/internal/terminal"
	"github.com/demo/agent-client/internal/websocket"
	"github.com/sirupsen/logrus"
)

var (
	version   = "v1.0.0"
	buildTime = "unknown"
)

// InventoryCollectorInterface defines the interface for inventory collectors
type InventoryCollectorInterface interface {
	Collect() (map[string]interface{}, error)
}

// localCollectorWrapper wraps the local Collector to implement InventoryCollectorInterface
type localCollectorWrapper struct {
	collector *inventory.Collector
}

func (w *localCollectorWrapper) Collect() (map[string]interface{}, error) {
	inv, err := w.collector.Collect()
	if err != nil {
		return nil, err
	}
	return inv.ToMap(), nil
}

// bmcCollectorWrapper wraps the BMC Collector to implement InventoryCollectorInterface
type bmcCollectorWrapper struct {
	collector *inventory.BMCCollector
}

func (w *bmcCollectorWrapper) Collect() (map[string]interface{}, error) {
	inv, err := w.collector.Collect()
	if err != nil {
		return nil, err
	}
	return inv.ToMap(), nil
}

// hybridCollector collects from both local and BMC
type hybridCollector struct {
	localCollector *inventory.Collector
	bmcCollector   *inventory.BMCCollector
}

func (h *hybridCollector) Collect() (map[string]interface{}, error) {
	result := make(map[string]interface{})

	// Collect local inventory
	if h.localCollector != nil {
		localInv, err := h.localCollector.Collect()
		if err == nil {
			result["local"] = localInv.ToMap()
		}
	}

	// Collect BMC inventory
	if h.bmcCollector != nil {
		bmcInv, err := h.bmcCollector.Collect()
		if err == nil {
			result["bmc"] = bmcInv.ToMap()
		}
	}

	result["collected_at"] = time.Now().Unix()
	return result, nil
}

func main() {
	// Parse command line flags
	configPath := flag.String("config", "/etc/agent/config.yaml", "Path to config file")
	showVersion := flag.Bool("version", false, "Show version information")
	bmcOnly := flag.Bool("bmc-only", false, "Collect from BMC only (no local collection)")
	flag.Parse()

	// Show version if requested
	if *showVersion {
		fmt.Printf("Agent Client %s (built: %s)\n", version, buildTime)
		os.Exit(0)
	}

	// Initialize logger
	logger := logrus.New()
	logger.SetFormatter(&logrus.TextFormatter{
		FullTimestamp:   true,
		TimestampFormat: "2006-01-02 15:04:05",
	})

	logger.Infof("Agent Client %s starting...", version)

	// Load configuration
	cfg, err := config.LoadConfig(*configPath)
	if err != nil {
		logger.Fatalf("Failed to load config: %v", err)
	}

	// Set log level
	level, err := logrus.ParseLevel(cfg.LogLevel)
	if err != nil {
		level = logrus.InfoLevel
	}
	logger.SetLevel(level)

	// Set log file if specified
	if cfg.LogFile != "" {
		file, err := os.OpenFile(cfg.LogFile, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0644)
		if err != nil {
			logger.Warnf("Failed to open log file: %v", err)
		} else {
			logger.SetOutput(file)
		}
	}

	logger.Infof("Configuration loaded: server=%s, client_id=%s", cfg.ServerURL, cfg.ClientID)

	// Log BMC mode status
	if cfg.IsBMCMode() {
		logger.Infof("BMC mode enabled: ip=%s, protocol=%s", cfg.BMC.IP, cfg.BMC.Protocol)
	}

	// Create WebSocket client
	wsClient := websocket.NewClient(cfg, logger)

	// Create heartbeat manager
	hb := heartbeat.NewHeartbeat(wsClient, cfg.HeartbeatInterval, version, logger)

	// Create inventory collector(s) based on configuration
	var invCollector InventoryCollectorInterface

	if cfg.IsBMCMode() {
		bmcCollector := inventory.NewBMCCollector(&cfg.BMC, logger)

		if *bmcOnly {
			// BMC-only mode: collect from BMC only
			logger.Info("Running in BMC-only mode")
			invCollector = &bmcCollectorWrapper{collector: bmcCollector}
		} else {
			// Hybrid mode: collect from both local and BMC
			logger.Info("Running in hybrid mode (local + BMC)")
			localCollector := inventory.NewCollector(logger)
			invCollector = &hybridCollector{
				localCollector: localCollector,
				bmcCollector:   bmcCollector,
			}
		}
	} else {
		// Local-only mode: collect from local host
		logger.Info("Running in local-only mode")
		localCollector := inventory.NewCollector(logger)
		invCollector = &localCollectorWrapper{collector: localCollector}
	}

	// Create terminal executor with message sender
	termExecutor := terminal.NewExecutor(func(msgType string, data map[string]interface{}) error {
		return wsClient.SendMessage(msgType, data)
	}, logger)

	// Register terminal command handler
	wsClient.RegisterHandler("terminal_command", func(msg *websocket.Message) {
		termExecutor.HandleCommand(msg.Data)
	})

	// Stop channels
	stopChan := make(chan struct{})
	inventoryStopChan := make(chan struct{})

	// Set up connection handlers
	wsClient.SetConnectHandler(func() {
		logger.Info("Connected to server")

		// Start heartbeat
		go hb.Start()

		// Start inventory collection
		go runInventoryCollectorGeneric(wsClient, invCollector, cfg.CollectInterval, inventoryStopChan, logger)
	})

	wsClient.SetDisconnectHandler(func() {
		logger.Info("Disconnected from server")

		// Stop heartbeat
		hb.Stop()

		// Stop inventory collector
		select {
		case <-inventoryStopChan:
			// Already stopped
		default:
			close(inventoryStopChan)
		}

		// Reset channels for reconnection
		hb = heartbeat.NewHeartbeat(wsClient, cfg.HeartbeatInterval, version, logger)
		inventoryStopChan = make(chan struct{})
	})

	// Connect to server (with reconnection)
	go wsClient.RunWithReconnect(stopChan)

	// Wait for interrupt signal
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, os.Interrupt, syscall.SIGTERM)

	<-sigChan
	logger.Info("Received shutdown signal")

	// Graceful shutdown
	close(stopChan)
	termExecutor.CloseAll() // Close all terminal sessions
	wsClient.Disconnect()

	logger.Info("Agent stopped. Goodbye!")
}

// runInventoryCollectorGeneric runs periodic inventory collection using the generic interface
func runInventoryCollectorGeneric(
	wsClient *websocket.Client,
	collector InventoryCollectorInterface,
	intervalSeconds int,
	stopChan <-chan struct{},
	logger *logrus.Logger,
) {
	// Collect and send initial inventory
	sendInventoryGeneric(wsClient, collector, logger)

	ticker := time.NewTicker(time.Duration(intervalSeconds) * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-ticker.C:
			sendInventoryGeneric(wsClient, collector, logger)
		case <-stopChan:
			logger.Debug("Inventory collector stopped")
			return
		}
	}
}

// sendInventoryGeneric collects and sends inventory using the generic interface
func sendInventoryGeneric(wsClient *websocket.Client, collector InventoryCollectorInterface, logger *logrus.Logger) {
	if !wsClient.IsConnected() {
		return
	}

	invData, err := collector.Collect()
	if err != nil {
		logger.Errorf("Failed to collect inventory: %v", err)
		return
	}

	if err := wsClient.SendMessage("inventory", invData); err != nil {
		logger.Errorf("Failed to send inventory: %v", err)
	} else {
		logger.Debug("Inventory sent")
	}
}

// runInventoryCollector runs periodic inventory collection (kept for backward compatibility)
func runInventoryCollector(
	wsClient *websocket.Client,
	collector *inventory.Collector,
	intervalSeconds int,
	stopChan <-chan struct{},
	logger *logrus.Logger,
) {
	// Collect and send initial inventory
	sendInventory(wsClient, collector, logger)

	ticker := time.NewTicker(time.Duration(intervalSeconds) * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-ticker.C:
			sendInventory(wsClient, collector, logger)
		case <-stopChan:
			logger.Debug("Inventory collector stopped")
			return
		}
	}
}

// sendInventory collects and sends inventory
func sendInventory(wsClient *websocket.Client, collector *inventory.Collector, logger *logrus.Logger) {
	if !wsClient.IsConnected() {
		return
	}

	inv, err := collector.Collect()
	if err != nil {
		logger.Errorf("Failed to collect inventory: %v", err)
		return
	}

	if err := wsClient.SendMessage("inventory", inv.ToMap()); err != nil {
		logger.Errorf("Failed to send inventory: %v", err)
	} else {
		logger.Debug("Inventory sent")
	}
}
