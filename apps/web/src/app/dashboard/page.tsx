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
    // Dynamically build the WebSocket URL based on the current window location
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    setWsUrl(`${protocol}//${window.location.host}/ws`);
  }, []);

  const { isConnected, lastMessageTime, stormData, systemHealth } = useWebSocket(wsUrl);
  
  const [horizon, setHorizon] = useState<number>(0);
  const [selectedStormId, setSelectedStormId] = useState<string | null>(null);

  const selectedStorm = stormData?.storms.find(s => s.cell_id === selectedStormId) || null;
  const selectedRisk = stormData?.risks.find(r => r.cell_id === selectedStormId) || null;

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
