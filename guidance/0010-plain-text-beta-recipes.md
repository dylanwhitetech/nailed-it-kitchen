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
text lines and ordered instruction text steps; allow only an optional plain-text source
and optional plain-text notes (yield, equipment, tips) so source recipes convert without
losing details. Preserve original source fixtures.

Sync reviewed content to a minimal PostgreSQL recipe model through an idempotent
seeder. Keep stable identity, timestamps and nonnegative durable view counts; reseeding
must preserve identity/counters. File removal does not delete database rows, and changing a
slug creates a new row instead of renaming or deleting the old one. Future fields use tested
Alembic migrations, not speculative graph, tags, ratings or generic attribute tables.

Use PostgreSQL lexical/full-text search over title, ingredients and instructions.
Default browsing is case-insensitive A-Z with stable pagination/tie-breaks.
Most-viewed uses approximate atomic detail-read counts, not unique visitors.
List/search/health and HEAD requests are not detail views. Count on the server as
read telemetry, not a separate unprotected public mutation endpoint.

## Consequences
- No grid/DAG model, structured units, tags or semantic service is needed for beta.
- Render recipe content as text and validate it with a safe loader/serializer.
- A later graph/metadata decision must preserve existing plain recipes and view counts.
- The schema, safe YAML rules and deterministic paste extraction are defined in
  [docs/recipe-format.md](../docs/recipe-format.md); persistence and migration behavior
  land with their implementation.

## References
- [Recipe format](../docs/recipe-format.md)
- [Format contract](https://github.com/dylanwhitetech/nailed-it-kitchen/issues/20)
- [Persistence contract](https://github.com/dylanwhitetech/nailed-it-kitchen/issues/15)
- [Reading API](https://github.com/dylanwhitetech/nailed-it-kitchen/issues/32)
- [Post-beta growth research](https://github.com/dylanwhitetech/nailed-it-kitchen/issues/70)
