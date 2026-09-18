"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import * as maplibregl from "maplibre-gl";
import { StormUpdatePayload } from "@/lib/types";

interface WeatherMapProps {
  data: StormUpdatePayload | null;
  forecastHorizon: number; // 0 (now) to 60 (minutes)
  onStormSelect: (cellId: string | null) => void;
  selectedStormId: string | null;
  showInfrastructure?: boolean;
  infrastructureAssets?: InfrastructureAsset[];
  focusLocation?: { lat: number; lon: number } | null;
}

type RadarPoint = { lat: number; lon: number; dbz: number };

function getRadarPoints(response: unknown): RadarPoint[] {
  if (typeof response !== "object" || response === null || !("points" in response)) return [];
  const { points } = response as { points?: unknown };
  if (!Array.isArray(points)) return [];
  return points.filter((point): point is RadarPoint => {
    if (typeof point !== "object" || point === null) return false;
    const candidate = point as Partial<RadarPoint>;
    return typeof candidate.lat === "number" && typeof candidate.lon === "number" && typeof candidate.dbz === "number";
  });
}

interface InfrastructureAsset {
  id: string;
  name: string;
  category: string;
  lat: number;
  lon: number;
  threat_level: "critical" | "warning" | "watch" | "safe";
  estimated_arrival_minutes?: number | null;
}

// ---- Lerp animation helper ----
interface AnimatingMarker {
  marker: maplibregl.Marker;
  fromLng: number;
  fromLat: number;
  toLng: number;
  toLat: number;
  startTime: number;
  duration: number; // ms
}

function lerpMarkers(animating: Map<string, AnimatingMarker>, rafRef: React.MutableRefObject<number | null>) {
  const now = performance.now();
  let anyActive = false;

  animating.forEach((anim) => {
    const elapsed = now - anim.startTime;
    const t = Math.min(1, elapsed / anim.duration);
    // Smooth ease-out cubic
    const ease = 1 - Math.pow(1 - t, 3);

    const lng = anim.fromLng + (anim.toLng - anim.fromLng) * ease;
    const lat = anim.fromLat + (anim.toLat - anim.fromLat) * ease;
    anim.marker.setLngLat([lng, lat]);

    if (t < 1) {
      anyActive = true;
    } else {
      anim.marker.setLngLat([anim.toLng, anim.toLat]);
    }
  });

  if (anyActive) {
    rafRef.current = requestAnimationFrame(() => lerpMarkers(animating, rafRef));
  } else {
    rafRef.current = null;
  }
}

export function WeatherMap({ data, forecastHorizon, onStormSelect, selectedStormId, showInfrastructure = false, infrastructureAssets = [], focusLocation = null }: WeatherMapProps) {
  const mapContainer = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const markersRef = useRef<{ [key: string]: maplibregl.Marker }>({});
  const markerPositions = useRef<{ [key: string]: { lng: number; lat: number } }>({});
  const assetMarkersRef = useRef<{ [key: string]: maplibregl.Marker }>({});
  const animatingRef = useRef<Map<string, AnimatingMarker>>(new Map());
  const rafRef = useRef<number | null>(null);

  const [svgOverlay, setSvgOverlay] = useState<{
    polylines: Array<{ cellId: string; points: string; color: string }>;
    cones: Array<{ cellId: string; pathD: string; color: string }>;
    nodes: Array<{ x: number; y: number; label: string; color: string; confidence?: number }>;
  }>({ polylines: [], cones: [], nodes: [] });

  // Initialize Map Instance
  useEffect(() => {
    if (!mapContainer.current || map.current) return;

    const instance = new maplibregl.Map({
      container: mapContainer.current,
      style: {
        version: 8,
        sources: {
          'esri-satellite': {
            type: 'raster',
            tiles: [
              'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'
            ],
            tileSize: 256,
            attribution: 'Esri'
          },
          'esri-labels': {
            type: 'raster',
            tiles: [
              'https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}'
            ],
            tileSize: 256
          },
          'radar-grid': { type: 'geojson', data: { type: 'FeatureCollection', features: [] } }
        },
        layers: [
          {
            id: 'esri-satellite-layer',
            type: 'raster',
            source: 'esri-satellite',
            minzoom: 0,
            maxzoom: 18,
            paint: {
              'raster-brightness-max': 0.72,
              'raster-contrast': 0.15,
              'raster-saturation': -0.25
            }
          },
          {
            id: 'radar-heatmap-layer',
            type: 'heatmap',
            source: 'radar-grid',
            paint: {
              'heatmap-weight': ['get', 'weight'],
              'heatmap-intensity': 5.5,
              'heatmap-color': [
                'interpolate', ['linear'], ['heatmap-density'],
                0.00, 'rgba(0, 0, 0, 0)',
                0.005, 'rgba(6, 182, 212, 0.70)',   // Electric Cyan (Drizzle 10-25 dBZ)
                0.05, 'rgba(34, 197, 94, 0.88)',    // Lush Emerald Green (Light Rain 25-35 dBZ)
                0.15, 'rgba(234, 179, 8, 0.95)',    // Bright Sunflower Yellow (Moderate Rain 35-45 dBZ)
                0.35, 'rgba(249, 115, 22, 1.00)',   // Fiery Orange (Heavy Rain 45-55 dBZ)
                0.60, 'rgba(239, 68, 68, 1.00)',    // Intense Crimson Red (Severe Storm 55-65 dBZ)
                0.80, 'rgba(217, 70, 239, 1.00)'    // Vivid Magenta (>65 dBZ Hail Core)
              ],
              'heatmap-radius': ['interpolate', ['linear'], ['zoom'], 4, 45, 7, 100, 9, 175, 12, 280],
              'heatmap-opacity': 0.96
            }
          },
          {
            id: 'radar-rainband-glow',
            type: 'circle',
            source: 'radar-grid',
            minzoom: 5,
            filter: ['>=', ['get', 'dbz'], 14],
            paint: {
              'circle-radius': ['interpolate', ['linear'], ['zoom'], 5, 14, 8.5, 30, 11, 50, 14, 70],
              'circle-color': [
                'step', ['get', 'dbz'],
                'rgba(6, 182, 212, 0.65)',
                25, 'rgba(34, 197, 94, 0.85)',
                38, 'rgba(234, 179, 8, 0.92)',
                48, 'rgba(249, 115, 22, 0.98)',
                58, 'rgba(239, 68, 68, 1.0)',
                66, 'rgba(217, 70, 239, 1.0)'
              ],
              'circle-opacity': 0.85,
              'circle-blur': 0.70
            }
          },
          {
            id: 'esri-labels-layer',
            type: 'raster',
            source: 'esri-labels',
            minzoom: 0,
            maxzoom: 18
          }
        ]
      },
      center: [72.85, 23.0],
      zoom: 8.5,
      pitch: 25,
      bearing: 0
    });

    map.current = instance;

    // Fetch initial radar grid immediately on style ready
    const fetchInitialRadar = () => {
      const updateFromData = (radarData: unknown) => {
        const points = getRadarPoints(radarData);
        if (points.length > 0 && map.current) {
          try {
            const rSource = map.current.getSource('radar-grid') as maplibregl.GeoJSONSource | undefined;
            if (rSource) {
              const radarFeatures = points.map((p) => ({
                type: 'Feature' as const,
                properties: {
                  dbz: Number(p.dbz),
                  weight: Math.max(1.0, (Number(p.dbz) - 8.0) * 0.4)
                },
                geometry: {
                  type: 'Point' as const,
                  coordinates: [Number(p.lon), Number(p.lat)]
                }
              }));
              rSource.setData({
                type: 'FeatureCollection',
                features: radarFeatures
              });
            }
          } catch {}
        }
      };

      fetch('/api/radar/current')
        .then(res => res.ok ? res.json() : null)
        .then(updateFromData)
        .catch(err => console.warn("Notice: initial radar grid fetch:", err));
    };

    instance.on('load', fetchInitialRadar);
    instance.on('styledata', fetchInitialRadar);

    instance.on('click', () => {
      onStormSelect(null);
    });

    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      Object.values(markersRef.current).forEach(m => m.remove());
      Object.values(assetMarkersRef.current).forEach(m => m.remove());
      markersRef.current = {};
      assetMarkersRef.current = {};
      markerPositions.current = {};
      instance.remove();
      map.current = null;
    };
  }, [onStormSelect]);

  // Update SVG Trajectory Line + Uncertainty Cone Projections
  const syncSvgOverlay = useCallback(() => {
    if (!map.current || !data || !data.trajectories) return;

    const polylines: Array<{ cellId: string; points: string; color: string }> = [];
    const cones: Array<{ cellId: string; pathD: string; color: string }> = [];
    const nodes: Array<{ x: number; y: number; label: string; color: string; confidence?: number }> = [];

    data.trajectories.forEach(traj => {
      let color = '#3b82f6';
      const risk = data.risks.find(r => r.cell_id === traj.cell_id);
      if (risk) {
        if (risk.risk_level === 'moderate') color = '#eab308';
        if (risk.risk_level === 'high') color = '#f97316';
        if (risk.risk_level === 'severe') color = '#ef4444';
      }

      const coords = traj.trajectory_coords || [[traj.current_lon, traj.current_lat]];
      const pts = coords.map(c => {
        const p = map.current!.project([c[0], c[1]]);
        return `${p.x.toFixed(1)},${p.y.toFixed(1)}`;
      });

      if (pts.length > 1) {
        polylines.push({
          cellId: traj.cell_id,
          color,
          points: pts.join(' ')
        });
      }

      // Build uncertainty cone from forecast uncertainty radii
      if (traj.forecasts && traj.forecasts.length > 0 && coords.length > 1) {
        const upperPath: string[] = [];
        const lowerPath: string[] = [];

        // Start from current position
        const startP = map.current!.project([coords[0][0], coords[0][1]]);
        upperPath.push(`${startP.x.toFixed(1)},${startP.y.toFixed(1)}`);
        lowerPath.push(`${startP.x.toFixed(1)},${startP.y.toFixed(1)}`);

        traj.forecasts.forEach((f, idx) => {
          const cp = map.current!.project([f.predicted_lon, f.predicted_lat]);

          // Uncertainty in pixels (approximate: 1km ≈ some pixels at current zoom)
          const metersPerPixel = 156543.03392 * Math.cos(f.predicted_lat * Math.PI / 180) / Math.pow(2, map.current!.getZoom());
          const uncertaintyPx = Math.max(8, (f.uncertainty_km * 1000) / metersPerPixel);

          // Direction perpendicular to trajectory
          let perpAngle = Math.PI / 2;
          if (idx > 0) {
            const prevCoord = coords[idx]; // coords[0] is current, coords[idx] is previous forecast
            const prevP = map.current!.project([prevCoord[0], prevCoord[1]]);
            perpAngle = Math.atan2(cp.y - prevP.y, cp.x - prevP.x) + Math.PI / 2;
          }

          upperPath.push(`${(cp.x + Math.cos(perpAngle) * uncertaintyPx).toFixed(1)},${(cp.y + Math.sin(perpAngle) * uncertaintyPx).toFixed(1)}`);
          lowerPath.push(`${(cp.x - Math.cos(perpAngle) * uncertaintyPx).toFixed(1)},${(cp.y - Math.sin(perpAngle) * uncertaintyPx).toFixed(1)}`);
        });

        // Build closed path: upper forward, lower reversed
        const pathD = `M ${upperPath[0]} L ${upperPath.join(' L ')} L ${lowerPath.reverse().join(' L ')} Z`;
        cones.push({ cellId: traj.cell_id, pathD, color });
      }

      if (traj.forecasts) {
        traj.forecasts.forEach(f => {
          const p = map.current!.project([f.predicted_lon, f.predicted_lat]);
          nodes.push({
            x: p.x,
            y: p.y,
            label: `+${f.horizon_minutes}m`,
            color,
            confidence: f.confidence_score,
          });
        });
      }
    });

    setSvgOverlay({ polylines, cones, nodes });
  }, [data]);

  useEffect(() => {
    if (!map.current) return;
    const m = map.current;
    m.on('move', syncSvgOverlay);
    m.on('zoom', syncSvgOverlay);
    m.on('pitch', syncSvgOverlay);

    syncSvgOverlay();

    return () => {
      m.off('move', syncSvgOverlay);
      m.off('zoom', syncSvgOverlay);
      m.off('pitch', syncSvgOverlay);
    };
  }, [syncSvgOverlay]);

  // HTML Markers Sync with Lerp Animation (no jumping)
  useEffect(() => {
    if (!map.current || !data) return;

    const currentCellIds = new Set(data.storms.map(s => s.cell_id));

    // Remove markers no longer present
    Object.keys(markersRef.current).forEach(cellId => {
      if (!currentCellIds.has(cellId)) {
        markersRef.current[cellId].remove();
        delete markersRef.current[cellId];
        delete markerPositions.current[cellId];
        animatingRef.current.delete(cellId);
      }
    });

    // Create or update HTML markers with smooth lerp animation
    data.storms.forEach(storm => {
      const isSelected = storm.cell_id === selectedStormId;
      let targetLat = storm.center_lat;
      let targetLng = storm.center_lon;

      if (forecastHorizon > 0) {
        const traj = data.trajectories.find(t => t.cell_id === storm.cell_id);
        if (traj && traj.forecasts) {
          const fc = traj.forecasts.find(f => f.horizon_minutes === forecastHorizon);
          if (fc) {
            targetLat = fc.predicted_lat;
            targetLng = fc.predicted_lon;
          }
        }
      }

      let color = '#3b82f6';
      if (storm.intensity === 'moderate') color = '#eab308';
      if (storm.intensity === 'strong') color = '#f97316';
      if (storm.intensity === 'severe') color = '#ef4444';

      let marker = markersRef.current[storm.cell_id];

      if (!marker) {
        // Create new marker at target position
        const el = document.createElement('div');
        el.className = 'storm-marker-node cursor-pointer group flex flex-col items-center select-none z-20';

        el.innerHTML = `
          <div class="relative flex items-center justify-center">
            <span class="pulse-ring absolute w-10 h-10 rounded-full opacity-75 animate-ping" style="background-color: ${color};"></span>
            <div class="marker-core w-8 h-8 rounded-full flex items-center justify-center text-[12px] font-bold text-white shadow-xl border-2 border-white transition-all group-hover:scale-125" style="background-color: ${color};">
              ⚡
            </div>
          </div>
          <div class="marker-label mt-1 px-2 py-0.5 rounded-md bg-slate-900/90 text-white text-[11px] font-semibold border border-slate-700/80 shadow-lg backdrop-blur whitespace-nowrap flex items-center gap-1">
            <span>${storm.cell_id}</span>
            <span style="color: ${color}; font-weight: 700;">• ${storm.max_reflectivity_dbz.toFixed(0)} dBZ</span>
          </div>
        `;

        el.addEventListener('click', (e) => {
          e.stopPropagation();
          onStormSelect(storm.cell_id);
        });

        marker = new maplibregl.Marker({ element: el, anchor: 'center' })
          .setLngLat([targetLng, targetLat])
          .addTo(map.current!);

        markersRef.current[storm.cell_id] = marker;
        markerPositions.current[storm.cell_id] = { lng: targetLng, lat: targetLat };
      } else {
        // Animate to new position using lerp
        const prev = markerPositions.current[storm.cell_id] || { lng: targetLng, lat: targetLat };

        // Only animate if position actually changed
        if (Math.abs(prev.lng - targetLng) > 0.00001 || Math.abs(prev.lat - targetLat) > 0.00001) {
          animatingRef.current.set(storm.cell_id, {
            marker,
            fromLng: prev.lng,
            fromLat: prev.lat,
            toLng: targetLng,
            toLat: targetLat,
            startTime: performance.now(),
            duration: 900, // 900ms smooth animation
          });

          markerPositions.current[storm.cell_id] = { lng: targetLng, lat: targetLat };

          // Start animation loop if not running
          if (rafRef.current === null) {
            rafRef.current = requestAnimationFrame(() => lerpMarkers(animatingRef.current, rafRef));
          }
        }

        // Update marker label/styling
        const el = marker.getElement();
        const core = el.querySelector('.marker-core');
        if (core) {
          if (isSelected) {
            core.className = 'marker-core w-10 h-10 rounded-full flex items-center justify-center text-[14px] font-bold text-white shadow-2xl border-4 border-amber-400 scale-110 transition-all';
          } else {
            core.className = 'marker-core w-8 h-8 rounded-full flex items-center justify-center text-[12px] font-bold text-white shadow-xl border-2 border-white transition-all group-hover:scale-125';
          }
        }

        // Update dBZ value in label
        const dbzSpan = el.querySelector('.marker-label span:last-child');
        if (dbzSpan) {
          dbzSpan.innerHTML = `• ${storm.max_reflectivity_dbz.toFixed(0)} dBZ`;
        }
      }
    });

    syncSvgOverlay();
  }, [data, forecastHorizon, onStormSelect, selectedStormId, syncSvgOverlay]);

  // Toggleable critical-infrastructure layer. HTML markers keep the feature
  // usable with the current compact in-memory asset catalogue.
  useEffect(() => {
    const currentMap = map.current;
    if (!currentMap) return;
    if (!showInfrastructure) {
      Object.values(assetMarkersRef.current).forEach((marker) => marker.remove());
      assetMarkersRef.current = {};
      return;
    }

    const liveIds = new Set(infrastructureAssets.map((asset) => asset.id));
    Object.entries(assetMarkersRef.current).forEach(([id, marker]) => {
      if (!liveIds.has(id)) {
        marker.remove();
        delete assetMarkersRef.current[id];
      }
    });

    const colours: Record<InfrastructureAsset["threat_level"], string> = {
      critical: "#f43f5e",
      warning: "#f97316",
      watch: "#facc15",
      safe: "#34d399",
    };
    const symbols: Record<string, string> = { hospital: "+", airport: "✈", highway: "≋", power_grid: "⚡" };
    infrastructureAssets.forEach((asset) => {
      let marker = assetMarkersRef.current[asset.id];
      if (!marker) {
        const element = document.createElement("button");
        element.type = "button";
        element.title = `${asset.name} — ${asset.threat_level}${asset.estimated_arrival_minutes == null ? "" : `, ETA ${asset.estimated_arrival_minutes} min`}`;
        element.setAttribute("aria-label", element.title);
        element.style.cssText = `width:25px;height:25px;border-radius:9999px;border:2px solid white;background:${colours[asset.threat_level]};color:#fff;font-size:13px;font-weight:700;box-shadow:0 0 0 5px ${colours[asset.threat_level]}55;cursor:pointer;display:flex;align-items:center;justify-content:center;`;
        element.textContent = symbols[asset.category] ?? "●";
        element.addEventListener("click", (event) => {
          event.stopPropagation();
          map.current?.flyTo({ center: [asset.lon, asset.lat], zoom: 11, essential: true });
        });
        marker = new maplibregl.Marker({ element, anchor: "center" }).setLngLat([asset.lon, asset.lat]).addTo(currentMap);
        assetMarkersRef.current[asset.id] = marker;
      } else {
        marker.setLngLat([asset.lon, asset.lat]);
        const element = marker.getElement() as HTMLButtonElement;
        element.style.background = colours[asset.threat_level];
        element.style.boxShadow = `0 0 0 5px ${colours[asset.threat_level]}55`;
      }
    });
  }, [infrastructureAssets, showInfrastructure]);

  useEffect(() => {
    if (!map.current || !focusLocation) return;
    map.current.flyTo({ center: [focusLocation.lon, focusLocation.lat], zoom: 11, essential: true });
  }, [focusLocation]);

  // Camera flyTo on storm selection
  const lastSelectedId = useRef<string | null>(null);
  useEffect(() => {
    if (map.current && selectedStormId && selectedStormId !== lastSelectedId.current) {
      lastSelectedId.current = selectedStormId;

      const storm = data?.storms.find(s => s.cell_id === selectedStormId);
      const targetLat = storm?.center_lat;
      const targetLon = storm?.center_lon;

      if (!targetLat || !targetLon) {
        fetch(`/api/storms/${selectedStormId}`)
          .then(res => res.json())
          .then(detail => {
            if (detail && detail.cell && map.current) {
              map.current.flyTo({
                center: [detail.cell.center_lon, detail.cell.center_lat],
                zoom: 10,
                essential: true
              });
            }
          })
          .catch(e => console.warn("Notice: storm detail fetch:", e));
      } else {
        map.current.flyTo({
          center: [targetLon, targetLat],
          zoom: 10,
          essential: true
        });
      }
    } else if (!selectedStormId) {
      lastSelectedId.current = null;
    }
  }, [selectedStormId, data]);

  // Continuously Update Radar Grid Heatmap Data Source from real-time stream or API
  useEffect(() => {
    if (!map.current) return;

    const applyPoints = (points: Array<{ lat: number; lon: number; dbz: number }>) => {
      if (!points || points.length === 0 || !map.current) return;
      try {
        const rSource = map.current.getSource('radar-grid') as maplibregl.GeoJSONSource | undefined;
        if (rSource) {
          const radarFeatures = points.map(p => ({
            type: 'Feature' as const,
            properties: {
              dbz: Number(p.dbz),
              weight: Math.max(1.0, (Number(p.dbz) - 8.0) * 0.4)
            },
            geometry: {
              type: 'Point' as const,
              coordinates: [Number(p.lon), Number(p.lat)]
            }
          }));
          rSource.setData({
            type: 'FeatureCollection',
            features: radarFeatures
          });
        }
      } catch {}
    };

    if (data?.radar_points && data.radar_points.length > 0) {
      applyPoints(data.radar_points);
    } else {
      fetch('/api/radar/current')
        .then(res => res.ok ? res.json() : null)
        .then(radarData => {
          if (radarData && radarData.points) {
            applyPoints(radarData.points);
          }
        })
        .catch(err => console.warn("Notice: radar grid fetch:", err));
    }
  }, [data]);

  return (
    <div className="w-full h-full absolute inset-0 z-0 overflow-hidden">
      {/* Map Canvas */}
      <div ref={mapContainer} className="w-full h-full absolute inset-0 z-0" />

      {/* Trajectory Vector SVG Overlay */}
      <svg className="w-full h-full absolute inset-0 pointer-events-none z-10 overflow-hidden">
        <defs>
          <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="3" result="blur" />
            <feComposite in="SourceGraphic" in2="blur" operator="over" />
          </filter>
        </defs>

        {/* Uncertainty Cones */}
        {svgOverlay.cones.map((cone, idx) => (
          <path
            key={`cone-${cone.cellId || idx}`}
            d={cone.pathD}
            fill={cone.color}
            fillOpacity="0.08"
            stroke={cone.color}
            strokeWidth="1"
            strokeOpacity="0.2"
            strokeDasharray="4 3"
          />
        ))}

        {/* Trajectory Polylines */}
        {svgOverlay.polylines.map((line, idx) => (
          <g key={line.cellId || idx}>
            <polyline
              points={line.points}
              fill="none"
              stroke={line.color}
              strokeWidth="8"
              strokeOpacity="0.4"
              strokeLinecap="round"
              strokeLinejoin="round"
              filter="url(#glow)"
            />
            <polyline
              points={line.points}
              fill="none"
              stroke={line.color}
              strokeWidth="3.5"
              strokeDasharray="6 4"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </g>
        ))}

        {/* Horizon Dots, Time Labels & Confidence Badges */}
        {svgOverlay.nodes.map((node, idx) => (
          <g key={idx} transform={`translate(${node.x}, ${node.y})`}>
            <circle r="5" fill={node.color} stroke="#ffffff" strokeWidth="2" />
            <rect x="-14" y="-20" width="28" height="14" rx="3" fill="#0f172a" opacity="0.85" />
            <text
              x="0"
              y="-10"
              textAnchor="middle"
              fill="#ffffff"
              fontSize="9"
              fontWeight="bold"
              fontFamily="monospace"
            >
              {node.label}
            </text>
            {/* Confidence badge */}
            {node.confidence != null && (
              <>
                <rect x="10" y="-6" width="22" height="12" rx="3"
                  fill={node.confidence > 0.7 ? '#22c55e' : node.confidence > 0.4 ? '#eab308' : '#ef4444'}
                  opacity="0.9"
                />
                <text x="21" y="3" textAnchor="middle" fill="#fff" fontSize="7" fontWeight="bold" fontFamily="monospace">
                  {Math.round(node.confidence * 100)}%
                </text>
              </>
            )}
          </g>
        ))}
      </svg>

      {/* Radar dBZ Reflectivity Scale Legend */}
      <div className="absolute bottom-6 left-6 bg-[#0a0e27]/90 backdrop-blur-md border border-slate-700/60 rounded-lg p-2.5 z-30 shadow-xl flex flex-col space-y-1.5 text-xs select-none">
        <div className="text-[11px] font-bold text-slate-300 uppercase tracking-wider flex items-center justify-between">
          <span>Doppler Radar (dBZ)</span>
          <span className="text-emerald-400 font-mono text-[10px]">LIVE</span>
        </div>
        <div className="h-3 w-48 rounded overflow-hidden flex" style={{
          background: 'linear-gradient(to right, rgba(6,182,212,0.8), rgba(34,197,94,0.9), rgba(234,179,8,0.95), rgba(249,115,22,1), rgba(239,68,68,1), rgba(217,70,239,1))'
        }} />
        <div className="flex justify-between text-[9px] font-mono text-slate-400 pt-0.5">
          <span>10 (Drizzle)</span>
          <span>35</span>
          <span>50</span>
          <span>70+ (Severe)</span>
        </div>
      </div>
    </div>
  );
}
