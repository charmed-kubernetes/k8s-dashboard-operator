import pytest

from ops.model import ActiveStatus, BlockedStatus, WaitingStatus
from ops.testing import Harness
import yaml

from charm import K8sDashboardCharm


if yaml.__with_libyaml__:
    _DefaultDumper = yaml.CSafeDumper
else:
    _DefaultDumper = yaml.SafeDumper


@pytest.fixture
def harness():
    return Harness(K8sDashboardCharm)


def test_not_leader(harness):
    harness.begin()
    assert isinstance(harness.charm.model.unit.status, WaitingStatus)


def test_missing_image(harness):
    harness.set_leader(True)
    harness.begin_with_initial_hooks()
    assert isinstance(harness.charm.model.unit.status, BlockedStatus)


def test_main_no_relation(harness):
    harness.set_leader(True)
    harness.add_oci_resource(
        "k8s-dashboard-image",
        {
            "registrypath": "kubernetesui/dashboard:v2.0.4",
            "username": "",
            "password": "",
        },
    )
    harness.begin_with_initial_hooks()
    assert isinstance(harness.charm.model.unit.status, ActiveStatus)
    pod_spec = harness.get_pod_spec()

    # confirm that we can serialize the pod spec
    yaml.dump(pod_spec, Dumper=_DefaultDumper)

    assert "--metrics-provider=none" in pod_spec[0]["containers"][0]["args"]


def test_main_with_relation(harness):
    harness.set_leader(True)
    harness.add_oci_resource(
        "k8s-dashboard-image",
        {
            "registrypath": "kubernetesui/dashboard:v2.0.4",
            "username": "",
            "password": "",
        },
    )
    rel_id = harness.add_relation("metrics-scraper", "dashboard-metrics-scraper")
    harness.begin_with_initial_hooks()
    assert isinstance(harness.charm.model.unit.status, WaitingStatus)
    harness.add_relation_unit(rel_id, "dashboard-metrics-scraper/0")
    harness.update_relation_data(
        rel_id,
        "dashboard-metrics-scraper",
        {"service-name": "dashboard-metrics-scraper", "service-port": "8000"},
    )
    assert isinstance(harness.charm.model.unit.status, ActiveStatus)

    pod_spec = harness.get_pod_spec()
    yaml.dump(pod_spec, Dumper=_DefaultDumper)
    metrics_provider = "--metrics-provider=sidecar"
    sidecar_host = "--sidecar-host=http://dashboard-metrics-scraper:8000"
    assert metrics_provider in pod_spec[0]["containers"][0]["args"]
    assert sidecar_host in pod_spec[0]["containers"][0]["args"]
