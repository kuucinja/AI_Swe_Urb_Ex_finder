#!/bin/bash

# Force UTF-8 so text doesn't break on Windows terminals
export LANG=C.UTF-8
export LC_ALL=C.UTF-8

# curl -X POST https://api.berget.ai/v1/chat/completions \
#   -H "Content-Type: application/json" \
#   -H "Authorization: Bearer sk_ber_3j3HVhZB2R1XPn0FaYDO6avfgpZ7bD9NbiDMR_d73634cfee2d4aa1" \
#   -d '{
#     "model": "openai/gpt-oss-120b",
#     "messages": [
#       { "role": "system", "content": "You are a helpful AI assistant." },
#       { "role": "user", "content": "Hello, how are you?" }
#     ],
#     "temperature": 0.7,
#     "max_tokens": 150
#   }' | jq -r '.choices[0].message.content'

history=""
API_KEY=sk_ber_3j3HVhZB2R1XPn0FaYDO6avfgpZ7bD9NbiDMR_d73634cfee2d4aa1

call_llm () {
  local messages="$1"

  response=$(curl -s -X POST https://api.berget.ai/v1/chat/completions \
    -H "Authorization: Bearer $API_KEY" \
    -H "Content-Type: application/json" \
    -d "{
      \"model\": \"openai/gpt-oss-120b\",
      \"messages\": [
        { \"role\": \"system\", \"content\": \"You are a helpful AI assistant.\" },
        { \"role\": \"user\", \"content\": \"$messages\" }
      ],
      \"temperature\": 0.7,
      \"max_tokens\": 150
    }") 
  echo "=== RAW RESPONSE ==="
  echo "$response"
  echo "===================="

  echo "$response" | jq -r '
    if has("choices") then
      .choices[0].message.content
    else
      "ERROR: " + (.error.message // "unknown error")
    end'
} 


while true; do
  read -p "You: " input

  history="$history
User: $input"

  response=$(call_llm "$history")
  echo "$response"
  reply=$(echo "$response" | jq -r '
  if has("choices") then
    .choices[0].message.content
  else
    "ERROR: " + (.error.message // "Unknown error")
  end
')

  echo "Agent: $reply"

  history="$history
Assistant: $reply"
done