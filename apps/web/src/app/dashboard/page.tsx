"use client";

import { useState, useEffect } from "react";
import { useWebSocket } from "@/hooks/useWebSocket";
import { StatusBar } from "@/components/layout/StatusBar";
import { WeatherMap } from "@/components/map/WeatherMap";
import { ForecastTimeline } from "@/components/timeline/ForecastTimeline";
import { StormDetails } from "@/components/panels/StormDetails";
import { RiskPanel } from "@/components/panels/RiskPanel";

export default function DashboardPage() {
  const [wsUrl, setWsUrl] = useState<string>("");

  useEffect(() => {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const hostname = window.location.hostname || "localhost";
    setWsUrl(`${protocol}//${hostname}:8000/ws`);
  }, []);

  const { isConnected, lastMessageTime, stormData, systemHealth } = useWebSocket(wsUrl);
  
  const [horizon, setHorizon] = useState<number>(0);
  const [selectedStormId, setSelectedStormId] = useState<string | null>(null);

  const selectedRisk = stormData?.risks.find(r => r.cell_id === selectedStormId) || null;
  
  // Find matching storm cell or construct fallback from risk data
  const selectedStorm = stormData?.storms.find(s => s.cell_id === selectedStormId) || (
    selectedRisk ? {
      cell_id: selectedRisk.cell_id,
      center_lat: selectedRisk.target?.lat || 22.8059,
      center_lon: selectedRisk.target?.lon || 72.8040,
      max_reflectivity_dbz: 52.5,
      area_sq_km: 650,
      lightning_rate: 28.5,
      movement_speed_kmh: selectedRisk.speed_kmh || 12,
      movement_direction_deg: selectedRisk.direction_deg || 45,
      intensity: selectedRisk.intensity || (selectedRisk.risk_level === 'severe' ? 'severe' : 'strong'),
      trend: selectedRisk.trend || 'steady'
    } : null
  );

  return (
    <main className="flex flex-col h-full w-full relative">
      <StatusBar 
        health={systemHealth} 
        isConnected={isConnected} 
        lastMessageTime={lastMessageTime} 
      />
      
      <div className="flex-1 relative w-full h-full">
        <WeatherMap 
          data={stormData} 
          forecastHorizon={horizon}
          selectedStormId={selectedStormId}
          onStormSelect={setSelectedStormId}
        />

        {stormData && (
          <RiskPanel risks={stormData.risks} onSelect={setSelectedStormId} />
        )}

        <StormDetails 
          storm={selectedStorm} 
          risk={selectedRisk} 
          onClose={() => setSelectedStormId(null)} 
        />

        <ForecastTimeline 
          horizon={horizon} 
          onHorizonChange={setHorizon} 
          timestamp={stormData?.timestamp || null}
        />
      </div>
    </main>
  );
}
