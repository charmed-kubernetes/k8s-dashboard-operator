#!/usr/bin/env python3

import logging

from ops.charm import CharmBase
from ops.main import main
from ops.model import ActiveStatus, MaintenanceStatus, WaitingStatus

from oci_image import OCIImageResource, OCIImageResourceError


class K8sDashboardCharm(CharmBase):
    def __init__(self, *args):
        super().__init__(*args)
        if not self.unit.is_leader():
            # We can't do anything useful when not the leader, so do nothing.
            self.model.unit.status = WaitingStatus('Waiting for leadership')
            return
        self.log = logging.getLogger(__name__)
        self.dashboard_image = OCIImageResource(self, 'k8s-dashboard-image')
        for event in [self.on.install,
                      self.on.leader_elected,
                      self.on.upgrade_charm,
                      self.on.config_changed]:
            self.framework.observe(event, self.main)

    def main(self, event):
        try:
            dashboard_image_details = self.dashboard_image.fetch()
        except OCIImageResourceError as e:
            self.model.unit.status = e.status
            return

        self.model.unit.status = MaintenanceStatus('Setting pod spec')

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
                    'name': 'kubernetes-dashboard',
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
                        '--sidecar-host=http://dashboard-metrics-scraper:8000',
                        "--authentication-mode={}".format(
                            self.model.config['authentication-mode']),
                    ],
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
                            'juju-app': 'kubernetes-dashboard',
                        },
                        'ports': [{
                            'protocol': 'TCP',
                            'port': 443,
                            'targetPort': 8443,
                        }],
                    },
                }],
            },
        })

        self.model.unit.status = ActiveStatus()


if __name__ == "__main__":
    main(K8sDashboardCharm)
