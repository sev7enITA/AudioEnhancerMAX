"""
AudioEnhancerMAX by Fd - Cluster Manager (Orchestrator)
Manages distributed audio processing across network devices.
Handles worker discovery, chunk splitting, parallel dispatch, and reassembly.
"""
import asyncio
import io
import json
import logging
import socket
import struct
import threading
import time
from collections import OrderedDict
from typing import Dict, List, Optional, Tuple

import numpy as np
import soundfile as sf

logger = logging.getLogger(__name__)

# Discovery port for UDP broadcast (workers -> server)
DISCOVERY_PORT = 9999
DISCOVERY_MAGIC = b"AEMAX_DISCOVER"
# Server announcement port (server -> workers)
SERVER_ANNOUNCE_PORT = 9998
SERVER_MAGIC = b"AEMAX_SERVER"
WORKER_API_PORT = 8877

# DSP-only filters that can be offloaded to workers
OFFLOADABLE_FILTERS = {
    "remove_noise", "wind_noise_remover", "buzzing_noise_remover",
    "static_noise_remover", "reverb_echo_remover", "remove_mouth_sounds",
    "remove_breaths", "remove_long_silences", "auto_eq", "studio_sound",
    "normalize", "frequency_restoration",
}

# Filters requiring heavy ML models - NEVER offload these
LOCAL_ONLY_FILTERS = {
    "remove_filler_words", "eliminate_hesitations", "remove_stuttering",
    "keep_music",  # Demucs
}


class WorkerInfo:
    """Represents a connected edge compute worker."""

    def __init__(self, ip: str, port: int = WORKER_API_PORT):
        self.ip = ip
        self.port = port
        self.name = ""
        self.device_model = ""
        self.cpu_cores = 0
        self.ram_gb = 0.0
        self.available_filters = []
        self.benchmark_score = 0.0  # chunks/second
        self.status = "unknown"  # online, busy, offline
        self.last_seen = 0.0
        self.tasks_completed = 0
        self.total_processing_seconds = 0.0
        self.current_task = None

    @property
    def url(self) -> str:
        return f"http://{self.ip}:{self.port}"

    def to_dict(self) -> dict:
        return {
            "ip": self.ip,
            "port": self.port,
            "name": self.name,
            "device_model": self.device_model,
            "cpu_cores": self.cpu_cores,
            "ram_gb": self.ram_gb,
            "available_filters": self.available_filters,
            "benchmark_score": self.benchmark_score,
            "status": self.status,
            "last_seen": self.last_seen,
            "tasks_completed": self.tasks_completed,
            "avg_speed": round(
                self.total_processing_seconds / max(1, self.tasks_completed), 2
            ),
            "current_task": self.current_task,
        }


class ClusterManager:
    """Orchestrates distributed audio processing across edge workers."""

    def __init__(self):
        self._workers: Dict[str, WorkerInfo] = OrderedDict()
        self._lock = asyncio.Lock()
        self._discovery_thread: Optional[threading.Thread] = None
        self._announce_thread: Optional[threading.Thread] = None
        self._running = False

    @property
    def worker_count(self) -> int:
        return len(self._workers)

    @property
    def online_workers(self) -> List[WorkerInfo]:
        now = time.time()
        return [
            w for w in self._workers.values()
            if w.status in ("online", "busy") and (now - w.last_seen) < 30
        ]

    def start(self):
        """Start discovery listener and server announcer."""
        if self._running:
            return
        self._running = True
        self._discovery_thread = threading.Thread(
            target=self._discovery_listener, daemon=True
        )
        self._discovery_thread.start()
        self._announce_thread = threading.Thread(
            target=self._server_broadcaster, daemon=True
        )
        self._announce_thread.start()
        logger.info("Cluster manager started - listener UDP:%d, announcer UDP:%d", DISCOVERY_PORT, SERVER_ANNOUNCE_PORT)

    def stop(self):
        self._running = False

    def _discovery_listener(self):
        """Listen for worker announcements via UDP broadcast."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            # Enable SO_REUSEPORT on macOS to allow multiple processes
            try:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            except (AttributeError, OSError):
                pass
            # Enable receiving broadcast packets
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.bind(("", DISCOVERY_PORT))
            sock.settimeout(2.0)

            logger.info(f" Discovery listener active on 0.0.0.0:{DISCOVERY_PORT}")

            while self._running:
                try:
                    data, addr = sock.recvfrom(8192)
                    ip = addr[0]

                    # Skip packets from our own IP
                    if self._is_local_ip(ip):
                        continue

                    if data.startswith(DISCOVERY_MAGIC):
                        payload_str = data[len(DISCOVERY_MAGIC):].decode("utf-8")
                        payload = json.loads(payload_str)
                        port = payload.get("port", WORKER_API_PORT)

                        # Register or update worker
                        key = f"{ip}:{port}"
                        if key not in self._workers:
                            worker = WorkerInfo(ip, port)
                            worker.name = payload.get("name", f"Worker-{ip}")
                            worker.device_model = payload.get("device_model", "Unknown")
                            worker.cpu_cores = payload.get("cpu_cores", 0)
                            worker.ram_gb = payload.get("ram_gb", 0)
                            worker.available_filters = payload.get("filters", [])
                            worker.benchmark_score = payload.get("benchmark", 0)
                            self._workers[key] = worker
                            logger.info(f" Worker discovered: {worker.name} ({ip}:{port}) - {worker.device_model}")
                        
                        self._workers[key].status = "online"
                        self._workers[key].last_seen = time.time()

                except socket.timeout:
                    # Check for stale workers every timeout cycle
                    self._expire_stale_workers()
                    continue
                except Exception as e:
                    logger.debug(f"Discovery parse error: {e}")

        except Exception as e:
            logger.error(f"Discovery listener failed: {e}", exc_info=True)
        finally:
            try:
                sock.close()
            except Exception:
                pass

    def _server_broadcaster(self):
        """Broadcast server presence on UDP so workers can find us and auto-register."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            try:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            except (AttributeError, OSError):
                pass

            local_ip = self._get_local_ip()
            payload = json.dumps({
                "ip": local_ip,
                "port": 8000,
                "name": "AudioEnhancerMAX",
                "cluster_api": f"http://{local_ip}:8000/api/cluster/add",
            }).encode("utf-8")

            message = SERVER_MAGIC + payload

            logger.info(f" Server announcer broadcasting on UDP:{SERVER_ANNOUNCE_PORT} (server IP: {local_ip})")

            while self._running:
                try:
                    # Broadcast to 255.255.255.255 and subnet broadcasts
                    for broadcast_addr in self._get_broadcast_addresses():
                        try:
                            packet = socket.inet_aton(broadcast_addr)
                            sock.sendto(message, (broadcast_addr, SERVER_ANNOUNCE_PORT))
                        except Exception:
                            pass
                    # Always try global broadcast
                    sock.sendto(message, ("255.255.255.255", SERVER_ANNOUNCE_PORT))
                except Exception as e:
                    logger.debug(f"Server announce failed: {e}")

                time.sleep(3)

        except Exception as e:
            logger.error(f"Server broadcaster failed: {e}")
        finally:
            try:
                sock.close()
            except Exception:
                pass

    @staticmethod
    def _get_broadcast_addresses() -> list:
        """Get subnet broadcast addresses for all interfaces."""
        import ipaddress
        addresses = []
        try:
            for iface_name in socket.if_nameindex():
                try:
                    # Get addresses for each interface using netifaces-like approach
                    pass
                except Exception:
                    pass
            # Fallback: derive from local IP
            local_ip = ClusterManager._get_local_ip()
            if local_ip != "unknown":
                # Assume /24 subnet
                parts = local_ip.split(".")
                if len(parts) == 4:
                    addresses.append(f"{parts[0]}.{parts[1]}.{parts[2]}.255")
        except Exception:
            pass
        return addresses

    async def add_worker(self, ip: str, port: int = WORKER_API_PORT) -> dict:
        """Manually add a worker by IP address."""
        import httpx

        key = f"{ip}:{port}"
        worker = WorkerInfo(ip, port)

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"{worker.url}/worker/health")
                if resp.status_code == 200:
                    data = resp.json()
                    worker.name = data.get("name", f"Worker-{ip}")
                    worker.device_model = data.get("device_model", "Unknown")
                    worker.cpu_cores = data.get("cpu_cores", 0)
                    worker.ram_gb = data.get("ram_gb", 0)
                    worker.available_filters = data.get("filters", [])
                    worker.benchmark_score = data.get("benchmark", 0)
                    worker.status = "online"
                    worker.last_seen = time.time()

                    async with self._lock:
                        self._workers[key] = worker

                    logger.info(f" Worker added: {worker.name} ({ip}:{port})")
                    return {"status": "ok", "worker": worker.to_dict()}
                else:
                    return {"status": "error", "message": f"Worker responded with {resp.status_code}"}

        except Exception as e:
            return {"status": "error", "message": f"Cannot reach worker at {ip}:{port}: {e}"}

    async def remove_worker(self, ip: str, port: int = WORKER_API_PORT) -> dict:
        """Remove a worker from the cluster."""
        key = f"{ip}:{port}"
        async with self._lock:
            if key in self._workers:
                del self._workers[key]
                return {"status": "ok", "message": f"Worker {key} removed"}
        return {"status": "error", "message": f"Worker {key} not found"}

    async def get_status(self) -> dict:
        """Get cluster status."""
        workers = [w.to_dict() for w in self._workers.values()]
        online = sum(1 for w in self._workers.values() if w.status in ("online", "busy"))

        # Get local machine IP for worker setup
        local_ip = self._get_local_ip()

        return {
            "total_workers": len(self._workers),
            "online_workers": online,
            "workers": workers,
            "orchestrator_ip": local_ip,
            "discovery_port": DISCOVERY_PORT,
            "worker_api_port": WORKER_API_PORT,
        }

    @staticmethod
    def _get_local_ip() -> str:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "unknown"

    @staticmethod
    def _is_local_ip(ip: str) -> bool:
        """Check if an IP belongs to this machine."""
        try:
            local_ips = set()
            local_ips.add("127.0.0.1")
            for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
                local_ips.add(info[4][0])
            # Also check via UDP trick
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ips.add(s.getsockname()[0])
            s.close()
            return ip in local_ips
        except Exception:
            return False

    def _expire_stale_workers(self):
        """Mark workers as offline if not seen for 30+ seconds."""
        now = time.time()
        for w in self._workers.values():
            if w.status == "online" and (now - w.last_seen) > 30:
                logger.info(f" Worker {w.name} ({w.ip}) went stale, marking offline")
                w.status = "offline"

    def can_distribute(self, options_dict: dict) -> bool:
        """Check if the current filter set can benefit from distribution."""
        workers = self.online_workers
        if not workers:
            return False

        # Check if any enabled filter is offloadable
        for key in OFFLOADABLE_FILTERS:
            if options_dict.get(key):
                return True
        return False

    async def process_distributed(
        self,
        audio: np.ndarray,
        sr: int,
        filters: dict,
        progress_callback=None,
    ) -> np.ndarray:
        """
        Split audio into chunks, distribute to workers, reassemble.
        Only DSP filters are offloaded; ML filters run locally after.
        """
        import httpx

        workers = self.online_workers
        if not workers:
            return audio

        # Only offload offloadable filters
        offload_filters = {
            k: v for k, v in filters.items()
            if k in OFFLOADABLE_FILTERS and v is True
        }

        if not offload_filters:
            return audio

        # Split audio into N+1 chunks (N workers + self)
        n_nodes = len(workers) + 1  # +1 for local processing
        chunk_size = len(audio) // n_nodes
        crossfade_samples = int(sr * 0.05)  # 50ms crossfade overlap

        chunks = []
        for i in range(n_nodes):
            start = max(0, i * chunk_size - crossfade_samples)
            end = min(len(audio), (i + 1) * chunk_size + crossfade_samples)
            chunks.append(audio[start:end])

        if progress_callback:
            await progress_callback(
                "cluster", 0.1,
                f" Distributing to {len(workers)} worker(s)..."
            )

        # Dispatch chunks to workers (last chunk processed locally)
        tasks = []
        for i, worker in enumerate(workers):
            if i < len(chunks) - 1:
                tasks.append(
                    self._send_chunk_to_worker(
                        worker, chunks[i], sr, offload_filters, i
                    )
                )

        # Process last chunk locally
        local_chunk = chunks[-1]

        # Gather remote results
        results = [None] * n_nodes
        if tasks:
            remote_results = await asyncio.gather(*tasks, return_exceptions=True)
            for i, result in enumerate(remote_results):
                if isinstance(result, Exception):
                    logger.warning(f"Worker {workers[i].name} failed: {result}, processing locally")
                    results[i] = chunks[i]  # fallback: use original chunk
                else:
                    results[i] = result
                    workers[i].tasks_completed += 1

        # Local chunk stays unprocessed here (will be processed in main pipeline)
        results[-1] = local_chunk

        if progress_callback:
            await progress_callback(
                "cluster", 0.3,
                f" Reassembling {n_nodes} chunks..."
            )

        # Reassemble with crossfade
        return self._reassemble_chunks(results, chunk_size, crossfade_samples)

    async def _send_chunk_to_worker(
        self,
        worker: WorkerInfo,
        chunk: np.ndarray,
        sr: int,
        filters: dict,
        chunk_id: int,
    ) -> np.ndarray:
        """Send an audio chunk to a worker for processing."""
        import httpx

        worker.status = "busy"
        worker.current_task = f"chunk-{chunk_id}"

        # Serialize audio as WAV bytes
        buf = io.BytesIO()
        sf.write(buf, chunk, sr, format="WAV", subtype="FLOAT")
        wav_bytes = buf.getvalue()

        start_time = time.time()

        try:
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(
                    f"{worker.url}/worker/process",
                    files={"audio": ("chunk.wav", wav_bytes, "audio/wav")},
                    data={"filters": json.dumps(filters), "sr": str(sr)},
                )

                if resp.status_code == 200:
                    # Deserialize result
                    result_buf = io.BytesIO(resp.content)
                    result_audio, _ = sf.read(result_buf)
                    elapsed = time.time() - start_time
                    worker.total_processing_seconds += elapsed
                    logger.info(
                        f" Worker {worker.name} processed chunk-{chunk_id} "
                        f"in {elapsed:.1f}s"
                    )
                    return result_audio.astype(np.float32)
                else:
                    raise Exception(f"HTTP {resp.status_code}: {resp.text[:200]}")

        except Exception as e:
            logger.error(f"Worker {worker.name} failed on chunk-{chunk_id}: {e}")
            raise
        finally:
            worker.status = "online"
            worker.current_task = None

    @staticmethod
    def _reassemble_chunks(
        chunks: List[np.ndarray],
        chunk_size: int,
        crossfade: int,
    ) -> np.ndarray:
        """Reassemble chunks with crossfade to avoid click artifacts."""
        if len(chunks) == 1:
            return chunks[0]

        # Simple concatenation with crossfade blending
        result_parts = []
        for i, chunk in enumerate(chunks):
            if chunk is None:
                continue

            if i == 0:
                # First chunk: use all except crossfade tail
                result_parts.append(chunk[:chunk_size])
            elif i == len(chunks) - 1:
                # Last chunk: skip crossfade head
                if crossfade > 0 and len(chunk) > crossfade:
                    # Crossfade blend with previous chunk's tail
                    overlap_len = min(crossfade, len(chunk))
                    if result_parts:
                        prev_tail = chunks[i-1][-overlap_len:] if chunks[i-1] is not None else np.zeros(overlap_len)
                        curr_head = chunk[:overlap_len]
                        fade_out = np.linspace(1, 0, overlap_len)
                        fade_in = np.linspace(0, 1, overlap_len)
                        blended = prev_tail * fade_out + curr_head * fade_in
                        result_parts.append(blended)
                    result_parts.append(chunk[overlap_len:])
                else:
                    result_parts.append(chunk)
            else:
                # Middle chunks
                if crossfade > 0:
                    result_parts.append(chunk[crossfade:-crossfade])
                else:
                    result_parts.append(chunk)

        return np.concatenate(result_parts)

    async def health_check_all(self):
        """Ping all workers and update status."""
        import httpx

        for key, worker in list(self._workers.items()):
            try:
                async with httpx.AsyncClient(timeout=5) as client:
                    resp = await client.get(f"{worker.url}/worker/health")
                    if resp.status_code == 200:
                        worker.status = "online"
                        worker.last_seen = time.time()
                    else:
                        worker.status = "offline"
            except Exception:
                if time.time() - worker.last_seen > 60:
                    worker.status = "offline"


# Global singleton
cluster_manager = ClusterManager()
