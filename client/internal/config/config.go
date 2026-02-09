// Package config provides configuration management for the agent
package config

import (
	"fmt"
	"os"
	"path/filepath"

	"github.com/spf13/viper"
)

// BMCConfig holds BMC-related configuration
type BMCConfig struct {
	Enabled            bool   `mapstructure:"enabled"`
	IP                 string `mapstructure:"ip"`
	Username           string `mapstructure:"username"`
	Password           string `mapstructure:"password"`
	Protocol           string `mapstructure:"protocol"` // "redfish" or "ipmi"
	Port               int    `mapstructure:"port"`
	InsecureSkipVerify bool   `mapstructure:"insecure_skip_verify"`
}

// Config holds all configuration for the agent
type Config struct {
	// Server connection info
	ServerURL   string `mapstructure:"server_url"`
	ClientID    string `mapstructure:"client_id"`
	ClientToken string `mapstructure:"client_token"`

	// WebSocket settings
	WSScheme string `mapstructure:"ws_scheme"`
	WSPath   string `mapstructure:"ws_path"`

	// Heartbeat settings
	HeartbeatInterval int `mapstructure:"heartbeat_interval"`
	ReconnectInterval int `mapstructure:"reconnect_interval"`

	// Inventory settings
	CollectInterval int `mapstructure:"collect_interval"`

	// BMC settings
	BMC BMCConfig `mapstructure:"bmc"`

	// Logging settings
	LogLevel string `mapstructure:"log_level"`
	LogFile  string `mapstructure:"log_file"`
}

// LoadConfig loads configuration from file
func LoadConfig(configPath string) (*Config, error) {
	v := viper.New()

	// Set defaults
	v.SetDefault("ws_scheme", "wss")
	v.SetDefault("ws_path", "/ws")
	v.SetDefault("heartbeat_interval", 15)
	v.SetDefault("reconnect_interval", 5)
	v.SetDefault("collect_interval", 60)
	v.SetDefault("log_level", "info")

	// BMC defaults
	v.SetDefault("bmc.enabled", false)
	v.SetDefault("bmc.protocol", "redfish")
	v.SetDefault("bmc.port", 443)
	v.SetDefault("bmc.insecure_skip_verify", true)

	// Check if config file exists
	if configPath != "" {
		if _, err := os.Stat(configPath); os.IsNotExist(err) {
			return nil, fmt.Errorf("config file not found: %s", configPath)
		}

		v.SetConfigFile(configPath)
		v.SetConfigType(filepath.Ext(configPath)[1:]) // yaml, json, etc.

		if err := v.ReadInConfig(); err != nil {
			return nil, fmt.Errorf("failed to read config file: %w", err)
		}
	}

	// Allow environment variables to override config
	v.AutomaticEnv()
	v.SetEnvPrefix("AGENT")

	var config Config
	if err := v.Unmarshal(&config); err != nil {
		return nil, fmt.Errorf("failed to unmarshal config: %w", err)
	}

	// Validate required fields
	if err := config.Validate(); err != nil {
		return nil, err
	}

	return &config, nil
}

// Validate checks if required configuration fields are set
func (c *Config) Validate() error {
	if c.ServerURL == "" {
		return fmt.Errorf("server_url is required")
	}
	if c.ClientID == "" {
		return fmt.Errorf("client_id is required")
	}
	if c.ClientToken == "" {
		return fmt.Errorf("client_token is required")
	}

	// Validate BMC config if enabled
	if c.BMC.Enabled {
		if c.BMC.IP == "" {
			return fmt.Errorf("bmc.ip is required when BMC is enabled")
		}
		if c.BMC.Username == "" {
			return fmt.Errorf("bmc.username is required when BMC is enabled")
		}
		if c.BMC.Password == "" {
			return fmt.Errorf("bmc.password is required when BMC is enabled")
		}
		if c.BMC.Protocol != "redfish" && c.BMC.Protocol != "ipmi" {
			return fmt.Errorf("bmc.protocol must be 'redfish' or 'ipmi'")
		}
	}

	return nil
}

// IsBMCMode returns true if BMC mode is enabled
func (c *Config) IsBMCMode() bool {
	return c.BMC.Enabled
}

// GetWSURL returns the full WebSocket URL
func (c *Config) GetWSURL() string {
	return fmt.Sprintf("%s://%s%s/%s?token=%s",
		c.WSScheme,
		c.ServerURL,
		c.WSPath,
		c.ClientID,
		c.ClientToken,
	)
}
