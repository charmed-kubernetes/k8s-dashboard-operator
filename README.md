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
