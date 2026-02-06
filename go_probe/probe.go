package main

import (
	"bytes"
	"compress/zlib"
	"encoding/binary"
	"encoding/gob"
	"fmt"
	"io"
	"math/rand"
	"net"
	"os"
	"runtime"
	"time"
)

// Custom opcodes matching server
const (
	OpcodeGreeting = 1
	OpcodePulse    = 2
	OpcodeMetrics  = 3
	OpcodeAck      = 4
	OpcodeReject   = 5
)

// ProbeConfig holds connection parameters
type ProbeConfig struct {
	ProbeID    string
	Secret     string
	HubAddress string
	HubPort    int
}

// BinaryCodec handles custom binary protocol
type BinaryCodec struct{}

func (bc *BinaryCodec) EncodePacket(opcode byte, payload map[string]interface{}) ([]byte, error) {
	// Serialize payload using gob
	var buf bytes.Buffer
	enc := gob.NewEncoder(&buf)
	if err := enc.Encode(payload); err != nil {
		return nil, err
	}
	
	// Compress
	var compressed bytes.Buffer
	zw := zlib.NewWriter(&compressed)
	if _, err := zw.Write(buf.Bytes()); err != nil {
		return nil, err
	}
	zw.Close()
	
	// Build packet: opcode (1 byte) + length (2 bytes) + compressed data
	compressedData := compressed.Bytes()
	packet := make([]byte, 3+len(compressedData))
	packet[0] = opcode
	binary.BigEndian.PutUint16(packet[1:3], uint16(len(compressedData)))
	copy(packet[3:], compressedData)
	
	return packet, nil
}

func (bc *BinaryCodec) DecodePacket(raw []byte) (byte, map[string]interface{}, error) {
	if len(raw) < 3 {
		return 0, nil, fmt.Errorf("packet too short")
	}
	
	opcode := raw[0]
	payloadLen := binary.BigEndian.Uint16(raw[1:3])
	
	if len(raw) < 3+int(payloadLen) {
		return 0, nil, fmt.Errorf("incomplete packet")
	}
	
	// Decompress
	compressed := bytes.NewReader(raw[3 : 3+payloadLen])
	zr, err := zlib.NewReader(compressed)
	if err != nil {
		return 0, nil, err
	}
	defer zr.Close()
	
	var decompressed bytes.Buffer
	if _, err := io.Copy(&decompressed, zr); err != nil {
		return 0, nil, err
	}
	
	// Deserialize
	var payload map[string]interface{}
	dec := gob.NewDecoder(&decompressed)
	if err := dec.Decode(&payload); err != nil {
		return 0, nil, err
	}
	
	return opcode, payload, nil
}

// MetricsHarvester collects system information
type MetricsHarvester struct{}

func (mh *MetricsHarvester) GatherMetrics() map[string]interface{} {
	// Unique metrics collection approach
	var memStats runtime.MemStats
	runtime.ReadMemStats(&memStats)
	
	hostname, _ := os.Hostname()
	
	// Custom metric computation using prime number seed
	seed := time.Now().UnixNano()
	rand.Seed(seed)
	
	return map[string]interface{}{
		"hostname":      hostname,
		"os_realm":      runtime.GOOS,
		"cpu_arch":      runtime.GOARCH,
		"goroutine_cnt": runtime.NumGoroutine(),
		"cpu_cores":     runtime.NumCPU(),
		"mem_alloc":     memStats.Alloc,
		"mem_total":     memStats.TotalAlloc,
		"gc_cycles":     memStats.NumGC,
		"collection_ts": time.Now().Unix(),
		"entropy_val":   rand.Intn(10000), // Unique fingerprint per collection
	}
}

// ProbeEngine manages connection and communication
type ProbeEngine struct {
	config       *ProbeConfig
	connection   net.Conn
	codec        *BinaryCodec
	harvester    *MetricsHarvester
	heartbeatTicker *time.Ticker
	metricsTicker   *time.Ticker
	isRunning    bool
}

func NewProbeEngine(config *ProbeConfig) *ProbeEngine {
	return &ProbeEngine{
		config:    config,
		codec:     &BinaryCodec{},
		harvester: &MetricsHarvester{},
		isRunning: false,
	}
}

func (pe *ProbeEngine) EstablishLink() error {
	address := fmt.Sprintf("%s:%d", pe.config.HubAddress, pe.config.HubPort)
	conn, err := net.Dial("tcp", address)
	if err != nil {
		return fmt.Errorf("link establishment failed: %w", err)
	}
	
	pe.connection = conn
	
	// Send handshake
	handshakePayload := map[string]interface{}{
		"probe_id": pe.config.ProbeID,
		"secret":   pe.config.Secret,
	}
	
	packet, err := pe.codec.EncodePacket(OpcodeGreeting, handshakePayload)
	if err != nil {
		return err
	}
	
	if _, err := pe.connection.Write(packet); err != nil {
		return err
	}
	
	// Wait for ACK
	response := make([]byte, 4096)
	n, err := pe.connection.Read(response)
	if err != nil {
		return err
	}
	
	opcode, payload, err := pe.codec.DecodePacket(response[:n])
	if err != nil {
		return err
	}
	
	if opcode == OpcodeReject {
		return fmt.Errorf("handshake rejected: %v", payload)
	}
	
	fmt.Printf("Link established. Welcome: %v\n", payload)
	return nil
}

func (pe *ProbeEngine) TransmitPulse() error {
	pulsePayload := map[string]interface{}{
		"pulse_time": time.Now().Unix(),
		"probe_id":   pe.config.ProbeID,
	}
	
	packet, err := pe.codec.EncodePacket(OpcodePulse, pulsePayload)
	if err != nil {
		return err
	}
	
	_, err = pe.connection.Write(packet)
	return err
}

func (pe *ProbeEngine) TransmitMetrics() error {
	metrics := pe.harvester.GatherMetrics()
	
	metricsPayload := map[string]interface{}{
		"metrics":  metrics,
		"probe_id": pe.config.ProbeID,
	}
	
	packet, err := pe.codec.EncodePacket(OpcodeMetrics, metricsPayload)
	if err != nil {
		return err
	}
	
	_, err = pe.connection.Write(packet)
	return err
}

func (pe *ProbeEngine) BeginTransmission() {
	pe.isRunning = true
	
	// Start heartbeat rhythm (every 15 seconds)
	pe.heartbeatTicker = time.NewTicker(15 * time.Second)
	go func() {
		for range pe.heartbeatTicker.C {
			if !pe.isRunning {
				return
			}
			if err := pe.TransmitPulse(); err != nil {
				fmt.Printf("Pulse transmission failed: %v\n", err)
			}
		}
	}()
	
	// Start metrics rhythm (every 60 seconds)
	pe.metricsTicker = time.NewTicker(60 * time.Second)
	go func() {
		// Send initial metrics immediately
		pe.TransmitMetrics()
		
		for range pe.metricsTicker.C {
			if !pe.isRunning {
				return
			}
			if err := pe.TransmitMetrics(); err != nil {
				fmt.Printf("Metrics transmission failed: %v\n", err)
			}
		}
	}()
	
	// Listen for incoming messages
	go pe.listenForMessages()
}

func (pe *ProbeEngine) listenForMessages() {
	buffer := make([]byte, 4096)
	for pe.isRunning {
		n, err := pe.connection.Read(buffer)
		if err != nil {
			if pe.isRunning {
				fmt.Printf("Read error: %v\n", err)
			}
			return
		}
		
		opcode, _, err := pe.codec.DecodePacket(buffer[:n])
		if err != nil {
			fmt.Printf("Decode error: %v\n", err)
			continue
		}
		
		if opcode == OpcodeAck {
			// Silently acknowledge
			continue
		}
	}
}

func (pe *ProbeEngine) Terminate() {
	pe.isRunning = false
	if pe.heartbeatTicker != nil {
		pe.heartbeatTicker.Stop()
	}
	if pe.metricsTicker != nil {
		pe.metricsTicker.Stop()
	}
	if pe.connection != nil {
		pe.connection.Close()
	}
}

// ReconnectionOrchestrator handles connection resilience
type ReconnectionOrchestrator struct {
	engine         *ProbeEngine
	maxRetries     int
	retryDelay     time.Duration
}

func NewReconnectionOrchestrator(engine *ProbeEngine) *ReconnectionOrchestrator {
	return &ReconnectionOrchestrator{
		engine:     engine,
		maxRetries: -1, // Infinite retries
		retryDelay: 5 * time.Second,
	}
}

func (ro *ReconnectionOrchestrator) MaintainLink() {
	attempt := 0
	
	for {
		attempt++
		fmt.Printf("Connection attempt #%d\n", attempt)
		
		err := ro.engine.EstablishLink()
		if err != nil {
			fmt.Printf("Link failed: %v. Retrying in %v...\n", err, ro.retryDelay)
			time.Sleep(ro.retryDelay)
			continue
		}
		
		// Connection successful
		fmt.Println("Link active. Beginning transmission...")
		ro.engine.BeginTransmission()
		
		// Wait for disconnection
		for ro.engine.isRunning {
			time.Sleep(1 * time.Second)
		}
		
		fmt.Println("Link lost. Reconnecting...")
		time.Sleep(ro.retryDelay)
	}
}

func main() {
	// Configuration would normally come from file or flags
	config := &ProbeConfig{
		ProbeID:    "probe_123456", // Would be from registration
		Secret:     "key_789012",    // Would be from registration
		HubAddress: "localhost",
		HubPort:    7777,
	}
	
	fmt.Println("Initializing probe...")
	
	engine := NewProbeEngine(config)
	orchestrator := NewReconnectionOrchestrator(engine)
	
	// Maintain connection indefinitely
	orchestrator.MaintainLink()
}
