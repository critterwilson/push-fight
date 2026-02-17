# UDS Deployment Guide

Deploy the Push Fight RL training app using **UDS (Unicorn Delivery Service)** with Zarf for air-gap compatible packaging and UDS Core for a baseline security posture (Istio, Pepr, Keycloak).

Reference: [UDS Core Tutorial](https://uds.defenseunicorns.com/tutorials/deploy-with-uds-core/)

## Prerequisites

- **Docker**: For building the application image.
- **UDS CLI**: For bundling and deployment (includes Zarf). Install from [uds.defenseunicorns.com](https://uds.defenseunicorns.com/).
- **kubectl**: For interacting with the cluster.

## Step 1: Build the Application Image

```bash
docker build -t push-fight-app:latest .
```

This builds the container image targeting headless RL training (`app.rl.train`).

## Step 2: Create the Zarf Package

Package the app manifests and container image into a Zarf package:

```bash
zarf package create --confirm
```

This reads `zarf.yaml` and produces a `zarf-package-push-fight-app-*.tar.zst` archive containing the deployment manifests, network policies, and the `push-fight-app:latest` container image.

## Step 3: Create the UDS Bundle

Bundle the Zarf package with UDS Core (k3d cluster, Zarf init, Istio/Pepr/Keycloak):

```bash
uds create --confirm
```

This reads `uds-bundle.yaml` and produces a `uds-bundle-push-fight-bundle-*.tar.zst` archive that includes:
1. **uds-k3d** - Local k3d cluster creation
2. **Zarf init** - Zarf bootstrapping (in-cluster registry)
3. **UDS Core** - Istio service mesh, Pepr policy engine, Keycloak SSO
4. **push-fight-app** - The application Zarf package

## Step 4: Deploy

Deploy the full stack (cluster + core services + app):

```bash
uds deploy uds-bundle-push-fight-bundle-amd64-0.0.1.tar.zst --confirm
```

This will:
- Create a local k3d cluster
- Bootstrap Zarf with an in-cluster registry
- Deploy UDS Core (Istio, Pepr, Keycloak)
- Deploy the Push Fight app into the `push-fight` namespace with Istio sidecar injection

## Step 5: Verify Deployment

Check the app is running:

```bash
kubectl get pods -n push-fight
kubectl logs -n push-fight deploy/push-fight-app -f
```

You should see RL training output (timesteps, reward progress).

## Cleanup

Remove the entire UDS deployment and cluster:

```bash
k3d cluster delete uds
```

## File Reference

| File | Purpose |
|------|---------|
| `Dockerfile` | Builds the app image (targets RL training) |
| `deployment.yaml` | K8s namespace + deployment for the app |
| `network-policies.yaml` | Default-deny + DNS egress for the app |
| `zarf.yaml` | Zarf package definition (manifests + images) |
| `uds-bundle.yaml` | UDS bundle (k3d + init + core + app) |
