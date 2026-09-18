"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  RiskAssessment,
  StormCell,
  StormTrajectory,
  StormUpdatePayload,
  SystemHealth,
} from "@/lib/types";

interface WebSocketMessage {
  type: string;
  data: unknown;
  timestamp?: string;
}

interface StormsResponse {
  storms: StormCell[];
}

interface TrajectoriesResponse {
  trajectories: StormTrajectory[];
}

interface RadarResponse {
  max_reflectivity?: number;
  points?: Array<{ lat: number; lon: number; dbz: number }>;
}

export interface AlertUpdate {
  event: string;
  alert?: { id?: string; status?: string };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function parseWebSocketMessage(payload: string): WebSocketMessage | null {
  const parsed: unknown = JSON.parse(payload);
  if (!isRecord(parsed) || typeof parsed.type !== "string") return null;
  return {
    type: parsed.type,
    data: parsed.data,
    timestamp: typeof parsed.timestamp === "string" ? parsed.timestamp : undefined,
  };
}

function withUtcSuffix(timestamp?: string): string | undefined {
  if (!timestamp || timestamp.endsWith("Z") || timestamp.includes("+")) return timestamp;
  return `${timestamp}Z`;
}

function messageTimestamp(message: WebSocketMessage): string | undefined {
  if (message.timestamp) return withUtcSuffix(message.timestamp);
  if (isRecord(message.data) && typeof message.data.timestamp === "string") {
    return withUtcSuffix(message.data.timestamp);
  }
  return undefined;
}

async function fetchJson<T>(url: string): Promise<T | null> {
  const response = await fetch(url);
  return response.ok ? (await response.json()) as T : null;
}

function fallbackRiskLevel(storm: StormCell): RiskAssessment["risk_level"] {
  if (storm.intensity === "severe") return "severe";
  if (storm.intensity === "strong") return "high";
  if (storm.intensity === "moderate") return "moderate";
  return "low";
}

export function useWebSocket(url: string) {
  const [isConnected, setIsConnected] = useState(false);
  const [lastMessageTime, setLastMessageTime] = useState<Date | null>(null);
  const [stormData, setStormData] = useState<StormUpdatePayload | null>(null);
  const [systemHealth, setSystemHealth] = useState<SystemHealth | null>(null);
  const [alertUpdate, setAlertUpdate] = useState<AlertUpdate | null>(null);

  const ws = useRef<WebSocket | null>(null);
  const reconnectTimeout = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const isMounted = useRef(true);
  const reconnectDelay = useRef(1_000);
  const fallbackDelay = useRef(5_000);
  const connectRef = useRef<() => void>(() => undefined);

  const scheduleReconnect = useCallback((delay: number) => {
    if (reconnectTimeout.current) clearTimeout(reconnectTimeout.current);
    reconnectTimeout.current = setTimeout(() => {
      if (isMounted.current) connectRef.current();
    }, delay);
  }, []);

  const connect = useCallback(() => {
    if (!url || !isMounted.current) return;

    try {
      if (ws.current) {
        ws.current.onopen = null;
        ws.current.onmessage = null;
        ws.current.onerror = null;
        ws.current.onclose = null;
        ws.current.close();
      }

      const socket = new WebSocket(url);
      ws.current = socket;

      socket.onopen = () => {
        if (!isMounted.current) return;
        reconnectDelay.current = 1_000;
        fallbackDelay.current = 5_000;
        setIsConnected(true);
      };

      socket.onclose = () => {
        if (!isMounted.current) return;
        setIsConnected(false);
        const delay = reconnectDelay.current;
        reconnectDelay.current = Math.min(reconnectDelay.current * 2, 30_000);
        scheduleReconnect(delay);
      };

      socket.onmessage = (event) => {
        if (!isMounted.current) return;
        try {
          const message = parseWebSocketMessage(event.data);
          if (!message) return;

          setLastMessageTime(new Date(messageTimestamp(message) ?? Date.now()));
          if (message.type === "storm_update") {
            setStormData(message.data as StormUpdatePayload);
          } else if (message.type === "health_update") {
            setSystemHealth(message.data as SystemHealth);
          } else if (message.type === "alert_update") {
            setAlertUpdate(message.data as AlertUpdate);
          }
        } catch (error) {
          console.warn("Failed to parse WebSocket message:", error);
        }
      };

      socket.onerror = () => {
        console.warn("WebSocket connecting/reconnecting notice");
      };
    } catch (error) {
      console.warn("WebSocket initialization notice:", error);
      if (isMounted.current) scheduleReconnect(reconnectDelay.current);
    }
  }, [scheduleReconnect, url]);

  useEffect(() => {
    connectRef.current = connect;
  }, [connect]);

  useEffect(() => {
    isMounted.current = true;
    const startTimeout = setTimeout(connect, 0);

    return () => {
      isMounted.current = false;
      clearTimeout(startTimeout);
      if (reconnectTimeout.current) clearTimeout(reconnectTimeout.current);
      if (ws.current) {
        ws.current.onopen = null;
        ws.current.onmessage = null;
        ws.current.onerror = null;
        ws.current.onclose = null;
        ws.current.close();
        ws.current = null;
      }
    };
  }, [connect]);

  // When the WebSocket cannot connect, poll through the same-origin Next proxy
  // with an exponential delay. This prevents a rejected upgrade from flooding
  // the browser with API requests or 400 entries.
  useEffect(() => {
    let pollTimeout: ReturnType<typeof setTimeout> | undefined;
    let cancelled = false;

    const fetchFallback = async () => {
      try {
        const [stormsResponse, trajectoriesResponse, radarResponse] = await Promise.all([
          fetchJson<StormsResponse>("/api/storms"),
          fetchJson<TrajectoriesResponse>("/api/storms/trajectories"),
          fetchJson<RadarResponse>("/api/radar/current"),
        ]);

        if (stormsResponse?.storms && isMounted.current) {
          const risks: RiskAssessment[] = stormsResponse.storms.map((storm) => ({
            cell_id: storm.cell_id,
            risk_level: fallbackRiskLevel(storm),
            thunderstorm_probability: 0.85,
            lightning_probability: 0.7,
            intensity: storm.intensity,
            speed_kmh: storm.movement_speed_kmh,
            direction_deg: storm.movement_direction_deg,
            trend: storm.trend,
          }));
          const payload: StormUpdatePayload = {
            timestamp: new Date().toISOString(),
            storms: stormsResponse.storms,
            trajectories: trajectoriesResponse?.trajectories ?? [],
            risks,
            lightning: [],
            radar_summary: {
              max_reflectivity: radarResponse?.max_reflectivity ?? 55,
              mean_reflectivity: 38,
              active_cells: stormsResponse.storms.length,
            },
            radar_points: radarResponse?.points ?? [],
          };
          setStormData(payload);
          setLastMessageTime(new Date());
          fallbackDelay.current = 5_000;
        } else {
          fallbackDelay.current = Math.min(fallbackDelay.current * 2, 30_000);
        }
      } catch (error) {
        fallbackDelay.current = Math.min(fallbackDelay.current * 2, 30_000);
        console.warn("REST fallback poll notice:", error);
      } finally {
        if (!cancelled && isMounted.current) {
          pollTimeout = setTimeout(fetchFallback, fallbackDelay.current);
        }
      }
    };

    if (url && !isConnected) void fetchFallback();

    return () => {
      cancelled = true;
      if (pollTimeout) clearTimeout(pollTimeout);
    };
  }, [isConnected, url]);

  return { isConnected, lastMessageTime, stormData, systemHealth, alertUpdate };
}
