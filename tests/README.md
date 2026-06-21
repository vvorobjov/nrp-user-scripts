# NRP stack acceptance tests

Automated end-to-end tests that run a real `husky_braitenberg` simulation
against the **live containerized stack** and check that it actually runs — not
just that it launches. Two complementary suites, both in `acceptance/` and run
by the same pytest runner:

| Suite | File | What it proves |
| --- | --- | --- |
| CLI / REST | `acceptance/test_cli_experiment.py` | Drives the proxy + nrp-services REST API the way the frontend does: authenticate → clone → create → start → assert the simulation reaches `started`, the **simulation clock advances**, MQTT status events flow, and no `runtime_error` is published → stop. |
| UI (Playwright) | `acceptance/test_ui_experiment.py` | Drives the real frontend in a headless browser: FS login → open the Experiments overview → Open a husky experiment → **Initialize + Start** in the workbench → assert no error status and the on-screen simulation clock advances. |

`husky_gate.sh` remains as a fast bash smoke check; these pytest suites are the
thorough gate (the CLI suite is its structured, deeper-asserting successor).

## How it runs

The suite runs in a container (`acceptance/Dockerfile`, official Playwright
image) that **shares haproxy's network namespace**:

```
docker run --rm --network container:nrp-haproxy nrp-acceptance
```

Sharing the namespace means `localhost:9000` inside the container *is* the
proxy, so the frontend's build-time-baked `localhost:9000` proxy/MQTT URLs
resolve with **no host port published** — it works identically on a dev box
(even with something else on host `:9000`, e.g. MinIO) and in CI.

## Running locally

```bash
cd nrp-user-scripts
./start_nrp_docker.sh --wait        # bring the variant stack up (backend :nest-gazebo)
./tests/run_acceptance.sh           # build the suite image + run both suites
#   ./tests/run_acceptance.sh -m cli      # only the REST suite
#   ./tests/run_acceptance.sh -m ui       # only the UI suite
#   ./tests/run_acceptance.sh -k advances # any pytest args pass through
docker compose down
```

JUnit XML and Playwright traces land in `tests/acceptance-results/`.

## In CI

`.github/workflows/acceptance.yml` (GitHub Actions on the mirror) brings the
published stack up and runs both suites on every push to `development`/`master`
and on PRs, uploading the JUnit + trace artifacts.

> The deep "simulation clock advances" assertions require the **EBR2-97** fix
> (start-vs-simserver-subscription race) to be present in the published
> `nrp-backend` image. Without it, a sim launched via create-then-immediate-start
> freezes at t=0 and these assertions fail by design.

## Configuration (env overrides)

`NRP_BASE_URL` (default `http://localhost:9000`), `NRP_FS_USER`/`NRP_FS_PASSWORD`
(`nrpuser`/`password`), `NRP_MQTT_HOST` (`mqtt-broker-service`), `START_TIMEOUT`,
`HUSKY_TEMPLATE`, `HUSKY_CONFIG`. Runner knobs for `run_acceptance.sh`:
`ACCEPTANCE_IMAGE`, `NRP_HAPROXY_CONTAINER`, `RESULTS_DIR`.
