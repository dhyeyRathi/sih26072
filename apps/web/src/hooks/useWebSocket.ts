"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { StormUpdatePayload, SystemHealth } from "@/lib/types";

interface WebSocketMessage {
  type: string;
  data: any;
  timestamp: string;
}

export function useWebSocket(url: string) {
  const [isConnected, setIsConnected] = useState(false);
  const [lastMessageTime, setLastMessageTime] = useState<Date | null>(null);
  
  const [stormData, setStormData] = useState<StormUpdatePayload | null>(null);
  const [systemHealth, setSystemHealth] = useState<SystemHealth | null>(null);
  
  const ws = useRef<WebSocket | null>(null);
  const reconnectTimeout = useRef<NodeJS.Timeout>();

  const connect = useCallback(() => {
    if (!url) return;
    try {
      console.log(`Attempting WebSocket connection to: ${url}`);
      ws.current = new WebSocket(url);

      ws.current.onopen = () => {
        console.log("WebSocket connected to", url);
        setIsConnected(true);
      };

      ws.current.onclose = () => {
        console.log("WebSocket disconnected from", url);
        setIsConnected(false);
        // Auto-reconnect after 3 seconds
        reconnectTimeout.current = setTimeout(connect, 3000);
      };

      ws.current.onmessage = (event) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data);
          
          // Fix naive UTC timestamps from python backend
          if (message.timestamp && !message.timestamp.endsWith('Z') && !message.timestamp.includes('+')) {
            message.timestamp += 'Z';
          }
          if (message.data && message.data.timestamp && !message.data.timestamp.endsWith('Z') && !message.data.timestamp.includes('+')) {
            message.data.timestamp += 'Z';
          }
          
          setLastMessageTime(new Date(message.timestamp));

          if (message.type === "storm_update") {
            setStormData(message.data as StormUpdatePayload);
          } else if (message.type === "health_update") {
            setSystemHealth(message.data as SystemHealth);
          }
        } catch (error) {
          console.error("Failed to parse WebSocket message:", error);
        }
      };

      ws.current.onerror = (error) => {
        console.error("WebSocket error:", error);
        ws.current?.close();
      };
    } catch (error) {
      console.error("Failed to create WebSocket:", error);
      reconnectTimeout.current = setTimeout(connect, 3000);
    }
  }, [url]);

  useEffect(() => {
    connect();

    return () => {
      if (reconnectTimeout.current) {
        clearTimeout(reconnectTimeout.current);
      }
      if (ws.current) {
        ws.current.close();
      }
    };
  }, [connect]);

  return {
    isConnected,
    lastMessageTime,
    stormData,
    systemHealth,
  };
}
