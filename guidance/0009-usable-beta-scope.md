# 0009: One usable beta before feature expansion

## Status
Accepted

## Context
The grid-first foundations/MVP phases introduced too much work before the team could
browse recipes. The owner approved a smaller first working release, called Beta.

## Decision
Use one [Beta delivery epic](https://github.com/dylanwhitetech/nailed-it-kitchen/issues/69)
with native implementation and human-verification children. Keep one Post-beta backlog.
Historical phases and Sequence values are navigation, not execution order.

Beta includes clean responsive reading, NIK branding, most-viewed recipes, paginated
A-Z browsing, keyword search, plain recipe pages, protected recipe PR submissions and
a recoverable live-domain deployment. Keep the existing application/GitOps stack.

Grid recipes, advanced metadata/filtering, semantic search, ratings, feedback, accounts,
photos, comments, scaling, print, AI conversion, visual polish and optional agent
tooling are Post-beta. None may block beta launch.

## Consequences
- Reuse simplified issues and close replaced planning items as superseded, not completed.
- Beta exits only with actual live-domain submission/review/release and recovery evidence.
- The scope reset does not claim that application code, branding or deployment already exists.

## References
- [Roadmap](https://github.com/dylanwhitetech/nailed-it-kitchen/issues/2)
- [Beta scope](../README.md#beta-scope)
- [Application stack](0001-application-stack.md)
- [Hosting](0005-gitops-hosting-through-k3s-infrastructure.md)
