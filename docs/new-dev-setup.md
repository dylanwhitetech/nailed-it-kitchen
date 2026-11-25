# New Dev Setup

This guide covers access, tools, and the first steps for developing Nailed It Kitchen.
The repository is public, but only collaborators can contribute issues and pull requests.

> **Current status:** The frontend shell, backend foundation and local Compose stack exist.
> Recipe browsing/search and protected submissions remain beta work in progress.

## 1. Get access

1. Ask a repository owner for **Write** access to
   [nailed-it-kitchen](https://github.com/dylanwhitetech/nailed-it-kitchen).
   Accept any invitation in your email or [GitHub notifications](https://github.com/notifications).
2. Ask the owner for **Writer** access to the
   [project board](https://github.com/users/dylanwhitetech/projects/1), and confirm
   you can open both the repository and the board while signed in.
3. Use your own GitHub account and an available GitHub Copilot subscription or seat.
   The [GitHub Copilot app](https://github.com/features/copilot) is optional.

## 2. Install development tools

| Tool | Requirement | Verify |
| --- | --- | --- |
| [Git](https://git-scm.com/install/) | Install Git and configure your commit identity. | `git --version` |
| [GitHub CLI](https://cli.github.com/) | Install `gh` and authenticate with your GitHub account. | `gh --version`, then `gh auth status` |
| [VS Code](https://code.visualstudio.com/) | Install VS Code and the [GitHub Copilot extension](https://marketplace.visualstudio.com/items?itemName=GitHub.copilot); sign in to Copilot. | Open Copilot Chat in VS Code. |
| [Node.js](https://nodejs.org/) | Install Node.js 24 LTS, including npm. | `node --version` (24.x), `npm --version` |
| [Python](https://www.python.org/downloads/) | Install Python 3.12. | `python --version` or `python3 --version` (3.12.x) |
| [Docker Desktop](https://docs.docker.com/desktop/) | Install and start Docker Desktop with Docker Compose. | `docker version`, `docker compose version` |

Use the Python command appropriate for your platform. If a version check fails,
install or select the required version and restart your terminal. Follow Docker
Desktop's platform-specific installation instructions, including any prerequisites.
Run `gh auth login` if `gh auth status` shows you are not authenticated.

## 3. Clone and explore

```sh
gh repo clone dylanwhitetech/nailed-it-kitchen
cd nailed-it-kitchen
git status
```

Open the folder in VS Code. Read the README sections **Decisions & why**,
**Run & test locally (Docker)**, and **AI-first workflow**. The
[getting started roadmap](https://github.com/dylanwhitetech/nailed-it-kitchen/issues/2)
and project board describe current work; select an issue whose actual prerequisites
are complete rather than treating roadmap numbers as a mandatory sequence.

## 4. Try the main agent

In VS Code, open Copilot Chat, select **naileditkitchen-main** from the agent
dropdown, and ask it to explain the recipe submission flow. Select it at the start
of every session; no repository file makes it the default (see
[Selecting the main agent](../README.md#selecting-the-main-agent)). Review its output and any changes it proposes. The
[AI-first workflow](../README.md#ai-first-workflow) describes the other supported
Copilot entry points and repository agents.

## 5. Start and test the app

Follow the
[Run & test locally (Docker)](../README.md#run--test-locally-docker) instructions
before pushing. Copy `.env.example` to `.env`, start
services with `docker compose up --build`, and run the documented Docker checks.
Postgres migrations and recipe seeding run before the API starts. No production
GitHub credentials are needed; keep submissions disabled.
The README's `docker compose down -v` reset **deletes local volumes and their data**;
use it only when you intend to reset the local database.

### Turnstile configuration when implemented

The public production site key for the `naileditkitchen` widget is
`0x4AAAAAAGRU0eFMd1cnYD4J`. Chart configuration is planned.

For local development, use Cloudflare's visible, always-pass test site key
`1x00000000000000000000AA` and always-pass test secret
`1x0000000000000000000000000000000AA`, as documented in
[Cloudflare's testing guide](https://developers.cloudflare.com/turnstile/troubleshooting/testing/).
These public test keys are not production credentials. Test site keys produce dummy
tokens that require a test secret; production secrets reject them. Never use a
production secret for local testing or put it in Git or issues. `.env.example` records
`TURNSTILE_SITE_KEY` and `TURNSTILE_SECRET_KEY`; the submission workstream will consume them.

## 6. Work safely

- Follow the issue-to-review workflow in [CONTRIBUTING.md](../CONTRIBUTING.md).
  A human CODEOWNER reviews and merges; agents never merge.
- Never commit or share credentials, private keys, tokens, or real `.env` values.
  Ask an owner for any access you need; local setup should use placeholder values.
- Cluster access is not required for local onboarding. Production and cluster changes
  follow the separate [k3s-infrastructure](https://github.com/dylanwhitetech/k3s-infrastructure)
  workflow and require appropriate access.
