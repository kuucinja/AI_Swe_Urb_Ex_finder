import requests
import sys
import tiktoken
import time

API_KEY = "ADD_API_KEY_HERE"
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

def run_agent(user_input):
    messages = [
        {"role": "system", "content": "You are an autonomous assistant. Think step by step and complete the task. Return only 1 sentence."},
        {"role": "user", "content": user_input}
    ]

    memory = ""


    for step in range(2):  # agent loop limit
        if len(messages) > 11:
            #input(f"summarizing, current messages: {messages} \n press to continue..., length: {len(messages)}")
            memory = summarize(messages)

            messages = [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "system", "content": f"Memory summary: {memory}"}
            ]
        reply = call_llm(messages)
        print(f"\n[STEP {step}]\n{reply}")

        messages.append({"role": "assistant", "content": reply})

        # simple stopping condition
        if "FINAL ANSWER:" in reply:
            print(reply)
            return reply

        # otherwise continue loop (you could add tool execution here)

    return messages[-1]["content"]


if __name__ == "__main__":
    result = run_agent("this is not the main file, please explain it and tell what a good agent design looks like")
    print("\nFINAL OUTPUT:\n", result)



