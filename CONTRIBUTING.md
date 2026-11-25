# Contributing

This repository is public, but only collaborators open issues and software pull requests.
The planned public recipe contribution path is through the app; the form is not available yet.

1. Start from an issue whose prerequisites are complete. Read the README and relevant
   `guidance/` records before changing the agreed scope or stack.
2. Work on an issue-specific branch or an existing session-managed branch, not `main`.
   Follow the branch naming rules in [AGENTS.md](AGENTS.md#branch-pr-title-and-commit-conventions);
   do not rename a session-managed branch.
3. Run the checks applicable to the change before pushing. The
   [local Docker workflow](README.md#run--test-locally-docker) and application checks are
   planned, not runnable yet; do not report them as passing until implemented.
4. Open a pull request using the repository template and link the issue with `Closes #N`.
   A human CODEOWNER reviews and merges it; agents never merge.

Commits use [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/),
for example `chore: document contributor workflow`. PR titles follow the separate
issue-prefixed convention in AGENTS.md. A human doing a squash merge must use a
Conventional Commit squash message, not the slash-form PR title.

Never commit credentials, private keys, tokens, or real `.env` values. Use the
documented local placeholders and test values instead.
