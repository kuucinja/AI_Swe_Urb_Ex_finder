import type { AgentResponse, Location } from "../../retrieval/types";
import { callPythonAgent } from "./pythonAgent";

type ChatPayload = {
  message: string;
};

function isAgentResponse(value: unknown): value is AgentResponse {
  if (!value || typeof value !== "object") return false;
  const record = value as Record<string, unknown>;
  return (
    typeof record.reply === "string" &&
    Array.isArray(record.locations) &&
    record.locations.every(
      (item) =>
        typeof item === "object" &&
        item !== null &&
        typeof (item as Record<string, unknown>).id === "string",
    )
  );
}

async function tryChatApi(message: string): Promise<AgentResponse | null> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 12000);

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ message } satisfies ChatPayload),
      signal: controller.signal,
    });

    if (!response.ok) return null;

    const data: unknown = await response.json();
    return isAgentResponse(data) ? data : null;
  } catch {
    return null;
  } finally {
    window.clearTimeout(timeout);
  }
}

export async function sendChatMessage(
  message: string,
  locations: Location[],
): Promise<AgentResponse> {
  const res = await fetch("http://localhost:8000/chat", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      message,
      locations,
    }),
  });

  return res.json();
}
