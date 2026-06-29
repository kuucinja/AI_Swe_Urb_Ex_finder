import type { AgentResponse, Location } from "../../retrieval/types";

const categoryHints: Record<string, string[]> = {
  factory: ["factory", "mill", "plant", "industrial", "warehouse", "workshop"],
  hospital: ["hospital", "clinic", "ward", "medical"],
  bunker: ["bunker", "shelter", "subterranean", "underground"],
  military: ["military", "base", "depot", "fort", "airfield", "army", "navy"],
  tunnel: ["tunnel", "subway", "cave", "passage"],
  warehouse: ["warehouse", "storage", "logistics", "depot", "yard"],
};




function scoreLocation(message: string, location: Location): number {
  const text = message.toLowerCase();
  const name = location.name.toLowerCase();
  let score = 0;

  if (text.includes(name)) score += 12;
  if (text.includes(location.category)) score += 8;

  for (const hint of categoryHints[location.category] ?? []) {
    if (text.includes(hint)) score += 3;
  }

  if (text.includes(location.risk)) score += 2;

  return score;
}

export function buildMockAgentResponse(
  message: string,
  locations: Location[],
): AgentResponse {
  const scored = locations
    .map((location) => ({
      location,
      score: scoreLocation(message, location),
    }))
    .sort((a, b) => b.score - a.score);

  const matched = scored.filter((item) => item.score > 0).slice(0, 3);

  if (!matched.length) {
    return {
      reply:
        "I do not have a confident pin yet. Give me a place name, a category, or a rough area and I will narrow the map down.",
      locations: [],
    };
  }

  if (matched.length === 1) {
    return {
      reply: `I found one strong match: ${matched[0].location.name}. I have highlighted it on the map.`,
      locations: [{ id: matched[0].location.id }],
    };
  }

  return {
    reply: `I found ${matched.length} likely locations: ${matched
      .map((item) => item.location.name)
      .join(", ")}. I have highlighted them on the map.`,
    locations: matched.map((item) => ({ id: item.location.id })),
  };
}
