"use client";

import { useState, useEffect } from "react";
import { useWebSocket } from "@/hooks/useWebSocket";
import { StatusBar } from "@/components/layout/StatusBar";
import { WeatherMap } from "@/components/map/WeatherMap";
import { ForecastTimeline } from "@/components/timeline/ForecastTimeline";
import { StormDetails } from "@/components/panels/StormDetails";
import { RiskPanel } from "@/components/panels/RiskPanel";
import { ExposurePanel } from "@/components/panels/ExposurePanel";
import { ExplainabilityModal } from "@/components/panels/ExplainabilityModal";
import { ModelComparisonModal } from "@/components/panels/ModelComparisonModal";

type InfrastructureAsset = {
  id: string;
  name: string;
  category: string;
  lat: number;
  lon: number;
  threat_level: "critical" | "warning" | "watch" | "safe";
  estimated_arrival_minutes?: number | null;
};

export default function DashboardPage() {
  const wsUrl = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000/ws";

  const { isConnected, lastMessageTime, stormData, systemHealth, alertUpdate } = useWebSocket(wsUrl);
  
  const [horizon, setHorizon] = useState<number>(0);
  const [selectedStormId, setSelectedStormId] = useState<string | null>(null);
  const [showExposure, setShowExposure] = useState(false);
  const [showAblation, setShowAblation] = useState(false);
  const [showExplainability, setShowExplainability] = useState(false);
  const [infrastructureAssets, setInfrastructureAssets] = useState<InfrastructureAsset[]>([]);
  const [focusLocation, setFocusLocation] = useState<{ lat: number; lon: number } | null>(null);


  useEffect(() => {
    let cancelled = false;
    const refreshAssets = async () => {
      try {
        const response = await fetch("/api/exposure/assets");
        if (!response.ok) return;
        const body = await response.json();
        if (!cancelled) setInfrastructureAssets(body.assets ?? []);
      } catch {
        // The exposure panel has its own recoverable message.
      }
    };
    void refreshAssets();
    const timer = setInterval(refreshAssets, 10_000);
    return () => { cancelled = true; clearInterval(timer); };
  }, []);

  const selectedRisk = stormData?.risks.find(r => r.cell_id === selectedStormId) || null;
  const selectedStorm = stormData?.storms.find(s => s.cell_id === selectedStormId) || null;
  const selectedForecast = stormData?.trajectories
    ?.find((t) => t.cell_id === selectedStormId)
    ?.forecasts.find((f) => f.horizon_minutes === horizon)
    ?? stormData?.trajectories?.[0]?.forecasts.find((f) => f.horizon_minutes === horizon);
  const horizonConfidence = horizon === 0 ? null : selectedForecast?.confidence_score ?? null;

  return (
    <main className="flex flex-col h-full w-full relative">
      <StatusBar 
        health={systemHealth} 
        isConnected={isConnected} 
        lastMessageTime={lastMessageTime} 
        stormData={stormData}
        onOpenAblation={() => setShowAblation(true)}
      />
      
      <div className="flex-1 relative w-full h-full">
        {!stormData && (
          <div className="absolute inset-0 z-20 flex items-center justify-center bg-[var(--surface)]/40 backdrop-blur-[2px]">
            <div className="glass-panel rounded-xl px-6 py-5 text-center shadow-2xl">
              <div className="mx-auto mb-3 h-2 w-2 animate-pulse rounded-full bg-sky-400" />
              <div className="text-sm font-semibold text-white">Connecting to nowcast stream</div>
              <p className="mt-1 text-xs text-slate-400">Waiting for live radar, trajectories, and risk assessments.</p>
            </div>
          </div>
        )}

        <WeatherMap 
          data={stormData} 
          forecastHorizon={horizon}
          selectedStormId={selectedStormId}
          onStormSelect={setSelectedStormId}
          showInfrastructure={showExposure}
          infrastructureAssets={infrastructureAssets}
          focusLocation={focusLocation}
          onToggleInfrastructure={() => setShowExposure((prev) => !prev)}
        />

        {stormData && (
          <RiskPanel risks={stormData.risks} onSelect={setSelectedStormId} onExplain={(cellId) => { setSelectedStormId(cellId); setShowExplainability(true); }} />
        )}

        <StormDetails 
          storm={selectedStorm} 
          risk={selectedRisk} 
          awaitingSelection={Boolean(selectedStormId) && !selectedStorm}
          onClose={() => setSelectedStormId(null)} 
          onExplain={() => setShowExplainability(true)}
        />

        <ForecastTimeline 
          horizon={horizon} 
          onHorizonChange={setHorizon} 
          timestamp={stormData?.timestamp || null}
          confidence={horizonConfidence}
        />

        <ExposurePanel open={showExposure} onClose={() => setShowExposure(false)} onFocus={setFocusLocation} />
        <ExplainabilityModal open={showExplainability} cellId={selectedStormId} onClose={() => setShowExplainability(false)} />
        <ModelComparisonModal open={showAblation} onClose={() => setShowAblation(false)} />
      </div>
    </main>
  );
}
