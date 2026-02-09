// Package heartbeat provides heartbeat functionality
package heartbeat

import (
	"time"

	"github.com/demo/agent-client/internal/websocket"
	"github.com/sirupsen/logrus"
)

// Heartbeat manages heartbeat sending
type Heartbeat struct {
	wsClient  *websocket.Client
	interval  time.Duration
	stopChan  chan struct{}
	logger    *logrus.Logger
	startTime time.Time
	version   string
}

// NewHeartbeat creates a new heartbeat manager
func NewHeartbeat(wsClient *websocket.Client, intervalSeconds int, version string, logger *logrus.Logger) *Heartbeat {
	return &Heartbeat{
		wsClient:  wsClient,
		interval:  time.Duration(intervalSeconds) * time.Second,
		stopChan:  make(chan struct{}),
		logger:    logger,
		startTime: time.Now(),
		version:   version,
	}
}

// Start begins sending heartbeats
func (h *Heartbeat) Start() {
	ticker := time.NewTicker(h.interval)
	defer ticker.Stop()

	h.logger.Infof("Heartbeat started (interval: %v)", h.interval)

	// Send initial heartbeat
	h.sendHeartbeat()

	for {
		select {
		case <-ticker.C:
			h.sendHeartbeat()
		case <-h.stopChan:
			h.logger.Info("Heartbeat stopped")
			return
		}
	}
}

// Stop stops the heartbeat
func (h *Heartbeat) Stop() {
	select {
	case <-h.stopChan:
		// Already stopped
	default:
		close(h.stopChan)
	}
}

// sendHeartbeat sends a heartbeat message
func (h *Heartbeat) sendHeartbeat() {
	if !h.wsClient.IsConnected() {
		h.logger.Warn("Cannot send heartbeat: not connected")
		return
	}

	uptime := int64(time.Since(h.startTime).Seconds())

	data := map[string]interface{}{
		"status":        "alive",
		"uptime":        uptime,
		"agent_version": h.version,
	}

	if err := h.wsClient.SendMessage("heartbeat", data); err != nil {
		h.logger.Errorf("Failed to send heartbeat: %v", err)
	} else {
		h.logger.Debug("Heartbeat sent")
	}
}
