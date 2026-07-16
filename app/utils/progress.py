"""
AudioEnhancerMAX by Fd - Progress Tracking via WebSocket
Enhanced with adaptive ETA from the Timing Engine.
"""
import asyncio
import json
import time
from typing import Dict, Optional
from fastapi import WebSocket


class ProgressTracker:
    """Manages WebSocket connections for real-time progress updates."""

    def __init__(self):
        self.connections: Dict[str, WebSocket] = {}
        self._lock = asyncio.Lock()
        self._step_timers: Dict[str, float] = {}  # file_id -> step start time
        self._job_timers: Dict[str, float] = {}    # file_id -> job start time

    async def connect(self, file_id: str, websocket: WebSocket):
        """Register a WebSocket connection for a file processing job."""
        await websocket.accept()
        async with self._lock:
            self.connections[file_id] = websocket
            self._job_timers[file_id] = time.monotonic()

    async def disconnect(self, file_id: str):
        """Remove a WebSocket connection."""
        async with self._lock:
            self.connections.pop(file_id, None)
            self._step_timers.pop(file_id, None)
            self._job_timers.pop(file_id, None)

    async def send_progress(
        self,
        file_id: str,
        step: str,
        progress: float,
        message: str,
        status: str = "processing",
        # ── New ETA fields ──
        estimated_total_seconds: Optional[float] = None,
        estimated_remaining_seconds: Optional[float] = None,
        step_estimate_seconds: Optional[float] = None,
        steps_completed: Optional[int] = None,
        steps_total: Optional[int] = None,
        eta_confidence: Optional[str] = None,
        eta_source: Optional[str] = None,
        eta_breakdown_text: Optional[str] = None,
    ):
        """Send a progress update to the client with optional ETA data."""
        async with self._lock:
            ws = self.connections.get(file_id)
            if ws:
                now = time.monotonic()

                # Calculate step elapsed time
                step_elapsed = 0.0
                if file_id in self._step_timers:
                    step_elapsed = now - self._step_timers[file_id]
                self._step_timers[file_id] = now  # reset for next step

                # Calculate total job elapsed
                job_elapsed = 0.0
                if file_id in self._job_timers:
                    job_elapsed = now - self._job_timers[file_id]

                payload = {
                    "file_id": file_id,
                    "step": step,
                    "progress": min(1.0, max(0.0, progress)),
                    "message": message,
                    "status": status,
                    "step_elapsed_seconds": round(step_elapsed, 2),
                    "total_elapsed_seconds": round(job_elapsed, 2),
                }

                # Append ETA fields if provided
                if estimated_total_seconds is not None:
                    payload["estimated_total_seconds"] = round(estimated_total_seconds, 1)
                if estimated_remaining_seconds is not None:
                    payload["estimated_remaining_seconds"] = round(estimated_remaining_seconds, 1)
                if step_estimate_seconds is not None:
                    payload["step_estimate_seconds"] = round(step_estimate_seconds, 1)
                if steps_completed is not None:
                    payload["steps_completed"] = steps_completed
                if steps_total is not None:
                    payload["steps_total"] = steps_total
                if eta_confidence is not None:
                    payload["eta_confidence"] = eta_confidence
                if eta_source is not None:
                    payload["eta_source"] = eta_source
                if eta_breakdown_text is not None:
                    payload["eta_breakdown_text"] = eta_breakdown_text

                try:
                    await ws.send_json(payload)
                except Exception:
                    self.connections.pop(file_id, None)

    async def send_estimate(
        self,
        file_id: str,
        estimate: dict,
    ):
        """
        Send an initial estimate to the client before processing starts.
        This is the 'anchor' ETA that the frontend will count down from.
        """
        async with self._lock:
            ws = self.connections.get(file_id)
            if ws:
                try:
                    await ws.send_json({
                        "file_id": file_id,
                        "status": "estimate",
                        "step": "estimate",
                        "progress": 0.0,
                        "message": f"Stima: ~{self._fmt_eta(estimate['total_seconds'])}",
                        "estimated_total_seconds": estimate.get("total_seconds", 0),
                        "estimated_remaining_seconds": estimate.get("total_seconds", 0),
                        "eta_confidence": estimate.get("confidence", "low"),
                        "eta_source": estimate.get("source", "benchmark"),
                        "eta_breakdown_text": estimate.get("breakdown_text", ""),
                        "per_step_estimates": estimate.get("per_step", {}),
                    })
                except Exception:
                    self.connections.pop(file_id, None)

    async def send_complete(self, file_id: str, result_url: str):
        """Send completion notification."""
        await self.send_progress(
            file_id, "complete", 1.0,
            f"Processing complete! Download ready.",
            "completed",
            estimated_remaining_seconds=0,
        )
        async with self._lock:
            ws = self.connections.get(file_id)
            if ws:
                try:
                    # Include total elapsed time
                    job_elapsed = 0.0
                    if file_id in self._job_timers:
                        job_elapsed = time.monotonic() - self._job_timers[file_id]

                    await ws.send_json({
                        "file_id": file_id,
                        "status": "completed",
                        "result_url": result_url,
                        "total_elapsed_seconds": round(job_elapsed, 2),
                    })
                except Exception:
                    pass

    async def send_error(self, file_id: str, error: str):
        """Send error notification."""
        await self.send_progress(
            file_id, "error", 0.0, f"Error: {error}", "error"
        )

    @staticmethod
    def _fmt_eta(seconds: float) -> str:
        """Format seconds as human-readable ETA."""
        seconds = max(0, int(seconds))
        if seconds < 60:
            return f"0:{seconds:02d}"
        m = seconds // 60
        s = seconds % 60
        return f"{m}:{s:02d}"


# Global progress tracker instance
progress_tracker = ProgressTracker()
