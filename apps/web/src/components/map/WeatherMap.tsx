"use client";

import { useEffect, useRef, useState } from "react";
import * as maplibregl from "maplibre-gl";
import { StormUpdatePayload } from "@/lib/types";

interface WeatherMapProps {
  data: StormUpdatePayload | null;
  forecastHorizon: number; // 0 (now) to 60 (minutes)
  onStormSelect: (cellId: string | null) => void;
  selectedStormId: string | null;
}

export function WeatherMap({ data, forecastHorizon, onStormSelect, selectedStormId }: WeatherMapProps) {
  const mapContainer = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const markersRef = useRef<{ [key: string]: maplibregl.Marker }>({});

  const [svgOverlay, setSvgOverlay] = useState<{
    polylines: Array<{ cellId: string; points: string; color: string }>;
    nodes: Array<{ x: number; y: number; label: string; color: string }>;
  }>({ polylines: [], nodes: [] });

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
            maxzoom: 18
          },
          {
            id: 'esri-labels-layer',
            type: 'raster',
            source: 'esri-labels',
            minzoom: 0,
            maxzoom: 18
          },
          {
            id: 'radar-heatmap-layer',
            type: 'heatmap',
            source: 'radar-grid',
            paint: {
              'heatmap-weight': ['interpolate', ['linear'], ['get', 'weight'], 0, 0, 1, 1],
              'heatmap-intensity': 2.5,
              'heatmap-color': [
                'interpolate', ['linear'], ['heatmap-density'],
                0.00, 'rgba(0, 0, 0, 0)',
                0.08, 'rgba(6, 182, 212, 0.65)',  // Cyan (Drizzle 10-25 dBZ)
                0.25, 'rgba(34, 197, 94, 0.82)',  // Bright Green (Light Rain 25-35 dBZ)
                0.45, 'rgba(234, 179, 8, 0.92)',  // Yellow (Moderate Rain 35-45 dBZ)
                0.65, 'rgba(249, 115, 22, 0.98)', // Orange (Heavy Rain 45-55 dBZ)
                0.82, 'rgba(239, 68, 68, 1.00)',  // Crimson Red (Severe Storm 55-65 dBZ)
                1.00, 'rgba(217, 70, 239, 1.00)'  // Magenta (Extreme Hail >65 dBZ)
              ],
              'heatmap-radius': ['interpolate', ['linear'], ['zoom'], 5, 45, 8, 85, 12, 160],
              'heatmap-opacity': 0.85
            }
          }
        ]
      },
      center: [72.85, 23.0],
      zoom: 8.5,
      pitch: 25,
      bearing: 0,
      antialias: true
    });

    map.current = instance;

    // Fetch initial radar grid immediately on style ready
    const fetchInitialRadar = () => {
      fetch('/api/radar/current')
        .then(res => res.json())
        .then(radarData => {
          if (radarData && radarData.points && map.current) {
            const radarFeatures = radarData.points.map((p: any) => ({
              type: 'Feature',
              properties: {
                dbz: p.dbz,
                weight: Math.min(1.0, Math.max(0.1, (p.dbz - 10) / 55.0))
              },
              geometry: { type: 'Point', coordinates: [p.lon, p.lat] }
            }));
            const rSource = map.current.getSource('radar-grid') as maplibregl.GeoJSONSource;
            if (rSource) {
              rSource.setData({ type: 'FeatureCollection', features: radarFeatures as any });
            }
          }
        })
        .catch(err => console.error("Failed to fetch initial radar grid:", err));
    };

    instance.on('load', fetchInitialRadar);
    instance.on('styledata', fetchInitialRadar);

    instance.on('click', () => {
      onStormSelect(null);
    });

    return () => {
      Object.values(markersRef.current).forEach(m => m.remove());
      markersRef.current = {};
      instance.remove();
      map.current = null;
    };
  }, []);

  // Update SVG Trajectory Line Projections on Map Move/Zoom
  const syncSvgOverlay = () => {
    if (!map.current || !data || !data.trajectories) return;

    const polylines: Array<{ cellId: string; points: string; color: string }> = [];
    const nodes: Array<{ x: number; y: number; label: string; color: string }> = [];

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

      if (traj.forecasts) {
        traj.forecasts.forEach(f => {
          const p = map.current!.project([f.predicted_lon, f.predicted_lat]);
          nodes.push({
            x: p.x,
            y: p.y,
            label: `+${f.horizon_minutes}m`,
            color
          });
        });
      }
    });

    setSvgOverlay({ polylines, nodes });
  };

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
  }, [data, forecastHorizon]);

  // HTML Markers Sync for Storm Cell Nodes
  useEffect(() => {
    if (!map.current || !data) return;

    const currentCellIds = new Set(data.storms.map(s => s.cell_id));

    // Remove markers no longer present
    Object.keys(markersRef.current).forEach(cellId => {
      if (!currentCellIds.has(cellId)) {
        markersRef.current[cellId].remove();
        delete markersRef.current[cellId];
      }
    });

    // Create or update HTML markers
    data.storms.forEach(storm => {
      const isSelected = storm.cell_id === selectedStormId;
      let lat = storm.center_lat;
      let lon = storm.center_lon;

      if (forecastHorizon > 0) {
        const traj = data.trajectories.find(t => t.cell_id === storm.cell_id);
        if (traj && traj.forecasts) {
          const fc = traj.forecasts.find(f => f.horizon_minutes === forecastHorizon);
          if (fc) {
            lat = fc.predicted_lat;
            lon = fc.predicted_lon;
          }
        }
      }

      let color = '#3b82f6';
      if (storm.intensity === 'moderate') color = '#eab308';
      if (storm.intensity === 'strong') color = '#f97316';
      if (storm.intensity === 'severe') color = '#ef4444';

      let marker = markersRef.current[storm.cell_id];

      if (!marker) {
        const el = document.createElement('div');
        el.className = 'storm-marker-node cursor-pointer group flex flex-col items-center select-none z-20';
        el.style.transition = 'transform 0.8s cubic-bezier(0.25, 1, 0.5, 1), left 0.8s, top 0.8s';
        
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
          .setLngLat([lon, lat])
          .addTo(map.current);

        markersRef.current[storm.cell_id] = marker;
      } else {
        marker.setLngLat([lon, lat]);
        const el = marker.getElement();
        el.style.transition = 'transform 0.8s cubic-bezier(0.25, 1, 0.5, 1), left 0.8s, top 0.8s';
        const core = el.querySelector('.marker-core');
        if (core) {
          if (isSelected) {
            core.className = 'marker-core w-10 h-10 rounded-full flex items-center justify-center text-[14px] font-bold text-white shadow-2xl border-4 border-amber-400 scale-110 transition-all';
          } else {
            core.className = 'marker-core w-8 h-8 rounded-full flex items-center justify-center text-[12px] font-bold text-white shadow-xl border-2 border-white transition-all group-hover:scale-125';
          }
        }
      }
    });

    syncSvgOverlay();
  }, [data, forecastHorizon, selectedStormId]);

  // Camera flyTo on storm selection
  const lastSelectedId = useRef<string | null>(null);
  useEffect(() => {
    if (map.current && selectedStormId && selectedStormId !== lastSelectedId.current) {
      lastSelectedId.current = selectedStormId;
      
      let storm = data?.storms.find(s => s.cell_id === selectedStormId);
      let targetLat = storm?.center_lat;
      let targetLon = storm?.center_lon;

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
          .catch(e => console.error(e));
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

  // Continuously Update Radar Grid Heatmap Data Source
  useEffect(() => {
    if (!map.current) return;

    const updateRadar = () => {
      fetch('/api/radar/current')
        .then(res => res.json())
        .then(radarData => {
          if (radarData && radarData.points && map.current) {
            const radarFeatures = radarData.points.map((p: any) => ({
              type: 'Feature',
              properties: {
                dbz: p.dbz,
                weight: Math.min(1.0, Math.max(0.1, (p.dbz - 10) / 55.0))
              },
              geometry: { type: 'Point', coordinates: [p.lon, p.lat] }
            }));
            const rSource = map.current.getSource('radar-grid') as maplibregl.GeoJSONSource;
            if (rSource) {
              rSource.setData({ type: 'FeatureCollection', features: radarFeatures as any });
            }
          }
        })
        .catch(err => console.error("Failed to fetch radar grid:", err));
    };

    updateRadar();
    const interval = setInterval(updateRadar, 2000);
    return () => clearInterval(interval);
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

        {/* Horizon Dots & Time Labels */}
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
