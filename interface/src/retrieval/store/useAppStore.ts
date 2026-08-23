import { create } from "zustand";
import type { ChatMessage, CrawlerStatus, GeocodeCandidate, Location, MapState } from "../types";
import {
  sendChatMessage,
  correctLocation,
  searchGeocodeCandidates,
  confirmGeocodeCandidate,
  getCrawlerStatus,
  startCrawler,
  stopCrawler,
} from "../../agentic-tools/services/agent";

type AppState = {
  locations: Location[];
  messages: ChatMessage[];
  highlightedLocationIds: string[];
  selectedLocationId: string | null;
  mapState: MapState;
  isChatLoading: boolean;
  isLocationsLoading: boolean;
  error: string | null;
  focusToken: number;
  crawlerStatus: CrawlerStatus | null;
  setLocations: (locations: Location[]) => void;
  setMapState: (state: Partial<MapState>) => void;
  selectLocation: (locationId: string | null) => void;
  setHighlightedLocations: (locationIds: string[]) => void;
  sendMessage: (message: string) => Promise<void>;
  correctLocationEntity: (id: string, entity: string) => Promise<boolean>;
  searchGeocode: (id: string, query: string) => Promise<GeocodeCandidate[]>;
  correctLocationGeocode: (id: string, candidate: GeocodeCandidate) => Promise<boolean>;
  refreshCrawlerStatus: () => Promise<void>;
  startCrawling: () => Promise<void>;
  stopCrawling: () => Promise<void>;
  clearError: () => void;
};

function createMessage(role: ChatMessage["role"], content: string): ChatMessage {
  return {
    id: crypto.randomUUID(),
    role,
    content,
    createdAt: new Date().toISOString(),
  };
}

export const useAppStore = create<AppState>((set, get) => ({
  locations: [],
  messages: [
    createMessage(
      "assistant",
      "I am ready. Send me a clue, an area, or a category and I will narrow the Urbex map.",
    ),
  ],
  highlightedLocationIds: [],
  selectedLocationId: null,
  mapState: {
    center: [15.0, 62.0],
    zoom: 4.8,
    bearing: 0,
    pitch: 0,
  },
  isChatLoading: false,
  isLocationsLoading: false,
  error: null,
  focusToken: 0,
  crawlerStatus: null,
  setLocations: (locations) => set({ locations, isLocationsLoading: false }),
  setMapState: (state) =>
    set((current) => ({
      mapState: {
        ...current.mapState,
        ...state,
      },
    })),
  selectLocation: (locationId) => set({ selectedLocationId: locationId }),
  setHighlightedLocations: (locationIds) =>
    set({
      highlightedLocationIds: locationIds,
      focusToken: Date.now(),
      selectedLocationId: locationIds[0] ?? null,
    }),
  clearError: () => set({ error: null }),
  correctLocationEntity: async (id, entity) => {
    const updated = await correctLocation(id, entity);
    if (!updated) return false;

    set((current) => ({
      locations: current.locations.map((location) =>
        location.id === id ? updated : location,
      ),
    }));
    return true;
  },
  searchGeocode: (id, query) => searchGeocodeCandidates(id, query),
  correctLocationGeocode: async (id, candidate) => {
    const updated = await confirmGeocodeCandidate(id, candidate);
    if (!updated) return false;

    set((current) => ({
      locations: current.locations.map((location) =>
        location.id === id ? updated : location,
      ),
    }));
    return true;
  },
  refreshCrawlerStatus: async () => {
    const status = await getCrawlerStatus();
    if (status) set({ crawlerStatus: status });
  },
  startCrawling: async () => {
    const status = await startCrawler();
    if (status) set({ crawlerStatus: status });
  },
  stopCrawling: async () => {
    const status = await stopCrawler();
    if (status) set({ crawlerStatus: status });
  },
  sendMessage: async (message) => {
    const content = message.trim();
    if (!content) return;

    const userMessage = createMessage("user", content);
    set((current) => ({
      messages: [...current.messages, userMessage],
      isChatLoading: true,
      error: null,
    }));

    try {
      const response = await sendChatMessage(content, get().locations);
      if (!response) throw new Error("Agent returned an unreadable response");

      console.log("agent locations:", response.locations);
      const assistantMessage = createMessage("assistant", response.reply.answer);
      set((current) => ({
        messages: [...current.messages, assistantMessage],
        highlightedLocationIds: response.locations.map((item) => item.id),
        selectedLocationId: response.locations[0]?.id ?? current.selectedLocationId,
        focusToken: response.locations.length ? Date.now() : current.focusToken,
        isChatLoading: false,
      }));
    } catch (error) {
      set((current) => ({
        messages: [
          ...current.messages,
          createMessage(
            "assistant",
            "I hit a routing problem while reaching the agent. Try again in a moment.",
          ),
        ],
        isChatLoading: false,
        error: error instanceof Error ? error.message : "Unknown agent error",
      }));
    }
  },
}));
