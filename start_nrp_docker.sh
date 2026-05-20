#!/bin/bash
#
# Boot the local NRP containerized stack.
#
# Usage:
#   ./start_nrp_docker.sh                   # detach + wait for healthchecks
#   ./start_nrp_docker.sh --foreground      # legacy foreground behaviour
#                                           # (--abort-on-container-exit)
#   ./start_nrp_docker.sh -- <extra args>   # pass-through to docker compose
#
# Required env:
#   HBP                  — path to the parent dir holding nrp-user-scripts
# Optional env:
#   STORAGE_PATH         — default $HOME/.opt/nrpStorage
#   NRP_IMAGE_TAG        — default :latest
#   NRP_DOCKER_REGISTRY  — default docker.io/hbpneurorobotics/
#                          (compose `image:` paths are flattened, EBR2-56)
#   NRP_NEST_DESKTOP     — set to ON to use docker-compose-nest-desktop.yaml

set -euo pipefail

export NRP_IMAGE_TAG="${NRP_IMAGE_TAG:-:latest}"
export NRP_DOCKER_REGISTRY="${NRP_DOCKER_REGISTRY:-docker.io/hbpneurorobotics/}"

if [ -z "${HBP:-}" ]; then
  echo "Your HBP variable is not set!" >&2
  echo "Please set it up: export HBP=<path with nrp-user-scripts repository folder>" >&2
  exit 1
fi

if [ -z "${STORAGE_PATH:-}" ]; then
    export STORAGE_PATH="$HOME/.opt/nrpStorage"
    echo "STORAGE_PATH is set to default $STORAGE_PATH"
fi

# ----------------------------------------------------------------------------
# TingoDB FS-storage bootstrap.
# Pre-fix: a Ctrl-C during the createFSUser run (or a non-zero exit from
# `docker compose down`) could leave $STORAGE_PATH/FS_db/ partially written
# but with the `users` file missing. The original guard
#
#   if [ ! -d "$STORAGE_PATH/FS_db" ] || [ ! -f "$STORAGE_PATH/FS_db/users" ];
#
# would still trigger on the next run, but the in-flight container could
# write into a half-initialised directory and fail in confusing ways. Now:
# trap interruption, roll the directory back, and surface a clear retry.
# ----------------------------------------------------------------------------
storage_bootstrap_needed() {
  [ ! -d "$STORAGE_PATH/FS_db" ] || [ ! -f "$STORAGE_PATH/FS_db/users" ]
}

if storage_bootstrap_needed; then
  mkdir -p "$STORAGE_PATH" || { echo "ERROR, couldn't create $STORAGE_PATH" >&2; exit 1; }

  bootstrap_started_at=$(date +%s)
  bootstrap_rollback() {
    if storage_bootstrap_needed; then
      echo "Bootstrap interrupted — rolling back partial $STORAGE_PATH/FS_db/" >&2
      rm -rf "$STORAGE_PATH/FS_db" 2>/dev/null || true
    fi
  }
  trap 'bootstrap_rollback; exit 130' INT TERM
  trap 'bootstrap_rollback' EXIT

  echo "Bootstrapping FS storage at $STORAGE_PATH (creating user 'nrpuser')..."
  if ! docker compose run --rm nrp-proxy-service \
        node_modules/ts-node/dist/bin.js utils/createFSUser.ts \
        --user nrpuser --password password; then
    echo "createFSUser failed; rolling back." >&2
    bootstrap_rollback
    trap - INT TERM EXIT
    exit 1
  fi
  docker compose down

  trap - INT TERM EXIT

  if storage_bootstrap_needed; then
    echo "ERROR: FS storage bootstrap completed without writing FS_db/users." >&2
    echo "  $STORAGE_PATH/FS_db is in an inconsistent state — remove it and retry." >&2
    exit 1
  fi
  echo "FS storage ready (took $(( $(date +%s) - bootstrap_started_at ))s)."
fi

# ----------------------------------------------------------------------------
# Compose-file selection and stack boot.
# ----------------------------------------------------------------------------
DOCKER_COMPOSE_FILE="docker-compose.yaml"
if [ "${NRP_NEST_DESKTOP:-OFF}" = "ON" ]; then
  DOCKER_COMPOSE_FILE="docker-compose-nest-desktop.yaml"
fi

# Argument parsing: --foreground keeps the legacy
# `up --abort-on-container-exit` behaviour. Default is `up --wait` so the
# script returns once HEALTHCHECKs pass (relies on EBR2-37 healthchecks).
mode="wait"
extra_args=()
for a in "$@"; do
  case "$a" in
    --foreground|-f)
      mode="foreground"
      ;;
    --)
      ;;
    *)
      extra_args+=("$a")
      ;;
  esac
done

if [ "$mode" = "foreground" ]; then
  exec docker compose -f "$DOCKER_COMPOSE_FILE" up --abort-on-container-exit "${extra_args[@]}"
else
  docker compose -f "$DOCKER_COMPOSE_FILE" up -d --wait "${extra_args[@]}"
  echo
  echo "Stack is up. Follow logs with:"
  echo "  docker compose -f $DOCKER_COMPOSE_FILE logs -f"
  echo "Bring it down with:"
  echo "  docker compose -f $DOCKER_COMPOSE_FILE down"
fi
