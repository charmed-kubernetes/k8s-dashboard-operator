#!/usr/bin/env python3

import logging

from ops.charm import CharmBase
from ops.main import main
from ops.model import ActiveStatus, MaintenanceStatus, WaitingStatus
from ops.framework import StoredState

from k8s_service import RequireK8sService
from oci_image import OCIImageResource, OCIImageResourceError
from urllib.parse import urlparse


class K8sDashboardCharm(CharmBase):
    state = StoredState()

    def __init__(self, *args):
        super().__init__(*args)
        if not self.unit.is_leader():
            # We can't do anything useful when not the leader, so do nothing.
            self.model.unit.status = WaitingStatus('Waiting for leadership')
            return
        self.log = logging.getLogger(__name__)
        self.dashboard_image = OCIImageResource(self, 'k8s-dashboard-image')
        self.metrics_scraper = RequireK8sService(self, "metrics-scraper")
        for event in [self.on.install,
                      self.on.leader_elected,
                      self.on.upgrade_charm,
                      self.on.config_changed,
                      self.metrics_scraper.on.k8s_services_changed]:
            self.framework.observe(event, self.main)

    def main(self, event):
        try:
            dashboard_image_details = self.dashboard_image.fetch()
        except OCIImageResourceError as e:
            self.model.unit.status = e.status
            return

        if not self.metrics_scraper.is_created:
            metrics_scraper_args = ["--metrics-provider=none"]
        else:
            if not self.metrics_scraper.is_available:
                self.model.unit.status = WaitingStatus("Waiting for Metrics Scraper")
                return
            ms_service_name, ms_service_port = self.metrics_scraper.services[0]
            metrics_scraper_args = ["--metrics-provider=sidecar",
                                    "--sidecar-host=http://{}:{}".format(
                                        ms_service_name,
                                        ms_service_port)]

        self.model.unit.status = MaintenanceStatus('Setting pod spec')
        ingress_resources = self._build_pod_ingress_resources()

        self.model.pod.set_spec({
            'version': 3,
            'service': {
                'updateStrategy': {
                    'type': 'RollingUpdate',
                    'rollingUpdate': {'maxUnavailable': 1},
                },
            },
            'configMaps': {
                'kubernetes-dashboard-settings': {},
            },
            'containers': [
                {
                    'name': "{}-charm".format(self.model.app.name),
                    'imageDetails': dashboard_image_details,
                    'imagePullPolicy': 'Always',
                    'ports': [
                        {
                            'name': 'dashboard',
                            'containerPort': 8443,
                            'protocol': 'TCP',
                        },
                    ],
                    'args': [
                        '--auto-generate-certificates',
                        "--namespace={}".format(self.model.name),
                        "--authentication-mode={}".format(
                            self.model.config['authentication-mode']),
                    ] + metrics_scraper_args,
                    'volumeConfig': [
                        {
                            'name': 'kubernetes-dashboard-certs',
                            'mountPath': '/certs',
                            'secret': {
                                'name': 'kubernetes-dashboard-certs',
                            },
                        },
                        {
                            'name': 'tmp-volume',
                            'mountPath': '/tmp',
                            'emptyDir': {
                                'medium': 'Memory',
                            },
                        },
                    ],
                    'kubernetes': {
                        'securityContext': {
                            'allowPrivilegeEscalation': False,
                            'readOnlyRootFilesystem': True,
                            'runAsUser': 1001,
                            'runAsGroup': 2001,
                        },
                        'livenessProbe': {
                            'httpGet': {
                                'scheme': 'HTTPS',
                                'path': '/',
                                'port': 8443,
                            },
                            'initialDelaySeconds': 30,
                            'timeoutSeconds': 30,
                        },
                    },
                },
            ],
            'serviceAccount': {
                'roles': [
                    {
                        'rules': [
                            {
                                'apiGroups': [''],
                                'resources': ['secrets'],
                                'resourceNames': [
                                    'kubernetes-dashboard-key-holder',
                                    'kubernetes-dashboard-certs',
                                    'kubernetes-dashboard-csrf',
                                ],
                                'verbs': ['get', 'update', 'delete'],
                            },
                            {
                                'apiGroups': [''],
                                'resources': ['configmaps'],
                                'resourceNames': [
                                    'kubernetes-dashboard-settings'],
                                'verbs': ['get', 'update'],
                            },
                            {
                                'apiGroups': [''],
                                'resources': ['services'],
                                'resourceNames': [
                                    'heapster',
                                    'dashboard-metrics-scraper',
                                ],
                                'verbs': ['proxy'],
                            },
                            {
                                'apiGroups': [''],
                                'resources': ['services/proxy'],
                                'resourceNames': [
                                    'heapster',
                                    'http:heapster',
                                    'https:heapster',
                                    'dashboard-metrics-scraper',
                                    'http:dashboard-metrics-scraper',
                                ],
                                'verbs': ['get'],
                            },
                            {
                                'apiGroups': ['metrics.k8s.io'],
                                'resources': ['pods', 'nodes'],
                                'verbs': ['get', 'list', 'watch'],
                            },
                        ],
                    },
                    {
                        'global': True,
                        'rules': [
                            {
                                'apiGroups': ['metrics.k8s.io'],
                                'resources': ['pods', 'nodes'],
                                'verbs': ['get', 'list', 'watch'],
                            },
                        ],
                    },
                ],
            },
            'kubernetesResources': {
                'secrets': [
                    {
                        'name': 'kubernetes-dashboard-certs',
                        'type': 'Opaque',
                    },
                    {
                        'name': 'kubernetes-dashboard-csrf',
                        'type': 'Opaque',
                        'data': {'csrf': ''},
                    },
                    {
                        'name':  'kubernetes-dashboard-key-holder',
                        'type': 'Opaque',
                    },
                ],
                'services': [{
                    'name': 'kubernetes-dashboard',
                    'spec': {
                        'selector': {
                            'juju-app': self.model.app.name,
                        },
                        'ports': [{
                            'protocol': 'TCP',
                            'port': 443,
                            'targetPort': 8443,
                        }],
                    },
                }],
                'ingressResources': ingress_resources or [],
            },
        })

        self.model.unit.status = ActiveStatus()

    def _build_pod_ingress_resources(self):
        """Generate pod ingress resources.

        Returns:
            List[Dict[str, Any]]: pod ingress resources.
        """

        site_url = self.model.config['site-url']
        if not site_url:
            return

        parsed = urlparse(site_url)

        if not parsed.scheme.startswith('http'):
            return

        annotations = {
            'nginx.ingress.kubernetes.io/proxy-body-size': '{}m'.format(
                self.model.config['max-file-size'])
            }
        ingress = {
            "name": "{}-ingress".format(self.app.name),
            "spec": {
                "rules": [
                    {
                        "host": parsed.hostname,
                        "http": {
                            "paths": [{
                                "path": "/",
                                "backend": {
                                    "serviceName": self.app.name,
                                    "servicePort": 8443
                                }
                            }],
                        },
                    },
                ],
            },
        }
        if parsed.scheme == 'https':
            ingress['spec']['tls'] = [{'hosts': [parsed.hostname]}]
            tls_secret_name = self.model.config['tls-secret-name']
            if tls_secret_name:
                ingress['spec']['tls'][0]['secretName'] = tls_secret_name
        else:
            annotations['nginx.ingress.kubernetes.io/ssl-redirect'] = 'false'

        whitelist_source_range = self.model.config['ingress-whitelist-source-range']
        if whitelist_source_range:
            whitelist_annotation = 'nginx.ingress.kubernetes.io/whitelist-source-range'
            annotations[whitelist_annotation] = whitelist_source_range

        if annotations:
            ingress['annotations'] = annotations

        return [ingress]


if __name__ == "__main__":
    main(K8sDashboardCharm)
