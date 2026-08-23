import type { AgentResponse, CrawlerStatus, GeocodeCandidate, Location } from "../../retrieval/types";
import { callPythonAgent } from "./pythonAgent";

type ChatPayload = {
  raw_query: string;
};

function isAgentResponse(value: unknown): value is AgentResponse {
  if (!value || typeof value !== "object") return false;
  const record = value as Record<string, unknown>;
  return (
    typeof record.reply === "object" &&
    record.reply !== null &&
    typeof (record.reply as any).answer === "string" &&
    Array.isArray(record.locations)
  );
}

// async function tryChatApi(raw_query: string): Promise<AgentResponse | null> {
//   const controller = new AbortController();
//   const timeout = window.setTimeout(() => controller.abort(), 12000);

//   try {
//     const response = await fetch("http://localhost:8000/chat", {
//       method: "POST",
//       headers: {
//         "Content-Type": "application/json",
//       },
//       body: JSON.stringify({ raw_query } satisfies ChatPayload),
//       signal: controller.signal,
//     });

//     if (!response.ok) return null;

//     const data: unknown = await response.json();
//     return isAgentResponse(data) ? data : null;
//   } catch {
//     return null;
//   } finally {
//     window.clearTimeout(timeout);
//   }
// }

export async function sendChatMessage(
  raw_query: string,
  locations: Location[],
): Promise<AgentResponse | null> {
  const res = await fetch("http://localhost:8000/chat", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      raw_query,
      locations,
    }),
  });

  const data: unknown = await res.json();
  return isAgentResponse(data) ? data : null;
}

function isLocation(value: unknown): value is Location {
  if (!value || typeof value !== "object") return false;
  const record = value as Record<string, unknown>;
  return typeof record.id === "string" && typeof record.entity === "string";
}

export async function correctLocation(
  id: string,
  entity: string,
): Promise<Location | null> {
  const res = await fetch(`http://localhost:8000/locations/${id}`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ entity }),
  });

  if (!res.ok) return null;

  const data: unknown = await res.json();
  return isLocation(data) ? data : null;
}

function isGeocodeCandidate(value: unknown): value is GeocodeCandidate {
  if (!value || typeof value !== "object") return false;
  const record = value as Record<string, unknown>;
  return typeof record.lat === "number" && typeof record.lon === "number";
}

export async function searchGeocodeCandidates(
  id: string,
  query: string,
): Promise<GeocodeCandidate[]> {
  const res = await fetch(
    `http://localhost:8000/locations/${id}/geocode-candidates?${new URLSearchParams({ q: query })}`,
  );

  if (!res.ok) return [];

  const data: unknown = await res.json();
  if (!data || typeof data !== "object") return [];
  const candidates = (data as Record<string, unknown>).candidates;
  return Array.isArray(candidates) ? candidates.filter(isGeocodeCandidate) : [];
}

export async function confirmGeocodeCandidate(
  id: string,
  candidate: GeocodeCandidate,
): Promise<Location | null> {
  const res = await fetch(`http://localhost:8000/locations/${id}/geocode`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(candidate),
  });

  if (!res.ok) return null;

  const data: unknown = await res.json();
  return isLocation(data) ? data : null;
}

function isCrawlerStatus(value: unknown): value is CrawlerStatus {
  if (!value || typeof value !== "object") return false;
  const record = value as Record<string, unknown>;
  return typeof record.running === "boolean" && typeof record.threads_known === "number";
}

async function crawlerRequest(path: string, method: "GET" | "POST"): Promise<CrawlerStatus | null> {
  try {
    const res = await fetch(`http://localhost:8000/crawler/${path}`, { method });
    if (!res.ok) return null;
    const data: unknown = await res.json();
    return isCrawlerStatus(data) ? data : null;
  } catch {
    return null;
  }
}

export const getCrawlerStatus = () => crawlerRequest("status", "GET");
export const startCrawler = () => crawlerRequest("start", "POST");
export const stopCrawler = () => crawlerRequest("stop", "POST");
