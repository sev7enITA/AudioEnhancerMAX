"""
AudioEnhancerMAX by Fd - System Monitor Service v2
Real-time CPU and memory metrics, with optional Apple Silicon sensors from macmon.

Architecture:
  - psutil thread: collects CPU/RAM/disk/net every 2s
  - macmon thread: reads pipe continuously, updates a separate sensor buffer
  - get_stats(): returns merged snapshot (protected by the snapshot lock)
"""
import json
import logging
import math
import os
import platform
import shutil
import subprocess
import sys
import threading
import time
from collections import deque
from typing import Optional

import psutil

from app.services.apple_acceleration import detect_host_chip

logger = logging.getLogger(__name__)

# Rolling history at the two-second snapshot cadence.
_HISTORY_SIZE = 60
_MACMON_MAX_SAMPLE_AGE = 5.0
_OPTIONAL_SENSOR_FIELDS = dict.fromkeys((
    "soc_cpu_percent", "gpu_percent", "gpu_freq_ghz", "ane_percent",
    "ane_power_watts", "power_watts", "cpu_temp_c", "gpu_temp_c", "thermal_pressure",
))


def _is_measurement(value, *, minimum=0, maximum=math.inf):
    return type(value) in (int, float) and math.isfinite(value) and minimum <= value <= maximum


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
        self._macmon_sample_time = None

        # Static info
        self._chip = detect_host_chip()
        self._platform = platform.machine()

        # Current snapshot (merged)
        self._current = {
            "cpu_percent": 0.0,
            **_OPTIONAL_SENSOR_FIELDS,
            "app_cpu_percent": 0.0,
            "app_cpu_core_percent": 0.0,
            "app_ram_mb": 0.0,
            "cpu_per_core": [],
            "ram_percent": 0.0,
            "ram_used_gb": 0.0,
            "ram_total_gb": 0.0,
            "cpu_freq_ghz": None,
            "swap_used_gb": 0.0,
            "disk_read_mb_s": 0.0,
            "disk_write_mb_s": 0.0,
            "net_sent_mb_s": 0.0,
            "net_recv_mb_s": 0.0,
            "timestamp": 0.0,
            "platform": self._platform,
            "chip": self._chip,
            "macmon_available": False,
            "metric_scope": "system",
        }

        # History ring buffers
        self._history = {
            "cpu_percent": deque(maxlen=_HISTORY_SIZE),
            "gpu_percent": deque(maxlen=_HISTORY_SIZE),
            "ane_percent": deque(maxlen=_HISTORY_SIZE),
            "ane_power_watts": deque(maxlen=_HISTORY_SIZE),
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
        self._process = psutil.Process(os.getpid())
        self._process.cpu_percent(interval=None)
        self._tracked_children: dict[int, psutil.Process] = {}

    def _find_macmon(self) -> Optional[str]:
        """Find an executable macmon on compatible hosts."""
        if sys.platform != "darwin" or self._platform not in {"arm64", "aarch64"}:
            return None
        for path in ("/opt/homebrew/bin/macmon", "/usr/local/bin/macmon"):
            if os.path.isfile(path) and os.access(path, os.X_OK):
                return path
        return shutil.which("macmon")

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
            logger.info("Optional macmon sensors unavailable; using psutil metrics")

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

        # Backend process plus active model workers. psutil reports process CPU
        # as 100% per fully occupied core, so keep both the core-equivalent
        # value and a whole-machine-normalized value for an honest dashboard.
        process_cpu = 0.0
        process_ram = 0
        try:
            live_children = {
                child.pid: child for child in self._process.children(recursive=True)
            }
            for pid, child in live_children.items():
                if pid not in self._tracked_children:
                    # Prime the per-process counter once; subsequent polls on
                    # this cached object report the interval instead of zero.
                    child.cpu_percent(interval=None)
                    self._tracked_children[pid] = child
            for pid in list(self._tracked_children):
                if pid not in live_children:
                    self._tracked_children.pop(pid, None)

            processes = [self._process, *self._tracked_children.values()]
            for process in processes:
                try:
                    process_cpu += process.cpu_percent(interval=None)
                    process_ram += process.memory_info().rss
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        logical_cpus = max(1, psutil.cpu_count(logical=True) or 1)

        # RAM
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()

        # Disk I/O delta
        disk = psutil.disk_io_counters()
        disk_read = 0.0
        disk_write = 0.0
        if disk and self._prev_disk and dt > 0:
            disk_read = (disk.read_bytes - self._prev_disk.read_bytes) / dt / 1024 / 1024
            disk_write = (disk.write_bytes - self._prev_disk.write_bytes) / dt / 1024 / 1024
        self._prev_disk = disk

        # Network I/O delta
        net = psutil.net_io_counters()
        net_sent = 0.0
        net_recv = 0.0
        if net and self._prev_net and dt > 0:
            net_sent = (net.bytes_sent - self._prev_net.bytes_sent) / dt / 1024 / 1024
            net_recv = (net.bytes_recv - self._prev_net.bytes_recv) / dt / 1024 / 1024
        self._prev_net = net
        self._prev_time = now

        self._psutil_data = {
            "cpu_percent": round(cpu_pct, 1),
            "app_cpu_percent": round(min(100.0, process_cpu / logical_cpus), 1),
            "app_cpu_core_percent": round(process_cpu, 1),
            "app_ram_mb": round(process_ram / 1024**2, 1),
            "cpu_per_core": [round(c, 1) for c in cpu_per_core],
            "cpu_freq_ghz": round(cpu_freq.current / 1000, 2) if cpu_freq and cpu_freq.current > 0 else None,
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
            with self._lock:
                self._macmon_sample_time = None
                self._macmon_data = {}
            logger.info("macmon pipe stopped")

    def _parse_macmon_line(self, line: str):
        """Parse a single macmon JSON line and update macmon data buffer."""
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            return

        if not isinstance(data, dict):
            return

        result = {}
        # Cluster residency differs from the whole-system CPU reading.
        cpu_fraction = data.get("cpu_usage_pct")
        if _is_measurement(cpu_fraction, maximum=1):
            result["soc_cpu_percent"] = round(cpu_fraction * 100, 1)

        gpu = data.get("gpu_usage")
        if isinstance(gpu, list) and len(gpu) >= 2:
            freq_mhz, fraction = gpu[:2]
            if _is_measurement(fraction, maximum=1):
                result["gpu_percent"] = round(fraction * 100, 1)
            if _is_measurement(freq_mhz) and freq_mhz > 0:
                result["gpu_freq_ghz"] = round(freq_mhz / 1000, 2)
        elif _is_measurement(gpu, maximum=100):
            result["gpu_percent"] = round(gpu * 100 if gpu <= 1 else gpu, 1)

        # The sampler reports ANE power in watts, without a utilization ratio.
        ane_power = data.get("ane_power")
        if _is_measurement(ane_power):
            result["ane_power_watts"] = round(ane_power, 2)
        system_power = data.get("sys_power")
        if _is_measurement(system_power):
            result["power_watts"] = round(system_power, 1)

        temperatures = data.get("temp")
        if isinstance(temperatures, dict):
            for component in ("cpu", "gpu"):
                temperature = temperatures.get(f"{component}_temp_avg")
                if _is_measurement(temperature) and temperature > 0:
                    result[f"{component}_temp_c"] = round(temperature, 1)

        # Thermal pressure is a separate system measurement from temperature.
        thermal = data.get("thermal_pressure")
        if thermal in ("nominal", "fair", "serious", "critical"):
            result["thermal_pressure"] = thermal

        with self._lock:
            self._macmon_data = result
            self._macmon_sample_time = time.monotonic() if result else None

    # ── Snapshot merging ──────────────────────────────────

    def _sensor_snapshot(self):
        sample_time = self._macmon_sample_time
        fresh = sample_time is not None and time.monotonic() - sample_time <= _MACMON_MAX_SAMPLE_AGE
        sensors = dict(_OPTIONAL_SENSOR_FIELDS)
        if fresh:
            sensors.update(self._macmon_data)
        sensors["macmon_available"] = fresh
        return sensors

    def _update_snapshot_and_history(self):
        """Update the psutil snapshot and keep missing sensor samples as gaps."""
        with self._lock:
            now = time.time()
            self._current.update(self._psutil_data)
            sample = {**self._current, **self._sensor_snapshot()}
            self._current["timestamp"] = now

            for key, history in self._history.items():
                history.append(now if key == "timestamps" else sample[key])

    # ── Public API ────────────────────────────────────────

    def get_stats(self) -> dict:
        """Get current system stats snapshot."""
        with self._lock:
            return {**self._current, **self._sensor_snapshot()}

    def get_history(self) -> dict:
        """Get the most recent samples at the snapshot cadence."""
        with self._lock:
            return {
                k: list(v) for k, v in self._history.items()
            }


# Global singleton
system_monitor = SystemMonitor()
