import requests
import sys
import tiktoken
import time
from dotenv import load_dotenv
import os
import json

load_dotenv()

API_KEY = os.getenv("API_KEY")
API_URL = "https://api.berget.ai/v1/chat/completions"


retries = 15 # retry count for LLM calls, to get around transient errors or rate limits
MAX_TOKENS = 6000  # safe buffer
enc = tiktoken.get_encoding("cl100k_base")
MODEL_TYPE = "openai/gpt-oss-120b"



def count_tokens(messages):
    total = 0
    for m in messages:
        total += len(enc.encode(m["content"]))
    return total

def trim_to_limit(messages):
    while count_tokens(messages) > MAX_TOKENS and len(messages) > 2:
        # remove oldest NON-system message safely
        for i in range(len(messages)):
            if messages[i]["role"] != "system":
                messages.pop(i)
                break
    return messages

def summarize(messages):
    print("TOKENS, during summarize:", count_tokens(messages))
    print("Messages during summarize:")
    for m in messages:
        print(m["role"], len(m["content"]))
    summary_input = str(messages)

    print("SUMMARY INPUT CHARS:", len(summary_input))
    print("SUMMARY INPUT PREVIEW:", summary_input[:500])
    # input("pause before trying to access API for summary...")
    for i in range(retries):
    
        response = requests.post(
            API_URL,
            headers={'Authorization': f'Bearer {API_KEY}'},
            json={
                'model': MODEL_TYPE,
                'messages': [
                    {"role": "system", "content": "Summarize in max 5 bullet points."},
                    {"role": "user", "content": str(messages)}
                ],
                'temperature': 0.2,
                'max_tokens': 120   # 🔥 IMPORTANT
            }
        )
        data = response.json()

        if response.status_code == 200 and "choices" in data:
            return data["choices"][0]["message"]["content"]

        print(f"[Retry {i+1}] failed:", data)

        time.sleep(0.5 * (i + 1))  # exponential backoff
    
    raise Exception(f"FAILED AFTER RETRIES: {data}")

    if response.status_code != 200:
        print("SUMMARY ERROR:", data)
        raise Exception("Summary unavailable.")

    if "choices" not in data:
        print("SUMMARY ERROR:", data)
        raise Exception("Summary unavailable.")

    return data["choices"][0]["message"]["content"]

def call_llm(messages):
    messages = trim_to_limit(messages)
    print("TOKENS, during call_llm:", count_tokens(messages))
    print("messages during call_llm:")
    for m in messages:
        print(m["role"], len(m["content"]))
    
    for i in range(retries):
        response = response = requests.post(
        API_URL,
        headers={
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {API_KEY}'
        },
        json={
            'model': MODEL_TYPE,
            'messages': messages,
            'temperature': 0.7,
            'max_tokens': 300
        }
    )



        data = response.json()

        if response.status_code == 200 and "choices" in data:
            return data["choices"][0]["message"]["content"]

        print(f"[Retry {i+1}] failed:", data)

        time.sleep(0.5 * (i + 1))  # exponential backoff
    
    raise Exception(f"FAILED AFTER RETRIES: {data}")
    # data = response.json()

    # DEBUG (VERY IMPORTANT)
    # # print("STATUS:", response.status_code)
    # # print("RAW:", data)

    # # ❗ handle API errors properly
    # if response.status_code != 200:
    #     raise Exception(f"API ERROR: {data}")

    # if "choices" not in data:
    #     raise Exception(f"NO CHOICES RETURNED: {data}")

    # return data["choices"][0]["message"]["content"]


    # print(response.status_code)
    # print(response.text)
    # print(response.json())

    # return response.json()["choices"][0]["message"]["content"]

