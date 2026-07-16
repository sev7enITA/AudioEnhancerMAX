"""
AudioEnhancerMAX by Fd - System Monitor Service v2
Real-time CPU/GPU/ANE/RAM monitoring for Apple Silicon M3 MAX.
Uses psutil (CPU/RAM) + macmon pipe (GPU/ANE/Power/Thermal).

Architecture:
  - psutil thread: collects CPU/RAM/disk/net every 2s
  - macmon thread: reads pipe continuously, updates atomic buffer
  - get_stats(): returns merged snapshot (lock-free dict copy)
"""
import json
import logging
import os
import platform
import shutil
import subprocess
import threading
import time
from collections import deque
from typing import Optional

import psutil

logger = logging.getLogger(__name__)

# Rolling history (60 seconds at 1-second intervals)
_HISTORY_SIZE = 60


class SystemMonitor:
    """Collects real-time system metrics for Apple Silicon."""

    def __init__(self):
        self._lock = threading.Lock()
        self._running = False
        self._psutil_thread: Optional[threading.Thread] = None
        self._macmon_thread: Optional[threading.Thread] = None
        self._macmon_proc: Optional[subprocess.Popen] = None

        # Separate data stores for each source - merged on read
        self._psutil_data = {}
        self._macmon_data = {}

        # Static info
        self._chip = self._detect_chip()
        self._platform = platform.machine()

        # Current snapshot (merged)
        self._current = {
            "cpu_percent": 0.0,
            "cpu_per_core": [],
            "ram_percent": 0.0,
            "ram_used_gb": 0.0,
            "ram_total_gb": 0.0,
            "gpu_percent": 0.0,
            "ane_percent": 0.0,
            "power_watts": 0.0,
            "thermal_pressure": "nominal",
            "cpu_freq_ghz": 0.0,
            "gpu_freq_ghz": 0.0,
            "swap_used_gb": 0.0,
            "cpu_temp_c": 0,
            "gpu_temp_c": 0,
            "disk_read_mb_s": 0.0,
            "disk_write_mb_s": 0.0,
            "net_sent_mb_s": 0.0,
            "net_recv_mb_s": 0.0,
            "timestamp": 0.0,
            "platform": self._platform,
            "chip": self._chip,
            "macmon_available": False,
        }

        # History ring buffers
        self._history = {
            "cpu_percent": deque(maxlen=_HISTORY_SIZE),
            "gpu_percent": deque(maxlen=_HISTORY_SIZE),
            "ane_percent": deque(maxlen=_HISTORY_SIZE),
            "ram_percent": deque(maxlen=_HISTORY_SIZE),
            "power_watts": deque(maxlen=_HISTORY_SIZE),
            "timestamps": deque(maxlen=_HISTORY_SIZE),
        }

        # I/O counters for delta calculation
        self._prev_disk = None
        self._prev_net = None
        self._prev_time = time.time()

        # psutil warmup - MUST be called before first interval=None call
        # See: https://psutil.readthedocs.io/en/latest/#psutil.cpu_percent
        psutil.cpu_percent(interval=None)
        psutil.cpu_percent(interval=None, percpu=True)

    @staticmethod
    def _detect_chip() -> str:
        """Detect Apple Silicon chip name."""
        try:
            result = subprocess.run(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                capture_output=True, text=True, timeout=5
            )
            return result.stdout.strip()
        except Exception:
            return platform.processor() or "Unknown"

    def _find_macmon(self) -> Optional[str]:
        """Find macmon binary."""
        for p in ["/opt/homebrew/bin/macmon", "/usr/local/bin/macmon"]:
            if os.path.isfile(p):
                return p
        found = shutil.which("macmon")
        return found

    def start(self):
        """Start the monitoring background threads."""
        if self._running:
            return
        self._running = True

        # Thread 1: psutil metrics (CPU/RAM/disk/net) - every 2s
        self._psutil_thread = threading.Thread(
            target=self._psutil_loop, daemon=True, name="sysmon-psutil"
        )
        self._psutil_thread.start()

        # Thread 2: macmon pipe reader (GPU/ANE/power/temp) - continuous
        macmon_path = self._find_macmon()
        if macmon_path:
            self._macmon_thread = threading.Thread(
                target=self._macmon_loop, args=(macmon_path,),
                daemon=True, name="sysmon-macmon"
            )
            self._macmon_thread.start()
        else:
            logger.info("macmon not found - GPU/ANE metrics unavailable, using psutil only")

        logger.info(f"System monitor started (chip: {self._chip})")

    def stop(self):
        """Stop monitoring."""
        self._running = False
        if self._macmon_proc:
            try:
                self._macmon_proc.terminate()
            except Exception:
                pass
        if self._psutil_thread:
            self._psutil_thread.join(timeout=3)
        if self._macmon_thread:
            self._macmon_thread.join(timeout=3)

    # ── psutil collection thread ──────────────────────────

    def _psutil_loop(self):
        """Collect CPU/RAM/disk/net metrics every 2 seconds."""
        while self._running:
            try:
                self._collect_psutil_metrics()
                self._update_snapshot_and_history()
                time.sleep(2)
            except Exception as e:
                logger.error(f"psutil monitor error: {e}")
                time.sleep(3)

    def _collect_psutil_metrics(self):
        """Collect CPU, RAM, disk, network metrics via psutil."""
        now = time.time()
        dt = now - self._prev_time

        # CPU - interval=None is non-blocking after warmup
        cpu_pct = psutil.cpu_percent(interval=None)
        cpu_per_core = psutil.cpu_percent(interval=None, percpu=True)
        cpu_freq = psutil.cpu_freq()

        # RAM
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()

        # Disk I/O delta
        disk = psutil.disk_io_counters()
        disk_read = 0.0
        disk_write = 0.0
        if self._prev_disk and dt > 0:
            disk_read = (disk.read_bytes - self._prev_disk.read_bytes) / dt / 1024 / 1024
            disk_write = (disk.write_bytes - self._prev_disk.write_bytes) / dt / 1024 / 1024
        self._prev_disk = disk

        # Network I/O delta
        net = psutil.net_io_counters()
        net_sent = 0.0
        net_recv = 0.0
        if self._prev_net and dt > 0:
            net_sent = (net.bytes_sent - self._prev_net.bytes_sent) / dt / 1024 / 1024
            net_recv = (net.bytes_recv - self._prev_net.bytes_recv) / dt / 1024 / 1024
        self._prev_net = net
        self._prev_time = now

        self._psutil_data = {
            "cpu_percent": round(cpu_pct, 1),
            "cpu_per_core": [round(c, 1) for c in cpu_per_core],
            "cpu_freq_ghz": round(cpu_freq.current / 1000, 2) if cpu_freq else 0,
            "ram_percent": round(mem.percent, 1),
            "ram_used_gb": round(mem.used / 1024**3, 2),
            "ram_total_gb": round(mem.total / 1024**3, 2),
            "swap_used_gb": round(swap.used / 1024**3, 2),
            "disk_read_mb_s": round(max(0, disk_read), 1),
            "disk_write_mb_s": round(max(0, disk_write), 1),
            "net_sent_mb_s": round(max(0, net_sent), 2),
            "net_recv_mb_s": round(max(0, net_recv), 2),
        }

    # ── macmon pipe reader thread ─────────────────────────

    def _macmon_loop(self, macmon_path: str):
        """Continuously read macmon pipe output in dedicated thread."""
        try:
            self._macmon_proc = subprocess.Popen(
                [macmon_path, "pipe", "--interval", "1000"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
            )
            logger.info(f"macmon pipe started: {macmon_path}")

            with self._lock:
                self._current["macmon_available"] = True

            while self._running and self._macmon_proc.poll() is None:
                line = self._macmon_proc.stdout.readline()
                if not line:
                    break
                self._parse_macmon_line(line.strip())

        except Exception as e:
            logger.warning(f"macmon failed: {e}")
        finally:
            if self._macmon_proc:
                try:
                    self._macmon_proc.terminate()
                except Exception:
                    pass
            logger.info("macmon pipe stopped")

    def _parse_macmon_line(self, line: str):
        """Parse a single macmon JSON line and update macmon data buffer."""
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            return

        result = {}

        # CPU usage - macmon gives 0-1 float
        cpu_pct = data.get("cpu_usage_pct", 0)
        if isinstance(cpu_pct, (int, float)) and cpu_pct > 0:
            result["cpu_percent"] = round(cpu_pct * 100, 1)

        # GPU usage - macmon gives [freq_mhz, usage_fraction]
        gpu_data = data.get("gpu_usage")
        if isinstance(gpu_data, list) and len(gpu_data) >= 2:
            gpu_freq_mhz = gpu_data[0]
            gpu_pct = gpu_data[1]  # 0.0 to 1.0
            result["gpu_percent"] = round(gpu_pct * 100, 1)
            if gpu_freq_mhz > 0:
                result["gpu_freq_ghz"] = round(gpu_freq_mhz / 1000, 2)
        elif isinstance(gpu_data, (int, float)):
            result["gpu_percent"] = round(gpu_data * 100 if gpu_data <= 1 else gpu_data, 1)

        # ANE power -> proxy for ANE usage (max ~8W on M3 Max)
        ane_power = data.get("ane_power", 0)
        if isinstance(ane_power, (int, float)) and ane_power > 0:
            result["ane_percent"] = round(min(100, ane_power / 8.0 * 100), 1)

        # Total system power
        sys_power = data.get("sys_power", data.get("all_power", 0))
        if isinstance(sys_power, (int, float)) and sys_power > 0:
            result["power_watts"] = round(sys_power, 1)

        # Memory from macmon (unified memory - more accurate than psutil)
        mem_data = data.get("memory", {})
        if isinstance(mem_data, dict):
            ram_total = mem_data.get("ram_total", 0)
            ram_usage = mem_data.get("ram_usage", 0)
            if ram_total > 0:
                result["ram_total_gb"] = round(ram_total / 1024**3, 2)
                result["ram_used_gb"] = round(ram_usage / 1024**3, 2)
                result["ram_percent"] = round(ram_usage / ram_total * 100, 1)
            swap_usage = mem_data.get("swap_usage", 0)
            if swap_usage > 0:
                result["swap_used_gb"] = round(swap_usage / 1024**3, 2)

        # Temperature
        temp_data = data.get("temp", {})
        if isinstance(temp_data, dict):
            cpu_temp = temp_data.get("cpu_temp_avg", 0)
            gpu_temp = temp_data.get("gpu_temp_avg", 0)
            if cpu_temp:
                result["cpu_temp_c"] = round(cpu_temp, 1)
            if gpu_temp:
                result["gpu_temp_c"] = round(gpu_temp, 1)
            # Thermal pressure from temperature
            if cpu_temp > 95:
                result["thermal_pressure"] = "critical"
            elif cpu_temp > 85:
                result["thermal_pressure"] = "serious"
            elif cpu_temp > 75:
                result["thermal_pressure"] = "moderate"
            else:
                result["thermal_pressure"] = "nominal"

        # Store atomically
        self._macmon_data = result

    # ── Snapshot merging ──────────────────────────────────

    def _update_snapshot_and_history(self):
        """Merge psutil + macmon data into current snapshot and update history."""
        with self._lock:
            now = time.time()

            # Start with psutil data as base
            self._current.update(self._psutil_data)

            # Overlay macmon data (overwrites psutil for shared keys like ram_percent)
            if self._macmon_data:
                self._current.update(self._macmon_data)

            self._current["timestamp"] = now

            # Update history
            self._history["cpu_percent"].append(self._current["cpu_percent"])
            self._history["gpu_percent"].append(self._current["gpu_percent"])
            self._history["ane_percent"].append(self._current["ane_percent"])
            self._history["ram_percent"].append(self._current["ram_percent"])
            self._history["power_watts"].append(self._current["power_watts"])
            self._history["timestamps"].append(now)

    # ── Public API ────────────────────────────────────────

    def get_stats(self) -> dict:
        """Get current system stats snapshot."""
        with self._lock:
            return dict(self._current)

    def get_history(self) -> dict:
        """Get last 60 seconds of metrics history."""
        with self._lock:
            return {
                k: list(v) for k, v in self._history.items()
            }


# Global singleton
system_monitor = SystemMonitor()
