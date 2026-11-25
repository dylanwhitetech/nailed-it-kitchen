# 0010: Plain text recipe content for beta

## Status
Accepted

## Context
The unimplemented grid format in 0002 required step graphs, ingredient references
and branching before a recipe could be displayed. Beta needs ingredients followed
by cooking instructions instead.

## Decision
Supersede [0002](0002-recipes-as-yaml-with-json-schema.md). Keep reviewed YAML files
as content source of truth, validated by JSON Schema. Require a slug, title, ingredient
text lines and ordered instruction text steps. Preserve original source fixtures.

Sync reviewed content to a minimal PostgreSQL recipe model through an idempotent
seeder. Keep stable identity, timestamps and nonnegative durable view counts; reseeding
must preserve identity/counters. Future fields use tested Alembic migrations, not
speculative graph, tags, ratings or generic attribute tables.

Use PostgreSQL lexical/full-text search over title, ingredients and instructions.
Default browsing is case-insensitive A-Z with stable pagination/tie-breaks.
Most-viewed uses approximate atomic detail-read counts, not unique visitors.
List/search/health and HEAD requests are not detail views. Count on the server as
read telemetry, not a separate unprotected public mutation endpoint.

## Consequences
- No grid/DAG model, structured units, tags or semantic service is needed for beta.
- Render recipe content as text and validate it with a safe loader/serializer.
- A later graph/metadata decision must preserve existing plain recipes and view counts.
- Exact schema, parser rules and migration behavior land with their implementation.

## References
- [Format contract](https://github.com/dylanwhitetech/nailed-it-kitchen/issues/20)
- [Persistence contract](https://github.com/dylanwhitetech/nailed-it-kitchen/issues/15)
- [Reading API](https://github.com/dylanwhitetech/nailed-it-kitchen/issues/32)
- [Post-beta growth research](https://github.com/dylanwhitetech/nailed-it-kitchen/issues/70)
