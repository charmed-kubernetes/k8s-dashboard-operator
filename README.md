# Kubernetes Dashboard Operator

## How to build and deploy:

1. Pull the repository locally
3. `cd dashboard-operator`
4. build both charms:
`charmcraft build -f charms/kubernetes-dashboard`
`charmcraft build -f charms/dashboard-metrics-scraper`
5. deploy with the overlay: 
    `juju deploy ./docs/local-overlay.yaml`

## Testing

`kubectl proxy`

Open in your browser the following url:

<http://localhost:8001/api/v1/namespaces/kubernetes-dashboard/services/https:kubernetes-dashboard:/proxy/>

## Using ingress

The kubernetes dashboard charm comes with ingress support. To enable the follwoing config 
variable needs to be changed:

`juju config k8s-dashboard site-url=http://k8sdashboard.<application-ip>.xip.io`

If the `site-url` uses HTTPS (urls needs to start with `https://`) a secret with the tls
certificates needs to be created and the name of that secret provided:

```
juju config k8s-dashboard tls-secret=<tls-secret-name>
juju config k8s-dashboard site-url=https://k8sdashboard.<application-ip>.xip.io
```
