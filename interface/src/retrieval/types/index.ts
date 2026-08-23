// Mirrors one row of the `locations` table (database/schema.sql), as
// returned by database/repository.py's location queries via the
// backend. Field names match the Postgres columns 1:1 - no renaming
// layer, so this type breaks (loudly, at compile time) the moment the
// backend's shape changes instead of silently drifting.
export interface LocationEvidence {
  source?: string | null;
  thread_url?: string | null;
  post_id?: string | null;
  username?: string | null;
  time_raw?: string | null;
  confidence?: number | null;
  comment?: string | null;
  reasoning?: string | null;
}

export interface Location {
  id: string;
  entity: string;
  lat: number;
  lon: number;
  query?: string | null;
  display_name?: string | null;
  osm_type?: string | null;
  osm_id?: string | null;
  geocode_confidence?: number | null;
  post_id?: string | null;
  thread_url?: string | null;
  username?: string | null;
  time_raw?: string | null;
  confidence?: number | null;
  comment?: string | null;
  evidence?: LocationEvidence[];
  reasoning?: string | null;
  verified?: boolean;
}

// A raw Nominatim search result, as returned by
// GET /locations/{id}/geocode-candidates - osm_id is a number here
// (Nominatim's native type), unlike Location.osm_id which is text once
// stored (see database/schema.sql).
export interface GeocodeCandidate {
  lat: number;
  lon: number;
  display_name: string | null;
  osm_type?: string | null;
  osm_id?: number | null;
  importance?: number;
}

// The perpetual background crawler's status (retrieval/crawler.py),
// polled from GET /crawler/status. threads_known/threads_scraped count
// urbex-relevant threads specifically, not the whole forum.
export interface CrawlerStatus {
  running: boolean;
  current_activity: string | null;
  started_at: string | null;
  threads_known: number;
  threads_scraped: number;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  createdAt: string;
}

export type AgentResponse = {
  reply: {
    answer: string;
    used_locations: string[];
    confidence: number;
  };
  locations: Location[];
};

export interface MapState {
  center: [number, number];
  zoom: number;
  bearing: number;
  pitch: number;
}
