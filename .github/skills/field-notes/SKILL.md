---
name: field-notes
description: "Records short field notes about agentic learnings and blockers in the current session's files folder, never in the repository, so a curator can later improve the owning agent, skill, or AGENTS.md. Use when an agent or skill was wrong or blocked and a fix was found, a tool or command was retried with changes, the user corrected the agent, or guidance was missing or stale."
---

# Field notes

Capture what happened while it is fresh. One note per lesson. A curator reviews notes across
sessions and turns them into small itemized changes to the owning file.

## Triggers

Triggers: agent/skill was wrong or blocked and a fix was found; same tool/command retried with
changes; user corrected the agent; guidance was missing/stale. Never write notes into the repo.

## Where

`<session-state>/<session-id>/files/field-notes/YYYYMMDD-HHMM-<slug>.md`, inside the current
session's folder (for example `~/.copilot/session-state/<session-id>/files/field-notes/`). Create
the folder if needed. Never write notes to the repository or commit them.

## Format

```
repo: owner/name          owner: <agent-or-skill-file or AGENTS.md>
kind: wrong | blocked | repeated-tool | user-correction | missing-guidance
trigger: what happened (1-3 lines)
fix: what worked
proposed change: one itemized add/edit/remove for the owner file
evidence: commands, errors, PR/issue links
status: new
```

## Rules

- `owner` is the repo-relative path of the file that should change (agent, skill, `AGENTS.md`, or a
  `guidance/` record).
- One proposed change per note, small enough to apply as a single edit.
- Redact secrets, tokens, private hosts, and personal data from evidence.
- Do not edit the owner file from the note; the curator proposes changes in a PR. Fix the current
  task normally.
- Leave `status: new`; the curator updates it.

## References

- Agentic Context Engineering (reflector/curator idea, used lightly): https://arxiv.org/html/2510.04618v3
- About agent skills: https://docs.github.com/en/copilot/concepts/agents/about-agent-skills
- Source: written from scratch; no awesome-copilot skill fits (`skills/memory-merger` targets VS Code
  memory files, not session-folder notes).
