import maplibregl, { type GeoJSONSource, type Map as MapLibreMap, Popup } from "maplibre-gl";
import { useEffect, useMemo, useRef } from "react";
import { createRoot } from "react-dom/client";
import { useAppStore } from "../../retrieval/store/useAppStore";
import type { Location } from "../../retrieval/types";
import { LocationPopup } from "./LocationPopup";

const MAP_STYLE = "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";

const CATEGORY_COLORS: Record<Location["category"], string> = {
  factory: "#22d3ee",
  hospital: "#34d399",
  bunker: "#f59e0b",
  military: "#fb7185",
  tunnel: "#a78bfa",
  warehouse: "#38bdf8",
};

function toFeatureCollection(locations: Location[]) {
  return {
    type: "FeatureCollection" as const,
    features: locations.map((location) => ({
      type: "Feature" as const,
      geometry: {
        type: "Point" as const,
        coordinates: location.coordinates,
      },
      properties: {
        id: location.id,
        name: location.name,
        category: location.category,
        description: location.description,
        risk: location.risk,
        comments: location.comments ?? [],
        sourceUrl: location.sourceUrl ?? null,
        threadUrl: location.threadUrl ?? null,
      },
    })),
  };
}

export function MapView() {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const visibleLocationsRef = useRef<Location[]>([]);
  const highlightIdsRef = useRef<string[]>([]);

  const locations = useAppStore((state) => state.locations);
  const activeCategories = useAppStore((state) => state.activeCategories);
  const highlightedLocationIds = useAppStore((state) => state.highlightedLocationIds);
  const selectedLocationId = useAppStore((state) => state.selectedLocationId);
  const focusToken = useAppStore((state) => state.focusToken);
  const setMapState = useAppStore((state) => state.setMapState);
  const selectLocation = useAppStore((state) => state.selectLocation);

  const visibleLocations = useMemo(() => {
    if (!activeCategories.length) return locations;
    return locations.filter((location) => activeCategories.includes(location.category));
  }, [activeCategories, locations]);

  const highlightIds = useMemo(
    () => Array.from(new Set([...(highlightedLocationIds ?? []), selectedLocationId].filter(Boolean) as string[])),
    [highlightedLocationIds, selectedLocationId],
  );

  useEffect(() => {
    visibleLocationsRef.current = visibleLocations;
  }, [visibleLocations]);

  useEffect(() => {
    highlightIdsRef.current = highlightIds;
  }, [highlightIds]);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: MAP_STYLE,
      center: [15, 62],
      zoom: 4.8,
      pitch: 25,
      bearing: 0,
      attributionControl: false,
    });

    map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "top-right");
    map.addControl(new maplibregl.AttributionControl({ compact: true }), "bottom-right");

    const syncData = () => {
      const source = map.getSource("locations") as GeoJSONSource | undefined;
      if (source) {
        source.setData(toFeatureCollection(visibleLocationsRef.current));
      }

      if (map.getLayer("locations-highlight")) {
        map.setFilter("locations-highlight", [
          "in",
          ["get", "id"],
          ["literal", highlightIdsRef.current],
        ]);
      }
    };

    map.on("load", () => {
      map.addSource("locations", {
        type: "geojson",
        data: toFeatureCollection(visibleLocationsRef.current),
      });

      map.addLayer({
        id: "locations-glow",
        type: "circle",
        source: "locations",
        paint: {
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 3, 5, 10, 7, 14, 9],
          "circle-color": [
            "match",
            ["get", "category"],
            "factory",
            CATEGORY_COLORS.factory,
            "hospital",
            CATEGORY_COLORS.hospital,
            "bunker",
            CATEGORY_COLORS.bunker,
            "military",
            CATEGORY_COLORS.military,
            "tunnel",
            CATEGORY_COLORS.tunnel,
            "warehouse",
            CATEGORY_COLORS.warehouse,
            "#60a5fa",
          ],
          "circle-opacity": 0.15,
          "circle-blur": 0.9,
        },
      });

      map.addLayer({
        id: "locations-circle",
        type: "circle",
        source: "locations",
        paint: {
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 3, 4, 10, 6, 14, 8],
          "circle-color": [
            "match",
            ["get", "category"],
            "factory",
            CATEGORY_COLORS.factory,
            "hospital",
            CATEGORY_COLORS.hospital,
            "bunker",
            CATEGORY_COLORS.bunker,
            "military",
            CATEGORY_COLORS.military,
            "tunnel",
            CATEGORY_COLORS.tunnel,
            "warehouse",
            CATEGORY_COLORS.warehouse,
            "#60a5fa",
          ],
          "circle-stroke-width": 1.5,
          "circle-stroke-color": "#0f172a",
          "circle-opacity": [
            "match",
            ["get", "risk"],
            "high",
            1,
            "medium",
            0.92,
            0.84,
          ],
        },
      });

      map.addLayer({
        id: "locations-highlight",
        type: "circle",
        source: "locations",
        filter: ["in", ["get", "id"], ["literal", highlightIdsRef.current]],
        paint: {
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 3, 8, 10, 12, 14, 16],
          "circle-color": "#f8fafc",
          "circle-opacity": 0.3,
          "circle-stroke-width": 3,
          "circle-stroke-color": "#67e8f9",
        },
      });

      map.addLayer({
        id: "locations-labels",
        type: "symbol",
        source: "locations",
        layout: {
          "text-field": ["get", "name"],
          "text-size": 12,
          "text-offset": [0, 1.4],
          "text-anchor": "top",
          "text-allow-overlap": false,
        },
        paint: {
          "text-color": "#dbeafe",
          "text-halo-color": "#020617",
          "text-halo-width": 1.25,
        },
      });

      map.on("mouseenter", "locations-circle", () => {
        map.getCanvas().style.cursor = "pointer";
      });
      map.on("mouseleave", "locations-circle", () => {
        map.getCanvas().style.cursor = "";
      });

      map.on("click", "locations-circle", (event) => {
        const feature = event.features?.[0];
        if (!feature) return;

        const properties = feature.properties as Record<string, string | undefined>;
        const id = properties.id;
        const location = visibleLocationsRef.current.find((item) => item.id === id);
        if (!location) return;

        selectLocation(id ?? null);

        const popupContainer = document.createElement("div");
        const popupRoot = createRoot(popupContainer);
        popupRoot.render(
          <LocationPopup
            location={location}
            isHighlighted={highlightIdsRef.current.includes(location.id)}
          />,
        );

        new Popup({ closeButton: true, offset: 16 })
          .setLngLat(location.coordinates)
          .setDOMContent(popupContainer)
          .addTo(map)
          .on("close", () => {
            popupRoot.unmount();
          });
      });

      map.on("moveend", () => {
        const center = map.getCenter();
        setMapState({
          center: [center.lng, center.lat],
          zoom: map.getZoom(),
          bearing: map.getBearing(),
          pitch: map.getPitch(),
        });
      });

      mapRef.current = map;
    });

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, [selectLocation, setMapState]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    syncRenderedMap(map);

    if (!visibleLocations.length) return;

    const targetLocations = highlightIds.length
      ? visibleLocations.filter((location) => highlightIds.includes(location.id))
      : visibleLocations;

    if (!targetLocations.length) return;

    if (targetLocations.length === 1) {
      map.easeTo({
        center: targetLocations[0].coordinates,
        zoom: Math.max(map.getZoom(), 13),
        duration: 900,
      });
      return;
    }

    const bounds = new maplibregl.LngLatBounds();
    for (const location of targetLocations) {
      bounds.extend(location.coordinates);
    }
    map.fitBounds(bounds, {
      padding: { top: 80, bottom: 80, left: 80, right: 80 },
      duration: 1000,
      maxZoom: 14,
    });
  }, [focusToken, highlightIds, visibleLocations]);

  function syncRenderedMap(map: MapLibreMap) {
    const source = map.getSource("locations") as GeoJSONSource | undefined;
    if (source) {
      source.setData(toFeatureCollection(visibleLocations));
    }

    if (map.getLayer("locations-highlight")) {
      map.setFilter("locations-highlight", [
        "in",
        ["get", "id"],
        ["literal", highlightIds],
      ]);
    }
  }

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    syncRenderedMap(map);
  }, [highlightIds, visibleLocations]);

  return (
    <div className="relative h-full min-h-0 overflow-hidden bg-slate-950">
      <div
        ref={containerRef}
        className="absolute inset-0"
        aria-label="Interactive Urbex map"
      />

      <div className="pointer-events-none absolute left-4 top-4 z-10 max-w-[320px] rounded-2xl border border-white/10 bg-slate-950/70 px-4 py-3 text-xs text-slate-300 shadow-panel backdrop-blur-xl">
        <p className="uppercase tracking-[0.2em] text-slate-400">map state</p>
        <div className="mt-2 grid grid-cols-2 gap-2">
          <div>
            <div className="text-slate-500">visible</div>
            <div className="text-sm text-white">{visibleLocations.length}</div>
          </div>
          <div>
            <div className="text-slate-500">highlighted</div>
            <div className="text-sm text-white">{highlightIds.length}</div>
          </div>
        </div>
      </div>
    </div>
  );
}
