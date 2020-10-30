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
    harness.add_oci_resource('metrics-scraper-image', {
        'registrypath': 'kubernetesui/metrics-scraper:v1.0.5',
        'username': '',
        'password': '',
    })
    harness.begin_with_initial_hooks()
    assert isinstance(harness.charm.model.unit.status, ActiveStatus)
    # confirm that we can serialize the pod spec
    yaml.dump(harness.get_pod_spec(), Dumper=_DefaultDumper)
