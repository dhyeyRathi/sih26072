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
import { ForecasterDesk } from "@/components/panels/ForecasterDesk";
import { HistoricalAnalogueDrawer } from "@/components/panels/HistoricalAnalogueDrawer";
import { MeteorologicalCopilot } from "@/components/panels/MeteorologicalCopilot";
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
  // Keep browser traffic on the Next.js origin. The /ws rewrite forwards it
  // to FastAPI, avoiding host/port and CORS mismatches in development or deployment.
  const wsUrl = typeof window === "undefined"
    ? ""
    : `${window.location.protocol === "https:" ? "wss:" : "ws:"}//${window.location.host}/ws`;

  const { isConnected, lastMessageTime, stormData, systemHealth, alertUpdate } = useWebSocket(wsUrl);
  
  const [horizon, setHorizon] = useState<number>(0);
  const [selectedStormId, setSelectedStormId] = useState<string | null>(null);
  const [showExposure, setShowExposure] = useState(false);
  const [showDesk, setShowDesk] = useState(false);
  const [showHistorical, setShowHistorical] = useState(false);
  const [showCopilot, setShowCopilot] = useState(false);
  const [showAblation, setShowAblation] = useState(false);
  const [showExplainability, setShowExplainability] = useState(false);
  const [pendingAlertCount, setPendingAlertCount] = useState(0);
  const [infrastructureAssets, setInfrastructureAssets] = useState<InfrastructureAsset[]>([]);
  const [focusLocation, setFocusLocation] = useState<{ lat: number; lon: number } | null>(null);

  useEffect(() => {
    let cancelled = false;
    const refreshPendingAlerts = async () => {
      try {
        const response = await fetch("/api/alerts/pending");
        if (!response.ok) return;
        const body = await response.json();
        if (!cancelled) setPendingAlertCount(body.count ?? 0);
      } catch {
        // The desk itself presents a useful error state if the API is unavailable.
      }
    };
    void refreshPendingAlerts();
    const timer = setInterval(refreshPendingAlerts, 10_000);
    return () => { cancelled = true; clearInterval(timer); };
  }, []);

  useEffect(() => {
    if (!alertUpdate) return;
    fetch("/api/alerts/pending")
      .then((response) => response.ok ? response.json() : null)
      .then((body) => { if (body) setPendingAlertCount(body.count ?? 0); })
      .catch(() => undefined);
  }, [alertUpdate]);

  useEffect(() => {
    if (!showExposure) return;
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
  }, [showExposure]);

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
        pendingAlertCount={pendingAlertCount}
        onOpenExposure={() => setShowExposure(true)}
        onOpenDesk={() => setShowDesk(true)}
        onOpenHistorical={() => setShowHistorical(true)}
        onOpenAblation={() => setShowAblation(true)}
        onOpenCopilot={() => setShowCopilot(true)}
      />
      
      <div className="flex-1 relative w-full h-full">
        <WeatherMap 
          data={stormData} 
          forecastHorizon={horizon}
          selectedStormId={selectedStormId}
          onStormSelect={setSelectedStormId}
          showInfrastructure={showExposure}
          infrastructureAssets={infrastructureAssets}
          focusLocation={focusLocation}
        />

        {stormData && (
          <RiskPanel risks={stormData.risks} onSelect={setSelectedStormId} onExplain={(cellId) => { setSelectedStormId(cellId); setShowExplainability(true); }} />
        )}

        <StormDetails 
          storm={selectedStorm} 
          risk={selectedRisk} 
          onClose={() => setSelectedStormId(null)} 
          onExplain={() => setShowExplainability(true)}
        />

        <ForecastTimeline 
          horizon={horizon} 
          onHorizonChange={setHorizon} 
          timestamp={stormData?.timestamp || null}
        />

        <ExposurePanel open={showExposure} onClose={() => setShowExposure(false)} onFocus={setFocusLocation} />
        <ForecasterDesk open={showDesk} onClose={() => setShowDesk(false)} onPendingCountChange={setPendingAlertCount} />
        <HistoricalAnalogueDrawer open={showHistorical} cellId={selectedStormId} onClose={() => setShowHistorical(false)} />
        <MeteorologicalCopilot open={showCopilot} cellId={selectedStormId} onClose={() => setShowCopilot(false)} />
        <ExplainabilityModal open={showExplainability} cellId={selectedStormId} onClose={() => setShowExplainability(false)} />
        <ModelComparisonModal open={showAblation} onClose={() => setShowAblation(false)} />
      </div>
    </main>
  );
}
