---
name: visual-explanation
description: "Use when a user asks to 'show me' or requests a visual explanation of a process, structure, change, interaction, or layout. Choose a compact text diagram or a focused HTML artifact appropriate to the question."
---

# Visual explanation

Make the question easier to understand, not a complete design document. Keep commentary brief
and put it beside the relevant visual.

## Workflow

1. Identify the point to explain, intended audience, and available evidence. Inspect relevant
   files or conversation context when needed. If the topic or a consequential detail is unclear,
   ask; otherwise state any necessary assumptions.
2. Identify only the important elements, relationships, direction, and boundaries. Choose the
   smallest form that shows them; combine forms only when that makes the answer clearer:
   - Concise text or pseudocode for decisions and algorithms.
   - A tree for calls, components, ownership, or files.
   - A diff for a before/after change, with enough context to orient the reader.
   - Mermaid for interactions, sequences, or flows when a diagram helps. Include a short text
     equivalent because the host may show the source rather than render it.
   - One focused HTML file for a layout, comparison, or complex visual that the simpler forms
     cannot explain well. Do not create an artifact merely to answer a simple question.
3. Use verified names and relationships; distinguish existing behavior from a proposal. Mark
   placeholders, unknowns, and illustrative pseudocode clearly. Never invent repository paths,
   code, data, or behavior and present them as fact. Never include secrets, personal information,
   private host details, or other sensitive material in the visual or preview.
4. Check the visual against the evidence: ordering, connections, labels, and any diff context
   must be accurate. Keep it legible and avoid irrelevant details. Say what could not be verified.

## HTML artifacts and preview

- Write only when the user requests an artifact or it is warranted by the question and file
  creation is permitted. Use a user-specified path if provided; otherwise choose a clearly named
  non-conflicting local path and report it. Never overwrite an existing file without permission.
- Keep the artifact self-contained and offline: no external scripts, fonts, images, analytics,
  or upload/preview services. Use semantic HTML, a title, readable contrast and responsive layout;
  include text labels and a textual explanation of essential relationships, not color alone.
  Ensure any controls work with keyboard and have accessible names.
- When applicable, use verified existing product design cues such as colors, typography, spacing,
  and components; do not invent a design system or sacrifice accessibility to match it.
- Preview using an available, supported host preview or browser only when permitted. On Windows,
  the Copilot app, CLI, VS Code, and cloud environments, do not assume a particular OS command,
  browser, GUI, or preview tool exists. Never send local content to a third party to preview it.
  If preview is unavailable, give the local path and tell the user they can open the file in a
  local browser; provide a concise text equivalent in the response.
- Check the artifact's contents and, if preview is available, check rendering and usability at
  narrow and wide widths. Report what was actually checked; never claim an unperformed preview.

## Response

Provide the visual and a brief explanation of its main point. For an HTML artifact, provide its
path, text equivalent, preview instructions or limitation, and validation status. Identify any
assumptions or gaps that affect interpretation.

## References

- About agent skills: https://docs.github.com/en/copilot/concepts/agents/about-agent-skills
- Creating agent skills: https://docs.github.com/en/copilot/how-tos/use-copilot-agents/coding-agent/create-skills
- Source: workflow adapted from awesome-copilot
  [`skills/excalidraw-diagram-generator/SKILL.md`](https://github.com/github/awesome-copilot/blob/main/skills/excalidraw-diagram-generator/SKILL.md)
  (MIT); replaced its Excalidraw-specific output with format selection and portable preview guidance.
- Inspiration (no content copied): [humanlayer show-me](https://github.com/humanlayer/skills/blob/main/plugins/show-me/skills/show-me/SKILL.md).
