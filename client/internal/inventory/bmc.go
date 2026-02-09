// Package inventory provides BMC (Baseboard Management Controller) inventory collection
package inventory

import (
	"crypto/tls"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"

	"github.com/demo/agent-client/internal/config"
	"github.com/sirupsen/logrus"
)

// ProcessorInfo represents CPU information from BMC
type ProcessorInfo struct {
	ID           string `json:"id"`
	Model        string `json:"model"`
	Manufacturer string `json:"manufacturer"`
	Cores        int    `json:"cores"`
	Threads      int    `json:"threads"`
	MaxSpeedMHz  int    `json:"max_speed_mhz"`
	Status       string `json:"status"`
}

// MemoryInfo represents memory module information from BMC
type MemoryInfo struct {
	ID           string `json:"id"`
	Manufacturer string `json:"manufacturer"`
	PartNumber   string `json:"part_number"`
	SerialNumber string `json:"serial_number"`
	CapacityMiB  int    `json:"capacity_mib"`
	SpeedMHz     int    `json:"speed_mhz"`
	MemoryType   string `json:"memory_type"`
	Status       string `json:"status"`
}

// StorageInfo represents storage information from BMC
type StorageInfo struct {
	ID           string `json:"id"`
	Name         string `json:"name"`
	Model        string `json:"model"`
	Manufacturer string `json:"manufacturer"`
	CapacityGB   int64  `json:"capacity_gb"`
	MediaType    string `json:"media_type"`
	Protocol     string `json:"protocol"`
	Status       string `json:"status"`
}

// NetworkPortInfo represents network port information from BMC
type NetworkPortInfo struct {
	ID          string   `json:"id"`
	MACAddress  string   `json:"mac_address"`
	SpeedMbps   int      `json:"speed_mbps"`
	LinkStatus  string   `json:"link_status"`
	IPAddresses []string `json:"ip_addresses,omitempty"`
}

// PowerInfo represents power supply information from BMC
type PowerInfo struct {
	ID              string `json:"id"`
	Manufacturer    string `json:"manufacturer"`
	Model           string `json:"model"`
	SerialNumber    string `json:"serial_number"`
	PowerCapacity   int    `json:"power_capacity_watts"`
	PowerOutputWatts int   `json:"power_output_watts,omitempty"`
	Status          string `json:"status"`
}

// FanInfo represents fan information from BMC
type FanInfo struct {
	ID         string `json:"id"`
	Name       string `json:"name"`
	SpeedRPM   int    `json:"speed_rpm"`
	SpeedPct   int    `json:"speed_percent"`
	Status     string `json:"status"`
}

// TempInfo represents temperature sensor information from BMC
type TempInfo struct {
	ID               string  `json:"id"`
	Name             string  `json:"name"`
	ReadingCelsius   float64 `json:"reading_celsius"`
	UpperThreshold   float64 `json:"upper_threshold,omitempty"`
	CriticalThreshold float64 `json:"critical_threshold,omitempty"`
	Status           string  `json:"status"`
}

// BMCInventory represents collected BMC information
type BMCInventory struct {
	// BMC basic info
	BMCType    string `json:"bmc_type"`
	BMCVersion string `json:"bmc_version"`
	BMCIP      string `json:"bmc_ip"`

	// System info
	Manufacturer string `json:"manufacturer"`
	Model        string `json:"model"`
	SerialNumber string `json:"serial_number"`
	SKU          string `json:"sku,omitempty"`
	BIOSVersion  string `json:"bios_version"`
	UUID         string `json:"uuid,omitempty"`

	// Processor info
	Processors []ProcessorInfo `json:"processors"`

	// Memory info
	MemoryTotal   uint64       `json:"memory_total"`
	MemoryModules []MemoryInfo `json:"memory_modules"`

	// Storage info
	Storage []StorageInfo `json:"storage"`

	// Network ports
	NetworkPorts []NetworkPortInfo `json:"network_ports"`

	// Power state and supplies
	PowerState         string      `json:"power_state"`
	PowerConsumedWatts int         `json:"power_consumed_watts"`
	PowerSupplies      []PowerInfo `json:"power_supplies"`

	// Cooling info
	Fans         []FanInfo  `json:"fans"`
	Temperatures []TempInfo `json:"temperatures"`

	// Health status
	HealthStatus string `json:"health_status"`

	// Collection timestamp
	CollectedAt int64 `json:"collected_at"`

	// Raw data for extended info
	RawData map[string]interface{} `json:"raw_data"`
}

// BMCCollector collects inventory from BMC
type BMCCollector struct {
	config *config.BMCConfig
	logger *logrus.Logger
	client *http.Client
}

// NewBMCCollector creates a new BMC inventory collector
func NewBMCCollector(cfg *config.BMCConfig, logger *logrus.Logger) *BMCCollector {
	// Create HTTP client with TLS config
	transport := &http.Transport{
		TLSClientConfig: &tls.Config{
			InsecureSkipVerify: cfg.InsecureSkipVerify,
		},
	}

	client := &http.Client{
		Transport: transport,
		Timeout:   30 * time.Second,
	}

	return &BMCCollector{
		config: cfg,
		logger: logger,
		client: client,
	}
}

// Collect gathers all BMC information
func (c *BMCCollector) Collect() (*BMCInventory, error) {
	switch c.config.Protocol {
	case "redfish":
		return c.collectViaRedfish()
	case "ipmi":
		return c.collectViaIPMI()
	default:
		return nil, fmt.Errorf("unsupported BMC protocol: %s", c.config.Protocol)
	}
}

// collectViaRedfish collects BMC information using Redfish API
func (c *BMCCollector) collectViaRedfish() (*BMCInventory, error) {
	inv := &BMCInventory{
		BMCIP:       c.config.IP,
		CollectedAt: time.Now().Unix(),
		RawData:     make(map[string]interface{}),
	}

	baseURL := fmt.Sprintf("https://%s:%d", c.config.IP, c.config.Port)

	// Get service root to detect BMC type
	serviceRoot, err := c.redfishGet(baseURL + "/redfish/v1/")
	if err != nil {
		return nil, fmt.Errorf("failed to get Redfish service root: %w", err)
	}
	inv.RawData["service_root"] = serviceRoot

	// Detect BMC type from service root
	if vendor, ok := serviceRoot["Vendor"].(string); ok {
		inv.BMCType = vendor
	} else if product, ok := serviceRoot["Product"].(string); ok {
		inv.BMCType = product
	}
	if version, ok := serviceRoot["RedfishVersion"].(string); ok {
		inv.BMCVersion = version
	}

	// Discover the system URL dynamically
	systemURL, err := c.discoverSystemURL(baseURL)
	if err != nil {
		c.logger.Warnf("Failed to discover system URL: %v", err)
		systemURL = "/redfish/v1/Systems/1" // Fallback to common default
	}
	c.logger.Debugf("Using system URL: %s", systemURL)

	// Get system information
	if err := c.collectSystemInfo(baseURL, systemURL, inv); err != nil {
		c.logger.Warnf("Failed to collect system info: %v", err)
	}

	// Get processor information
	if err := c.collectProcessorInfo(baseURL, systemURL, inv); err != nil {
		c.logger.Warnf("Failed to collect processor info: %v", err)
	}

	// Get memory information
	if err := c.collectMemoryInfo(baseURL, systemURL, inv); err != nil {
		c.logger.Warnf("Failed to collect memory info: %v", err)
	}

	// Get storage information
	if err := c.collectStorageInfo(baseURL, systemURL, inv); err != nil {
		c.logger.Warnf("Failed to collect storage info: %v", err)
	}

	// Get network information
	if err := c.collectNetworkInfo(baseURL, systemURL, inv); err != nil {
		c.logger.Warnf("Failed to collect network info: %v", err)
	}

	// Get chassis information (power, fans, temperatures)
	if err := c.collectChassisInfo(baseURL, inv); err != nil {
		c.logger.Warnf("Failed to collect chassis info: %v", err)
	}

	return inv, nil
}

// discoverSystemURL discovers the system URL from the Systems collection
func (c *BMCCollector) discoverSystemURL(baseURL string) (string, error) {
	systems, err := c.redfishGet(baseURL + "/redfish/v1/Systems")
	if err != nil {
		return "", err
	}

	members, ok := systems["Members"].([]interface{})
	if !ok || len(members) == 0 {
		return "", fmt.Errorf("no systems found in collection")
	}

	// Get the first system's URL
	firstMember, ok := members[0].(map[string]interface{})
	if !ok {
		return "", fmt.Errorf("invalid member format")
	}

	systemURL, ok := firstMember["@odata.id"].(string)
	if !ok {
		return "", fmt.Errorf("no @odata.id in system member")
	}

	return systemURL, nil
}

// collectSystemInfo collects system information from Redfish
func (c *BMCCollector) collectSystemInfo(baseURL string, systemURL string, inv *BMCInventory) error {
	// Get system details using the discovered URL
	system, err := c.redfishGet(baseURL + systemURL)
	if err != nil {
		return err
	}
	inv.RawData["system"] = system

	// Extract system info
	if mfr, ok := system["Manufacturer"].(string); ok {
		inv.Manufacturer = mfr
	}
	if model, ok := system["Model"].(string); ok {
		inv.Model = model
	}
	if sn, ok := system["SerialNumber"].(string); ok {
		inv.SerialNumber = sn
	}
	if sku, ok := system["SKU"].(string); ok {
		inv.SKU = sku
	}
	if uuid, ok := system["UUID"].(string); ok {
		inv.UUID = uuid
	}
	if ps, ok := system["PowerState"].(string); ok {
		inv.PowerState = ps
	}

	// Get BIOS version
	if bios, ok := system["BiosVersion"].(string); ok {
		inv.BIOSVersion = bios
	}

	// Get health status
	if status, ok := system["Status"].(map[string]interface{}); ok {
		if health, ok := status["Health"].(string); ok {
			inv.HealthStatus = health
		}
	}

	return nil
}

// collectProcessorInfo collects processor information from Redfish
func (c *BMCCollector) collectProcessorInfo(baseURL string, systemURL string, inv *BMCInventory) error {
	processors, err := c.redfishGet(baseURL + systemURL + "/Processors")
	if err != nil {
		return err
	}

	members, ok := processors["Members"].([]interface{})
	if !ok {
		return fmt.Errorf("no processor members found")
	}

	for _, member := range members {
		memberMap := member.(map[string]interface{})
		procURL := memberMap["@odata.id"].(string)

		proc, err := c.redfishGet(baseURL + procURL)
		if err != nil {
			c.logger.Warnf("Failed to get processor %s: %v", procURL, err)
			continue
		}

		procInfo := ProcessorInfo{
			ID: getStringValue(proc, "Id"),
		}

		if model, ok := proc["Model"].(string); ok {
			procInfo.Model = model
		}
		if mfr, ok := proc["Manufacturer"].(string); ok {
			procInfo.Manufacturer = mfr
		}
		if cores, ok := proc["TotalCores"].(float64); ok {
			procInfo.Cores = int(cores)
		}
		if threads, ok := proc["TotalThreads"].(float64); ok {
			procInfo.Threads = int(threads)
		}
		if speed, ok := proc["MaxSpeedMHz"].(float64); ok {
			procInfo.MaxSpeedMHz = int(speed)
		}
		if status, ok := proc["Status"].(map[string]interface{}); ok {
			if health, ok := status["Health"].(string); ok {
				procInfo.Status = health
			}
		}

		inv.Processors = append(inv.Processors, procInfo)
	}

	inv.RawData["processors"] = processors

	return nil
}

// collectMemoryInfo collects memory information from Redfish
func (c *BMCCollector) collectMemoryInfo(baseURL string, systemURL string, inv *BMCInventory) error {
	memory, err := c.redfishGet(baseURL + systemURL + "/Memory")
	if err != nil {
		return err
	}

	members, ok := memory["Members"].([]interface{})
	if !ok {
		return fmt.Errorf("no memory members found")
	}

	var totalMemory uint64
	for _, member := range members {
		memberMap := member.(map[string]interface{})
		memURL := memberMap["@odata.id"].(string)

		mem, err := c.redfishGet(baseURL + memURL)
		if err != nil {
			c.logger.Warnf("Failed to get memory %s: %v", memURL, err)
			continue
		}

		memInfo := MemoryInfo{
			ID: getStringValue(mem, "Id"),
		}

		if mfr, ok := mem["Manufacturer"].(string); ok {
			memInfo.Manufacturer = mfr
		}
		if pn, ok := mem["PartNumber"].(string); ok {
			memInfo.PartNumber = strings.TrimSpace(pn)
		}
		if sn, ok := mem["SerialNumber"].(string); ok {
			memInfo.SerialNumber = strings.TrimSpace(sn)
		}
		if cap, ok := mem["CapacityMiB"].(float64); ok {
			memInfo.CapacityMiB = int(cap)
			totalMemory += uint64(cap) * 1024 * 1024 // Convert MiB to bytes
		}
		if speed, ok := mem["OperatingSpeedMhz"].(float64); ok {
			memInfo.SpeedMHz = int(speed)
		}
		if mt, ok := mem["MemoryDeviceType"].(string); ok {
			memInfo.MemoryType = mt
		}
		if status, ok := mem["Status"].(map[string]interface{}); ok {
			if health, ok := status["Health"].(string); ok {
				memInfo.Status = health
			}
		}

		inv.MemoryModules = append(inv.MemoryModules, memInfo)
	}

	inv.MemoryTotal = totalMemory
	inv.RawData["memory"] = memory

	return nil
}

// collectStorageInfo collects storage information from Redfish
func (c *BMCCollector) collectStorageInfo(baseURL string, systemURL string, inv *BMCInventory) error {
	storage, err := c.redfishGet(baseURL + systemURL + "/Storage")
	if err != nil {
		return err
	}

	members, ok := storage["Members"].([]interface{})
	if !ok {
		return nil
	}

	for _, member := range members {
		memberMap := member.(map[string]interface{})
		storageURL := memberMap["@odata.id"].(string)

		storageController, err := c.redfishGet(baseURL + storageURL)
		if err != nil {
			continue
		}

		// Get drives from this controller
		drives, ok := storageController["Drives"].([]interface{})
		if !ok {
			continue
		}

		for _, drive := range drives {
			driveMap := drive.(map[string]interface{})
			driveURL := driveMap["@odata.id"].(string)

			driveInfo, err := c.redfishGet(baseURL + driveURL)
			if err != nil {
				continue
			}

			storageInfo := StorageInfo{
				ID: getStringValue(driveInfo, "Id"),
			}

			if name, ok := driveInfo["Name"].(string); ok {
				storageInfo.Name = name
			}
			if model, ok := driveInfo["Model"].(string); ok {
				storageInfo.Model = model
			}
			if mfr, ok := driveInfo["Manufacturer"].(string); ok {
				storageInfo.Manufacturer = mfr
			}
			if cap, ok := driveInfo["CapacityBytes"].(float64); ok {
				storageInfo.CapacityGB = int64(cap / (1024 * 1024 * 1024))
			}
			if media, ok := driveInfo["MediaType"].(string); ok {
				storageInfo.MediaType = media
			}
			if proto, ok := driveInfo["Protocol"].(string); ok {
				storageInfo.Protocol = proto
			}
			if status, ok := driveInfo["Status"].(map[string]interface{}); ok {
				if health, ok := status["Health"].(string); ok {
					storageInfo.Status = health
				}
			}

			inv.Storage = append(inv.Storage, storageInfo)
		}
	}

	inv.RawData["storage"] = storage

	return nil
}

// collectNetworkInfo collects network information from Redfish
func (c *BMCCollector) collectNetworkInfo(baseURL string, systemURL string, inv *BMCInventory) error {
	// Try to get network interfaces from system
	network, err := c.redfishGet(baseURL + systemURL + "/EthernetInterfaces")
	if err != nil {
		return err
	}

	members, ok := network["Members"].([]interface{})
	if !ok {
		return nil
	}

	for _, member := range members {
		memberMap := member.(map[string]interface{})
		nicURL := memberMap["@odata.id"].(string)

		nic, err := c.redfishGet(baseURL + nicURL)
		if err != nil {
			continue
		}

		portInfo := NetworkPortInfo{
			ID: getStringValue(nic, "Id"),
		}

		if mac, ok := nic["MACAddress"].(string); ok {
			portInfo.MACAddress = mac
		}
		if speed, ok := nic["SpeedMbps"].(float64); ok {
			portInfo.SpeedMbps = int(speed)
		}
		if link, ok := nic["LinkStatus"].(string); ok {
			portInfo.LinkStatus = link
		}

		// Get IP addresses
		if ipv4, ok := nic["IPv4Addresses"].([]interface{}); ok {
			for _, ip := range ipv4 {
				ipMap := ip.(map[string]interface{})
				if addr, ok := ipMap["Address"].(string); ok && addr != "" {
					portInfo.IPAddresses = append(portInfo.IPAddresses, addr)
				}
			}
		}

		inv.NetworkPorts = append(inv.NetworkPorts, portInfo)
	}

	inv.RawData["network"] = network

	return nil
}

// collectChassisInfo collects chassis information (power, fans, temps) from Redfish
func (c *BMCCollector) collectChassisInfo(baseURL string, inv *BMCInventory) error {
	// Get chassis collection
	chassis, err := c.redfishGet(baseURL + "/redfish/v1/Chassis")
	if err != nil {
		return err
	}

	members, ok := chassis["Members"].([]interface{})
	if !ok || len(members) == 0 {
		return fmt.Errorf("no chassis found")
	}

	// Find the best chassis for power/thermal data
	// Priority: "Self" > chassis with Power endpoint > first chassis
	var chassisURL string
	
	// First, look for "Self" chassis
	for _, member := range members {
		memberMap := member.(map[string]interface{})
		url := memberMap["@odata.id"].(string)
		if strings.HasSuffix(url, "/Self") {
			chassisURL = url
			break
		}
	}
	
	// If no "Self" found, try to find a chassis with Power data
	if chassisURL == "" {
		for _, member := range members {
			memberMap := member.(map[string]interface{})
			url := memberMap["@odata.id"].(string)
			// Try to access Power endpoint
			if power, err := c.redfishGet(baseURL + url + "/Power"); err == nil {
				if _, hasPowerControl := power["PowerControl"]; hasPowerControl {
					chassisURL = url
					break
				}
				if _, hasPowerSupplies := power["PowerSupplies"]; hasPowerSupplies {
					chassisURL = url
					break
				}
			}
		}
	}
	
	// Fall back to first chassis if nothing else found
	if chassisURL == "" {
		firstMember := members[0].(map[string]interface{})
		chassisURL = firstMember["@odata.id"].(string)
	}

	// Get power information
	c.collectPowerInfo(baseURL+chassisURL, inv)

	// Get thermal information (fans and temperatures)
	c.collectThermalInfo(baseURL+chassisURL, inv)

	return nil
}

// collectPowerInfo collects power supply information
func (c *BMCCollector) collectPowerInfo(chassisURL string, inv *BMCInventory) {
	power, err := c.redfishGet(chassisURL + "/Power")
	if err != nil {
		return
	}

	// Get total power consumption from PowerControl
	if powerControl, ok := power["PowerControl"].([]interface{}); ok && len(powerControl) > 0 {
		if pc, ok := powerControl[0].(map[string]interface{}); ok {
			if consumed, ok := pc["PowerConsumedWatts"].(float64); ok {
				inv.PowerConsumedWatts = int(consumed)
			}
		}
	}

	// Debug: log raw power supplies data to see what fields BMC returns
	if supplies, ok := power["PowerSupplies"].([]interface{}); ok {
		c.logger.Debugf("Found %d power supplies in Redfish response", len(supplies))
		for i, supply := range supplies {
			if supplyMap, ok := supply.(map[string]interface{}); ok {
				// Log all available fields for debugging
				c.logger.Debugf("PSU[%d] raw fields: %+v", i, supplyMap)
			}
		}
	}

	if supplies, ok := power["PowerSupplies"].([]interface{}); ok {
		for _, supply := range supplies {
			supplyMap := supply.(map[string]interface{})
			psuInfo := PowerInfo{
				ID: getStringValue(supplyMap, "MemberId"),
			}

			// Try multiple field names for Manufacturer (different BMC vendors use different names)
			if mfr, ok := supplyMap["Manufacturer"].(string); ok && mfr != "" {
				psuInfo.Manufacturer = mfr
			} else if mfr, ok := supplyMap["PowerSupplyType"].(string); ok && mfr != "" {
				// Some BMCs put manufacturer info in PowerSupplyType
				psuInfo.Manufacturer = mfr
			} else if name, ok := supplyMap["Name"].(string); ok && name != "" {
				// Fallback: extract from Name field
				psuInfo.Manufacturer = name
			}

			// Try multiple field names for Model
			if model, ok := supplyMap["Model"].(string); ok && model != "" {
				psuInfo.Model = model
			} else if pn, ok := supplyMap["PartNumber"].(string); ok && pn != "" {
				psuInfo.Model = pn
			} else if spn, ok := supplyMap["SparePartNumber"].(string); ok && spn != "" {
				psuInfo.Model = spn
			}

			if sn, ok := supplyMap["SerialNumber"].(string); ok {
				psuInfo.SerialNumber = sn
			}
			if cap, ok := supplyMap["PowerCapacityWatts"].(float64); ok {
				psuInfo.PowerCapacity = int(cap)
			}

			// Get individual PSU output power - try multiple field names
			if output, ok := supplyMap["PowerOutputWatts"].(float64); ok {
				psuInfo.PowerOutputWatts = int(output)
			} else if output, ok := supplyMap["LastPowerOutputWatts"].(float64); ok {
				psuInfo.PowerOutputWatts = int(output)
			} else if output, ok := supplyMap["PowerInputWatts"].(float64); ok {
				// Some BMCs report input instead of output
				psuInfo.PowerOutputWatts = int(output)
			} else if lineInput, ok := supplyMap["LineInputVoltage"].(float64); ok {
				// Try to get from line input info (some Gigabyte BMCs)
				if lineInputType, ok := supplyMap["LineInputVoltageType"].(string); ok && lineInputType != "" {
					c.logger.Debugf("PSU %s: LineInputVoltage=%.1fV, Type=%s", psuInfo.ID, lineInput, lineInputType)
				}
			}

			// Check Oem section for vendor-specific data (common for Gigabyte/AMI BMCs)
			if oem, ok := supplyMap["Oem"].(map[string]interface{}); ok {
				for vendor, data := range oem {
					if vendorData, ok := data.(map[string]interface{}); ok {
						c.logger.Debugf("PSU %s Oem/%s data: %+v", psuInfo.ID, vendor, vendorData)
						// Try to extract any useful info from OEM section
						if mfr, ok := vendorData["Manufacturer"].(string); ok && psuInfo.Manufacturer == "" {
							psuInfo.Manufacturer = mfr
						}
						if model, ok := vendorData["Model"].(string); ok && psuInfo.Model == "" {
							psuInfo.Model = model
						}
						if output, ok := vendorData["PowerOutputWatts"].(float64); ok && psuInfo.PowerOutputWatts == 0 {
							psuInfo.PowerOutputWatts = int(output)
						}
					}
				}
			}

			if status, ok := supplyMap["Status"].(map[string]interface{}); ok {
				if health, ok := status["Health"].(string); ok {
					psuInfo.Status = health
				}
			}

			// Log what we found for debugging
			c.logger.Debugf("PSU collected: ID=%s, Manufacturer=%s, Model=%s, Capacity=%dW, Output=%dW",
				psuInfo.ID, psuInfo.Manufacturer, psuInfo.Model, psuInfo.PowerCapacity, psuInfo.PowerOutputWatts)

			inv.PowerSupplies = append(inv.PowerSupplies, psuInfo)
		}
	}

	inv.RawData["power"] = power
}

// collectThermalInfo collects fan and temperature information
func (c *BMCCollector) collectThermalInfo(chassisURL string, inv *BMCInventory) {
	thermal, err := c.redfishGet(chassisURL + "/Thermal")
	if err != nil {
		return
	}

	// Collect fans
	if fans, ok := thermal["Fans"].([]interface{}); ok {
		for _, fan := range fans {
			fanMap := fan.(map[string]interface{})
			fanInfo := FanInfo{
				ID: getStringValue(fanMap, "MemberId"),
			}

			if name, ok := fanMap["Name"].(string); ok {
				fanInfo.Name = name
			}
			if rpm, ok := fanMap["Reading"].(float64); ok {
				fanInfo.SpeedRPM = int(rpm)
			}
			if pct, ok := fanMap["ReadingUnits"].(string); ok && pct == "Percent" {
				if reading, ok := fanMap["Reading"].(float64); ok {
					fanInfo.SpeedPct = int(reading)
				}
			}
			if status, ok := fanMap["Status"].(map[string]interface{}); ok {
				if health, ok := status["Health"].(string); ok {
					fanInfo.Status = health
				}
			}

			inv.Fans = append(inv.Fans, fanInfo)
		}
	}

	// Collect temperatures
	if temps, ok := thermal["Temperatures"].([]interface{}); ok {
		for _, temp := range temps {
			tempMap := temp.(map[string]interface{})
			tempInfo := TempInfo{
				ID: getStringValue(tempMap, "MemberId"),
			}

			if name, ok := tempMap["Name"].(string); ok {
				tempInfo.Name = name
			}
			if reading, ok := tempMap["ReadingCelsius"].(float64); ok {
				tempInfo.ReadingCelsius = reading
			}
			if upper, ok := tempMap["UpperThresholdNonCritical"].(float64); ok {
				tempInfo.UpperThreshold = upper
			}
			if critical, ok := tempMap["UpperThresholdCritical"].(float64); ok {
				tempInfo.CriticalThreshold = critical
			}
			if status, ok := tempMap["Status"].(map[string]interface{}); ok {
				if health, ok := status["Health"].(string); ok {
					tempInfo.Status = health
				}
			}

			inv.Temperatures = append(inv.Temperatures, tempInfo)
		}
	}

	inv.RawData["thermal"] = thermal
}

// redfishGet performs an authenticated GET request to the Redfish API
func (c *BMCCollector) redfishGet(url string) (map[string]interface{}, error) {
	req, err := http.NewRequest("GET", url, nil)
	if err != nil {
		return nil, err
	}

	// Set Basic Auth
	auth := base64.StdEncoding.EncodeToString(
		[]byte(c.config.Username + ":" + c.config.Password))
	req.Header.Set("Authorization", "Basic "+auth)
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Accept", "application/json")

	resp, err := c.client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("Redfish request failed: %d - %s", resp.StatusCode, string(body))
	}

	var result map[string]interface{}
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, err
	}

	return result, nil
}

// collectViaIPMI collects BMC information using IPMI protocol
func (c *BMCCollector) collectViaIPMI() (*BMCInventory, error) {
	inv := &BMCInventory{
		BMCIP:       c.config.IP,
		BMCType:     "IPMI",
		CollectedAt: time.Now().Unix(),
		RawData:     make(map[string]interface{}),
	}

	// IPMI collection requires ipmitool command
	// This is a simplified implementation - in production, consider using a Go IPMI library
	c.logger.Info("Collecting BMC information via IPMI")

	// Collect FRU info
	if err := c.collectIPMIFRU(inv); err != nil {
		c.logger.Warnf("Failed to collect IPMI FRU: %v", err)
	}

	// Collect sensor data
	if err := c.collectIPMISensors(inv); err != nil {
		c.logger.Warnf("Failed to collect IPMI sensors: %v", err)
	}

	// Get power status
	if err := c.collectIPMIPowerStatus(inv); err != nil {
		c.logger.Warnf("Failed to collect IPMI power status: %v", err)
	}

	return inv, nil
}

// collectIPMIFRU collects FRU (Field Replaceable Unit) data via IPMI
func (c *BMCCollector) collectIPMIFRU(inv *BMCInventory) error {
	// Note: In a production environment, use a proper IPMI library
	// This shows the structure for IPMI data collection
	inv.RawData["ipmi_fru"] = map[string]interface{}{
		"note": "IPMI FRU collection requires ipmitool or IPMI library",
	}
	return nil
}

// collectIPMISensors collects sensor data via IPMI
func (c *BMCCollector) collectIPMISensors(inv *BMCInventory) error {
	// Parse sensor data and populate temperatures, fans, etc.
	inv.RawData["ipmi_sensors"] = map[string]interface{}{
		"note": "IPMI sensor collection requires ipmitool or IPMI library",
	}
	return nil
}

// collectIPMIPowerStatus collects power status via IPMI
func (c *BMCCollector) collectIPMIPowerStatus(inv *BMCInventory) error {
	inv.PowerState = "Unknown"
	return nil
}

// ToMap converts BMCInventory to map for sending
func (inv *BMCInventory) ToMap() map[string]interface{} {
	return map[string]interface{}{
		"bmc_type":             inv.BMCType,
		"bmc_version":          inv.BMCVersion,
		"bmc_ip":               inv.BMCIP,
		"manufacturer":         inv.Manufacturer,
		"model":                inv.Model,
		"serial_number":        inv.SerialNumber,
		"sku":                  inv.SKU,
		"bios_version":         inv.BIOSVersion,
		"uuid":                 inv.UUID,
		"processors":           inv.Processors,
		"memory_total":         inv.MemoryTotal,
		"memory_modules":       inv.MemoryModules,
		"storage":              inv.Storage,
		"network_ports":        inv.NetworkPorts,
		"power_state":          inv.PowerState,
		"power_consumed_watts": inv.PowerConsumedWatts,
		"power_supplies":       inv.PowerSupplies,
		"fans":                 inv.Fans,
		"temperatures":         inv.Temperatures,
		"health_status":        inv.HealthStatus,
		"collected_at":         inv.CollectedAt,
		"raw_data":             inv.RawData,
	}
}

// getStringValue safely gets a string value from a map
func getStringValue(m map[string]interface{}, key string) string {
	if v, ok := m[key].(string); ok {
		return v
	}
	return ""
}
