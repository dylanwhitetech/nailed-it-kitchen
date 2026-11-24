# 0001: Application stack

## Status
Accepted

## Context
The two-person team needs a mainstream, well-documented stack that runs on a 3-node Raspberry Pi 4 (arm64) k3s cluster and is easy for Copilot and humans to work in.

## Decision
Use React + Vite + TypeScript (npm, Oxlint, Vitest) served by `nginx-unprivileged` for the frontend, and FastAPI on Python 3.12 (Ruff, pytest, SQLAlchemy + Alembic) for the backend. Build multi-arch (amd64/arm64) images on GHCR; use Docker Desktop + `docker compose` locally; k3s runs the images with containerd.

## Consequences
- Common tools make help, components, and agent output easy to find and review.
- The same images run on laptops, in CI, and on the Pis.
- Adding or replacing a framework, service, or tool needs an issue and a superseding record.

## References
- [README "Decisions & why"](../README.md#decisions--why)
- [AGENTS.md](../AGENTS.md)
