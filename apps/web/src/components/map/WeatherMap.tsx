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
  const [mapLoaded, setMapLoaded] = useState(false);

  // Initialize Map
  useEffect(() => {
    if (!mapContainer.current || map.current) return;

    map.current = new maplibregl.Map({
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
          'storm-cells': { type: 'geojson', data: { type: 'FeatureCollection', features: [] } },
          'storm-trajectories': { type: 'geojson', data: { type: 'FeatureCollection', features: [] } },
          'lightning-strikes': { type: 'geojson', data: { type: 'FeatureCollection', features: [] } },
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
              'heatmap-weight': ['interpolate', ['linear'], ['get', 'dbz'], 15, 0.1, 40, 0.5, 70, 1.0],
              'heatmap-intensity': 1.2,
              'heatmap-color': [
                'interpolate', ['linear'], ['heatmap-density'],
                0, 'rgba(0, 0, 0, 0)',
                0.2, 'rgba(59, 130, 246, 0.4)',
                0.4, 'rgba(34, 197, 94, 0.5)',
                0.6, 'rgba(234, 179, 8, 0.6)',
                0.8, 'rgba(249, 115, 22, 0.7)',
                1.0, 'rgba(239, 68, 68, 0.8)'
              ],
              'heatmap-radius': ['interpolate', ['linear'], ['zoom'], 5, 10, 9, 25, 14, 50],
              'heatmap-opacity': 0.8
            }
          },
          {
            id: 'trajectories-layer',
            type: 'line',
            source: 'storm-trajectories',
            paint: {
              'line-color': ['get', 'color'],
              'line-width': 2,
              'line-dasharray': [2, 2],
            }
          },
          {
            id: 'storm-cells-layer',
            type: 'circle',
            source: 'storm-cells',
            paint: {
              'circle-radius': ['get', 'radius_px'],
              'circle-color': ['get', 'color'],
              'circle-opacity': 0.6,
              'circle-stroke-width': ['case', ['boolean', ['get', 'selected'], false], 3, 1],
              'circle-stroke-color': '#ffffff'
            }
          },
          {
            id: 'lightning-layer',
            type: 'circle',
            source: 'lightning-strikes',
            paint: {
              'circle-radius': 4,
              'circle-color': '#fbbf24',
              'circle-opacity': 0.8,
              'circle-blur': 0.5,
            }
          }
        ]
      },
      center: [72.5714, 23.0225], // Ahmedabad
      zoom: 8,
      pitch: 45,
      bearing: 0,
      antialias: true,
    });

    map.current.on('style.load', () => {
      setMapLoaded(true);
    });

    // Interactivity
    map.current.on('click', 'storm-cells-layer', (e) => {
      if (e.features && e.features.length > 0) {
        const cellId = e.features[0].properties.cell_id;
        onStormSelect(cellId);
      }
    });

    map.current.on('mouseenter', 'storm-cells-layer', () => {
      if (map.current) map.current.getCanvas().style.cursor = 'pointer';
    });

    map.current.on('mouseleave', 'storm-cells-layer', () => {
      if (map.current) map.current.getCanvas().style.cursor = '';
    });

    // Deselect when clicking outside
    map.current.on('click', (e) => {
      const features = map.current?.queryRenderedFeatures(e.point, { layers: ['storm-cells-layer'] });
      if (!features || features.length === 0) {
        onStormSelect(null);
      }
    });

    return () => {
      map.current?.remove();
      map.current = null;
    };
  }, []);

  // Fly to selected storm (Only on explicit click, not on every data tick)
  const lastSelectedId = useRef<string | null>(null);
  useEffect(() => {
    if (mapLoaded && map.current && data && selectedStormId && selectedStormId !== lastSelectedId.current) {
      lastSelectedId.current = selectedStormId;
      const storm = data.storms.find(s => s.cell_id === selectedStormId);
      if (storm) {
        map.current.flyTo({
          center: [storm.center_lon, storm.center_lat],
          zoom: 10,
          essential: true
        });
      }
    } else if (!selectedStormId) {
      lastSelectedId.current = null;
    }
  }, [selectedStormId, mapLoaded]); // removed data from deps so it doesn't pan every 2s

  // Update Data Layers safely
  useEffect(() => {
    if (!mapLoaded || !map.current || !data) return;

    try {
      // 1. Storm Cells
      const cellFeatures = data.storms.map(storm => {
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

        return {
          type: 'Feature',
          properties: { 
            cell_id: storm.cell_id,
            selected: isSelected,
            color,
            radius_px: 15, // Hardcoded fallback just in case
            intensity: storm.intensity
          },
          geometry: {
            type: 'Point',
            coordinates: [lon, lat]
          }
        };
      });
      const cellsSource = map.current.getSource('storm-cells') as maplibregl.GeoJSONSource;
      cellsSource?.setData({ type: 'FeatureCollection', features: cellFeatures as any });
    } catch (e) { console.error('Storm cells error', e); }

    try {
      // 2. Trajectories
      const trajectoryFeatures = data.trajectories
        .filter(traj => traj.forecasts && traj.forecasts.length > 0)
        .map(traj => {
          const coords = [[traj.current_lon, traj.current_lat]];
          traj.forecasts.forEach(f => {
            coords.push([f.predicted_lon, f.predicted_lat]);
          });
          
          let color = '#94a3b8';
          const risk = data.risks.find(r => r.cell_id === traj.cell_id);
          if (risk) {
            if (risk.risk_level === 'moderate') color = '#eab308';
            if (risk.risk_level === 'high') color = '#f97316';
            if (risk.risk_level === 'severe') color = '#ef4444';
          }
          
          return {
            type: 'Feature',
            properties: { cell_id: traj.cell_id, color },
            geometry: { type: 'LineString', coordinates: coords }
          };
        });
      const tSource = map.current.getSource('storm-trajectories') as maplibregl.GeoJSONSource;
      tSource?.setData({ type: 'FeatureCollection', features: trajectoryFeatures as any });
    } catch (e) { console.error('Trajectories error', e); }

    try {
      // 3. Lightning Strikes
      if (forecastHorizon === 0 && data.lightning) {
        const lightningFeatures = data.lightning.map(strike => ({
          type: 'Feature',
          properties: { intensity: strike.intensity_ka },
          geometry: { type: 'Point', coordinates: [strike.lon, strike.lat] }
        }));
        const lSource = map.current.getSource('lightning-strikes') as maplibregl.GeoJSONSource;
        lSource?.setData({ type: 'FeatureCollection', features: lightningFeatures as any });
      } else {
        const lSource = map.current.getSource('lightning-strikes') as maplibregl.GeoJSONSource;
        lSource?.setData({ type: 'FeatureCollection', features: [] });
      }
    } catch (e) { console.error('Lightning error', e); }

    try {
      // 4. Raw Radar Grid Heatmap
      fetch('/api/radar/current')
        .then(res => res.json())
        .then(radarData => {
          if (radarData && radarData.points) {
            const radarFeatures = radarData.points.map((p: any) => ({
              type: 'Feature',
              properties: { dbz: p.dbz },
              geometry: { type: 'Point', coordinates: [p.lon, p.lat] }
            }));
            const rSource = map.current?.getSource('radar-grid') as maplibregl.GeoJSONSource;
            rSource?.setData({ type: 'FeatureCollection', features: radarFeatures as any });
          }
        })
        .catch(err => console.error("Failed to fetch radar grid:", err));
    } catch (e) { console.error('Radar fetch error', e); }

  }, [data, forecastHorizon, selectedStormId, mapLoaded]);

  return (
    <div className="w-full h-full absolute inset-0 z-0">
      <div ref={mapContainer} className="w-full h-full absolute inset-0 z-0" />
      
      {/* Fallback Debug Overlay to prove React is computing the layers */}
      {process.env.NODE_ENV === 'development' && data && (
        <div className="absolute top-4 left-4 bg-black/80 text-green-400 p-2 text-xs font-mono rounded z-50 pointer-events-none">
          Map Data Sync:<br/>
          Storms: {data.storms.length}<br/>
          Traj: {data.trajectories.length}<br/>
          Horizon: {forecastHorizon}
        </div>
      )}
    </div>
  );
}
