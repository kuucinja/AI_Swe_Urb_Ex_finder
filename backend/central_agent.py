import requests
import sys
import tiktoken
import time
from dotenv import load_dotenv
import os
import json
from backend.orchestrator import handle_query
from backend.call_llm import call_llm, call_llm_json, trim_to_limit, summarize, count_tokens

memory = []  # global conversation memory

def update_memory(new_messages):
    global memory
    memory = trim_to_limit(memory + new_messages)

_ACTIVITY_PREFIXES = (
    "Reprocessed",
    "Started the background crawler",
    "Crawler already running",
    "Merged",
    "Checked for duplicates",
)


def _format_activity_note(log: list) -> str | None:
    """Build a short, deterministic summary of what the orchestrator
    actually did (cache/reprocess/ensure_crawling/deduplicate + why) and
    the background crawler's current status, so the chat reply always
    reports both accurately - the answer-generation LLM below is only
    ever given the resulting location data, not the decision process,
    crawler state, or merge results, and reliably doesn't mention any of
    that on its own. The crawler line is included on every reply, not
    just the one that started it. Every merge summary line is included
    (not just the first) - merges are never reported silently."""
    decision_line = next((l for l in log if l.startswith("Agent decision:")), None)
    activity_lines = [l for l in log if l.startswith(_ACTIVITY_PREFIXES)]
    crawler_line = next((l for l in log if l.startswith("Crawler status:")), None)

    parts = []
    if decision_line:
        parts.append(f"Action taken: {decision_line.replace('Agent decision: ', '', 1)}")
        parts.extend(activity_lines)
    if crawler_line:
        parts.append(crawler_line)

    return " ".join(parts) if parts else None

def run_agent(raw_query: str, locations=None):

    global memory

    memory.append({"role": "user", "content": raw_query})

    memory = trim_to_limit(memory)


    result = handle_query(raw_query)

    print(f"this is the result \n{result}")
    print(f"\n this is result source :\n {result['source']}\nthis is result locations:\n{result['locations']}")

    # give the LLM the data context, but keep it out of permanent memory
    # so you don't re-send a huge feature dump on every future turn
    data_context = json.dumps(
        {
            "source": result["source"],
            "locations": result["locations"]
        },
        indent=2
    )

    messages = [{
    "role": "system",
    "content": """
You are a grounded location assistant.

RULES:
- ONLY use the provided "locations" data.
- DO NOT invent places.
- If locations exist, base your answer strictly on them.
- If locations are empty, say you found nothing.

OUTPUT FORMAT (STRICT):
Return JSON only:

{
  "answer": string,
  "used_locations": [entity names],
  "confidence": number between 0 and 1
}
"""
},
    *memory[:-1],
    {
        "role": "user",
        "content": f"""
USER QUERY:
{raw_query}

AVAILABLE DATA (TRUST ONLY THIS):
{data_context}
"""
    }
]

    try:
        structured = call_llm_json(messages)
        if "answer" not in structured:
            raise ValueError(f"missing 'answer' key: {structured!r}")
    except Exception as exc:
        print(f"run_agent: failed to get a structured reply: {exc}")
        structured = {
            "answer": "I found the data but had trouble putting together a clean answer. Try rephrasing, or check the map pins directly.",
            "used_locations": [],
            "confidence": 0.0
        }

    activity_note = _format_activity_note(result.get("log", []))
    if activity_note:
        structured["answer"] = f"{structured['answer']}\n\n_{activity_note}_"

    memory.append({
    "role": "assistant",
    "content": json.dumps(structured)
})

    return {
        "reply": structured,
        "locations": result['locations']
    }

# if __name__ == "__main__":
#     input_data = json.loads(sys.argv[1])
#     # input(input_data)
#     message = input_data["message"]

#     output = run_agent(message)
#     print(json.dumps(output))