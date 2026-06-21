#!/bin/bash
#
# [EBR2-96] Build and run the containerized-stack acceptance suite.
#
# Runs the pytest UI (Playwright) + CLI/REST suites against a *running* stack.
# The suite container shares haproxy's network namespace, so the frontend's
# build-time-baked http://localhost:9000 proxy URL resolves to the proxy with
# no host port published — this works identically on a dev box (even with
# something else on host :9000, e.g. MinIO) and in CI.
#
# Prerequisite: the stack is up and healthy (./start_nrp_docker.sh).
#
# Usage:
#   ./tests/run_acceptance.sh                 # both suites
#   ./tests/run_acceptance.sh -m cli          # only the REST suite
#   ./tests/run_acceptance.sh -m ui           # only the UI suite
#   ./tests/run_acceptance.sh -k time_advances # any pytest args pass through
#
# Env overrides: ACCEPTANCE_IMAGE, NRP_HAPROXY_CONTAINER, RESULTS_DIR,
#                NRP_BASE_URL, NRP_MQTT_HOST, START_TIMEOUT.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SUITE_DIR="$SCRIPT_DIR/acceptance"
IMAGE="${ACCEPTANCE_IMAGE:-nrp-acceptance:local}"
HAPROXY_CTR="${NRP_HAPROXY_CONTAINER:-nrp-haproxy}"
RESULTS_DIR="${RESULTS_DIR:-$SCRIPT_DIR/acceptance-results}"

if ! docker inspect "$HAPROXY_CTR" >/dev/null 2>&1; then
  echo "ERROR: container '$HAPROXY_CTR' not found — start the stack first:" >&2
  echo "       ./start_nrp_docker.sh --wait" >&2
  exit 2
fi

echo ">> building acceptance image: $IMAGE"
docker build -t "$IMAGE" "$SUITE_DIR"

mkdir -p "$RESULTS_DIR"
echo ">> running acceptance suite (sharing '$HAPROXY_CTR' network namespace)"
exec docker run --rm \
  --network "container:$HAPROXY_CTR" \
  -v "$RESULTS_DIR:/suite/results" \
  -e NRP_BASE_URL="${NRP_BASE_URL:-http://localhost:9000}" \
  -e NRP_MQTT_HOST="${NRP_MQTT_HOST:-mqtt-broker-service}" \
  -e START_TIMEOUT="${START_TIMEOUT:-120}" \
  "$IMAGE" \
  -v --junitxml=/suite/results/junit.xml \
  --tracing=retain-on-failure --output=/suite/results/artifacts \
  "$@"
