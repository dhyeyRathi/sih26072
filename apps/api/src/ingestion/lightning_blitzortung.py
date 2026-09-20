"""
Blitzortung Community Lightning Ingestion Client.
Connects to Blitzortung's public MQTT feed and maintains a rolling 60-minute strike buffer.

NOTE: This is community/crowdsourced data for informational/proxy use only,
NOT certified IMD operational lightning data.
"""

import json
import time
import threading
from typing import List, Dict, Any
import paho.mqtt.client as mqtt

# Bounding box for Gujarat / Ahmedabad region
LAT_MIN, LAT_MAX = 20.0, 25.0
LON_MIN, LON_MAX = 68.0, 75.0

MQTT_HOST = "mqtt.blitzortung.org"
MQTT_PORT = 1883
BUFFER_WINDOW_SECONDS = 3600  # 60 minutes

_strike_buffer: List[Dict[str, Any]] = []
_buffer_lock = threading.Lock()
_connected = False
_client: mqtt.Client = None


def _on_connect(client, userdata, flags, rc, properties=None):
    global _connected
    if rc == 0:
        _connected = True
        # Subscribe to lightning strike topic
        client.subscribe("blitzortung/live/#", qos=0)
    else:
        _connected = False


def _on_message(client, userdata, msg):
    global _strike_buffer
    try:
        payload = json.loads(msg.payload.decode("utf-8"))
        lat = payload.get("lat")
        lon = payload.get("lon")
        strike_time = payload.get("time", time.time())

        if lat is None or lon is None:
            return

        # Spatial filter for region
        if LAT_MIN <= lat <= LAT_MAX and LON_MIN <= lon <= LON_MAX:
            with _buffer_lock:
                _strike_buffer.append({
                    "lat": float(lat),
                    "lon": float(lon),
                    "timestamp": float(strike_time),
                    "peak_current_ka": payload.get("peak_current", 0.0)
                })
    except Exception:
        pass


def _prune_old_strikes():
    """Removes strikes older than 60 minutes."""
    global _strike_buffer
    cutoff = time.time() - BUFFER_WINDOW_SECONDS
    with _buffer_lock:
        _strike_buffer = [s for s in _strike_buffer if s["timestamp"] >= cutoff]


def start_listener():
    """Starts background MQTT client with non-blocking connection."""
    global _client
    if _client is not None:
        return

    try:
        _client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    except AttributeError:
        _client = mqtt.Client()

    _client.on_connect = _on_connect
    _client.on_message = _on_message

    def _run_loop():
        try:
            _client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
            _client.loop_start()
        except Exception as e:
            print(f"[WARN] Blitzortung MQTT connection skipped/failed: {e}")

    thread = threading.Thread(target=_run_loop, daemon=True)
    thread.start()


def recent_strikes(window_minutes: int = 15) -> List[Dict[str, Any]]:
    """Returns strikes occurring in the last N minutes."""
    _prune_old_strikes()
    cutoff = time.time() - (window_minutes * 60)
    with _buffer_lock:
        return [s for s in _strike_buffer if s["timestamp"] >= cutoff]


def flash_density_rate(window_minutes: int = 15) -> Dict[str, Any]:
    """
    Computes real flash rate per minute over Gujarat/Ahmedabad.
    """
    strikes = recent_strikes(window_minutes)
    count = len(strikes)
    rate = count / float(window_minutes) if window_minutes > 0 else 0.0

    return {
        "source": "Blitzortung.org (Community/Non-Operational Proxy)",
        "window_minutes": window_minutes,
        "total_strikes": count,
        "rate_per_minute": round(rate, 2),
        "is_connected": _connected,
        "label": "community_proxy"
    }