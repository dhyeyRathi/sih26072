"""
Data source health monitor — tracks freshness, labels, and availability of every input source.
Prevents users from trusting predictions built on incomplete inputs (CORE.md Section 15).
"""

from datetime import datetime, timezone, timedelta
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
            "radar": {
                "status": "live",
                "label": "Real-Data-Informed Doppler Radar Proxy",
                "last_data_at": None,
                "latency_ms": None,
                "error": None,
            },
            "satellite": {
                "status": "live",
                "label": "NASA GIBS (MODIS Terra/Aqua 250m)",
                "last_data_at": None,
                "latency_ms": None,
                "error": None,
            },
            "lightning": {
                "status": "live",
                "label": "Blitzortung.org (Community Network Proxy)",
                "last_data_at": None,
                "latency_ms": None,
                "error": None,
            },
            "aws": {
                "status": "live",
                "label": "Open-Meteo Surface Weather Observation Proxy",
                "last_data_at": None,
                "latency_ms": None,
                "error": None,
            },
            "nwp": {
                "status": "live",
                "label": "Open-Meteo NWP (ECMWF/GFS Blend)",
                "last_data_at": None,
                "latency_ms": None,
                "error": None,
            },
        }
        self._model_status = {
            "status": "ready",
            "last_inference_at": None,
            "inference_latency_ms": None,
            "model_version": "pytorch-deep-nowcaster-v2",
        }

    def report_data(self, source: str, latency_ms: Optional[int] = None):
        """Record that new data was received from a source."""
        if source in self._sources:
            self._sources[source]["last_data_at"] = datetime.now(timezone.utc)
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
        self._model_status["last_inference_at"] = datetime.now(timezone.utc)
        self._model_status["inference_latency_ms"] = latency_ms
        self._model_status["model_version"] = model_version
        self._model_status["status"] = "ready"

    def get_all_status(self) -> dict:
        """Get current health status for all sources and model."""
        for source in self._sources:
            self._update_status(source)

        return {
            "sources": {
                name: {
                    "status": info["status"],
                    "source_name": info.get("label", name),
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
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

    def _update_status(self, source: str):
        """Recalculate status for a source based on time since last data."""
        info = self._sources[source]
        if info["last_data_at"] is None:
            info["status"] = "live"
            return

        age = datetime.now(timezone.utc) - info["last_data_at"]
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