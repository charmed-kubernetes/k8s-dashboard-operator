#!/usr/bin/env python3

import logging

from ops.charm import CharmBase
from ops.main import main
from ops.model import ActiveStatus, MaintenanceStatus, WaitingStatus

from oci_image import OCIImageResource, OCIImageResourceError
from k8s_service import ProvideK8sService


class DashboardMetricsScraperCharm(CharmBase):
    def __init__(self, *args):
        super().__init__(*args)
        if not self.unit.is_leader():
            # We can't do anything useful when not the leader, so do nothing.
            self.model.unit.status = WaitingStatus('Waiting for leadership')
            return

        ProvideK8sService(self,
                          'metrics-scraper',
                          service_name=self.app.name,
                          service_port=self.model.config["port"])

        self.log = logging.getLogger(__name__)
        self.scraper_image = OCIImageResource(self, 'metrics-scraper-image')
        for event in [self.on.install,
                      self.on.leader_elected,
                      self.on.upgrade_charm,
                      self.on.config_changed]:
            self.framework.observe(event, self.main)

    def main(self, event):
        try:
            scraper_image_details = self.scraper_image.fetch()
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
                'annotations': {
                    'seccomp.security.alpha.kubernetes.io/pod': 'runtime/default',
                },
            },
            'containers': [
                {
                    'name': self.model.app.name,
                    'imageDetails': scraper_image_details,
                    'ports': [
                        {
                            'name': 'scraper',
                            'containerPort': self.model.config["port"],
                            'protocol': 'TCP',
                        },
                    ],
                    'volumeConfig': [
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
                                'scheme': 'HTTP',
                                'path': '/',
                                'port': 8000,
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
        })

        self.model.unit.status = ActiveStatus()


if __name__ == "__main__":
    main(DashboardMetricsScraperCharm)
