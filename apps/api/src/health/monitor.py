"""
Data source health monitor — tracks freshness and availability of every input source.
Prevents users from trusting predictions built on incomplete inputs (CORE.md Section 15).
"""

from datetime import datetime, timedelta
from typing import Optional


class HealthMonitor:
    """
    Tracks the health status of each data source.

    Status levels:
    - LIVE: data received within the last 15 minutes
    - DELAYED: data received 15-30 minutes ago
    - STALE: data received 30-60 minutes ago
    - OFFLINE: no data for over 60 minutes
    """

    THRESHOLDS = {
        "live": timedelta(minutes=15),
        "delayed": timedelta(minutes=30),
        "stale": timedelta(minutes=60),
    }

    def __init__(self):
        self._sources: dict[str, dict] = {
            "radar": {"status": "offline", "last_data_at": None, "latency_ms": None, "error": None},
            "satellite": {"status": "offline", "last_data_at": None, "latency_ms": None, "error": None},
            "lightning": {"status": "offline", "last_data_at": None, "latency_ms": None, "error": None},
            "aws": {"status": "offline", "last_data_at": None, "latency_ms": None, "error": None},
            "nwp": {"status": "offline", "last_data_at": None, "latency_ms": None, "error": None},
        }
        self._model_status = {
            "status": "ready",
            "last_inference_at": None,
            "inference_latency_ms": None,
            "model_version": "persistence-v1",
        }

    def report_data(self, source: str, latency_ms: Optional[int] = None):
        """Record that new data was received from a source."""
        if source in self._sources:
            self._sources[source]["last_data_at"] = datetime.utcnow()
            self._sources[source]["latency_ms"] = latency_ms
            self._sources[source]["error"] = None
            self._update_status(source)

    def report_error(self, source: str, error: str):
        """Record an error from a data source."""
        if source in self._sources:
            self._sources[source]["error"] = error
            self._update_status(source)

    def report_inference(self, latency_ms: int, model_version: str):
        """Record a completed model inference."""
        self._model_status["last_inference_at"] = datetime.utcnow()
        self._model_status["inference_latency_ms"] = latency_ms
        self._model_status["model_version"] = model_version
        self._model_status["status"] = "ready"

    def get_all_status(self) -> dict:
        """Get current health status for all sources and model."""
        # Update all statuses before returning
        for source in self._sources:
            self._update_status(source)

        return {
            "sources": {
                name: {
                    "status": info["status"],
                    "last_data_at": info["last_data_at"].isoformat() if info["last_data_at"] else None,
                    "latency_ms": info["latency_ms"],
                    "error": info["error"],
                }
                for name, info in self._sources.items()
            },
            "model": {
                **self._model_status,
                "last_inference_at": (
                    self._model_status["last_inference_at"].isoformat()
                    if self._model_status["last_inference_at"] else None
                ),
            },
            "overall": self._overall_status(),
            "checked_at": datetime.utcnow().isoformat(),
        }

    def _update_status(self, source: str):
        """Recalculate status for a source based on time since last data."""
        info = self._sources[source]
        if info["last_data_at"] is None:
            info["status"] = "offline"
            return

        age = datetime.utcnow() - info["last_data_at"]
        if age <= self.THRESHOLDS["live"]:
            info["status"] = "live"
        elif age <= self.THRESHOLDS["delayed"]:
            info["status"] = "delayed"
        elif age <= self.THRESHOLDS["stale"]:
            info["status"] = "stale"
        else:
            info["status"] = "offline"

    def _overall_status(self) -> str:
        """Determine overall system health."""
        statuses = [s["status"] for s in self._sources.values()]
        if all(s == "live" for s in statuses):
            return "healthy"
        elif any(s == "offline" for s in statuses):
            return "degraded"
        elif any(s == "stale" for s in statuses):
            return "warning"
        return "operational"


# Singleton
health_monitor = HealthMonitor()
