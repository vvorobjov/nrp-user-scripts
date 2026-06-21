# [EBR2-96] Shared fixtures for the containerized-stack acceptance suite.
#
# Both the CLI/REST suite (test_cli_experiment.py) and the UI suite
# (test_ui_experiment.py) run an actual husky_braitenberg simulation through the
# live stack and check the result. These fixtures own the expensive bits — FS
# authentication, cloning the template into storage, launching the simulation,
# and collecting MQTT status events — so the individual test functions stay
# small and each assert one property.
#
# Everything is overridable by env so the same suite runs three ways unchanged:
#   * on the host against http://localhost:9000 (stack on :9000),
#   * in a container sharing haproxy's netns (the default; localhost:9000 == the
#     proxy, so the frontend's build-time-baked proxy URL resolves with no host
#     port and no MinIO :9000 clash),
#   * in CI on the GitHub mirror.
import json
import os
import threading
import time

import pytest
import requests

BASE_URL = os.environ.get("NRP_BASE_URL", "http://localhost:9000")
FS_USER = os.environ.get("NRP_FS_USER", "nrpuser")
FS_PASSWORD = os.environ.get("NRP_FS_PASSWORD", "password")
MQTT_HOST = os.environ.get("NRP_MQTT_HOST", "mqtt-broker-service")
MQTT_PORT = int(os.environ.get("NRP_MQTT_PORT", "1883"))
HUSKY_TEMPLATE = os.environ.get("HUSKY_TEMPLATE", "husky_braitenberg/simulation_config.json")
HUSKY_CONFIG = os.environ.get("HUSKY_CONFIG", "simulation_config.json")
START_TIMEOUT = int(os.environ.get("START_TIMEOUT", "120"))


# --------------------------------------------------------------------------- #
# REST client                                                                 #
# --------------------------------------------------------------------------- #
class NRPClient:
    """Thin wrapper over the proxy + nrp-services REST surface used by the UI."""

    def __init__(self, base_url, session, auth_headers):
        self.base_url = base_url
        self.s = session
        self.auth = auth_headers

    def clone(self, template=HUSKY_TEMPLATE):
        r = self.s.post(f"{self.base_url}/proxy/storage/clone", headers=self.auth,
                        data=json.dumps({"expPath": template}), timeout=120)
        r.raise_for_status()
        return r.text.strip().strip('"')

    def delete_experiment(self, exp_id):
        return self.s.delete(f"{self.base_url}/proxy/storage/{exp_id}",
                             headers=self.auth, timeout=30)

    def create_sim(self, exp_id, config=HUSKY_CONFIG):
        r = self.s.post(f"{self.base_url}/nrp-services/simulation", headers=self.auth,
                        data=json.dumps({"experimentID": exp_id,
                                         "experimentConfiguration": config,
                                         "state": "created"}), timeout=180)
        r.raise_for_status()
        return r.json()["simulationID"]

    def set_state(self, sim_id, state):
        return self.s.put(f"{self.base_url}/nrp-services/simulation/{sim_id}/state",
                          headers=self.auth, data=json.dumps({"state": state}), timeout=180)

    def get_state(self, sim_id):
        r = self.s.get(f"{self.base_url}/nrp-services/simulation/{sim_id}",
                       headers=self.auth, timeout=30)
        return r.json().get("state") if r.status_code == 200 else None

    def list_simulations(self):
        r = self.s.get(f"{self.base_url}/nrp-services/simulation", headers=self.auth, timeout=30)
        return r.json() if r.status_code == 200 else []

    def stop_all_running(self):
        """Stop every non-terminal simulation (used to clean up after the UI test)."""
        for entry in self.list_simulations():
            if entry.get("state") not in ("stopped", "failed"):
                self.set_state(entry["simulationID"], "stopped")


# --------------------------------------------------------------------------- #
# MQTT collector                                                              #
# --------------------------------------------------------------------------- #
class MQTTCollector:
    """Background subscriber to ``nrp_simulation/#`` that records every message.

    The simserver publishes a status payload every second:
        {"realTime": .., "simulationTime": .., "state": .., "simulationTimeLeft": ..}
    and any fault on ``.../runtime_error``. Tests query this collector instead of
    shelling out to ``mosquitto_sub`` like the legacy husky_gate.sh did.
    """

    def __init__(self):
        self._messages = []          # list[(topic, payload_str)]
        self._lock = threading.Lock()
        self._client = None
        self.available = False
        self.reason = ""

    def start(self):
        try:
            import paho.mqtt.client as mqtt
            try:                      # paho-mqtt 2.x
                client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
            except (AttributeError, TypeError):   # paho-mqtt 1.x
                client = mqtt.Client()
            client.on_message = self._on_message
            client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
            client.subscribe("nrp_simulation/#")
            client.loop_start()
            self._client = client
            self.available = True
        except Exception as exc:       # broker unreachable -> tests skip, not fail
            self.available = False
            self.reason = f"{MQTT_HOST}:{MQTT_PORT} -> {exc}"

    def _on_message(self, *args):
        msg = args[-1]
        with self._lock:
            self._messages.append((msg.topic, msg.payload.decode("utf-8", "replace")))

    def stop(self):
        if self._client:
            self._client.loop_stop()
            self._client.disconnect()

    def topics(self):
        with self._lock:
            return [t for t, _ in self._messages]

    def status_messages(self, sim_id):
        suffix = f"/{sim_id}/status"
        out = []
        with self._lock:
            for topic, payload in self._messages:
                if topic.endswith(suffix):
                    try:
                        out.append(json.loads(payload))
                    except ValueError:
                        pass
        return out

    def runtime_errors(self, sim_id):
        suffix = f"/{sim_id}/runtime_error"
        with self._lock:
            return [p for t, p in self._messages if t.endswith(suffix)]


# --------------------------------------------------------------------------- #
# Fixtures                                                                     #
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="session")
def base_url():
    return BASE_URL


@pytest.fixture(scope="session")
def http():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    yield s
    s.close()


@pytest.fixture(scope="session")
def proxy_up(http, base_url):
    """Fail fast with a clear message if the stack is not running."""
    try:
        code = http.get(f"{base_url}/proxy/health", timeout=15).status_code
    except requests.RequestException as exc:
        pytest.fail(f"proxy not reachable at {base_url} ({exc}) — start the stack first")
    assert code == 200, f"proxy /health -> HTTP {code} at {base_url} — start the stack first"


@pytest.fixture(scope="session")
def auth_token(http, base_url, proxy_up):
    r = http.post(f"{base_url}/proxy/authentication/authenticate",
                  data=json.dumps({"user": FS_USER, "password": FS_PASSWORD}), timeout=30)
    assert r.status_code == 200, f"authenticate -> HTTP {r.status_code}: {r.text[:200]}"
    token = r.text.strip().strip('"')
    assert token and token not in ("no-token", "malformed-token"), "no usable auth token"
    return token


@pytest.fixture(scope="session")
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="session")
def nrp(base_url, http, auth_headers):
    return NRPClient(base_url, http, auth_headers)


@pytest.fixture(scope="session")
def mqtt():
    collector = MQTTCollector()
    collector.start()
    yield collector
    collector.stop()


@pytest.fixture(scope="module")
def husky_experiment(nrp):
    """Clone the husky_braitenberg template into FS storage; delete on teardown."""
    exp_id = nrp.clone()
    assert exp_id.startswith("husky_braitenberg"), f"unexpected clone result: {exp_id[:120]}"
    yield exp_id
    nrp.delete_experiment(exp_id)


@pytest.fixture(scope="module")
def started_simulation(nrp, husky_experiment, mqtt):
    """Create + start a husky simulation via REST, poll until 'started'.

    Module-scoped so the heavy nrp-core/Gazebo/NEST launch happens once; stopped
    on teardown so it does not collide with the UI suite's own launch.
    """
    sim_id = nrp.create_sim(husky_experiment)
    resp = nrp.set_state(sim_id, "started")
    assert resp.status_code == 200, f"PUT state=started -> {resp.status_code}: {resp.text[:200]}"

    state, deadline = None, time.time() + START_TIMEOUT
    while time.time() < deadline:
        state = nrp.get_state(sim_id)
        if state in ("started", "paused"):
            break
        if state in ("failed", "halted"):
            pytest.fail(f"simulation entered terminal error state '{state}'")
        time.sleep(2)
    assert state in ("started", "paused"), \
        f"simulation did not reach 'started' within {START_TIMEOUT}s (last state: {state})"

    info = {"sim_id": sim_id, "state": state, "experiment": husky_experiment}
    yield info
    nrp.set_state(sim_id, "stopped")
