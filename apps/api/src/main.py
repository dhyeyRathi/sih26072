"""
SIH26072 — Thunderstorm & Lightning Nowcasting Platform
Main FastAPI Application

Architecture (CORE.md Section 5):
  Data Sources → Ingestion → Processing → ML Inference → Storm Detection/Tracking
  → Risk Engine → Alerts → Dashboard (via REST + WebSocket)
"""

import asyncio
import time
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from src.config import settings
from src.websocket.manager import ws_manager
from src.ingestion.simulator import data_generator
from src.storms.detection import detect_storm_cells
from src.storms.tracking import storm_tracker
from src.risk.engine import assess_storm_risk
from src.health.monitor import health_monitor

# Import routers
from src.storms.router import router as storms_router
from src.alerts.router import router as alerts_router, auto_generate_alert
from src.health.router import router as health_router


# ---------------------------------------------------------------------------
# Nowcasting pipeline — runs periodically
# ---------------------------------------------------------------------------

async def run_nowcasting_pipeline():
    """
    Core pipeline loop (CORE.md Section 24):
    New data → QC + preprocessing → ML inference → Storm-cell update
    → Risk/exposure → Persist → Push via WebSocket
    """
    while True:
        try:
            start = time.time()

            # 1. Ingest data (simulated for now)
            frame = data_generator.generate_radar_frame(timestamp=datetime.utcnow())
            lightning = data_generator.generate_lightning_data(frame)
            health_monitor.report_data("radar", latency_ms=int((time.time() - start) * 1000))
            health_monitor.report_data("lightning", latency_ms=5)

            # 2. Detect storm cells from reflectivity grid
            detected = detect_storm_cells(frame["grid"])

            # Merge lightning rates from simulation into detected cells
            for cell in detected:
                matching_sim = next(
                    (s for s in frame["storms"]
                     if abs(s["center_lat"] - cell["center_lat"]) < 0.05
                     and abs(s["center_lon"] - cell["center_lon"]) < 0.05),
                    None
                )
                if matching_sim:
                    cell["lightning_rate"] = matching_sim["lightning_rate"]

            # 3. Track cells across time
            tracked = storm_tracker.update(detected, timestamp=frame["timestamp"])

            # 4. Predict trajectories
            trajectories = storm_tracker.predict_trajectories()

            # 5. Risk assessment for each cell
            risks = []
            for cell in tracked:
                risk = assess_storm_risk(cell)
                risks.append(risk)

                # Auto-generate alerts for high/severe risk
                if risk["risk_level"] in ("high", "severe"):
                    try:
                        auto_generate_alert(cell, risk)
                    except Exception:
                        pass  # Don't crash the pipeline for alert generation failures

            # 6. Report model inference health
            latency_ms = int((time.time() - start) * 1000)
            health_monitor.report_inference(latency_ms=latency_ms, model_version="persistence-v1")

            # 7. Broadcast updates via WebSocket
            await ws_manager.broadcast("storm_update", {
                "timestamp": frame["timestamp"],
                "storms": tracked,
                "trajectories": trajectories,
                "risks": risks,
                "lightning": lightning[:50],  # Cap for performance
                "radar_summary": {
                    "max_reflectivity": float(frame["grid"].max()),
                    "mean_reflectivity": float(frame["grid"][frame["grid"] > 10].mean()) if (frame["grid"] > 10).any() else 0,
                    "active_cells": len(tracked),
                },
            })

            await ws_manager.broadcast("health_update", health_monitor.get_all_status())

        except Exception as e:
            print(f"Pipeline error: {e}")
            import traceback
            traceback.print_exc()

        # Wait for next cycle (10-second interval for demo, configurable)
        await asyncio.sleep(2)


# ---------------------------------------------------------------------------
# App lifecycle
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start the nowcasting pipeline on app startup."""
    print("🌩️  SIH26072 — Thunderstorm & Lightning Nowcasting Platform")
    print(f"   MVP Region: Gujarat/Ahmedabad ({settings.mvp_center_lat}, {settings.mvp_center_lon})")
    print(f"   Grid: {settings.grid_height}x{settings.grid_width} @ {settings.mvp_grid_resolution_km}km")
    print(f"   Time step: {settings.mvp_time_step_minutes} min")
    print()

    # Start the background pipeline
    pipeline_task = asyncio.create_task(run_nowcasting_pipeline())

    yield

    # Cleanup
    pipeline_task.cancel()
    try:
        await pipeline_task
    except asyncio.CancelledError:
        pass


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="SIH26072 — Thunderstorm Nowcasting API",
    description="AI/ML based Nowcasting of thunderstorm and lightning using atmospheric observations",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(storms_router, prefix="/api")
app.include_router(alerts_router, prefix="/api")
app.include_router(health_router, prefix="/api")


# ---------------------------------------------------------------------------
# REST endpoints
# ---------------------------------------------------------------------------

@app.get("/")
async def root():
    return {
        "name": "SIH26072 — Thunderstorm & Lightning Nowcasting Platform",
        "version": "0.1.0",
        "status": "operational",
        "region": "Gujarat/Ahmedabad",
    }


@app.get("/api/radar/current")
async def get_current_radar():
    """Get the current radar reflectivity frame as a GeoJSON-compatible response."""
    frame = data_generator.get_current_frame()
    grid = frame["grid"]

    # Convert to a list of significant cells (above 15 dBZ) for lightweight transport
    significant_points = []
    step = 2  # Subsample for performance
    h, w = grid.shape
    for y in range(0, h, step):
        for x in range(0, w, step):
            val = float(grid[y, x])
            if val > 10:
                lat = settings.mvp_center_lat + (y - h / 2) * (settings.mvp_grid_resolution_km / 111.0)
                lon = settings.mvp_center_lon + (x - w / 2) * (settings.mvp_grid_resolution_km / 111.0)
                significant_points.append({
                    "lat": round(lat, 4),
                    "lon": round(lon, 4),
                    "dbz": round(val, 1),
                })

    return {
        "timestamp": frame["timestamp"],
        "grid_shape": frame["grid_shape"],
        "resolution_km": frame["resolution_km"],
        "center": {"lat": frame["center_lat"], "lon": frame["center_lon"]},
        "max_reflectivity": round(float(grid.max()), 1),
        "point_count": len(significant_points),
        "points": significant_points,
    }


@app.get("/api/lightning/current")
async def get_current_lightning():
    """Get current lightning strike data."""
    frame = data_generator.get_current_frame()
    strikes = data_generator.generate_lightning_data(frame)
    return {
        "timestamp": frame["timestamp"],
        "count": len(strikes),
        "strikes": strikes,
    }


@app.get("/api/forecast/{horizon}")
async def get_forecast(horizon: int):
    """
    Get forecast for a specific horizon (minutes ahead).
    Valid horizons: 10, 20, 30, 40, 50, 60
    """
    if horizon not in (10, 20, 30, 40, 50, 60):
        return {"error": "Horizon must be one of: 10, 20, 30, 40, 50, 60"}

    trajectories = storm_tracker.predict_trajectories(horizons_minutes=[horizon])

    forecasts = []
    for traj in trajectories:
        if traj["forecasts"]:
            fc = traj["forecasts"][0]
            forecasts.append({
                "cell_id": traj["cell_id"],
                "current": {"lat": traj["current_lat"], "lon": traj["current_lon"]},
                "predicted": {"lat": fc["predicted_lat"], "lon": fc["predicted_lon"]},
                "horizon_minutes": horizon,
                "thunderstorm_probability": fc["thunderstorm_probability"],
                "lightning_probability": fc["lightning_probability"],
                "uncertainty_km": fc["uncertainty_km"],
                "speed_kmh": traj["speed_kmh"],
                "direction_deg": traj["direction_deg"],
                "intensity": traj["intensity"],
            })

    return {
        "horizon_minutes": horizon,
        "count": len(forecasts),
        "forecasts": forecasts,
    }


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time dashboard updates.
    Clients receive: storm_update, health_update, alert_update messages.
    """
    await ws_manager.connect(websocket)
    try:
        # Send initial state
        await ws_manager.send_personal(websocket, "connected", {
            "message": "Connected to SIH26072 Nowcasting WebSocket",
            "region": "Gujarat/Ahmedabad"
        })

        # Send initial state immediately so the frontend populates instantly
        from src.storms.tracking import storm_tracker
        tracked = storm_tracker.get_active_cells()
        if tracked:
            trajectories = storm_tracker.predict_trajectories()
            risks = []
            for cell in tracked:
                from src.risk.engine import assess_storm_risk
                risks.append(assess_storm_risk(cell))
            
            frame = data_generator.get_current_frame()
            lightning = data_generator.generate_lightning_data(frame)
            
            await ws_manager.send_personal(websocket, "storm_update", {
                "timestamp": frame["timestamp"],
                "storms": tracked,
                "trajectories": trajectories,
                "risks": risks,
                "lightning": lightning,
            })
        await ws_manager.send_personal(websocket, "health_update", health_monitor.get_all_status())

        # Keep connection alive, process incoming messages
        while True:
            data = await websocket.receive_text()
            # Clients can send ping/pong or request specific data
            if data == "ping":
                await ws_manager.send_personal(websocket, "pong", {})
    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket)
    except Exception:
        await ws_manager.disconnect(websocket)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
    )
