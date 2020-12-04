import pytest

from ops.model import ActiveStatus, BlockedStatus, WaitingStatus
from ops.testing import Harness
import yaml

from charm import DashboardMetricsScraperCharm


if yaml.__with_libyaml__:
    _DefaultDumper = yaml.CSafeDumper
else:
    _DefaultDumper = yaml.SafeDumper


@pytest.fixture
def harness():
    return Harness(DashboardMetricsScraperCharm)


def test_not_leader(harness):
    harness.begin()
    assert isinstance(harness.charm.model.unit.status, WaitingStatus)


def test_missing_image(harness):
    harness.set_leader(True)
    harness.begin_with_initial_hooks()
    assert isinstance(harness.charm.model.unit.status, BlockedStatus)


def test_main(harness):
    harness.set_leader(True)
    harness.add_oci_resource(
        "metrics-scraper-image",
        {
            "registrypath": "kubernetesui/metrics-scraper:v1.0.5",
            "username": "",
            "password": "",
        },
    )
    harness.begin_with_initial_hooks()
    assert isinstance(harness.charm.model.unit.status, ActiveStatus)
    # confirm that we can serialize the pod spec
    yaml.dump(harness.get_pod_spec(), Dumper=_DefaultDumper)


def test_main_with_relation(harness):
    harness.set_leader(True)
    harness.add_oci_resource(
        "metrics-scraper-image",
        {
            "registrypath": "kubernetesui/metrics-scraper:v1.0.5",
            "username": "",
            "password": "",
        },
    )
    rel_id = harness.add_relation("metrics-scraper", "dashboard-metrics-scraper")
    harness.begin_with_initial_hooks()
    assert isinstance(harness.charm.model.unit.status, ActiveStatus)

    rel_data = harness.get_relation_data(rel_id, "dashboard-metrics-scraper")
    assert rel_data["service-name"] == "dashboard-metrics-scraper"
    assert rel_data["service-port"] == "8000"

    # confirm that we can serialize the pod spec
    yaml.dump(harness.get_pod_spec(), Dumper=_DefaultDumper)
