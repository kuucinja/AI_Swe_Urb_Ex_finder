import type { AgentResponse, Location } from "../../retrieval/types";

function scoreLocation(message: string, location: Location): number {
  const text = message.toLowerCase();
  const entity = location.entity.toLowerCase();
  let score = 0;

  if (text.includes(entity)) score += 12;
  if (location.comment && text.includes(location.comment.toLowerCase())) score += 3;
  if (location.display_name && text.includes(location.display_name.toLowerCase())) score += 3;

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
      reply: {
        answer:
          "I do not have a confident pin yet. Give me a place name or a rough area and I will narrow the map down.",
        used_locations: [],
        confidence: 0,
      },
      locations: [],
    };
  }

  if (matched.length === 1) {
    return {
      reply: {
        answer: `I found one strong match: ${matched[0].location.entity}. I have highlighted it on the map.`,
        used_locations: [matched[0].location.entity],
        confidence: 1,
      },
      locations: [matched[0].location],
    };
  }

  return {
    reply: {
      answer: `I found ${matched.length} likely locations: ${matched
        .map((item) => item.location.entity)
        .join(", ")}. I have highlighted them on the map.`,
      used_locations: matched.map((item) => item.location.entity),
      confidence: 1,
    },
    locations: matched.map((item) => item.location),
  };
}