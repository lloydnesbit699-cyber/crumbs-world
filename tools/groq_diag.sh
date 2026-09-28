#!/bin/bash
# groq_diag.sh — Melody brain diagnostic (no paste needed: bash tools/groq_diag.sh)
#
# Tests the workspace GROQ_API_KEY against Groq's API exactly the way
# melody_agent.py calls it. Prints HTTP codes + Groq's own error text.
# The key itself is NEVER printed.
#
# Test 1: GET /openai/v1/models            -> is the key valid at all?
# Test 2: POST /openai/v1/chat/completions -> does the brain's model + path work?
#   (model qwen/qwen3.6-27b, same payload shape as brain_chat())

set -u

KEY="${GROQ_API_KEY:-}"
if [ -z "$KEY" ]; then
  echo "RESULT: GROQ_API_KEY is NOT SET in this shell (Secrets has no such key, or shell not reloaded)"
  exit 1
fi
echo "RESULT: GROQ_API_KEY is set (length ${#KEY} chars; value hidden)"

echo ""
echo "--- Test 1: key validity  (GET /openai/v1/models) ---"
CODE1=$(curl -s -o /tmp/groq_diag_models.json -w "%{http_code}" \
  https://api.groq.com/openai/v1/models \
  -H "Authorization: Bearer $KEY")
echo "HTTP:$CODE1"
head -c 300 /tmp/groq_diag_models.json; echo ""

echo ""
echo "--- Test 1b: model IDs this key can actually use (one per line) ---"
python3 -c "import json;d=json.load(open('/tmp/groq_diag_models.json'));[print(m['id']) for m in d.get('data',[])]"

echo ""
echo "--- Test 2: brain path  (POST /openai/v1/chat/completions, qwen/qwen3.6-27b) ---"
CODE2=$(curl -s -o /tmp/groq_diag_chat.json -w "%{http_code}" \
  https://api.groq.com/openai/v1/chat/completions \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"qwen/qwen3.6-27b","messages":[{"role":"user","content":"say hi"}],"max_tokens":20,"temperature":0.7}')
echo "HTTP:$CODE2"
head -c 600 /tmp/groq_diag_chat.json; echo ""

echo ""
echo "--- done: report the two HTTP lines + any error text above to Wren ---"

# Test 3/4: candidate replacement models, with the EXACT payload shape
# brain_chat() sends (tools + tool_choice:auto). A model that 200s here
# will work as Melody's brain.
for CAND in "qwen/qwen3.8-27b" "openai/gpt-oss-120b"; do
  echo ""
  echo "--- Candidate: $CAND (with tools, brain-shaped payload) ---"
  CODE=$(curl -s -o /tmp/groq_diag_cand.json -w "%{http_code}" \
    https://api.groq.com/openai/v1/chat/completions \
    -H "Authorization: Bearer $KEY" \
    -H "Content-Type: application/json" \
    -d "{\"model\":\"$CAND\",\"messages\":[{\"role\":\"user\",\"content\":\"say hi\"}],\"max_tokens\":20,\"temperature\":0.7,\"tools\":[{\"type\":\"function\",\"function\":{\"name\":\"get_time\",\"description\":\"get the time\",\"parameters\":{\"type\":\"object\",\"properties\":{}}}}],\"tool_choice\":\"auto\"}")
  echo "HTTP:$CODE"
  head -c 400 /tmp/groq_diag_cand.json; echo ""
done
echo ""
echo "--- report the candidate HTTP lines to Wren ---"
