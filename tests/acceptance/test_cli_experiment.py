# [EBR2-96] CLI/REST acceptance suite.
#
# Drives the live stack over the same REST surface the frontend uses, launches a
# real husky_braitenberg simulation through nrp-backend (which forks nrp-core ->
# Gazebo + NEST), and checks the *result*: the simulation reaches 'started', its
# simulation clock actually advances, MQTT status events flow, and no
# runtime_error is published. This is the structured, deeply-asserting successor
# to husky_gate.sh.
import time

import pytest

pytestmark = pytest.mark.cli


def test_proxy_health(proxy_up):
    """The stack is up and the proxy answers /health."""


def test_authenticate(auth_token):
    """FS authentication yields a usable bearer token."""
    assert auth_token


def test_clone_creates_experiment(husky_experiment):
    """Cloning the template produces a husky_braitenberg_* storage experiment."""
    assert husky_experiment.startswith("husky_braitenberg")


def test_simulation_reaches_started(started_simulation):
    """create -> start drives the simulation to 'started' (or 'paused')."""
    assert started_simulation["state"] in ("started", "paused")


def test_simulation_time_advances(started_simulation, mqtt):
    """The experiment actually runs: the simulation clock moves off zero.

    Reads the per-second status payloads ({simulationTime: ..}) and waits for
    the clock to advance. This is the assertion husky_gate.sh never made — it
    proves nrp-core is stepping Gazebo + NEST, not merely that the REST state
    flipped to 'started'.
    """
    if not mqtt.available:
        pytest.skip(f"MQTT broker not reachable ({mqtt.reason})")

    sim_id = started_simulation["sim_id"]
    times, deadline = [], time.time() + 30
    while time.time() < deadline:
        times = [m["simulationTime"] for m in mqtt.status_messages(sim_id)
                 if "simulationTime" in m]
        if times and max(times) > 0.0:
            break
        time.sleep(2)

    assert times, f"no status messages carrying simulationTime on nrp_simulation/{sim_id}/status"
    assert max(times) > 0.0, f"simulation clock never advanced past 0 (saw {sorted(set(times))[:5]})"


def test_mqtt_status_events(started_simulation, mqtt):
    """Status events are published on the simulation's status topic."""
    if not mqtt.available:
        pytest.skip(f"MQTT broker not reachable ({mqtt.reason})")
    sim_id = started_simulation["sim_id"]
    assert mqtt.status_messages(sim_id), \
        f"no MQTT status events on nrp_simulation/{sim_id}/status"


def test_no_runtime_error(started_simulation, mqtt):
    """The simulation does not publish a runtime_error while running."""
    if not mqtt.available:
        pytest.skip(f"MQTT broker not reachable ({mqtt.reason})")
    sim_id = started_simulation["sim_id"]
    errors = mqtt.runtime_errors(sim_id)
    assert not errors, f"simulation published a runtime_error: {errors[:1]}"


def test_stop_transitions(started_simulation, nrp):
    """The simulation can be stopped through the REST API."""
    resp = nrp.set_state(started_simulation["sim_id"], "stopped")
    assert resp.status_code in (200, 204), f"PUT state=stopped -> {resp.status_code}: {resp.text[:200]}"
