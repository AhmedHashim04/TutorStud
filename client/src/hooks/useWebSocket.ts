import { useEffect, useCallback } from "react";
import { wsManager } from "@/lib/websocket";

export function useWebSocket() {
  const on = useCallback((event: string, callback: (data: any) => void) => {
    wsManager.on(event, callback);
    return () => wsManager.off(event, callback);
  }, []);

  const send = useCallback((data: any) => {
    wsManager.send(data);
  }, []);

  return { on, send };
}
