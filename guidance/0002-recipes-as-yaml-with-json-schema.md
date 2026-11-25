# 0002: Recipes as YAML validated by a JSON Schema

## Status
Superseded by [0010](0010-plain-text-beta-recipes.md)

## Context
Recipes are displayed as a "Cooking for Engineers" style grid and must be reviewable, versioned, and safe to render.

## Decision
Store recipe content as YAML files in `recipes/*.yaml`, validated in CI by a JSON Schema. Keep original free-text recipes in `recipes/source/` as golden test fixtures. The YAML files are the source of truth for content; never hand-edit generated recipe data.

## Consequences
- Recipes are reviewed in PRs like code and are easy for Copilot to write.
- The schema keeps the grid renderer simple and safe.
- Content changes need a PR and must pass schema validation.

## References
- [README "Decisions & why"](../README.md#decisions--why)
