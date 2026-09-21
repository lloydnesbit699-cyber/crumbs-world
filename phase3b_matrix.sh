#!/bin/bash
# Phase 3B failure-path matrix. Each scenario runs the real server,
# kills it the way the scenario demands, restarts, and inspects
# .crumbs_recovery/last_report.json + journal. Cleans up after itself.
set -u
SRC=~/workspace/goals/crumbs-vault-dungeon-game/files/crumbs-vault-dungeon
T=/tmp/p3btest
PORT=18794
PASS=0; FAIL=0

rm -rf $T; mkdir -p $T
for f in crumbs_hud.py crumbs_core.py editor.html crumbs_recovery.py; do cp $SRC/$f $T/$f; done
cd $T

pid_on_port() { ss -tlnp 2>/dev/null | grep ":$PORT" | grep -oP 'pid=\K[0-9]+' | head -1; }
start_server() { (PORT=$PORT python3 -u crumbs_hud.py > server_$1.log 2>&1 &); sleep 6; }
stop_sigterm() { P=$(pid_on_port); [ -n "$P" ] && kill -TERM $P; sleep 2; }
stop_kill9()   { P=$(pid_on_port); [ -n "$P" ] && kill -9 $P; sleep 1; }
report() { python3 -c "
import json
r = json.load(open('.crumbs_recovery/last_report.json'))
print('category=' + r['interruption']['category'])
print('risk=' + r['risk']['level'] + ' (' + r['risk']['reason'] + ')')
print('action=' + r['action'] + ' detail=' + json.dumps(r['action_detail']))
print('outcome=' + r['verification']['outcome'])
print('steps=' + ','.join(s['name'] + ':' + s['status'] for s in r['verification']['steps']))
print('finding=' + r['checkpoint']['finding'] + ' slot=' + str(r['checkpoint']['slot']) + ' primary=' + r['primary']['state'])
"; }
check() { # check <desc> <expected> <actual>
  if [ "$2" = "$3" ]; then PASS=$((PASS+1)); echo "  ok: $1";
  else FAIL=$((FAIL+1)); echo "  FAIL: $1 (expected $2, got $3)"; fi
}
rep_field() { python3 -c "
import json; r = json.load(open('.crumbs_recovery/last_report.json'))
v = r$1; print(v if not isinstance(v, (dict, list)) else json.dumps(v))"; }
journal_has() { grep -c "\"event\":\"$1\"" .crumbs_recovery/recovery-journal.jsonl 2>/dev/null || true; }

echo "=== T1: clean shutdown (SIGTERM) ==="
start_server A
curl -s -X POST -H "Content-Type: application/json" -d '{}' http://127.0.0.1:$PORT/api/save > /dev/null
stop_sigterm
[ -f .crumbs_recovery/clean.shutdown ] && [ ! -f .crumbs_recovery/dirty.flag ] \
  && echo "  ok: clean marker written, dirty flag cleared" && PASS=$((PASS+1)) \
  || { echo "  FAIL: lifecycle markers"; FAIL=$((FAIL+1)); }
start_server B
report
check "T1 category" "CLEAN_SHUTDOWN" "$(rep_field "['interruption']['category']")"
check "T1 risk" "LOW" "$(rep_field "['risk']['level']")"
check "T1 action" "NONE" "$(rep_field "['action']")"
check "T1 outcome" "RECOVERY_SUCCESS" "$(rep_field "['verification']['outcome']")"

echo "=== T2: kill -9, healthy primary ==="
curl -s -X POST -H "Content-Type: application/json" -d '{}' http://127.0.0.1:$PORT/api/save > /dev/null
sleep 7  # let a heartbeat land
stop_kill9
start_server C
report
check "T2 category" "CRASH" "$(rep_field "['interruption']['category']")"
check "T2 risk" "MEDIUM" "$(rep_field "['risk']['level']")"
check "T2 action" "NONE" "$(rep_field "['action']")"
check "T2 skip reason" "PRIMARY_HEALTHY" "$(rep_field "['action_detail']['reason']")"
check "T2 outcome" "RECOVERY_SUCCESS" "$(rep_field "['verification']['outcome']")"

echo "=== T3: kill -9, corrupted primary ==="
curl -s -X POST -H "Content-Type: application/json" -d '{}' http://127.0.0.1:$PORT/api/save > /dev/null
sleep 7
stop_kill9
echo "CORRUPT" > hud_map.json
start_server D
report
check "T3 category" "CORRUPTED_STATE" "$(rep_field "['interruption']['category']")"
check "T3 action" "RESTORED" "$(rep_field "['action']")"
check "T3 risk" "MEDIUM" "$(rep_field "['risk']['level']")"
check "T3 outcome" "RECOVERY_SUCCESS" "$(rep_field "['verification']['outcome']")"
[ "$(cat hud_map.json)" = "CORRUPT" ] && echo "  ok: corrupted primary untouched" && PASS=$((PASS+1)) \
  || { echo "  FAIL: primary was modified"; FAIL=$((FAIL+1)); }
[ "$(journal_has STATE_RESTORED)" -ge 1 ] && echo "  ok: STATE_RESTORED journaled" && PASS=$((PASS+1)) \
  || { echo "  FAIL: no STATE_RESTORED"; FAIL=$((FAIL+1)); }

echo "=== T4: fallback slot (latest corrupt) + corrupt primary ==="
echo "BROKEN" > .crumbs_recovery/latest.json
echo "CORRUPT" > hud_map.json
stop_kill9
start_server E
report
check "T4 finding" "FALLBACK" "$(rep_field "['checkpoint']['finding']")"
check "T4 risk" "HIGH" "$(rep_field "['risk']['level']")"
check "T4 action" "RESTORED" "$(rep_field "['action']")"
check "T4 outcome" "RECOVERY_PARTIAL" "$(rep_field "['verification']['outcome']")"
[ "$(journal_has INTERVENTION_NOTICE)" -ge 1 ] && echo "  ok: INTERVENTION_NOTICE journaled" && PASS=$((PASS+1)) \
  || { echo "  FAIL: no INTERVENTION_NOTICE"; FAIL=$((FAIL+1)); }

echo "=== T5: all slots corrupt + corrupt primary (nothing safe) ==="
echo "BROKEN" > .crumbs_recovery/prev-1.json
echo "BROKEN" > .crumbs_recovery/prev-2.json
echo "CORRUPT" > hud_map.json
stop_kill9
start_server G
report
check "T5 risk" "CRITICAL" "$(rep_field "['risk']['level']")"
check "T5 action" "WITHHELD" "$(rep_field "['action']")"
check "T5 outcome" "RECOVERY_UNSAFE" "$(rep_field "['verification']['outcome']")"
[ "$(cat hud_map.json)" = "CORRUPT" ] && [ "$(cat .crumbs_recovery/prev-1.json)" = "BROKEN" ] \
  && echo "  ok: evidence preserved, nothing overwritten" && PASS=$((PASS+1)) \
  || { echo "  FAIL: evidence was modified"; FAIL=$((FAIL+1)); }
HTTP=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:$PORT/)
check "T5 server still serves" "200" "$HTTP"

echo "=== T6: status endpoint ==="
ST=$(curl -s http://127.0.0.1:$PORT/api/recovery/status | python3 -c "
import sys, json
m = json.load(sys.stdin)
r = m['report']
print('report' if r else 'NOREPORT')
print(r['risk']['level'])
print('serving' if m['server_serving'] else 'NOTSERVING')
print('steps%d' % len(r['verification']['steps']))
print('hb' if (m['heartbeat_age'] or 999) < 30 else 'NOHB')
")
echo "$ST"
check "T6 endpoint report" "report" "$(echo "$ST" | sed -n 1p)"
check "T6 endpoint risk" "CRITICAL" "$(echo "$ST" | sed -n 2p)"
check "T6 server_serving" "serving" "$(echo "$ST" | sed -n 3p)"
check "T6 steps" "steps6" "$(echo "$ST" | sed -n 4p)"
check "T6 heartbeat fresh" "hb" "$(echo "$ST" | sed -n 5p)"

stop_kill9
cd /; rm -rf $T
echo "=== RESULT: $PASS passed, $FAIL failed ==="
