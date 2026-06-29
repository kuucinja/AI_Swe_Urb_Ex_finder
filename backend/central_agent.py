import requests
import sys
import tiktoken
import time
from dotenv import load_dotenv
import os
import json
from backend.orchestrator import handle_query
from backend.call_llm import call_llm, trim_to_limit, summarize, count_tokens

from pathlib import Path

geo_loc_path = Path("..") / "retrieval" / "data_locations" 

memory = []  # global conversation memory

def update_memory(new_messages):
    global memory
    memory = trim_to_limit(memory + new_messages)

def run_agent(message: str, locations=None):

    global memory

    memory.append({"role": "user", "content": message})

    memory = trim_to_limit(memory)


    result = handle_query(message, geojson_dir=geo_loc_path)

    # give the LLM the data context, but keep it out of permanent memory
    # so you don't re-send a huge feature dump on every future turn
    data_context = f"Relevant locations found ({result['source']}):\n{result['locations']}"


    response = call_llm([
        {"role": "system", "content": "You are test."},
        *memory[:-1],
        {"role": "user", "content": f"{message}\n\n{data_context}"}
    ])

    memory.append({"role": "assistant", "content": response})


    return {
        "reply": response,
        "locations": result['locations']
    }

# if __name__ == "__main__":
#     input_data = json.loads(sys.argv[1])
#     # input(input_data)
#     message = input_data["message"]

#     output = run_agent(message)
#     print(json.dumps(output))