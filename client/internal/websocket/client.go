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
	config       *config.Config
	conn         *websocket.Conn
	connected    bool
	mu           sync.RWMutex
	writeMu      sync.Mutex // Protects all writes to conn (gorilla/websocket doesn't allow concurrent writes)
	stopChan     chan struct{}
	sendChan     chan *Message
	handlers     map[string]MessageHandler
	logger       *logrus.Logger
	onConnect    func()
	onDisconnect func()
	disconnectCh chan struct{} // Signals disconnection to trigger reconnect
}

// NewClient creates a new WebSocket client
func NewClient(cfg *config.Config, logger *logrus.Logger) *Client {
	return &Client{
		config:       cfg,
		connected:    false,
		stopChan:     make(chan struct{}),
		sendChan:     make(chan *Message, 100),
		handlers:     make(map[string]MessageHandler),
		logger:       logger,
		disconnectCh: make(chan struct{}, 1),
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

// Disconnect closes the WebSocket connection gracefully
func (c *Client) Disconnect() {
	c.mu.Lock()
	defer c.mu.Unlock()

	if !c.connected {
		return
	}

	c.connected = false
	
	// Close stopChan to signal goroutines to stop
	select {
	case <-c.stopChan:
		// Already closed
	default:
		close(c.stopChan)
	}

	if c.conn != nil {
		// Send close message with write lock
		c.writeMu.Lock()
		c.conn.WriteMessage(websocket.CloseMessage, 
			websocket.FormatCloseMessage(websocket.CloseNormalClosure, ""))
		c.writeMu.Unlock()
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
		c.logger.Debug("readPump exiting, triggering disconnect...")
		
		c.mu.Lock()
		wasConnected := c.connected
		c.connected = false
		if c.conn != nil {
			c.conn.Close()
		}
		c.mu.Unlock()

		if c.onDisconnect != nil {
			c.onDisconnect()
		}

		// Signal disconnection to trigger reconnect (only if we were connected)
		if wasConnected {
			c.logger.Debug("Sending disconnect signal for reconnection")
			select {
			case c.disconnectCh <- struct{}{}:
				c.logger.Debug("Disconnect signal sent")
			default:
				c.logger.Warn("Disconnect channel full, signal dropped")
			}
		}
	}()

	// Set read deadline and pong handler for connection health check
	c.conn.SetReadDeadline(time.Now().Add(60 * time.Second))
	c.conn.SetPongHandler(func(string) error {
		c.conn.SetReadDeadline(time.Now().Add(60 * time.Second))
		return nil
	})

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

			// Reset read deadline on successful read
			c.conn.SetReadDeadline(time.Now().Add(60 * time.Second))

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
	pingTicker := time.NewTicker(30 * time.Second)
	defer pingTicker.Stop()

	for {
		select {
		case <-c.stopChan:
			return
		case <-pingTicker.C:
			c.mu.RLock()
			connected := c.connected
			c.mu.RUnlock()
			
			if !connected {
				return
			}
			
			c.writeMu.Lock()
			c.conn.SetWriteDeadline(time.Now().Add(10 * time.Second))
			err := c.conn.WriteMessage(websocket.PingMessage, nil)
			c.writeMu.Unlock()
			
			if err != nil {
				c.logger.Errorf("Ping error: %v", err)
				return
			}
		case msg := <-c.sendChan:
			c.mu.RLock()
			connected := c.connected
			c.mu.RUnlock()
			
			if !connected {
				return
			}

			c.writeMu.Lock()
			c.conn.SetWriteDeadline(time.Now().Add(10 * time.Second))
			err := c.conn.WriteJSON(msg)
			c.writeMu.Unlock()
			
			if err != nil {
				c.logger.Errorf("Write error: %v", err)
				return
			}
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
	baseInterval := time.Duration(c.config.ReconnectInterval) * time.Second
	maxInterval := 60 * time.Second
	currentInterval := baseInterval

	c.logger.Info("Starting connection loop with auto-reconnect")

	for {
		select {
		case <-ctx:
			c.logger.Info("Context cancelled, stopping reconnect loop")
			c.Disconnect()
			return
		default:
		}

		c.logger.Infof("Attempting to connect to server...")
		if err := c.Connect(); err != nil {
			c.logger.Errorf("Connection failed: %v, retrying in %v", err, currentInterval)
			
			select {
			case <-ctx:
				return
			case <-time.After(currentInterval):
			}
			
			// Exponential backoff (double the interval, up to max)
			currentInterval = currentInterval * 2
			if currentInterval > maxInterval {
				currentInterval = maxInterval
			}
			continue
		}

		// Connection successful, reset backoff
		currentInterval = baseInterval

		// Wait for disconnection signal
		c.logger.Debug("Waiting for disconnect signal...")
		select {
		case <-ctx:
			c.logger.Info("Context cancelled while connected")
			c.Disconnect()
			return
		case <-c.disconnectCh:
			c.logger.Info("Connection lost, will reconnect...")
		}

		// Reset channels for reconnection
		c.mu.Lock()
		c.stopChan = make(chan struct{})
		c.sendChan = make(chan *Message, 100)
		c.mu.Unlock()

		// Wait before reconnecting
		c.logger.Infof("Reconnecting in %v...", baseInterval)
		select {
		case <-ctx:
			return
		case <-time.After(baseInterval):
		}
	}
}
