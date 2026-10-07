# BASEFROM50 Free Guide — Codex instructions

Work ONLY inside `free-guide/` and `.agents/skills/basefrom50-editorial-pdf/` on this branch unless the user explicitly asks otherwise.

Primary goal: create a premium Russian-language PDF lead magnet for BASEFROM50. It must feel like a fashion/editorial publication, not a Word document, corporate report, or generic template.

Before making visual changes:
1. Read `free-guide/PROJECT_CONTEXT.md`.
2. Read `free-guide/content.md`.
3. Read `.agents/skills/basefrom50-editorial-pdf/SKILL.md`.
4. Render the PDF and inspect every page visually.
5. Fix overflow, awkward line breaks, weak hierarchy, and page-to-page inconsistency before reporting completion.

Technical rules:
- Source of truth is HTML/CSS.
- Export with Playwright/Chromium.
- A4 portrait.
- Keep each .page exactly one PDF page.
- Do not use ReportLab for layout.
- Do not modify the Telegram bot code in this repository.
- Final output path: `free-guide/output/basefrom50-free-guide.pdf`.
