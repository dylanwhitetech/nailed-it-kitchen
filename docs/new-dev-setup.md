# New Dev Setup

This guide covers access, tools, and the first steps for developing Nailed It Kitchen.
The repository is public, but only collaborators can contribute issues and pull requests.

> **Current status:** The app and local Docker Compose stack have not been built yet.
> You can complete the access, tool, and Copilot checks below now. The app startup
> and test commands in the README are placeholders until their linked issues land.

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

## 5. Start and test the app when available

For now, there is no app to run: the Compose file, `.env.example`, application
services, and their test commands are not yet present. Issue
[#18](https://github.com/dylanwhitetech/nailed-it-kitchen/issues/18) tracks the
local Compose stack; backend, frontend, and preflight tests are tracked by
[#15](https://github.com/dylanwhitetech/nailed-it-kitchen/issues/15),
[#16](https://github.com/dylanwhitetech/nailed-it-kitchen/issues/16), and
[#19](https://github.com/dylanwhitetech/nailed-it-kitchen/issues/19).

Once those issues land, follow the current
[Run & test locally (Docker)](../README.md#run--test-locally-docker) instructions
before pushing. The planned workflow copies `.env.example` to `.env`, starts
services with `docker compose up --build`, and runs the documented tests.
The README's `docker compose down -v` reset **deletes local volumes and their data**;
use it only when you intend to reset the local database.

## 6. Work safely

- Start from an issue, work on a branch, and open a pull request using the repository
  template. Follow the branch, PR title, and commit conventions in the
  [`AGENTS.md`](../AGENTS.md#branch-pr-title-and-commit-conventions).
  A human CODEOWNER reviews and merges; agents never merge.
- Never commit or share credentials, private keys, tokens, or real `.env` values.
  Ask an owner for any access you need; local setup should use placeholder values.
- Cluster access is not required for local onboarding. Production and cluster changes
  follow the separate [k3s-infrastructure](https://github.com/dylanwhitetech/k3s-infrastructure)
  workflow and require appropriate access.
