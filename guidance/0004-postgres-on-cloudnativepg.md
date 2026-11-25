# 0004: PostgreSQL on CloudNativePG with local storage and nightly dumps

## Status
Accepted

## Context
The app needs relational data (recipes, ingredients, ratings) with full-text search, and running Postgres directly on NFS risks corruption.

## Decision
Run PostgreSQL through the CloudNativePG operator (one `Cluster` per app) on a `local-path` volume pinned to one node. Back up with a nightly `pg_dump` CronJob to an `ssd-nfs` PVC. Schema changes go through Alembic migrations with a working downgrade, applied by an ordered migration/seed Job.
Fresh install must create CNPG and its credentials before dependent migration work;
an unconditional pre-install hook cannot depend on ordinary resources from the same
install. Verify bounded waits, failure reporting and upgrade/readiness ordering.

## Consequences
- CNPG handles failover, status, and backups and can be reused by future apps.
- Local disk is safe and fast; the NFS dump is the backup.
- Restores depend on the dump job staying healthy, so rollout checks include it.

## References
- [README "Decisions & why"](../README.md#decisions--why)
- [CloudNativePG documentation](https://cloudnative-pg.io/documentation/current/)
