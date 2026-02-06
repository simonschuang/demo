// Package terminal provides PTY-based terminal execution
package terminal

import (
	"encoding/base64"
	"errors"
	"fmt"
	"io"
	"os"
	"os/exec"
	"runtime"
	"sync"

	"github.com/creack/pty"
	"github.com/sirupsen/logrus"
)

// Session represents a terminal session
type Session struct {
	SessionID string
	PTY       *os.File
	Cmd       *exec.Cmd
	Rows      int
	Cols      int
	Shell     string
	closed    bool
}

// MessageSender is a function to send messages back to the server
type MessageSender func(msgType string, data map[string]interface{}) error

// Executor manages terminal sessions
type Executor struct {
	sessions   map[string]*Session
	mu         sync.RWMutex
	sendMsg    MessageSender
	logger     *logrus.Logger
}

// NewExecutor creates a new terminal executor
func NewExecutor(sender MessageSender, logger *logrus.Logger) *Executor {
	return &Executor{
		sessions: make(map[string]*Session),
		sendMsg:  sender,
		logger:   logger,
	}
}

// HandleCommand processes terminal commands from server
// This matches the websocket.MessageHandler signature
func (e *Executor) HandleCommand(data map[string]interface{}) {
	sessionID, ok := data["session_id"].(string)
	if !ok {
		e.logger.Error("Terminal command missing session_id")
		return
	}

	command, ok := data["command"].(string)
	if !ok {
		e.logger.Error("Terminal command missing command field")
		return
	}

	e.logger.Debugf("Terminal command: %s, session: %s", command, sessionID)

	var err error
	switch command {
	case "init":
		cols := 80
		rows := 24
		shell := ""
		if c, ok := data["cols"].(float64); ok {
			cols = int(c)
		}
		if r, ok := data["rows"].(float64); ok {
			rows = int(r)
		}
		if s, ok := data["shell"].(string); ok {
			shell = s
		}
		err = e.initTerminal(sessionID, cols, rows, shell)
	case "input":
		input, _ := data["data"].(string)
		err = e.handleInput(sessionID, input)
	case "resize":
		cols := 80
		rows := 24
		if c, ok := data["cols"].(float64); ok {
			cols = int(c)
		}
		if r, ok := data["rows"].(float64); ok {
			rows = int(r)
		}
		err = e.resizeTerminal(sessionID, cols, rows)
	case "close":
		err = e.closeTerminal(sessionID)
	default:
		e.logger.Warnf("Unknown terminal command: %s", command)
		return
	}

	if err != nil {
		e.logger.Errorf("Terminal command error: %v", err)
		e.sendError(sessionID, err.Error())
	}
}

// initTerminal creates a new PTY session
func (e *Executor) initTerminal(sessionID string, cols, rows int, shell string) error {
	e.mu.Lock()
	defer e.mu.Unlock()

	// Check if session already exists
	if _, exists := e.sessions[sessionID]; exists {
		return fmt.Errorf("session already exists: %s", sessionID)
	}

	// Use default shell if not specified
	if shell == "" {
		shell = getDefaultShell()
	}

	e.logger.Infof("Initializing terminal session %s: shell=%s, rows=%d, cols=%d", sessionID, shell, rows, cols)

	// Create command
	cmd := exec.Command(shell)
	cmd.Env = append(os.Environ(),
		"TERM=xterm-256color",
		fmt.Sprintf("COLUMNS=%d", cols),
		fmt.Sprintf("LINES=%d", rows),
	)

	// Start PTY
	ptmx, err := pty.Start(cmd)
	if err != nil {
		return fmt.Errorf("failed to start pty: %w", err)
	}

	// Set terminal size
	if err := pty.Setsize(ptmx, &pty.Winsize{
		Rows: uint16(rows),
		Cols: uint16(cols),
	}); err != nil {
		ptmx.Close()
		cmd.Process.Kill()
		return fmt.Errorf("failed to set terminal size: %w", err)
	}

	// Create session
	session := &Session{
		SessionID: sessionID,
		PTY:       ptmx,
		Cmd:       cmd,
		Rows:      rows,
		Cols:      cols,
		Shell:     shell,
		closed:    false,
	}
	e.sessions[sessionID] = session

	// Start reading output
	go e.readOutput(session)

	e.logger.Infof("Terminal session %s started", sessionID)
	return nil
}

// readOutput reads from PTY and sends to output handler
func (e *Executor) readOutput(session *Session) {
	buffer := make([]byte, 4096)

	for {
		n, err := session.PTY.Read(buffer)
		if err != nil {
			if !errors.Is(err, io.EOF) && !session.closed {
				e.logger.Errorf("Failed to read from PTY: %v", err)
			}
			break
		}

		if n > 0 && e.sendMsg != nil {
			// Send output to server (base64 encode for safe transport)
			output := base64.StdEncoding.EncodeToString(buffer[:n])
			e.sendMsg("terminal_output", map[string]interface{}{
				"session_id": session.SessionID,
				"output":     output,
				"type":       "output",
			})
		}
	}

	// Session ended, notify server
	if e.sendMsg != nil {
		e.sendMsg("terminal_closed", map[string]interface{}{
			"session_id": session.SessionID,
		})
	}

	// Clean up
	e.closeTerminal(session.SessionID)
}

// sendError sends an error message to the server
func (e *Executor) sendError(sessionID, errMsg string) {
	if e.sendMsg != nil {
		e.sendMsg("terminal_error", map[string]interface{}{
			"session_id": sessionID,
			"error":      errMsg,
		})
	}
}

// handleInput writes input to PTY
func (e *Executor) handleInput(sessionID string, input string) error {
	e.mu.RLock()
	session, exists := e.sessions[sessionID]
	e.mu.RUnlock()

	if !exists {
		return fmt.Errorf("session not found: %s", sessionID)
	}

	if input == "" {
		return nil
	}

	// Write to PTY
	_, err := session.PTY.Write([]byte(input))
	if err != nil {
		return fmt.Errorf("failed to write to PTY: %w", err)
	}

	return nil
}

// resizeTerminal changes the terminal size
func (e *Executor) resizeTerminal(sessionID string, cols, rows int) error {
	e.mu.RLock()
	session, exists := e.sessions[sessionID]
	e.mu.RUnlock()

	if !exists {
		return fmt.Errorf("session not found: %s", sessionID)
	}

	if err := pty.Setsize(session.PTY, &pty.Winsize{
		Rows: uint16(rows),
		Cols: uint16(cols),
	}); err != nil {
		return fmt.Errorf("failed to resize terminal: %w", err)
	}

	session.Rows = rows
	session.Cols = cols

	e.logger.Debugf("Terminal %s resized to %dx%d", sessionID, cols, rows)
	return nil
}

// closeTerminal closes a terminal session
func (e *Executor) closeTerminal(sessionID string) error {
	e.mu.Lock()
	defer e.mu.Unlock()

	session, exists := e.sessions[sessionID]
	if !exists {
		return nil // Already closed
	}

	session.closed = true

	// Close PTY
	if session.PTY != nil {
		session.PTY.Close()
	}

	// Kill process
	if session.Cmd != nil && session.Cmd.Process != nil {
		session.Cmd.Process.Kill()
		session.Cmd.Wait()
	}

	// Remove session
	delete(e.sessions, sessionID)

	e.logger.Infof("Terminal session %s closed", sessionID)
	return nil
}

// CloseAll closes all terminal sessions
func (e *Executor) CloseAll() {
	e.mu.Lock()
	sessionIDs := make([]string, 0, len(e.sessions))
	for id := range e.sessions {
		sessionIDs = append(sessionIDs, id)
	}
	e.mu.Unlock()

	for _, id := range sessionIDs {
		e.closeTerminal(id)
	}
}

// GetSessionCount returns the number of active sessions
func (e *Executor) GetSessionCount() int {
	e.mu.RLock()
	defer e.mu.RUnlock()
	return len(e.sessions)
}

// getDefaultShell returns the default shell for the current OS
func getDefaultShell() string {
	// Try to get user's preferred shell
	if shell := os.Getenv("SHELL"); shell != "" {
		return shell
	}

	// Fall back to OS default
	switch runtime.GOOS {
	case "windows":
		// Try PowerShell first, then cmd
		if _, err := exec.LookPath("powershell.exe"); err == nil {
			return "powershell.exe"
		}
		return "cmd.exe"
	case "darwin":
		return "/bin/zsh"
	default:
		// Try bash, then sh
		if _, err := exec.LookPath("/bin/bash"); err == nil {
			return "/bin/bash"
		}
		return "/bin/sh"
	}
}
