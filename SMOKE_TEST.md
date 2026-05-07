# SMOKE_TEST — local NRP stack end-to-end

This is the manual smoke procedure that proves the local containerized
Neurorobotics Platform stack works end-to-end. Run after a Phase 1
change lands (or any time the stack image set is bumped).

The test is intentionally manual and end-user-shaped: a person
launches it, a person watches the simulation start, a person reads
MQTT events. It's not meant to replace unit tests; it's meant to
catch the integration gaps that single-process tests miss
(entrypoint scripts, PYTHONPATH, gazebo plugins, MQTT proxy, nginx
↔ uWSGI wiring).

Issue: EBR2-40. Parent Epic: EBR2-33.

## Prerequisites

Host:
- Ubuntu 22.04+ (or any modern Linux with cgroups v2).
- Docker Engine 24+ and Docker Compose v2.
- ~10 GB free disk for image pulls and the `~/.opt/nrpStorage`
  bind-mount (configurable).
- A browser, and `mosquitto-clients` for the MQTT check
  (`apt-get install -y mosquitto-clients`).

Repo state:
- All NRP repositories cloned under one umbrella directory (the
  recommended path is `git clone --recurse-submodules
  git@github.com:vvorobjov/nrp-dev.git` and use that). Either
  `nrp-dev` umbrella or a flat checkout of the same submodules
  is fine — what matters is that `$HBP` points at the parent
  directory.
- Docker Hub baseline images published per EBR2-35 (`hbpneurorobotics/nrp-frontend`,
  `hbpneurorobotics/nrp-proxy`, `hbpneurorobotics/nrp-backend`,
  tag `revival-baseline` or whatever the current Phase 1 tag is).

## Procedure

### 1. Set environment

```bash
export HBP=/home/$(whoami)/git-tum            # or wherever your clones live
export STORAGE_PATH=$HOME/.opt/nrpStorage     # default; can be elsewhere
export NRP_DOCKER_REGISTRY=docker.io/         # Docker Hub
export NRP_IMAGE_TAG=:revival-baseline        # match the published tag
```

(`start_nrp_docker.sh` sets sensible defaults; setting them
explicitly here makes the test reproducible.)

### 2. Bring the stack up

```bash
cd "$HBP/nrp-user-scripts"
./start_nrp_docker.sh --wait
```

Expected: the script prints image pulls, then
- `mqtt-broker-service` starts.
- `nrp-backend-service` starts. After ~30–60 s it transitions to
  `healthy` (HEALTHCHECK on `/version` from EBR2-37).
- `nrp-proxy-service` starts and transitions to `healthy`.
- `haproxy-service` starts and transitions to `healthy`.
- `nrp-frontend-service` starts.

`docker compose ps` should show all services either `running (healthy)`
or `running` (mqtt and frontend don't yet have healthchecks).

### 3. Open the UI

Open `http://localhost:9000` in a browser. The frontend should load
the NRP entry page. Log in with the local FS user
(`nrpuser` / `password` is the bootstrapped default unless you
overrode it).

If the entry page does not load: `docker compose logs
nrp-frontend-service` and `docker compose logs haproxy-service`.

### 4. Start a sample experiment

From the experiments overview, pick a Husky / Braitenberg template
and launch it. Wait for the simulation viewport to render the world.

If the launch fails: `docker compose logs nrp-backend-service` —
look for nrp-core spawn errors, missing Models paths, or MQTT
connection refused.

### 5. Confirm MQTT events

In another terminal:

```bash
mosquitto_sub -h localhost -p 1883 -t 'nrp_simulation/#' -v
```

Expected: `nrp_simulation/status` events (`started`, `paused`, etc.)
appear in real time as the simulation steps. Errors show on
`nrp_simulation/runtime_error`.

### 6. Stop the simulation

Use the UI's stop button. The MQTT subscriber should print a
terminal `status` event. The backend container stays up.

### 7. Bring the stack down

```bash
cd "$HBP/nrp-user-scripts"
docker compose down
```

Expected: clean shutdown, no dangling containers.

## Pass criteria

All seven steps above pass with no manual intervention beyond
launching the experiment from the UI. If a step needs a workaround
(e.g. "kill the proxy container and restart"), that's a Phase 1
regression — open a follow-up EBR2 ticket and link it to EBR2-33.

## Recording the result

After running, paste a short result block into the EBR2-40 ticket
comment:

```
host: <distro + docker version>
images: <tag set used, e.g. revival-baseline @ 2026-MM-DD>
result: PASS / FAIL (which step)
notes: <links to follow-up tickets if any>
```

Once a known-good result is recorded once, the Story can close.
Subsequent regressions go into new tickets that reference EBR2-40.
