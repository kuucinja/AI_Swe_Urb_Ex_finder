export type LocationCategory =
  | "factory"
  | "hospital"
  | "bunker"
  | "military"
  | "tunnel"
  | "warehouse";

export interface Location {
  id: string;
  name: string;
  category: LocationCategory;
  description: string;
  risk: "low" | "medium" | "high";
  coordinates: [number, number];
  comments?: string[];
  sourceUrl?: string;
  threadUrl?: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  createdAt: string;
}

export interface AgentResponse {
  reply: string;
  locations: Array<{ id: string }>;
}

export interface MapState {
  center: [number, number];
  zoom: number;
  bearing: number;
  pitch: number;
}
