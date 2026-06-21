#!/bin/bash
#
# Husky-through-nrp-backend acceptance gate.
#
# Proves the revived stack can actually run a simulation end-to-end (the
# automated counterpart of SMOKE_TEST.md step 4, which is otherwise a manual
# browser action). Against a running stack it:
#   1. authenticates to the proxy (FS auth),
#   2. clones the husky_braitenberg template into FS storage,
#   3. creates + starts a simulation through nrp-backend's REST API
#      (this forks nrp-core -> gazebo + NEST),
#   4. asserts the simulation reaches 'started', emits MQTT status events,
#      and publishes NO runtime_error,
#   5. stops the simulation and deletes the cloned experiment.
#
# Exit 0 = PASS. Any failed assertion exits non-zero with a reason, so this is
# usable as a CI gate (bring the stack up, run this, tear it down).
#
# Prerequisite: the stack is up and healthy (./start_nrp_docker.sh).
#
# Overridable via env: NRP_BASE_URL, NRP_FS_USER, NRP_FS_PASSWORD,
# HUSKY_TEMPLATE, HUSKY_CONFIG, START_TIMEOUT, NRP_BACKEND_CONTAINER.
set -uo pipefail

BASE="${NRP_BASE_URL:-http://localhost:9000}"
USER_NAME="${NRP_FS_USER:-nrpuser}"
USER_PASS="${NRP_FS_PASSWORD:-password}"
TEMPLATE="${HUSKY_TEMPLATE:-husky_braitenberg/simulation_config.json}"
CONFIG="${HUSKY_CONFIG:-simulation_config.json}"
START_TIMEOUT="${START_TIMEOUT:-120}"
BACKEND_CTR="${NRP_BACKEND_CONTAINER:-nrp-backend}"

log()  { echo "[husky-gate] $*"; }
fail() { echo "[husky-gate] GATE FAIL: $*" >&2; exit 1; }

json_get() { python3 -c "import sys,json;
try: print(json.load(sys.stdin).get('$1',''))
except Exception: print('')"; }

# 0. precondition: proxy/backend healthy ---------------------------------------
hc=$(curl -s -o /dev/null -w '%{http_code}' "$BASE/proxy/health" || true)
[ "$hc" = "200" ] || fail "proxy not healthy at $BASE (HTTP $hc) — start the stack first (./start_nrp_docker.sh)"

# 1. authenticate --------------------------------------------------------------
TOK=$(curl -s -X POST "$BASE/proxy/authentication/authenticate" \
        -H 'Content-Type: application/json' \
        -d "{\"user\":\"$USER_NAME\",\"password\":\"$USER_PASS\"}" | tr -d '"[:space:]')
[ -n "$TOK" ] || fail "authentication returned no token"
AUTH="Authorization: Bearer $TOK"
log "authenticated as $USER_NAME"

# 2. clone the husky template into FS storage ----------------------------------
EXP=$(curl -s -X POST "$BASE/proxy/storage/clone" -H "$AUTH" \
        -H 'Content-Type: application/json' -d "{\"expPath\":\"$TEMPLATE\"}")
case "$EXP" in
  husky_braitenberg_*) ;;
  *) fail "clone of '$TEMPLATE' did not return an experiment id (got: ${EXP:0:200})" ;;
esac
log "cloned template -> storage experiment '$EXP'"

SIM=""
MQTT_PID=""
MQTT_LOG=$(mktemp)
cleanup() {
  [ -n "$MQTT_PID" ] && kill "$MQTT_PID" 2>/dev/null
  [ -n "$SIM" ] && curl -s -X PUT "$BASE/nrp-services/simulation/$SIM/state" \
      -H "$AUTH" -H 'Content-Type: application/json' -d '{"state":"stopped"}' >/dev/null 2>&1
  curl -s -X DELETE "$BASE/proxy/storage/$EXP" -H "$AUTH" >/dev/null 2>&1 \
      && log "cleaned up storage experiment '$EXP'"
  rm -f "$MQTT_LOG"
}
trap cleanup EXIT

# 3. capture MQTT (broker has no host port: subscribe on the stack network) ----
NET=$(docker inspect "$BACKEND_CTR" \
        -f '{{range $k,$v := .NetworkSettings.Networks}}{{$k}}{{end}}' 2>/dev/null)
[ -n "$NET" ] || fail "could not determine the stack docker network from container '$BACKEND_CTR'"
timeout $((START_TIMEOUT + 30)) docker run --rm --network "$NET" eclipse-mosquitto \
    mosquitto_sub -h mqtt-broker-service -p 1883 -t 'nrp_simulation/#' -v > "$MQTT_LOG" 2>&1 &
MQTT_PID=$!

# 4. create + start the simulation through nrp-backend -------------------------
CREATE=$(curl -s -X POST "$BASE/nrp-services/simulation" -H "$AUTH" \
        -H 'Content-Type: application/json' \
        -d "{\"experimentID\":\"$EXP\",\"experimentConfiguration\":\"$CONFIG\",\"state\":\"created\"}")
SIM=$(printf '%s' "$CREATE" | json_get simulationID)
[ -n "$SIM" ] || fail "create simulation failed: ${CREATE:0:300}"
log "created simulation id=$SIM"

sc=$(curl -s -o /dev/null -w '%{http_code}' -X PUT "$BASE/nrp-services/simulation/$SIM/state" \
        -H "$AUTH" -H 'Content-Type: application/json' -d '{"state":"started"}')
[ "$sc" = "200" ] || fail "PUT state=started returned HTTP $sc"

# 5. poll for 'started' --------------------------------------------------------
state=""
deadline=$((SECONDS + START_TIMEOUT))
while [ "$SECONDS" -lt "$deadline" ]; do
  state=$(curl -s "$BASE/nrp-services/simulation/$SIM" -H "$AUTH" | json_get state)
  case "$state" in
    started|paused) break ;;
    failed|halted)  fail "simulation entered terminal error state '$state'" ;;
  esac
  sleep 2
done
[ "$state" = "started" ] || [ "$state" = "paused" ] || \
  fail "simulation did not reach 'started' within ${START_TIMEOUT}s (last state: '$state')"
log "simulation reached '$state'"

sleep 6   # let it step so status events accrue

# 6. assert MQTT signals -------------------------------------------------------
kill "$MQTT_PID" 2>/dev/null; MQTT_PID=""
grep -q "nrp_simulation/$SIM/status" "$MQTT_LOG" \
  || fail "no MQTT status events on nrp_simulation/$SIM/status"
if grep -q "nrp_simulation/$SIM/runtime_error" "$MQTT_LOG"; then
  fail "simulation published a runtime_error: $(grep "nrp_simulation/$SIM/runtime_error" "$MQTT_LOG" | head -1)"
fi
log "MQTT status events present; no runtime_error"

log "PASS — husky launched and ran through nrp-backend (experiment=$EXP, sim=$SIM, state=$state)"
exit 0
