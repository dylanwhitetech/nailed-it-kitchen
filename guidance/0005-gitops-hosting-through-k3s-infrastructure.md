# 0005: GitOps hosting through k3s-infrastructure and Cloudflare Tunnel

## Status
Accepted

## Context
The app is intended to be served at `https://naileditkitchen.dylanlabs.dev` from a home cluster
without opening home ports, and every cluster change must be reviewable. The app is not live yet.

## Decision
Package the app as a Helm chart in `deploy/chart/`, released as an OCI chart on GHCR. Promote releases by PR to `dylanwhitetech/k3s-infrastructure`, where Flux deploys them. Traffic flows Cloudflare Tunnel to ingress-nginx; TLS ends at Cloudflare. Releases use release-please and SHA-tagged images ([0018](0018-release-please-and-trusted-promotion.md)). Agents never mutate the cluster directly.

## Consequences
- Cluster state lives in Git and every change is a reviewed PR.
- Each release needs a promotion PR in another repo; the trusted release workflow opens it and a
  human merges it.
- Manual cluster fixes must be codified in k3s-infrastructure.

## References
- [README "Decisions & why"](../README.md#decisions--why)
- [k3s-infrastructure guidance 0001](https://github.com/dylanwhitetech/k3s-infrastructure/blob/main/guidance/0001-publish-apps-through-cloudflare-tunnel.md)
