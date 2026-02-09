// Package websocket provides WebSocket client functionality
package websocket

import (
	"crypto/tls"
	"encoding/json"
	"fmt"
	"sync"
	"time"

	"github.com/demo/agent-client/internal/config"
	"github.com/gorilla/websocket"
	"github.com/sirupsen/logrus"
)

// Message represents a WebSocket message
type Message struct {
	Type      string                 `json:"type"`
	Data      map[string]interface{} `json:"data,omitempty"`
	Timestamp int64                  `json:"timestamp"`
	MessageID string                 `json:"message_id,omitempty"`
}

// MessageHandler is a function that handles incoming messages
type MessageHandler func(msg *Message)

// Client is a WebSocket client
type Client struct {
	config      *config.Config
	conn        *websocket.Conn
	connected   bool
	mu          sync.RWMutex
	stopChan    chan struct{}
	sendChan    chan *Message
	handlers    map[string]MessageHandler
	logger      *logrus.Logger
	onConnect   func()
	onDisconnect func()
}

// NewClient creates a new WebSocket client
func NewClient(cfg *config.Config, logger *logrus.Logger) *Client {
	return &Client{
		config:   cfg,
		connected: false,
		stopChan: make(chan struct{}),
		sendChan: make(chan *Message, 100),
		handlers: make(map[string]MessageHandler),
		logger:   logger,
	}
}

// SetConnectHandler sets the handler called when connection is established
func (c *Client) SetConnectHandler(handler func()) {
	c.onConnect = handler
}

// SetDisconnectHandler sets the handler called when disconnected
func (c *Client) SetDisconnectHandler(handler func()) {
	c.onDisconnect = handler
}

// RegisterHandler registers a message handler for a specific message type
func (c *Client) RegisterHandler(msgType string, handler MessageHandler) {
	c.handlers[msgType] = handler
}

// Connect establishes a WebSocket connection
func (c *Client) Connect() error {
	c.mu.Lock()
	defer c.mu.Unlock()

	if c.connected {
		return nil
	}

	url := c.config.GetWSURL()
	c.logger.Infof("Connecting to %s", url)

	dialer := websocket.Dialer{
		HandshakeTimeout: 10 * time.Second,
		TLSClientConfig: &tls.Config{
			InsecureSkipVerify: c.config.InsecureSkipVerify,
		},
	}

	conn, _, err := dialer.Dial(url, nil)
	if err != nil {
		return fmt.Errorf("failed to connect: %w", err)
	}

	c.conn = conn
	c.connected = true
	c.logger.Info("WebSocket connected")

	// Start goroutines for reading and writing
	go c.readPump()
	go c.writePump()

	// Call connect handler
	if c.onConnect != nil {
		c.onConnect()
	}

	return nil
}

// Disconnect closes the WebSocket connection
func (c *Client) Disconnect() {
	c.mu.Lock()
	defer c.mu.Unlock()

	if !c.connected {
		return
	}

	c.connected = false
	close(c.stopChan)

	if c.conn != nil {
		c.conn.Close()
	}

	c.logger.Info("WebSocket disconnected")

	// Call disconnect handler
	if c.onDisconnect != nil {
		c.onDisconnect()
	}
}

// IsConnected returns the connection status
func (c *Client) IsConnected() bool {
	c.mu.RLock()
	defer c.mu.RUnlock()
	return c.connected
}

// SendMessage sends a message through WebSocket
func (c *Client) SendMessage(msgType string, data map[string]interface{}) error {
	if !c.IsConnected() {
		return fmt.Errorf("not connected")
	}

	msg := &Message{
		Type:      msgType,
		Data:      data,
		Timestamp: time.Now().Unix(),
	}

	select {
	case c.sendChan <- msg:
		return nil
	default:
		return fmt.Errorf("send channel full")
	}
}

// readPump reads messages from WebSocket
func (c *Client) readPump() {
	defer func() {
		c.mu.Lock()
		c.connected = false
		c.mu.Unlock()
		if c.onDisconnect != nil {
			c.onDisconnect()
		}
	}()

	for {
		select {
		case <-c.stopChan:
			return
		default:
			_, messageBytes, err := c.conn.ReadMessage()
			if err != nil {
				if websocket.IsCloseError(err, websocket.CloseNormalClosure, websocket.CloseGoingAway) {
					c.logger.Info("Connection closed normally")
				} else {
					c.logger.Errorf("Read error: %v", err)
				}
				return
			}

			var msg Message
			if err := json.Unmarshal(messageBytes, &msg); err != nil {
				c.logger.Errorf("Failed to parse message: %v", err)
				continue
			}

			c.handleMessage(&msg)
		}
	}
}

// writePump writes messages to WebSocket
func (c *Client) writePump() {
	for {
		select {
		case <-c.stopChan:
			return
		case msg := <-c.sendChan:
			c.mu.RLock()
			if !c.connected {
				c.mu.RUnlock()
				return
			}

			if err := c.conn.WriteJSON(msg); err != nil {
				c.logger.Errorf("Write error: %v", err)
				c.mu.RUnlock()
				return
			}
			c.mu.RUnlock()
			c.logger.Debugf("Sent message: type=%s", msg.Type)
		}
	}
}

// handleMessage handles incoming messages
func (c *Client) handleMessage(msg *Message) {
	c.logger.Debugf("Received message: type=%s", msg.Type)

	// Call registered handler
	if handler, ok := c.handlers[msg.Type]; ok {
		handler(msg)
		return
	}

	// Default handling
	switch msg.Type {
	case "welcome":
		c.logger.Info("Received welcome from server")
		if data := msg.Data; data != nil {
			if version, ok := data["server_version"].(string); ok {
				c.logger.Infof("Server version: %s", version)
			}
		}
	case "heartbeat_ack":
		c.logger.Debug("Heartbeat acknowledged")
	case "inventory_ack":
		c.logger.Debug("Inventory acknowledged")
	case "command":
		c.logger.Infof("Received command: %v", msg.Data)
	default:
		c.logger.Warnf("Unknown message type: %s", msg.Type)
	}
}

// RunWithReconnect runs the client with automatic reconnection
func (c *Client) RunWithReconnect(ctx <-chan struct{}) {
	for {
		select {
		case <-ctx:
			c.Disconnect()
			return
		default:
			if err := c.Connect(); err != nil {
				c.logger.Errorf("Connection failed: %v", err)
				time.Sleep(time.Duration(c.config.ReconnectInterval) * time.Second)
				continue
			}

			// Wait for disconnection
			<-c.stopChan

			// Reset stop channel for reconnection
			c.stopChan = make(chan struct{})
			c.sendChan = make(chan *Message, 100)

			c.logger.Info("Reconnecting...")
			time.Sleep(time.Duration(c.config.ReconnectInterval) * time.Second)
		}
	}
}
