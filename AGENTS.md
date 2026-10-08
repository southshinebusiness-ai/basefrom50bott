# BASEFROM50 Free Guide — project instructions

Work ONLY inside `free-guide/` and `.agents/skills/` on branch `basefrom50-free-guide` unless the user explicitly asks otherwise.

Primary goal: create a premium Russian-language PDF lead magnet for BASEFROM50. It must feel like a fashion/editorial publication, not a Word document, corporate report, SaaS page, pitch deck, or generic AI template.

Before any visual redesign:
1. Read `free-guide/PROJECT_CONTEXT.md`.
2. Read `free-guide/content.md`.
3. Read `free-guide/DESIGN_BRIEF_NEXT.md`.
4. Read `.agents/skills/basefrom50-design-director/SKILL.md`.
5. Use `.agents/skills/basefrom50-editorial-pdf/SKILL.md` for PDF implementation/QA.
6. Render the relevant pages and inspect them visually before applying the style to the whole document.
7. Fix overflow, weak hierarchy, muddy color, awkward typography, and page-to-page inconsistency before reporting completion.

Design process:
- Never redesign the whole guide blindly.
- First audit the current version.
- Establish typography, color roles, hierarchy and one focal point per page.
- Prototype pages 1 and 5 first.
- Review as individual pages and as a contact sheet.
- Only then propagate the approved direction.
- Keep accent color restrained and verify hierarchy survives grayscale/squint testing.

Technical rules:
- Source of truth is HTML/CSS.
- Export to PDF with a browser engine.
- A4 portrait.
- Keep each .page exactly one PDF page.
- Do not use ReportLab as the main layout engine.
- Do not modify the Telegram bot code in this repository.
- Do not commit font files.
- Final output path: `free-guide/output/basefrom50-free-guide.pdf`.
