import { useEffect } from "react";
// import locationsUrl from "../../retrieval/data/locations.geojson?url";
import locationsUrl from "../../../../retrieval/data_locations/discovered_locations.geojson?url";
import { AppLayout } from "../components/AppLayout";
import { useAppStore } from "../../retrieval/store/useAppStore";
import type { Location } from "../../retrieval/types";

type GeoJSONLocationFeature = {
  type: "Feature";
  properties: Omit<Location, "coordinates">;
  geometry: {
    type: "Point";
    coordinates: [number, number];
  };
};

type GeoJSONLocationCollection = {
  type: "FeatureCollection";
  features: GeoJSONLocationFeature[];
};

export function UrbexAgentPage() {
  const setLocations = useAppStore((state) => state.setLocations);
  const setMapState = useAppStore((state) => state.setMapState);

  useEffect(() => {
    let active = true;

    async function loadLocations() {
      const response = await fetch(locationsUrl);
      const data: GeoJSONLocationCollection = await response.json();
      if (!active) return;

      const locations = data.features.map((feature) => ({
        ...feature.properties,
        coordinates: feature.geometry.coordinates,
      }));

      setLocations(locations);
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

  return <AppLayout />;
}

// const response = await fetch(locationsUrl);
// const data = await response.json();

// console.log("Loaded GeoJSON:", data);