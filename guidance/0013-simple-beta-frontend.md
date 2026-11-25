# 0013: Simple CSS and easily restyled beta components

## Status
Accepted

## Context
The owner wants a clean usable first version that Arthur can later make more
polished, not a component-library or design-system decision before development.

## Decision
Keep React/Vite/strict TypeScript. Use plain CSS with a few named styling variables,
small semantic components, and clear separation of layout/content/API access.
Provide a short frontend layout guide and comments for non-obvious contracts,
not commentary on every trivial component.

Include a simple original NIK logo/wordmark and favicon with a text fallback.
Original generated artwork is permitted during implementation; extensive branding
or post-beta styling research must not block basic readability and accessibility.

## Consequences
- No new frontend framework or component service is selected.
- Mobile/desktop readability, keyboard access and useful states remain beta criteria.
- Arthur can restyle components without replacing the recipe model or data access.
- Logo assets and the frontend guide land with frontend implementation, not this decision.

## References
- [Frontend foundation](https://github.com/dylanwhitetech/nailed-it-kitchen/issues/16)
- [Deferred visual work](https://github.com/dylanwhitetech/nailed-it-kitchen/issues/17)
- [Application stack](0001-application-stack.md)
