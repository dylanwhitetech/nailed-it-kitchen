# AGENTS.md

Canonical rules for AI agents and humans in Nailed It Kitchen. This file holds only rules that
cannot be worked out from the code or `README.md`; read the README for the product, architecture,
and local test steps. `.github/copilot-instructions.md` points here. Path-specific rules live in
`.github/instructions/`.

## Before you start

- **Issue first.** Software/configuration changes map to a GitHub issue. Create one with the
  `gh-issue-drafter` skill. The planned app-generated, recipe-content-only PR flow is the narrow
  exception: it uses the dedicated recipe review template without a synthetic submission issue.
- **Check guidance first.** Before a new scope of work, read `guidance/README.md` and the records
  related to the work. Legacy `[Sxx]` IDs and phase labels are navigation, not execution order;
  follow actual prerequisites and native dependencies, and work in parallel when nothing blocks.
- **The stack is decided.** Do not add or replace a framework, service, or tool (README
  "Decisions & why", `guidance/`) without an issue that decides it and a guidance record.

## Working rules

1. **Test locally before pushing** using README "Run & test locally (Docker)" (and the
   `local-preflight` skill once it exists). For documentation-only changes, run the available
   documentation/customization checks; never claim unavailable application or Docker checks passed.
2. **Software PRs** use the `gh-pr-drafter` skill, the PR template, and `Closes #N`.
   App-generated recipe-content-only PRs use the dedicated recipe template once implemented;
   never extend that exception to code, configuration, or workflow changes.
3. **Never merge to `main`.** A human from CODEOWNERS approves and merges; agents never merge.
4. **Do not disclose secrets, sensitive personal data, or private host details** in code, issues,
   PRs, prompts, examples, or logs. Secrets live in SOPS in `dylanwhitetech/k3s-infrastructure`
   or in GitHub repo secrets. Use placeholders.
5. **Codify everything.** Any manual change (cluster, Cloudflare, GitHub settings) must end up as
   code or docs. If something was done by hand, open an issue to codify it:
   cluster/platform → `dylanwhitetech/k3s-infrastructure`; app/chart → this repo.
6. **Public repo, private contributions.** Only collaborators or the authorized app open issues/PRs.
   The public submits recipes through the app, never directly on GitHub. App feedback is Post-beta.
7. **Guidance ships with the PR.** When a change introduces, replaces, or retires a lasting
   decision (architecture, stack, deployment, constraints), create or update a `guidance/` record
   in the same PR. Supersede records rather than deleting them.

## Local environment notes

- Before pushing a computed ref (`<sha>:refs/heads/x`), check the SHA is a non-empty 40-hex string;
  an empty source deletes the remote branch and closes its PR. Quote `^{tree}` and `^{commit}` in PowerShell (unquoted
  `<sha>^{commit}` makes `git cat-file` report an unknown switch).
- In PowerShell commit multi-line messages with `git commit -F <temp-file>` (`-F -` plus a here-string
  is parsed as a pathspec). `Set-Content -NoNewline` may be unavailable in Windows PowerShell; write
  LF files with the edit tool or Python.
- Session branch renames do not rename the worktree directory; use the workspace path the session supplies.
- Check the working-tree bytes (not git index state or `core.autocrlf`, e.g. `git ls-files --eol`
  showing `i/lf w/crlf`) of every touched file, including files Git wrote during a merge from `main`;
  normalize to LF (`.editorconfig`), then re-run validation.
- In PowerShell run venv tools as `& .\.venv\Scripts\python ...` from the active checkout, and validate
  the backend with that venv (`backend/requirements-dev.txt`), not global Python.
- Syntax-check the Compose nginx config alone with
  `docker run --rm --add-host=api:127.0.0.1 --mount ... nginx -t` (`docker compose run` has no `--add-host`).

## Engineering standards

- Keep code, configuration, and workflow changes in Git. Reuse existing patterns/helpers before
  adding new ones. Prefer KISS, DRY, YAGNI, and separation of concerns; avoid speculative
  abstractions, premature optimization, and shared mutable/global state.
- Keep changes scoped to one concern and reversible. Preserve existing contracts unless
  intentionally changing them; update user/operator docs alongside behavior or workflow changes.
  Update dependencies only in focused security/compatibility work.
- Official user and operator documentation must not reference specific issues; guidance records
  and field reports may include them.
- Add or update the smallest relevant tests for changed behavior; relevant validation must pass.
- Handle errors explicitly with useful context. Do not mask root causes with broad catch-alls,
  silent failures, or success-shaped fallbacks.
- Public write endpoints need Cloudflare Turnstile and rate limiting; validate all public input on
  the server. Database changes go through Alembic migrations with a working downgrade. Images are
  multi-arch (amd64/arm64) and run as non-root. Never hand-edit generated recipe data.

## Code documentation

- **Python:** Google-style docstrings and PEP 257 for public modules, classes, functions, and
  non-obvious contracts (summary plus applicable `Args`, `Returns`/`Yields`, `Raises`). Explain
  behavior, constraints, and side effects; do not repeat type annotations or document trivial code.
- **FastAPI:** document endpoint purpose and public behavior; docstrings can become OpenAPI
  descriptions, so keep them useful to API consumers and free of internals or secrets.
- **TypeScript/React:** TSDoc `/** ... */` for reusable exported components, hooks, utilities, and
  non-obvious props (semantics, defaults, units, constraints, side effects). Keep types in
  TypeScript, not JSDoc. No boilerplate on trivial components.
- **Helm/YAML:** document each configurable `values.yaml` property with a comment starting with its
  name; use Helm template comments for implementation notes; recipe content is defined by the schema.
- **SQL/migrations/config:** explain only non-obvious constraints, transformations, rollback
  assumptions, or operational decisions.
- Prefer readable code over comments. Do not add documentation generators or lint plugins solely
  to enforce these conventions.

## Branch, PR title, and commit conventions

- New branch names and PR titles: `<type>/<issue-number>-<short-hyphenated-description>`, e.g.
  `feat/1234-add-feature-x`. Types: only `feat`, `fix`, `cicd`, `chore` (docs count as `chore`).
  Use the GitHub issue number (not `S12`), lowercase kebab-case, no spaces, underscores, or
  empty/consecutive hyphens. The PR title matches a conforming branch. Session-managed branches are
  not renamed; their PR titles still follow the convention.
  The planned app-generated recipe-content-only flow uses server-generated branch/PR names and its
  dedicated review template instead; it must not accept user-chosen branches, paths, or workflows.
- Commits follow [Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/):
  `<type>[scope][!]: <imperative description>` (`feat`, `fix`, `docs`, `refactor`, `test`, `build`,
  `ci`, `chore`, ...). Mark breaking changes with `!` or a `BREAKING CHANGE:` footer. Commit types are
  independent of branch types (a `cicd/...` branch can hold `ci:` commits).
- Copilot-authored commits end with
  `Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>`.
- Release-please is planned, not configured. Slash-form PR titles are not Conventional Commits: the
  human merger must set a Conventional Commit squash message on `main`.

## Output structure (Minto Pyramid)

For replies, plans, reviews, handoffs, and issue/PR descriptions: (1) answer first in 1–2 sentences;
(2) 2–4 key-point bullets; (3) optional evidence (commands with results, `file:line`, links);
(4) "Next / needs a human" only when the reader must act. Scale to size. Required template headings
still win; put the answer inside the first section.

## Agents and skills

| Name | Type | Use it for |
|------|------|-----------|
| `naileditkitchen-main` | agent | Entry agent selected per session; plans, implements, delegates |
| `naileditkitchen-test` | agent | Writing and running tests (background subagent or its own session) |
| `naileditkitchen-deploy` | agent | Releases, promotion PRs to k3s-infrastructure, read-only rollout checks |
| `gh-issue-drafter` | skill | Issues from the target repo's real forms, labels, dependencies, Project fields |
| `gh-pr-drafter` | skill | Branch/PR names, Conventional Commits, the PR template |
| `visual-explanation` | skill | A concise visual or focused HTML artifact |
| `field-notes` | skill | Recording agentic learnings and blockers in the session folder |
| `copilot-authoring` | skill | Creating or changing agents, skills, instructions, templates, `AGENTS.md` |

Code review uses built-in Copilot code review on GitHub with
`.github/instructions/code-review.instructions.md`. Optional `local-preflight` and future grid
authoring support are Post-beta; normal documented validation does not depend on either skill.

## Learning loop

- **Field notes:** when an agent or skill was wrong or blocked and a fix was found, the same
  tool/command was retried with changes, the user corrected the agent, or guidance was missing or
  stale, use the `field-notes` skill. Notes go only in the current session's `files/field-notes/`
  folder, never in the repo. A curator later turns them into small itemized PRs.
- **New skills** only when a field note or observed failure shows the need; prefer editing an
  existing agent or skill.
- **Resources:** when the user shares a new agentic resource (paper, doc, guide), append it to
  `.github/skills/copilot-authoring/references.md` in the same PR.
- **Copilot customizations** (agents, skills, instructions, issue forms, PR templates, this file)
  follow the `copilot-authoring` skill: awesome-copilot prior art first, `Source:` attribution,
  official docs under `## References`.

## References

- AGENTS.md format: https://agents.md/
- Evaluating AGENTS.md (keep context files to non-discoverable rules): https://arxiv.org/html/2602.11988v3
- Repository custom instructions: https://docs.github.com/en/copilot/how-tos/configure-custom-instructions/add-repository-instructions
- Custom agents configuration: https://docs.github.com/en/copilot/reference/custom-agents-configuration
- About agent skills: https://docs.github.com/en/copilot/concepts/agents/about-agent-skills
- Minto Pyramid: https://untools.co/minto-pyramid/
- Conventional Commits 1.0.0: https://www.conventionalcommits.org/en/v1.0.0/
- Google Python docstrings: https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings
- PEP 257: https://peps.python.org/pep-0257/
- TSDoc: https://tsdoc.org/
- FastAPI docstring descriptions: https://fastapi.tiangolo.com/tutorial/path-operation-configuration/#description-from-docstring
- Helm values documentation: https://helm.sh/docs/chart_best_practices/values/
- Helm template comments: https://helm.sh/docs/chart_best_practices/templates/
- Source: rules moved from the previous `.github/copilot-instructions.md`; Git conventions adapted from
  awesome-copilot [conventional-branch](https://github.com/github/awesome-copilot/blob/main/skills/conventional-branch/SKILL.md)
  and [conventional-commit](https://github.com/github/awesome-copilot/blob/main/skills/conventional-commit/SKILL.md) (MIT);
  structure informed by [create-agentsmd](https://github.com/github/awesome-copilot/tree/main/skills/create-agentsmd).
