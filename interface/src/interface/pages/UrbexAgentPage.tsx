import { useEffect } from "react";
import { AppLayout } from "../components/AppLayout";
import { useAppStore } from "../../retrieval/store/useAppStore";
import type { Location } from "../../retrieval/types";

const LOCATIONS_URL = "http://localhost:8000/locations";
const CRAWLER_STATUS_POLL_MS = 5000;

export function UrbexAgentPage() {
  const setLocations = useAppStore((state) => state.setLocations);
  const setMapState = useAppStore((state) => state.setMapState);
  const refreshCrawlerStatus = useAppStore((state) => state.refreshCrawlerStatus);

  useEffect(() => {
    let active = true;

    async function loadLocations() {
      const response = await fetch(LOCATIONS_URL);
      const data: Location[] = await response.json();
      if (!active) return;

      setLocations(data);
      setMapState({
        center: [15, 62],
        zoom: 4.8,
        bearing: 0,
        pitch: 0,
      });
    }

    loadLocations().catch(() => {
      if (!active) return;
      setLocations([]);
    });

    return () => {
      active = false;
    };
  }, [setLocations, setMapState]);

  useEffect(() => {
    refreshCrawlerStatus();
    const interval = window.setInterval(refreshCrawlerStatus, CRAWLER_STATUS_POLL_MS);
    return () => window.clearInterval(interval);
  }, [refreshCrawlerStatus]);

  return <AppLayout />;
}