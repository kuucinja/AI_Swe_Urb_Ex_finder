import requests
import json

"""
MODEL OBJECT STRUCTURE (Berget API /v1/models)

Each model item contains:

- id (str)              -> full model identifier
- name (str)            -> display name
- object (str)          -> always "model"
- owned_by (str)        -> provider (openai, mistralai, etc.)
- root (str)            -> root model path
- parent (str|null)     -> parent model if derived
- model_type (str)      -> text / embedding / rerank / speech-to-text
- model_path (str)      -> internal model path
- model_size (int)      -> size (may be 0 if unknown)
- license (str)         -> license type
- lifecycle_state (str) -> stable / eval / deprecated
- release_date (str)    -> ISO date
- created (int)         -> timestamp
- status (dict)
    - up (bool)

- capabilities (dict)
    - streaming (bool)
    - function_calling (bool)
    - json_mode (bool)
    - formatted_output (bool)
    - vision (bool)
    - embeddings (bool)
    - classification (bool)

- pricing (dict)
    - input (float)
    - output (float)
    - currency (str)
    - unit (str)

- aliases (list[str])   -> alternative model names
"""




API_KEY = "sk_ber_3j3HVhZB2R1XPn0FaYDO6avfgpZ7bD9NbiDMR_d73634cfee2d4aa1"


url = "https://api.berget.ai/v1/models"

headers = {
    "Authorization": f"Bearer {API_KEY}"
}

response = requests.get(url, headers=headers)

data = response.json()["data"]

gpt_models = [
    m for m in data
    if "gpt" in m["id"].lower()
]

print(json.dumps(gpt_models, indent=2))