import subprocess
from pathlib import Path
from time import sleep

import pytest
import yaml
import base64
import requests


CHARM_DIR = Path(__file__).parent.parent.parent.resolve()
SPEC_FILE = Path(__file__).parent / 'validate-dns-spec.yaml'


def test_build_charm():
    print("Building Kubernetes Dashboard Charm")
    run('charmcraft', 'build', '-f', 'charms/kubernetes-dashboard')
    print("Building Dashboard Metrics Scraper Charm")
    run('charmcraft', 'build', '-f', 'charms/dashboard-metrics-scraper')

def test_deploy_charm():
    print("Adding Model")
    run('juju', 'add-model', 'kubernetes-dashboard', 'microk8s')
    print("Deploying Local Bundle")
    run('juju', 'deploy', './docs/local-overlay.yaml')
    print("Waiting For Deployment to Finish")
    run('juju', 'wait', '-wv')
    sleep(60)
    run('juju', 'wait', '-wv')

def test_charm():
    print("Testing Charms")
    metrics_scraper_ready = run(
        'microk8s.kubectl', 'get', 'pod', '-n', 'kubernetes-dashboard', '-l', 'juju-app=dashboard-metrics-scraper',
        '-o', 'jsonpath={..status.containerStatuses[0].ready}')
    assert metrics_scraper_ready == 'true'

    dashboard_ready = run(
        'microk8s.kubectl', 'get', 'pod', '-n', 'kubernetes-dashboard', '-l', 'juju-app=k8s-dashboard',
        '-o', 'jsonpath={..status.containerStatuses[0].ready}')
    assert dashboard_ready == 'true'

    raw_config_data = run(
        'microk8s.kubectl', 'config', 'view')
    config_data = yaml.safe_load(raw_config_data)
    url = config_data["clusters"][0]["cluster"]["server"]

    raw_secret_data = run(
        'microk8s.kubectl', 'get', 'secrets', '-n', 'kubernetes-dashboard',
        '-o', 'yaml', '--field-selector', 'type=kubernetes.io/service-account-token')

    secret_data = yaml.safe_load(raw_secret_data)

    for data in secret_data["items"]:
        if "k8s-dashboard-token" in data["metadata"]["name"]:
            token = base64.b64decode(data["data"]["token"]).decode("utf-8")
            break

    headers = {"Authorization": "Bearer {}".format(token)}

    dashboard_url = (
        "{}/api/v1/namespaces/kubernetes-dashboard/services/https:kubernetes-dashboard:/proxy/#/login"
    ).format(url)

    resp = requests.get(dashboard_url, headers=headers, verify=False)
    assert resp.status_code == 200 and "Dashboard" in resp.text


def run(*args):
    args = [str(a) for a in args]
    try:
        res = subprocess.run(args,
                             check=True,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
        return res.stdout.decode('utf8').strip()
    except subprocess.CalledProcessError as e:
        pytest.fail(f'Command {args} failed ({e.returncode}):\n'
                    f'stdout:\n{e.stdout.decode("utf8")}\n'
                    f'stderr:\n{e.stderr.decode("utf8")}\n')


def wait_for_output(*args, expected='', timeout=3 * 60):
    args = [str(a) for a in args]
    output = None
    for attempt in range(int(timeout / 5)):
        output = run(*args)
        if expected in output:
            break
        sleep(5)
    else:
        pytest.fail(f'Timed out waiting for "{expected}" from {args}:\n{output}')
