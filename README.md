# Dashboard Operator

## How to build and deploy:

1. Pull the repository locally
2. `cd dashboard-operator`
2. build both charms:
`charmcraft build -f charms/kubernetes-dashboard`
`charmcraft build -f charms/dashboard-metrics-scraper`
3. deploy with the overlay: 
    `juju deploy ./docs/local-overlay.yaml`

## Testing

`kubectl proxy`

Open in your browser the following url:

<localhost:8001/api/v1/namespaces/kubernetes-dashboard/services/https:kubernetes-dashboard:8443/proxy/>

In case you are deploying to a different namespaces than `kubernetes-dashboard`, you will  have to write that namespace after `v1/namespaces/`.

*TODO*: Set the default port of service to 443: [Discussion ongoing] (https://discourse.juju.is/t/different-pod-and-service-ports/3698).
