import requests
import sys
import tiktoken
import time
from dotenv import load_dotenv
import os
from backend.call_llm import call_llm, summarize



def run_agent_crawl(user_input):
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
    result = run_agent_crawl("this is not the main file, please explain it and tell what a good agent design looks like")
    print("\nFINAL OUTPUT:\n", result)



