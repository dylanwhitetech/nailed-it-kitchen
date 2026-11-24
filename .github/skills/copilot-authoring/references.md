# Agentic resource catalogue

Sources behind this repo's agents, skills, and instructions. When the user shares a new agentic
resource, append it here (one line: link, then what it is used for) in the same PR.

## Research and best practices

- Agentic Context Engineering (generator / reflector / curator playbooks; used lightly via field
  notes and a curator): https://arxiv.org/html/2510.04618v3
- Evaluating AGENTS.md (context-file overviews do not help and add cost; keep non-discoverable
  rules only): https://arxiv.org/html/2602.11988v3
- Anthropic agent skill best practices (concise, third-person what + when descriptions, under 500
  lines, one-level references): https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices

## GitHub Copilot official docs

- Copilot Memory: https://docs.github.com/en/copilot/concepts/prompting-and-context/copilot-memory
- Custom instructions (surfaces and precedence): https://docs.github.com/en/copilot/concepts/prompting-and-context/custom-instructions
- Repository custom instructions (`AGENTS.md`, path-specific): https://docs.github.com/en/copilot/how-tos/configure-custom-instructions/add-repository-instructions
- Custom agents concept: https://docs.github.com/en/copilot/concepts/customizations/custom-agents
- Custom agents configuration (frontmatter): https://docs.github.com/en/copilot/reference/custom-agents-configuration
- Creating custom agents (cloud agent): https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/customize-cloud-agent/create-custom-agents
- Creating custom agents for the CLI: https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/create-custom-agents-for-cli
- Invoking custom agents in the CLI: https://docs.github.com/en/copilot/how-tos/copilot-cli/use-copilot-cli/invoke-custom-agents
- Customizing the GitHub Copilot app (agent picker, `/agent`): https://docs.github.com/en/copilot/how-tos/github-copilot-app/customize-github-copilot-app
- Copilot app repository configuration (`.github/github-app.yml`): https://docs.github.com/en/copilot/reference/github-copilot-app-reference/repository-configuration
- About agent skills: https://docs.github.com/en/copilot/concepts/agents/about-agent-skills
- Adding agent skills: https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/customize-cloud-agent/add-skills
- Customization cheat sheet: https://docs.github.com/en/copilot/reference/customization-cheat-sheet
- Subagents (one hop): https://docs.github.com/en/copilot/how-tos/copilot-in-your-ide/use-copilot-agents/use-subagents
- Delegating and parallelizing work: https://docs.github.com/en/copilot/concepts/agent-capabilities/choosing-and-delegating-agent-work/delegating-and-parallelizing-work-with-agents
- Supported AI models (check `model:` pins): https://docs.github.com/en/copilot/reference/ai-models/supported-models
- Issue forms: https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/creating-issue-forms
- PR templates: https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/creating-a-pull-request-template-for-your-repository

## Prior art

- awesome-copilot (search first; MIT): https://github.com/github/awesome-copilot
- awesome-copilot index: https://awesome-copilot.github.com/llms.txt
- AGENTS.md format: https://agents.md/
