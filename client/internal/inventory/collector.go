// Package inventory provides system inventory collection
package inventory

import (
	"runtime"
	"time"

	"github.com/shirou/gopsutil/v3/cpu"
	"github.com/shirou/gopsutil/v3/disk"
	"github.com/shirou/gopsutil/v3/host"
	"github.com/shirou/gopsutil/v3/mem"
	"github.com/shirou/gopsutil/v3/net"
	"github.com/sirupsen/logrus"
)

// Inventory represents collected system information
type Inventory struct {
	// Common fields
	Hostname    string `json:"hostname"`
	OS          string `json:"os"`
	Platform    string `json:"platform"`
	Arch        string `json:"arch"`
	CollectedAt int64  `json:"collected_at"`

	// CPU
	CPUCount int    `json:"cpu_count"`
	CPUModel string `json:"cpu_model"`

	// Memory
	MemoryTotal uint64 `json:"memory_total"`
	MemoryUsed  uint64 `json:"memory_used"`
	MemoryFree  uint64 `json:"memory_free"`

	// Disk
	DiskTotal uint64 `json:"disk_total"`
	DiskUsed  uint64 `json:"disk_used"`
	DiskFree  uint64 `json:"disk_free"`

	// Network
	IPAddresses  []string `json:"ip_addresses"`
	MACAddresses []string `json:"mac_addresses"`

	// Raw data for extended info
	RawData map[string]interface{} `json:"raw_data"`
}

// Collector collects system inventory
type Collector struct {
	logger *logrus.Logger
}

// NewCollector creates a new inventory collector
func NewCollector(logger *logrus.Logger) *Collector {
	return &Collector{
		logger: logger,
	}
}

// Collect gathers all system information
func (c *Collector) Collect() (*Inventory, error) {
	inv := &Inventory{
		CollectedAt: time.Now().Unix(),
		RawData:     make(map[string]interface{}),
	}

	// Collect host info
	if err := c.collectHostInfo(inv); err != nil {
		c.logger.Warnf("Failed to collect host info: %v", err)
	}

	// Collect CPU info
	if err := c.collectCPUInfo(inv); err != nil {
		c.logger.Warnf("Failed to collect CPU info: %v", err)
	}

	// Collect memory info
	if err := c.collectMemoryInfo(inv); err != nil {
		c.logger.Warnf("Failed to collect memory info: %v", err)
	}

	// Collect disk info
	if err := c.collectDiskInfo(inv); err != nil {
		c.logger.Warnf("Failed to collect disk info: %v", err)
	}

	// Collect network info
	if err := c.collectNetworkInfo(inv); err != nil {
		c.logger.Warnf("Failed to collect network info: %v", err)
	}

	return inv, nil
}

// collectHostInfo collects host information
func (c *Collector) collectHostInfo(inv *Inventory) error {
	hostInfo, err := host.Info()
	if err != nil {
		return err
	}

	inv.Hostname = hostInfo.Hostname
	inv.OS = hostInfo.OS
	inv.Platform = hostInfo.Platform
	inv.Arch = runtime.GOARCH

	// Store raw data
	inv.RawData["host"] = map[string]interface{}{
		"hostname":         hostInfo.Hostname,
		"os":               hostInfo.OS,
		"platform":         hostInfo.Platform,
		"platform_family":  hostInfo.PlatformFamily,
		"platform_version": hostInfo.PlatformVersion,
		"kernel_version":   hostInfo.KernelVersion,
		"kernel_arch":      hostInfo.KernelArch,
		"uptime":           hostInfo.Uptime,
		"boot_time":        hostInfo.BootTime,
	}

	return nil
}

// collectCPUInfo collects CPU information
func (c *Collector) collectCPUInfo(inv *Inventory) error {
	cpuInfo, err := cpu.Info()
	if err != nil {
		return err
	}

	inv.CPUCount = len(cpuInfo)
	if len(cpuInfo) > 0 {
		inv.CPUModel = cpuInfo[0].ModelName
	}

	// Get logical CPU count
	logicalCount, _ := cpu.Counts(true)
	physicalCount, _ := cpu.Counts(false)

	inv.RawData["cpu"] = map[string]interface{}{
		"info":           cpuInfo,
		"logical_count":  logicalCount,
		"physical_count": physicalCount,
	}

	return nil
}

// collectMemoryInfo collects memory information
func (c *Collector) collectMemoryInfo(inv *Inventory) error {
	memInfo, err := mem.VirtualMemory()
	if err != nil {
		return err
	}

	inv.MemoryTotal = memInfo.Total
	inv.MemoryUsed = memInfo.Used
	inv.MemoryFree = memInfo.Free

	inv.RawData["memory"] = map[string]interface{}{
		"total":         memInfo.Total,
		"used":          memInfo.Used,
		"free":          memInfo.Free,
		"available":     memInfo.Available,
		"used_percent":  memInfo.UsedPercent,
		"cached":        memInfo.Cached,
		"buffers":       memInfo.Buffers,
	}

	return nil
}

// collectDiskInfo collects disk information
func (c *Collector) collectDiskInfo(inv *Inventory) error {
	partitions, err := disk.Partitions(false)
	if err != nil {
		return err
	}

	var totalDisk, usedDisk, freeDisk uint64
	diskDetails := []map[string]interface{}{}

	for _, part := range partitions {
		usage, err := disk.Usage(part.Mountpoint)
		if err != nil {
			continue
		}

		totalDisk += usage.Total
		usedDisk += usage.Used
		freeDisk += usage.Free

		diskDetails = append(diskDetails, map[string]interface{}{
			"device":       part.Device,
			"mountpoint":   part.Mountpoint,
			"fstype":       part.Fstype,
			"total":        usage.Total,
			"used":         usage.Used,
			"free":         usage.Free,
			"used_percent": usage.UsedPercent,
		})
	}

	inv.DiskTotal = totalDisk
	inv.DiskUsed = usedDisk
	inv.DiskFree = freeDisk

	inv.RawData["disks"] = diskDetails

	return nil
}

// collectNetworkInfo collects network information
func (c *Collector) collectNetworkInfo(inv *Inventory) error {
	interfaces, err := net.Interfaces()
	if err != nil {
		return err
	}

	ipAddrs := []string{}
	macAddrs := []string{}
	networkDetails := []map[string]interface{}{}

	for _, iface := range interfaces {
		// Skip loopback and down interfaces
		if iface.Name == "lo" || len(iface.Flags) == 0 {
			continue
		}

		// Collect IP addresses
		for _, addr := range iface.Addrs {
			ipAddrs = append(ipAddrs, addr.Addr)
		}

		// Collect MAC address
		if iface.HardwareAddr != "" {
			macAddrs = append(macAddrs, iface.HardwareAddr)
		}

		networkDetails = append(networkDetails, map[string]interface{}{
			"name":          iface.Name,
			"hardware_addr": iface.HardwareAddr,
			"addresses":     iface.Addrs,
			"flags":         iface.Flags,
			"mtu":           iface.MTU,
		})
	}

	inv.IPAddresses = ipAddrs
	inv.MACAddresses = macAddrs

	inv.RawData["network"] = networkDetails

	return nil
}

// ToMap converts Inventory to map for sending
func (inv *Inventory) ToMap() map[string]interface{} {
	return map[string]interface{}{
		"hostname":      inv.Hostname,
		"os":            inv.OS,
		"platform":      inv.Platform,
		"arch":          inv.Arch,
		"collected_at":  inv.CollectedAt,
		"cpu_count":     inv.CPUCount,
		"cpu_model":     inv.CPUModel,
		"memory_total":  inv.MemoryTotal,
		"memory_used":   inv.MemoryUsed,
		"memory_free":   inv.MemoryFree,
		"disk_total":    inv.DiskTotal,
		"disk_used":     inv.DiskUsed,
		"disk_free":     inv.DiskFree,
		"ip_addresses":  inv.IPAddresses,
		"mac_addresses": inv.MACAddresses,
		"raw_data":      inv.RawData,
	}
}
