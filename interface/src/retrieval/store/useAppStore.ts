import { create } from "zustand";
import type { ChatMessage, Location, MapState } from "../types";
import { sendChatMessage } from "../../agentic-tools/services/agent";

type AppState = {
  locations: Location[];
  messages: ChatMessage[];
  highlightedLocationIds: string[];
  selectedLocationId: string | null;
  activeCategories: Location["category"][];
  mapState: MapState;
  isChatLoading: boolean;
  isLocationsLoading: boolean;
  error: string | null;
  focusToken: number;
  setLocations: (locations: Location[]) => void;
  setMapState: (state: Partial<MapState>) => void;
  setActiveCategories: (categories: Location["category"][]) => void;
  toggleCategory: (category: Location["category"]) => void;
  selectLocation: (locationId: string | null) => void;
  setHighlightedLocations: (locationIds: string[]) => void;
  sendMessage: (message: string) => Promise<void>;
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
  activeCategories: [],
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
  setLocations: (locations) => set({ locations, isLocationsLoading: false }),
  setMapState: (state) =>
    set((current) => ({
      mapState: {
        ...current.mapState,
        ...state,
      },
    })),
  setActiveCategories: (categories) => set({ activeCategories: categories }),
  toggleCategory: (category) =>
    set((current) => {
      const activeCategories = current.activeCategories.includes(category)
        ? current.activeCategories.filter((item) => item !== category)
        : [...current.activeCategories, category];

      return { activeCategories };
    }),
  selectLocation: (locationId) => set({ selectedLocationId: locationId }),
  setHighlightedLocations: (locationIds) =>
    set({
      highlightedLocationIds: locationIds,
      focusToken: Date.now(),
      selectedLocationId: locationIds[0] ?? null,
    }),
  clearError: () => set({ error: null }),
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
      const assistantMessage = createMessage("assistant", response.reply);
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
